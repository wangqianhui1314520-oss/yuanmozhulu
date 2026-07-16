"""
元末逐鹿 3.0 · 统一启动入口

一键启动后端 + 前端开发服务器的统一起点。
用法:
  python server.py              # 仅后端 (API :8800)
  python server.py --frontend   # 后端 + 前端 (Vite :3000)
  python server.py --help       # 显示帮助
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def resolve_project_root() -> Path:
    """解析项目根目录（兼容直接运行和 uvicorn 嵌套启动）"""
    return Path(__file__).parent.resolve()


def load_env(project_root: Path):
    """加载 .env 文件（必须在 LLM 初始化前）"""
    try:
        from dotenv import load_dotenv
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"  [OK] .env 已加载 ({env_path})")
        else:
            print(f"  [WARN] .env 文件不存在 ({env_path})，AI 功能将不可用")
    except ImportError:
        print("  [WARN] python-dotenv 未安装，跳过 .env 加载")


def setup_windows_utf8():
    """Windows cp950 编码兼容"""
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception as e:
            print(f"[WARN] 编码重配置失败: {e}")


def check_dependencies():
    """验证核心依赖已安装"""
    deps = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
    ]
    all_ok = True
    for module_name, display_name in deps:
        try:
            mod = __import__(module_name)
            version = getattr(mod, "__version__", "?")
            print(f"  [OK] {display_name} {version}")
        except ImportError:
            print(f"  [ERROR] {display_name} 未安装")
            all_ok = False
    if not all_ok:
        print("\n  请运行: pip install -r server/requirements.txt")
        sys.exit(1)


def start_frontend_dev(project_root: Path):
    """启动前端 Vite 开发服务器（非阻塞子进程）"""
    frontend_dir = project_root / "frontend"
    if not (frontend_dir / "package.json").exists():
        print("  [WARN] frontend/package.json 不存在，跳过前端启动")
        return None

    print(f"\n  [FRONTEND] 启动 Vite 开发服务器...")
    try:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                ["cmd", "/c", "npm run dev"],
                cwd=str(frontend_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            proc = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=str(frontend_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        print(f"  [OK] 前端进程已启动 (PID={proc.pid})，等待 :3000...")
        return proc
    except FileNotFoundError:
        print("  [ERROR] npm 未找到，请先安装 Node.js")
        return None
    except Exception as e:
        print(f"  [ERROR] 前端启动失败: {e}")
        return None


def start_backend(project_root: Path):
    """启动后端 API 服务器"""
    print(f"\n  [BACKEND] 启动 FastAPI 服务器...")

    # 切换到项目根目录
    os.chdir(str(project_root))

    # 确保 server 在 Python 路径中
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from server.api_server import start
    start()


def main():
    parser = argparse.ArgumentParser(
        description="元末逐鹿 3.0 · 统一启动器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python server.py                仅启动后端 API 服务
  python server.py --frontend     同时启动后端 + 前端开发服务器
  python server.py -f             同上（简写）
        """,
    )
    parser.add_argument(
        "-f", "--frontend",
        action="store_true",
        help="同时启动前端 Vite 开发服务器 (端口 3000)",
    )
    args = parser.parse_args()

    project_root = resolve_project_root()

    # ---- 环境准备 ----
    setup_windows_utf8()

    print("=" * 60)
    print("  元末逐鹿 3.0 · 统一启动器")
    print("  至正十一年 · 六边形乱世 AI 国策")
    print("=" * 60)

    load_env(project_root)
    check_dependencies()

    # ---- 启动 ----
    frontend_proc = None
    if args.frontend:
        frontend_proc = start_frontend_dev(project_root)
        import time
        time.sleep(1.5)  # 给前端一点启动时间

    print()
    try:
        start_backend(project_root)
    except KeyboardInterrupt:
        print("\n  正在关闭服务...")
    finally:
        if frontend_proc:
            frontend_proc.terminate()
            print("  前端服务已关闭")


if __name__ == "__main__":
    main()
