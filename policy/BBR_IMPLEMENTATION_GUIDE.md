# BBR实现与Policy集成指南

## 一、项目完成历程总结

### 1. 已完成的工作

#### 1.1 Policy模块实现 (`policy/adaptive_split.py`)
- ✅ **NetworkScenario类**：定义了网络场景的数据结构
  - 包含网络参数：delay1/2, loss1/2, bw1/2
  - 包含拥塞控制算法：`cc`字段（当前只配置了"cubic"）
  - 提供计算属性：`rtt_ms`, `loss_pct`, `bottleneck_bw_mbps`

- ✅ **AdaptiveSplitPolicy类**：实现了自适应决策逻辑
  - 基于RTT和丢包率的rule-based策略
  - 决策逻辑**不依赖CC算法类型**，只基于网络条件
  - 支持三种策略：`no_split`, `always_split`, `adaptive_split`

#### 1.2 Demo运行脚本 (`demo/run_demo_with_policy.py`)
- ✅ 从JSON文件加载场景配置
- ✅ 循环运行三种策略的实验
- ✅ 调用`emulation/main.py`执行实际仿真
- ✅ 收集并聚合结果到JSON文件

#### 1.3 Demo可视化 (`policy/demo_adaptive_policy.ipynb`)
- ✅ 读取demo结果数据
- ✅ 对比三种策略的吞吐量
- ✅ 计算相对收益（gain）
- ✅ 验证policy决策行为

#### 1.4 当前配置 (`demo/scenarios.json`)
- ✅ 定义了3个网络场景
- ⚠️ **所有场景都只使用CUBIC**，没有BBR场景

### 2. 系统对BBR的支持情况

#### 2.1 代码层面已支持
- ✅ `emulation/main.py`支持`--congestion-control bbr`和`bbr2`
- ✅ `emulation/benchmark/tcp.py`通过`set_tcp_congestion_control()`设置CC算法
- ✅ `emulation/network/__init__.py`自动处理BBR的pacing需求

#### 2.2 系统层面需要配置
- ⚠️ **当前系统只支持CUBIC和Reno**（需要安装支持BBR的内核）
- 📝 需要按照`deps/BBRV3.md`安装BBRv2或BBRv3内核

## 二、如何实现BBR支持

### 步骤1：安装支持BBR的内核（可选，如果系统已有BBR可跳过）

根据`deps/BBRV3.md`的说明：

#### 对于BBRv3：
```bash
# 1. 安装依赖
sudo apt update
sudo apt install build-essential fakeroot libncurses-dev libssl-dev libelf-dev bison flex bc wget

# 2. 下载并编译内核（需要较长时间）
git clone https://kernel.ubuntu.com/git/ubuntu/ubuntu-jammy.git
cd ubuntu-jammy
git remote add google-bbr https://github.com/google/bbr.git
git fetch google-bbr
git checkout google-bbr/v3

# 3. 配置和编译（详细步骤见deps/BBRV3.md）
# 4. 安装并重启
sudo make modules_install
sudo make install
sudo update-grub
sudo reboot

# 5. 验证
sudo modprobe tcp_bbr
sysctl net.ipv4.tcp_available_congestion_control
# 应该看到: reno cubic bbr
```

#### 对于BBRv2：
类似步骤，但checkout `google-bbr/v2alpha`分支，内核版本为5.13.12。

**注意**：如果只是做demo，可以先用CUBIC验证policy逻辑，BBR内核安装可以后续进行。

### 步骤2：更新scenarios.json添加BBR场景

在`demo/scenarios.json`中添加BBR场景。有两种方式：

#### 方式A：为现有场景添加BBR版本（推荐）
为每个场景创建CUBIC和BBR两个版本，便于对比。

#### 方式B：添加新的BBR专用场景
创建专门测试BBR的场景。

### 步骤3：运行BBR实验

使用现有的`run_demo_with_policy.py`脚本，它会自动：
1. 读取scenarios.json中的`cc`字段
2. 传递给`emulation/main.py`的`--congestion-control`参数
3. Policy决策逻辑**不依赖CC类型**，会自动适配

## 三、Policy与BBR的集成

### 3.1 Policy设计特点

**关键点**：`AdaptiveSplitPolicy`的决策逻辑**完全独立于CC算法类型**：

```python
def should_split(self, scenario: NetworkScenario) -> bool:
    # 只使用RTT和loss，不关心scenario.cc
    if scenario.rtt_ms >= self.rtt_high_ms and scenario.loss_pct >= self.loss_nontrivial_pct:
        return True
    # ...
```

这意味着：
- ✅ **同一个policy可以同时用于CUBIC和BBR**
- ✅ **不需要为不同CC算法写不同的policy**
- ✅ **只需要在scenarios.json中配置不同的`cc`值**

### 3.2 集成方式

1. **在scenarios.json中配置BBR场景**：
   ```json
   {
     "id": "scene_1_bbr",
     "cc": "bbr",  // 或 "bbr2"
     // ... 其他网络参数
   }
   ```

2. **运行demo**：
   ```bash
   python demo/run_demo_with_policy.py --scenarios demo/scenarios.json
   ```

3. **Policy自动适配**：
   - 对于CUBIC场景，policy基于RTT/loss决策
   - 对于BBR场景，policy**使用相同的决策逻辑**
   - 结果会包含`cca`字段，可以在notebook中分别分析

### 3.3 分析BBR vs CUBIC

在`demo_adaptive_policy.ipynb`中可以：
1. 按`cca`字段分组，分别分析CUBIC和BBR
2. 对比相同网络条件下，BBR和CUBIC对splitting的响应
3. 验证policy在不同CC算法下的有效性

## 四、实施建议

### 最小改动方案（推荐）

1. **先验证CUBIC + Policy**（当前已完成）
2. **添加BBR场景到scenarios.json**（只需修改JSON）
3. **如果系统支持BBR，直接运行**；如果不支持，先用CUBIC完成demo

### 完整方案

1. 安装BBR内核（如果需要）
2. 更新scenarios.json，添加BBR场景
3. 运行完整实验（CUBIC + BBR）
4. 在notebook中对比分析

## 五、当前状态总结

| 模块 | 状态 | 说明 |
|------|------|------|
| Policy实现 | ✅ 完成 | 不依赖CC类型，可直接用于BBR |
| Demo脚本 | ✅ 完成 | 支持任意CC算法 |
| Demo Notebook | ✅ 完成 | 可分析不同CC的结果 |
| scenarios.json | ⚠️ 只有CUBIC | 需要添加BBR场景 |
| 系统BBR支持 | ⚠️ 未安装 | 需要安装BBR内核（可选） |

**结论**：代码层面已完全支持BBR，只需要：
1. 在scenarios.json中添加BBR场景（必须）
2. 安装BBR内核（如果系统需要，可选）

