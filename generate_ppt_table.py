#!/usr/bin/env python3
"""
生成用于 PPT 的汇总表格，包含吞吐量、增益和决策
"""
import json
import sys

def load_results(file_path):
    """加载结果文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_throughput(entry):
    """从结果条目中提取吞吐量"""
    outputs = entry.get('outputs', [])
    if not outputs or not outputs[0].get('success'):
        return 0.0
    return outputs[0].get('throughput_mbps', 0.0)

def calculate_gain(no_split, adaptive):
    """计算增益百分比"""
    if no_split == 0:
        return 0.0
    return ((adaptive - no_split) / no_split) * 100

def make_decision(cca, gain, no_split, adaptive):
    """根据 CCA 类型和增益做出决策"""
    # QUIC 协议（bbr2, bbr3）无法被 TCP PEP 拆分，但策略上可以判断
    if cca in ['bbr2', 'bbr3']:
        # 虽然物理上无法拆分，但策略上如果增益为正，说明应该启用（如果环境支持）
        if gain > 5:
            return "✓ (需QUIC PEP)"
        elif gain < -5:
            return "✗ (需QUIC PEP)"
        else:
            return "— (QUIC)"
    
    # TCP 协议（cubic, bbr）
    if gain > 10:
        return "✓ 启用"
    elif gain < -5:
        return "✗ 禁用"
    else:
        return "— 保持关闭"

def generate_table(results_file):
    """生成汇总表格"""
    data = load_results(results_file)
    
    # 组织数据: scene -> cca -> strategy -> throughput
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
    
    # 定义场景和 CCA 的顺序
    scene_order = ['scene_1_cubic', 'scene_1_bbr', 'scene_1_bbr2', 'scene_1_bbr3',
                   'scene_2_cubic', 'scene_2_bbr', 'scene_2_bbr2', 'scene_2_bbr3',
                   'scene_3_cubic', 'scene_3_bbr', 'scene_3_bbr2', 'scene_3_bbr3']
    
    cca_names = {
        'cubic': 'Cubic',
        'bbr': 'BBRv1',
        'bbr2': 'BBRv2',
        'bbr3': 'BBRv3'
    }
    
    scene_names = {
        'scene_1_cubic': 'Scene 1\n(低延迟, 0%丢包)',
        'scene_1_bbr': 'Scene 1\n(低延迟, 0%丢包)',
        'scene_1_bbr2': 'Scene 1\n(低延迟, 0%丢包)',
        'scene_1_bbr3': 'Scene 1\n(低延迟, 0%丢包)',
        'scene_2_cubic': 'Scene 2\n(中延迟, 1%丢包)',
        'scene_2_bbr': 'Scene 2\n(中延迟, 1%丢包)',
        'scene_2_bbr2': 'Scene 2\n(中延迟, 1%丢包)',
        'scene_2_bbr3': 'Scene 2\n(中延迟, 1%丢包)',
        'scene_3_cubic': 'Scene 3\n(中延迟, 2%丢包)',
        'scene_3_bbr': 'Scene 3\n(中延迟, 2%丢包)',
        'scene_3_bbr2': 'Scene 3\n(中延迟, 2%丢包)',
        'scene_3_bbr3': 'Scene 3\n(中延迟, 2%丢包)'
    }
    
    # 生成表格数据
    table_rows = []
    
    for scene in scene_order:
        if scene not in results_map:
            continue
        
        for cca in ['cubic', 'bbr', 'bbr2', 'bbr3']:
            if cca not in results_map[scene]:
                continue
            
            strats = results_map[scene][cca]
            no_split = strats.get('no_split', 0.0)
            adaptive = strats.get('adaptive_split', 0.0)
            gain = calculate_gain(no_split, adaptive)
            decision = make_decision(cca, gain, no_split, adaptive)
            
            table_rows.append({
                'scene': scene_names[scene],
                'cca': cca_names[cca],
                'no_split': no_split,
                'adaptive': adaptive,
                'gain': gain,
                'decision': decision
            })
    
    # 打印 Markdown 表格（适合复制到 PPT）
    print("\n" + "="*100)
    print("汇总表格（适合复制到 PPT）")
    print("="*100 + "\n")
    
    print("| 场景 | 拥塞控制算法 | No Split (Mbps) | Adaptive Split (Mbps) | 增益 (%) | 决策 |")
    print("|------|-------------|----------------|---------------------|---------|------|")
    
    for row in table_rows:
        print(f"| {row['scene']} | {row['cca']} | {row['no_split']:.2f} | {row['adaptive']:.2f} | {row['gain']:+.1f}% | {row['decision']} |")
    
    # 打印 CSV 格式（适合 Excel）
    print("\n" + "="*100)
    print("CSV 格式（适合导入 Excel）")
    print("="*100 + "\n")
    
    print("场景,拥塞控制算法,No Split (Mbps),Adaptive Split (Mbps),增益 (%),决策")
    for row in table_rows:
        print(f"{row['scene']},{row['cca']},{row['no_split']:.2f},{row['adaptive']:.2f},{row['gain']:.1f},{row['decision']}")
    
    # 按场景分组打印（更清晰的格式）
    print("\n" + "="*100)
    print("按场景分组（更清晰的展示）")
    print("="*100 + "\n")
    
    current_scene = None
    for row in table_rows:
        if row['scene'] != current_scene:
            if current_scene is not None:
                print()  # 场景之间的空行
            print(f"### {row['scene']}")
            print("| 拥塞控制算法 | No Split (Mbps) | Adaptive Split (Mbps) | 增益 (%) | 决策 |")
            print("|-------------|----------------|---------------------|---------|------|")
            current_scene = row['scene']
        
        print(f"| {row['cca']} | {row['no_split']:.2f} | {row['adaptive']:.2f} | {row['gain']:+.1f}% | {row['decision']} |")
    
    # 统计摘要
    print("\n" + "="*100)
    print("关键发现摘要")
    print("="*100 + "\n")
    
    cubic_gains = [r['gain'] for r in table_rows if r['cca'] == 'Cubic']
    bbr1_gains = [r['gain'] for r in table_rows if r['cca'] == 'BBRv1']
    bbr2_gains = [r['gain'] for r in table_rows if r['cca'] == 'BBRv2']
    bbr3_gains = [r['gain'] for r in table_rows if r['cca'] == 'BBRv3']
    
    print(f"**Cubic 平均增益**: {sum(cubic_gains)/len(cubic_gains):.1f}%")
    print(f"  - Scene 2: {cubic_gains[1]:.1f}%")
    print(f"  - Scene 3: {cubic_gains[2]:.1f}%")
    print()
    print(f"**BBRv1 平均增益**: {sum(bbr1_gains)/len(bbr1_gains):.1f}%")
    print(f"  - Scene 2: {bbr1_gains[1]:.1f}%")
    print(f"  - Scene 3: {bbr1_gains[2]:.1f}%")
    print()
    print(f"**BBRv2 平均增益**: {sum(bbr2_gains)/len(bbr2_gains):.1f}%")
    print(f"  - Scene 2: {bbr2_gains[1]:.1f}%")
    print(f"  - Scene 3: {bbr2_gains[2]:.1f}%")
    print()
    print(f"**BBRv3 平均增益**: {sum(bbr3_gains)/len(bbr3_gains):.1f}%")
    print(f"  - Scene 2: {bbr3_gains[1]:.1f}%")
    print(f"  - Scene 3: {bbr3_gains[2]:.1f}%")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_table(sys.argv[1])
    else:
        generate_table("results/final_results.json")
