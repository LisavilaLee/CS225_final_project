import re
import threading
from typing import Optional, Tuple

from benchmark import Benchmark
from network import EmulatedNetwork
from common import *


class CloudflareQUICBenchmark(Benchmark):
    def __init__(self, net: EmulatedNetwork, label: str, logdir: str, n: str,
                 cca: str, certfile: str, keyfile: str, pep: bool=False):
        super().__init__(net, Protocol.CLOUDFLARE_QUIC, label, logdir, n, cca,
                         certfile, keyfile, pep)

    def start_server(self, timeout: int=SETUP_TIMEOUT):
        base = 'deps/quiche/target/release'
        # Force RUST_LOG=info for server to reduce noise but keep key events
        cmd = f'/usr/bin/env RUST_LOG=info ./{base}/quiche-server '\
              f'--cert={self.certfile} '\
              f'--key={self.keyfile} '\
              f'--cc-algorithm {self.cca} ' \
              f'--listen {self.server.IP()}:4433'

        condition = threading.Condition()
        def notify_when_ready(line):
            if 'listening' in line.lower():
                with condition:
                    condition.notify()

        # The start_server() function blocks until the server is ready to
        # accept client requests. That is, when we observe the 'Serving'
        # string in the server output.
        logfile = self.logfile(self.server)
        self.net.popen(self.server, cmd, background=True,
            console_logger=DEBUG, logfile=logfile, func=notify_when_ready)
        with condition:
            notified = condition.wait(timeout=timeout)
            if not notified:
                raise TimeoutError(f'start_server timeout {timeout}s')

    def run_client(self, timeout: Optional[int]=None) -> Optional[Tuple[int, float]]:
        """Returns the status code and runtime (seconds) of the GET request.
        """
        # Debug: Check connectivity first
        DEBUG(f"Checking connectivity to {self.server.IP()}...")
        self.net.popen(self.client, f'ping -c 2 {self.server.IP()}', 
                      stdout=True, stderr=True, raise_error=False)

        # Create a temp dir for response dump to avoid stdout flooding
        dump_dir = f"/tmp/quiche_dump_{self.label}"
        self.net.popen(self.client, f"mkdir -p {dump_dir}")

        base = 'deps/quiche/target/release'
        # Force RUST_LOG=info to diagnose connection issues but avoid debug spam
        # Redirect stderr to stdout is NOT needed because popen handles both streams separately or merged depending on config
        # We use --dump-responses to prevent body printing to stdout which clogs the pipe
        cmd = f'/usr/bin/env RUST_LOG=info ./{base}/quiche-client '\
              f'--no-verify '\
              f'--method GET '\
              f'--dump-responses {dump_dir} '\
              f'--cc-algorithm {self.cca} ' \
              f'-- https://{self.server.IP()}:4433/{self.n}'


        result = []
        timed_out = False
        def parse_result(line):
            # Debug: log all lines to help diagnose
            DEBUG(f'quiche-client output: {line.strip()}')
            
            if 'response(s) received in ' not in line:
                # Also check for alternative formats
                if 'response' in line.lower() and 'received' in line.lower():
                    DEBUG(f'Found potential response line but format may differ: {line.strip()}')
                return
            if 'Not found' in line:
                return
            if 'timed out' in line or 'timeout' in line.lower():
                timed_out = True
                return
            try:
                # Rust Duration format can be like "1.234s" or "1234ms" or "1.234567s"
                # Match: "received in 1.234s" or "received in 1234ms" or "received in 1.234567s"
                # The format is: "received in {duration}, closing..."
                match = re.search(r'received in ([\d.]+)([sm]s?)', line)
                if match:
                    value = float(match.group(1))
                    unit = match.group(2)
                    # Convert to seconds
                    if unit.startswith('m'):  # milliseconds
                        time_s = value / 1000.0
                    else:  # seconds
                        time_s = value
                    DEBUG(f'Parsed time: {time_s}s from line: {line.strip()}')
                    result.append(time_s)
                else:
                    # Also look for the debug message "response(s) received in"
                    if "response(s) received in" in line:
                         DEBUG(f'Found response line in debug output: {line.strip()}')
                         # Try to match the time again from this line specifically
                         match = re.search(r'received in ([\d.]+)([sm]s?)', line)
                         if match:
                             value = float(match.group(1))
                             unit = match.group(2)
                             if unit.startswith('m'):
                                 time_s = value / 1000.0
                             else:
                                 time_s = value
                             DEBUG(f'Parsed time from debug line: {time_s}s')
                             result.append(time_s)
                         else:
                            DEBUG(f'Could not parse time from response line: {line.strip()}')

            except Exception as e:
                # Debug: print the line if parsing fails
                DEBUG(f'Failed to parse quiche-client output: {line.strip()}, error: {e}')
                pass

        logfile = self.logfile(self.client)
        timeout_flag = self.net.popen(self.client, cmd, background=False,
            console_logger=DEBUG, logfile=logfile, func=parse_result,
            timeout=timeout, raise_error=False)

        if timed_out:
            # Max idle timeout reached when there have been no packets received for
            # N seconds (default: 30); this implies that something went
            # wrong with the server or client, which should be distinguished from
            # a timeout due to insufficient bandwidth.
            WARN('Cloudflare QUIC client failed (idle timeout)')
        elif timeout_flag:
            return (HTTP_TIMEOUT_STATUSCODE, timeout)
        elif len(result) == 0:
            WARN('Cloudflare QUIC client failed to return result')
        elif len(result) > 1:
            WARN(f'Cloudflare QUIC client returned multiple results {result}')
        else:
            return (HTTP_OK_STATUSCODE, result[0])
