import json
import sys

def analyze_results(json_file):
    try:
        with open(json_file, 'r') as f:
            results = json.load(f)
    except FileNotFoundError:
        print(f"Error: File {json_file} not found.")
        return

    # Organize data: scenario -> cca -> strategy -> throughput
    data = {}
    
    for r in results:
        scene = r['scene_id']
        cca = r['cca']
        strategy = r['strategy']
        # Handle case where output might be empty or failed
        if not r['outputs'] or not r['outputs'][0]['success']:
            throughput = 0.0
        else:
            throughput = r['outputs'][0]['throughput_mbps']
            
        if scene not in data: data[scene] = {}
        if cca not in data[scene]: data[scene][cca] = {}
        data[scene][cca][strategy] = throughput

    print(f"{'Scenario':<15} {'CCA':<10} {'No Split':<10} {'Adaptive':<10} {'Gain %':<10} {'Decision'}")
    print("-" * 70)

    for scene in sorted(data.keys()):
        for cca in sorted(data[scene].keys()):
            strategies = data[scene][cca]
            no_split = strategies.get('no_split', 0)
            adaptive = strategies.get('adaptive_split', 0)
            
            if no_split > 0:
                gain = (adaptive - no_split) / no_split * 100
            else:
                gain = 0
                
            # Decision logic based on gain
            if gain > 5:
                decision = "YES (High Gain)"
            elif gain < -1:
                decision = "NO (Loss)"
            else:
                decision = "Neutral"

            print(f"{scene:<15} {cca:<10} {no_split:<10.2f} {adaptive:<10.2f} {gain:<+10.1f} {decision}")

if __name__ == "__main__":
    analyze_results('results/my_results.json')

