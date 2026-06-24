#!/bin/bash
echo "============================================"
echo "  出入库管理系统 - 启动中..."
echo "============================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python3"
    exit 1
fi

# 安装依赖
echo "[1/3] 安装依赖..."
pip3 install -r requirements.txt -q

# 启动服务
echo "[2/3] 启动服务器..."
python3 server.py &
sleep 3

echo "[3/3] 服务已启动！"
echo ""
echo "============================================"
echo "  访问地址: http://localhost:8001"
echo "============================================"
