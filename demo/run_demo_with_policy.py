import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, List

# 仓库根目录（demo/ 的上一级）
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from policy import NetworkScenario, AdaptiveSplitPolicy  # noqa: E402


def load_scenarios(path: str) -> List[NetworkScenario]:
    """从 JSON 文件加载场景配置，构造 NetworkScenario 列表。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    scenes: List[NetworkScenario] = []
    for s in data.get("scenes", []):
        scenes.append(
            NetworkScenario(
                scene_id=s["id"],
                delay1_ms=float(s["delay1_ms"]),
                delay2_ms=float(s["delay2_ms"]),
                loss1_pct=float(s["loss1_pct"]),
                loss2_pct=float(s["loss2_pct"]),
                bw1_mbps=float(s["bw1_mbps"]),
                bw2_mbps=float(s["bw2_mbps"]),
                cc=s["cc"],
            )
        )
    return scenes


def run_emulation(
    scene: NetworkScenario,
    strategy: str,
    pep: bool,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """
    调用 emulation/main.py 运行一次 two_segment 实验，返回 JSON 结果。
    """
    label = f"{scene.scene_id}_{scene.cc}_{strategy}"

    # ---- 全局参数（必须放在子命令 tcp 之前） ----
    cmd = [
        sys.executable,
        "emulation/main.py",
        "--label",
        label,
        "--logdir",
        args.logdir,
        "--topology",
        args.topology,
        "--delay1",
        str(int(scene.delay1_ms)),
        "--delay2",
        str(int(scene.delay2_ms)),
        "--loss1",
        str(int(scene.loss1_pct)),
        "--loss2",
        str(int(scene.loss2_pct)),
        "--bw1",
        str(int(scene.bw1_mbps)),
        "--bw2",
        str(int(scene.bw2_mbps)),
        "--qdisc",
        args.qdisc,
        "-t",
        str(args.trials),
    ]
    if args.timeout is not None:
        cmd += ["--timeout", str(args.timeout)]
    if args.network_statistics:
        cmd.append("--network-statistics")
    if pep:
        cmd.append("--pep")

    # ---- 子命令 tcp 及其参数（必须在最后） ----
    cmd += [
        "tcp",
        "-n",
        str(args.n_bytes),
        "--congestion-control",
        scene.cc,
    ]

    print(f"[INFO] Running scene={scene.scene_id}, cc={scene.cc}, "
          f"strategy={strategy}, pep={pep}")
    print("[INFO] Command:", " ".join(cmd))

    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        print("[ERROR] emulation failed, stderr:")
        print(proc.stderr)
        raise RuntimeError(f"emulation failed with code {proc.returncode}")

    # main.py 最后一行会输出 JSON，倒着找第一行 {...}
    last_json = None
    for line in proc.stdout.splitlines()[::-1]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("{") and line.endswith("}"):
            last_json = line
            break
    if last_json is None:
        print("[WARN] no JSON result found, raw stdout:")
        print(proc.stdout)
        raise ValueError("no JSON result found in emulation output")

    result: Dict[str, Any] = json.loads(last_json)
    # 附加一些元信息，后续分析会用到
    result["scene_id"] = scene.scene_id
    result["strategy"] = strategy
    result["pep"] = pep
    result["cca"] = scene.cc
    result["derived_rtt_ms"] = scene.rtt_ms
    result["derived_loss_pct"] = scene.loss_pct
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a small demo of connection-splitting with an adaptive policy.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        default="demo/scenarios.json",
        help="Path to the scenarios JSON file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="demo/demo_results.json",
        help="Where to store aggregated JSON results.",
    )
    parser.add_argument(
        "--logdir",
        type=str,
        default="/tmp/connection-splitting-demo",
        help="Directory where host logs are written.",
    )
    parser.add_argument(
        "--n-bytes",
        dest="n_bytes",
        type=int,
        default=10_000_000,
        help="Bytes to download in each HTTP request.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        help="Number of trials per (scene, strategy).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout (seconds) for each emulation run.",
    )
    parser.add_argument(
        "--topology",
        type=str,
        default="two_segment",
        choices=["direct", "two_segment"],
        help="Network topology to use.",
    )
    parser.add_argument(
        "--qdisc",
        type=str,
        default="red",
        choices=["red", "bfifo-large", "bfifo-small", "pie", "codel", "policer", "fq_codel"],
        help="Queueing discipline.",
    )
    parser.add_argument(
        "--no-network-statistics",
        dest="network_statistics",
        action="store_false",
        help="Disable --network-statistics flag.",
    )
    parser.set_defaults(network_statistics=True)

    args = parser.parse_args()

    # 确保在仓库根目录执行 emulation/main.py
    os.chdir(REPO_ROOT)
    os.makedirs(args.logdir, exist_ok=True)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    scenes = load_scenarios(args.scenarios)
    policy = AdaptiveSplitPolicy()

    all_results: List[Dict[str, Any]] = []

    for scene in scenes:
        for strategy in ["no_split", "always_split", "adaptive_split"]:
            if strategy == "no_split":
                pep = False
            elif strategy == "always_split":
                pep = True
            else:
                pep = policy.should_split(scene)

            result = run_emulation(scene, strategy, pep, args)
            all_results.append(result)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"[INFO] Wrote aggregated results to {args.output}")


if __name__ == "__main__":
    main()
