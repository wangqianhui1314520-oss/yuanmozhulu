#!/bin/bash
# =============================================================================
# 元末逐鹿 3.0 · CloudStudio 启动脚本 (Linux)
# =============================================================================

echo "========================================"
echo " 元末逐鹿 3.0 · CloudStudio 部署启动"
echo "========================================"

# 1. 安装 Python 依赖
echo "[1/3] 安装 Python 依赖..."
pip install -r server/requirements.txt -q

# 2. 构建前端
echo "[2/3] 构建前端..."
cd frontend
npm install --no-audit --no-fund
npm run build
cd ..

# 3. 设置环境变量
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# 4. 启动服务
echo "[3/3] 启动游戏服务器..."
python server.py
