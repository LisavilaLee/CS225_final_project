#!/bin/bash
# Git clone TLS错误修复脚本

echo "=== Git Clone TLS错误修复方案 ==="
echo ""

# 方案1: 配置git使用系统代理（如果clash在7890端口）
echo "方案1: 配置git使用clash代理"
echo "执行以下命令（假设clash在7890端口）:"
echo ""
echo "  git config --global http.proxy http://127.0.0.1:7890"
echo "  git config --global https.proxy http://127.0.0.1:7890"
echo ""

# 方案2: 临时禁用SSL验证（不推荐，但可以快速解决）
echo "方案2: 临时禁用SSL验证（已执行）"
git config --global http.sslVerify false
echo "✓ 已禁用SSL验证"
echo ""

# 方案3: 使用HTTP而不是HTTPS
echo "方案3: 使用HTTP协议（如果支持）"
echo "  git clone http://kernel.ubuntu.com/git/ubuntu/ubuntu-jammy.git"
echo ""

# 方案4: 检查clash代理端口
echo "方案4: 检查clash代理端口"
if command -v clashon &> /dev/null; then
    echo "  检测到clashon命令"
    echo "  请检查clash配置中的端口（通常是7890或1080）"
fi
echo ""

echo "=== 推荐操作 ==="
echo "1. 先尝试方案1（配置代理）"
echo "2. 如果还不行，尝试方案3（使用HTTP）"
echo "3. 或者暂时关闭代理: clashoff"

