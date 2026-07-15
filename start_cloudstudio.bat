@echo off
REM =============================================================================
REM 元末逐鹿 3.0 · CloudStudio 启动脚本
REM 安装依赖 + 构建前端 + 启动后端
REM =============================================================================

echo ========================================
echo  元末逐鹿 3.0 · CloudStudio 部署启动
echo ========================================

REM 1. 安装 Python 依赖
echo [1/3] 安装 Python 依赖...
pip install -r server/requirements.txt -q

REM 2. 构建前端
echo [2/3] 构建前端...
cd frontend
call npm install --no-audit --no-fund
call npm run build
cd ..

REM 3. 设置环境变量
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM 4. 启动服务
echo [3/3] 启动游戏服务器...
python server.py
