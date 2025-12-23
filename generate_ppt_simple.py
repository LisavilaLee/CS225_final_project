#!/usr/bin/env python3
"""
生成简洁的 PPT 表格，包含 True/False 决策
"""
import json
import sys

def load_results(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_throughput(entry):
    outputs = entry.get('outputs', [])
    if not outputs or not outputs[0].get('success'):
        return 0.0
    return outputs[0].get('throughput_mbps', 0.0)

def calculate_gain(no_split, adaptive):
    if no_split == 0:
        return 0.0
    return ((adaptive - no_split) / no_split) * 100

def make_decision_bool(cca, gain):
    """返回 True/False 决策"""
    # QUIC 协议：虽然物理上无法拆分，但策略上如果增益>5%则认为应该启用
    if cca in ['bbr2', 'bbr3']:
        return gain > 5
    
    # TCP 协议：增益>10%则启用
    return gain > 10

def generate_simple_table(results_file):
    data = load_results(results_file)
    
    results_map = {}
    for entry in data:
        scene = entry.get('scene_id', '')
        cca = entry.get('cca', '')
        strategy = entry.get('strategy', '')
        throughput = extract_throughput(entry)
        
        if scene not in results_map:
            results_map[scene] = {}
        if cca not in results_map[scene]:
            results_map[scene][cca] = {}
        results_map[scene][cca][strategy] = throughput
    
    # 按场景和 CCA 组织
    scenes = ['scene_1', 'scene_2', 'scene_3']
    ccas = ['cubic', 'bbr', 'bbr2', 'bbr3']
    cca_names = {'cubic': 'Cubic', 'bbr': 'BBRv1', 'bbr2': 'BBRv2', 'bbr3': 'BBRv3'}
    scene_labels = {
        'scene_1': 'Scene 1\n(低延迟, 0%丢包)',
        'scene_2': 'Scene 2\n(中延迟, 1%丢包)',
        'scene_3': 'Scene 3\n(中延迟, 2%丢包)'
    }
    
    print("\n" + "="*90)
    print("PPT 表格 - 简洁版（含 True/False 决策）")
    print("="*90 + "\n")
    
    print("| 场景 | 算法 | No Split<br>(Mbps) | Adaptive<br>(Mbps) | 增益<br>(%) | 决策<br>(启用?) |")
    print("|------|------|------------------|-------------------|-----------|-------------|")
    
    for scene_prefix in scenes:
        for cca in ccas:
            scene_id = f"{scene_prefix}_{cca}"
            if scene_id not in results_map or cca not in results_map[scene_id]:
                continue
            
            strats = results_map[scene_id][cca]
            no_split = strats.get('no_split', 0.0)
            adaptive = strats.get('adaptive_split', 0.0)
            gain = calculate_gain(no_split, adaptive)
            decision = "✓ True" if make_decision_bool(cca, gain) else "✗ False"
            
            scene_label = scene_labels[scene_prefix]
            print(f"| {scene_label} | {cca_names[cca]} | {no_split:.2f} | {adaptive:.2f} | {gain:+.1f}% | {decision} |")
    
    # 生成横向对比表（按算法分组）
    print("\n" + "="*90)
    print("横向对比表 - 按算法分组（适合 PPT 展示）")
    print("="*90 + "\n")
    
    for cca in ccas:
        print(f"\n### {cca_names[cca]}")
        print("| 场景 | No Split (Mbps) | Adaptive (Mbps) | 增益 (%) | 决策 |")
        print("|------|----------------|----------------|---------|------|")
        
        for scene_prefix in scenes:
            scene_id = f"{scene_prefix}_{cca}"
            if scene_id not in results_map or cca not in results_map[scene_id]:
                continue
            
            strats = results_map[scene_id][cca]
            no_split = strats.get('no_split', 0.0)
            adaptive = strats.get('adaptive_split', 0.0)
            gain = calculate_gain(no_split, adaptive)
            decision = "✓ True" if make_decision_bool(cca, gain) else "✗ False"
            
            scene_label = scene_labels[scene_prefix].replace('\n', ' ')
            print(f"| {scene_label} | {no_split:.2f} | {adaptive:.2f} | {gain:+.1f}% | {decision} |")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_simple_table(sys.argv[1])
    else:
        generate_simple_table("results/final_results.json")

