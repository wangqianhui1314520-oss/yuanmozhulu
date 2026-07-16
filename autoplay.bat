@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════╗
echo ║    元末逐鹿 — 自动游玩模式          ║
echo ╚══════════════════════════════════════╝
echo.
echo 可用模式:
echo   [1] 朱元璋自动游玩 (normal速度)
echo   [2] 观察模式 (观看AI势力互啄)
echo   [3] 快速模式 (朱元璋, 无等待)
echo   [4] 陈友谅自动游玩
echo   [5] 张士诚自动游玩
echo   [6] 元廷自动游玩
echo   [7] 自定义势力
echo   [8] 列出所有势力
echo   [9] 退出
echo.

set /p choice="请选择 (1-9): "

set FACTION=faction_zhuyuanzhang
set SPEED=normal
set MODE=

if "%choice%"=="1" goto :run
if "%choice%"=="2" set MODE=--watch & goto :run
if "%choice%"=="3" set SPEED=fast & goto :run
if "%choice%"=="4" set FACTION=faction_chenyouliang & goto :run
if "%choice%"=="5" set FACTION=faction_zhangshicheng & goto :run
if "%choice%"=="6" set FACTION=faction_yuan & goto :run
if "%choice%"=="7" goto :custom
if "%choice%"=="8" goto :list
if "%choice%"=="9" exit /b
goto :run

:list
echo.
python -m server.autoplay.autoplay --list-factions
echo.
goto :end

:custom
echo.
echo 可用势力缩写:
echo   yuan     元廷           zhu      朱元璋
echo   chen     陈友谅         zhang    张士诚
echo   fang     方国珍         xu       徐寿辉
echo   ming     明玉珍         wang     王保保
echo   mobei    漠北诸部
echo.
set /p FACTION="输入势力ID或名称: "
goto :run

:run
echo.
echo ══════════════════════════════════════════
echo 启动自动游玩
echo 提示: 按 Ctrl+C 可随时安全停止
echo ══════════════════════════════════════════
echo.

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

python -m server.autoplay.autoplay --faction %FACTION% %MODE% --speed %SPEED%

:end
echo.
echo 自动游玩结束，按任意键退出...
pause >nul
