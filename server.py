"""
元末逐鹿 3.0 启动入口
"""
import os
import sys
import subprocess
from pathlib import Path


def main():
    """主启动函数"""
    project_root = Path(__file__).parent
    server_dir = project_root / "server"
    
    # 切换到项目根目录
    os.chdir(str(project_root))
    
    # 加载 .env 环境变量（必须在任何 LLM 初始化之前）
    try:
        from dotenv import load_dotenv
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"  [OK] .env 已加载 ({env_path})")
        else:
            print(f"  [WARN] .env 文件不存在 ({env_path})，AI功能将不可用")
    except ImportError:
        print("  [WARN] python-dotenv 未安装，跳过 .env 加载")
    
    # 确保 server 在 Python 路径中
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # 设置 UTF-8 编码（Windows 兼容）
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    
    print("=" * 60)
    print("  元末逐鹿 3.0 · 服务端启动")
    print("  至正十一年 · 六边形乱世AI国策")
    print("=" * 60)
    
    # 检查依赖
    try:
        import fastapi
        import uvicorn
        import pydantic
        print(f"  [OK] FastAPI {fastapi.__version__}")
        print(f"  [OK] Uvicorn {uvicorn.__version__}")
        print(f"  [OK] Pydantic {pydantic.__version__}")
    except ImportError as e:
        print(f"  [ERROR] 缺少依赖: {e}")
        print("  请运行: pip install -r server/requirements.txt")
        sys.exit(1)
    
    # 启动服务器
    from server.api_server import start
    start()


if __name__ == "__main__":
    main()
