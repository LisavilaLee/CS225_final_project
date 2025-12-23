import json
import sys

def analyze(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return

    # Structure: results[scene_id][cca][strategy] = throughput
    results_map = {}
    
    for entry in data:
        scene = entry.get('scene_id')
        cca = entry.get('cca')
        strategy = entry.get('strategy')
        
        outputs = entry.get('outputs', [])
        if not outputs or not outputs[0].get('success'):
            throughput = 0.0
        else:
            throughput = outputs[0].get('throughput_mbps', 0.0)
            
        if scene not in results_map:
            results_map[scene] = {}
        if cca not in results_map[scene]:
            results_map[scene][cca] = {}
            
        results_map[scene][cca][strategy] = throughput

    # Print Table Header
    # Scene | CCA | No Split (Mbps) | Adaptive (Mbps) | Always Split (Mbps) | Gain (%) | Recommendation
    print(f"{'Scene':<15} {'CCA':<8} {'No Split':<10} {'Adaptive':<10} {'Always':<10} {'Gain (%)':<10} {'Decision'}")
    print("-" * 90)

    # Sort scenes: scene_1_..., scene_2_..., scene_3_...
    # Custom sort to handle strings nicely
    sorted_scenes = sorted(results_map.keys())
    
    for scene in sorted_scenes:
        ccas = sorted(results_map[scene].keys())
        # Sort CCAs order: cubic, bbr, bbr2, bbr3
        cca_order = {'cubic': 0, 'bbr': 1, 'bbr2': 2, 'bbr3': 3}
        ccas.sort(key=lambda x: cca_order.get(x, 99))

        for cca in ccas:
            strats = results_map[scene][cca]
            no_split = strats.get('no_split', 0.0)
            adaptive = strats.get('adaptive_split', 0.0)
            always = strats.get('always_split', 0.0)
            
            if no_split > 0:
                gain = ((adaptive - no_split) / no_split) * 100
            else:
                gain = 0.0
            
            # Simple decision logic based on gain and protocol
            # PEP only works for TCP (cubic, bbrv1). For UDP (bbr2, bbr3), it technically shouldn't work.
            # But we analyze based on numbers.
            decision = "Neutral"
            if cca in ['bbr2', 'bbr3']:
                decision = "N/A (UDP)"
            elif gain > 10:
                decision = "ENABLE"
            elif gain < -5:
                decision = "DISABLE"
            else:
                decision = "KEEP OFF"
            
            print(f"{scene:<15} {cca:<8} {no_split:<10.2f} {adaptive:<10.2f} {always:<10.2f} {gain:<10.2f} {decision}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze(sys.argv[1])
    else:
        print("Usage: python analyze_results_final.py <path_to_json>")

