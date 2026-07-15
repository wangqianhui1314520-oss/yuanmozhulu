"""
元末逐鹿 3.0 - API 服务器
FastAPI 应用主入口 · 统一 code/msg/data 响应格式 · 后端唯一数据源
"""
from __future__ import annotations
import asyncio
import importlib
import json
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

# 配置日志（必须最先，因其他代码依赖 logger）
# 确保日志目录存在
_logs_dir = Path(__file__).parent.parent / "logs"
_logs_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            _logs_dir / "api_server.log",
            encoding='utf-8', mode='a',
            maxBytes=10 * 1024 * 1024,  # 10MB 自动轮转
            backupCount=5,               # 保留 5 个历史文件
        ),
    ]
)
logger = logging.getLogger("yuanmo.api")

# Windows cp950 编码兼容
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception as e:
        # 编码重配置非关键路径，但可能导致中文日志乱码
        logger.warning(f"stdout/stderr UTF-8重配置失败: {e}，中文日志可能乱码")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# 确保日志目录存在
os.makedirs(Path(__file__).parent.parent / "logs", exist_ok=True)

# 响应构建器
from server.core.response import ApiResponse

# ============================================================
# 安全体系 (IOA Security Suite)
# ============================================================
from server.security import (
    setup_security, get_ioa_engine, get_agent_guard,
    get_validator, get_anomaly_detector, get_anonymizer, get_audit_logger,
)
from server.security.api_routes import router as security_router

# ============================================================
# 全局状态
# ============================================================

# LLM 客户端（延迟初始化）
_llm_clients: dict = {}
_llm_available: bool = False

# 游戏世界状态（唯一数据源）
from server.models.world_state import WorldState, TileType
from server.core.game_initializer import get_initializer
from server.core.round_engine import RoundEngine
from server.core.round_lock import get_round_lock, reset_round_lock  # 3.1
from server.core.mode_manager import get_mode_manager, reset_mode_manager  # 3.1
from server.core.responsibility import reset_responsibility_tracker  # 3.1
from server.core.ending_system import (
    get_ending_engine, reset_ending_engine,
    export_ending_configs, ENDING_CONFIGS,
)

_world_state: WorldState | None = None
_round_engine: RoundEngine | None = None
_pending_commands: list[dict] = []  # 待执行指令队列
_round_snapshots: list[dict] = []   # 回放快照列表
_state_lock = asyncio.Lock()  # 全局状态并发锁

# 配置缓存
_factions_config: dict = {}
_game_const: dict = {}

# P3: 关键模块启动验证标志 — 导入失败时阻止依赖模块的 API
_critical_modules_ok: bool = True
_critical_module_errors: list[str] = []

SERVER_DIR = Path(__file__).parent
PROJECT_DIR = SERVER_DIR.parent
CONFIG_DIR = SERVER_DIR / "config"
MAP_DATA_DIR = SERVER_DIR / "data" / "map"


def _safe_get_str(data: dict, key: str, default: str = "") -> str:
    """安全获取字符串参数，防御前端传入非字符串类型导致后续操作崩溃"""
    val = data.get(key, default)
    if val is None:
        return default
    if isinstance(val, str):
        return val
    try:
        return str(val)
    except Exception:
        return default


def _safe_get_int(data: dict, key: str, default: int = 0) -> int:
    """安全获取整数参数，防御前端传入非数字类型"""
    val = data.get(key, default)
    if val is None:
        return default
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, float):
        return int(val)
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def load_configs():
    global _factions_config, _game_const
    try:
        with open(CONFIG_DIR / "factions.json", "r", encoding="utf-8") as f:
            _factions_config = json.load(f)
        logger.info(f"势力配置加载成功: {len(_factions_config.get('factions', {}))} 个势力")
    except Exception as e:
        logger.warning(f"势力配置加载失败: {e}")
        _factions_config = {"version": "3.0", "factions": {}}
    
    try:
        import yaml
        with open(CONFIG_DIR / "game_const.yaml", "r", encoding="utf-8") as f:
            _game_const = yaml.safe_load(f)
        logger.info("游戏常量加载成功")
    except Exception as e:
        logger.warning(f"游戏常量加载失败: {e}")
        _game_const = {}


load_configs()


# ============================================================
# AI 辅助函数
# ============================================================

def _parse_strategy_result(text: str) -> tuple[list[str], list[str], list[str]]:
    """从 AI 策略分析文本中解析结构化字段"""
    threats, opportunities, recommendations = [], [], []
    lines = text.split('\n')
    current_section = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # 检测分段标题
        if any(kw in stripped for kw in ['威胁', '风险', '隐患', '危险', 'threat']):
            current_section = 'threats'
            continue
        if any(kw in stripped for kw in ['机遇', '机会', '契机', '良机', 'opportun']):
            current_section = 'opportunities'
            continue
        if any(kw in stripped for kw in ['建议', '行动', '对策', '策略', '方略', 'recommend']):
            current_section = 'recommendations'
            continue
        if any(kw in stripped for kw in ['总结', '总评', '综论', '以上']):
            current_section = None
            continue
        # 收集条目
        if current_section and len(stripped) > 3:
            entry = stripped.lstrip('1234567890.、-·•· ')
            if current_section == 'threats':
                threats.append(entry)
            elif current_section == 'opportunities':
                opportunities.append(entry)
            elif current_section == 'recommendations':
                recommendations.append(entry)
    return threats, opportunities, recommendations


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="元末逐鹿 3.0 API",
    description="回合制国风策略推演 · CloudAgent 多智能体全涌现式",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 安全体系中间件（IOA / AgentGuard / 速率限制 / 审计日志）
_ioa_engine = setup_security(app)

# 注册安全API路由
app.include_router(security_router)

# ============================================================
# 全局异常处理
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常捕获，不崩服务"""
    # 不捕获系统级异常
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise exc
    logger.error(f"未捕获异常 [{request.method} {request.url.path}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ApiResponse.server_error(f"服务器内部异常，请联系管理员")
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = str(exc.detail) if not isinstance(exc.detail, str) else exc.detail
    # P1修复: 返回真实HTTP状态码而非统一200，让前端拦截器能正确识别
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.error(exc.status_code, detail),
        headers=exc.headers if hasattr(exc, 'headers') else None,
    )



# ============================================================
# 关键模块导入验证（P0修复：防止运行时 ImportError）
# ============================================================

def _validate_critical_imports():
    """启动时验证所有关键子引擎可正确导入

    P3修复：导入失败时设置全局标志 _critical_modules_ok = False，
    阻止依赖模块的 API 端点，防止运行时崩溃。
    """
    global _critical_modules_ok, _critical_module_errors
    _critical_modules_ok = True
    _critical_module_errors = []

    # -- 第一阶段：验证模块文件可被 importlib 找到 --
    critical_modules = [
        ("settle_engine", "server.core.settle_engine"),
        ("ending_system", "server.core.ending_system"),
        ("war_orchestrator", "server.agent.war_orchestrator"),
        ("advanced_features", "server.core.advanced_features"),
        ("diplomacy_deep", "server.core.diplomacy_deep"),
    ]
    failed = []
    for short_name, full_path in critical_modules:
        try:
            importlib.import_module(full_path)
        except Exception as e:
            failed.append(f"{short_name}: {e}")
            _critical_module_errors.append(f"{short_name}: {e}")
            logger.error(f"关键模块导入失败 [{full_path}]: {e}")

    if failed:
        _critical_modules_ok = False
        logger.critical(f"以下关键模块无法加载，相关API端点将不可用: {failed}")
    else:
        logger.info(f"关键模块导入验证通过 ({len(critical_modules)}个模块)")

    # -- 第二阶段：验证关键类存在于正确模块中 --
    # 注意：MarchEngine/SpyEngine/DiplomacyEngine/CourtEngine 都在 settle_engine 中，
    #       不是独立模块；WarOrchestrator 在 server.agent.war_orchestrator 中。
    critical_classes = [
        ("MarchEngine", "server.core.settle_engine"),
        ("SpyEngine", "server.core.settle_engine"),
        ("DiplomacyEngine", "server.core.settle_engine"),
        ("CourtEngine", "server.core.settle_engine"),
        ("WarOrchestrator", "server.agent.war_orchestrator"),
    ]
    for cls_name, mod_path in critical_classes:
        try:
            mod = importlib.import_module(mod_path)
            if not hasattr(mod, cls_name):
                logger.error(f"关键类 {cls_name} 在模块 {mod_path} 中未找到")
        except Exception as e:
            logger.error(f"关键类验证失败 [{cls_name} from {mod_path}]: {e}")

    # -- 第三阶段：验证核心枚举 --
    try:
        from server.models.world_state import PolicyType, BuildingType, SiegeState
        _ = (PolicyType, BuildingType, SiegeState)
    except ImportError as e:
        logger.critical(f"核心枚举导入失败: {e}。请清除 __pycache__ 后重启。")

# ============================================================
# LLM 初始化
# ============================================================

async def init_llm_clients():
    global _llm_clients, _llm_available
    try:
        from server.infra.llm_client.hunyuan_client import get_global_clients
        _llm_clients = await get_global_clients()
        from server.infra.llm_client.config import LLMRuntimeConfig
        runtime = LLMRuntimeConfig.from_env()
        _llm_available = bool(runtime.advisor.api_key)
        logger.info(f"LLM客户端初始化完成, ai_available={_llm_available}")
    except Exception as e:
        logger.warning(f"LLM客户端初始化失败: {e}，AI功能将不可用")
        _llm_available = False
        _llm_clients = {}


@app.on_event("startup")
async def startup_event():
    """服务启动：初始化LLM + 关键模块导入验证"""
    # P0修复: 提前验证关键模块导入，避免运行时 ImportError
    _validate_critical_imports()
    await init_llm_clients()


@app.on_event("shutdown")
async def shutdown_event():
    try:
        from server.infra.llm_client.hunyuan_client import close_global_clients
        await close_global_clients()
    except Exception as e:
        logger.warning(f"关闭LLM全局客户端时出错: {e}")


# ============================================================
# API 端点 - 健康检查
# ============================================================

@app.get("/api/health")
async def health_check():
    # 获取Token消耗统计
    token_stats = {}
    if _llm_available and _llm_clients:
        from server.infra.llm_client import get_global_token_usage
        g = get_global_token_usage()
        token_stats = {
            "total_tokens_consumed": g.total_tokens,
            "prompt_tokens": g.prompt_tokens,
            "completion_tokens": g.completion_tokens,
            "per_client": {},
        }
        for key in ("advisor", "law", "enemy"):
            c = _llm_clients.get(key)
            if c and hasattr(c, "get_token_stats"):
                token_stats["per_client"][key] = c.get_token_stats()

    return ApiResponse.success({
        "status": "ok",
        "version": "3.0.0",
        "title": "元末逐鹿",
        "ai_available": _llm_available,
        "factions_loaded": len(_factions_config.get("factions", {})),
        "game_active": _world_state is not None,
        "current_round": _world_state.current_round if _world_state else 0,
        "token_stats": token_stats,
        "llm_models": {
            "advisor": (_llm_clients.get("advisor") or {}).model_name if hasattr(_llm_clients.get("advisor"), "model_name") else None,
            "law": (_llm_clients.get("law") or {}).model_name if hasattr(_llm_clients.get("law"), "model_name") else None,
            "enemy": (_llm_clients.get("enemy") or {}).model_name if hasattr(_llm_clients.get("enemy"), "model_name") else None,
        } if _llm_available else None,
    })


@app.get("/api/health/connectivity")
async def connectivity_test():
    """
    连通性诊断端点
    
    测试项目:
    1. 服务是否在线
    2. 关键依赖模块是否可导入
    3. 游戏世界状态是否正常
    4. LLM 是否可用
    """
    import time as _time
    import importlib

    t_start = _time.perf_counter()
    results = {
        "server": {"status": "online", "latency_ms": 0},
        "modules": {},
        "world_state": {"status": "no_game"},
        "llm": {},
        "diagnosis": {"errors": [], "warnings": []},
    }

    # 1. 关键模块检查
    module_checks = [
        ("world_state", "server.models.world_state"),
        ("settle_engine", "server.core.settle_engine"),
        ("round_engine", "server.core.round_engine"),
        ("ending_system", "server.core.ending_system"),
        ("response", "server.core.response"),
    ]
    for name, mod_path in module_checks:
        try:
            importlib.import_module(mod_path)
            results["modules"][name] = "ok"
        except Exception as e:
            results["modules"][name] = f"error: {e}"
            results["diagnosis"]["errors"].append(f"模块 {name} 导入失败: {e}")

    # 2. 核心枚举验证
    try:
        from server.models.world_state import PolicyType, BuildingType, SiegeState
        results["modules"]["core_enums"] = f"ok ({len(PolicyType.__members__)} policies)"
    except ImportError as e:
        results["modules"]["core_enums"] = f"error: {e}"
        results["diagnosis"]["errors"].append(f"核心枚举 PolicyType 等导入失败（请清除__pycache__）: {e}")

    # 3. 世界状态检查
    if _world_state:
        player = _world_state.get_player_faction()
        results["world_state"] = {
            "status": "active",
            "round": _world_state.current_round,
            "year": getattr(_world_state, 'current_year', '?'),
            "factions": len(_world_state.factions),
            "tiles": len(getattr(_world_state, 'tiles', {})),
            "player_alive": player.is_alive if player else False,
        }
    else:
        results["world_state"]["status"] = "no_game"

    # 4. LLM 可用性
    results["llm"] = {
        "available": _llm_available,
        "models": {},
    }
    if _llm_available and _llm_clients:
        for key in ("advisor", "law", "enemy"):
            client = _llm_clients.get(key)
            results["llm"]["models"][key] = {
                "available": client is not None,
                "model_name": getattr(client, 'model_name', 'unknown') if client else None,
            }

    t_end = _time.perf_counter()
    results["server"]["latency_ms"] = round((t_end - t_start) * 1000, 2)

    # 汇总诊断
    has_errors = len(results["diagnosis"]["errors"]) > 0
    results["diagnosis"]["overall"] = "healthy" if not has_errors else "degraded"

    return ApiResponse.success(results)


# ============================================================
# API 端点 - 配置
# ============================================================

@app.get("/api/config/factions")
async def get_factions_config():
    return ApiResponse.success(_factions_config)


@app.get("/api/config/faction/{faction_id}")
async def get_faction_detail(faction_id: str):
    faction = _factions_config.get("factions", {}).get(faction_id)
    if not faction:
        return ApiResponse.error(404, f"势力 {faction_id} 不存在")
    return ApiResponse.success(faction)


@app.get("/api/config/constants")
async def get_game_constants():
    return ApiResponse.success(_game_const)


@app.get("/api/config/counter-relations")
async def get_counter_relations():
    return ApiResponse.success(_factions_config.get("counter_relations", []))


# ============================================================
# API 端点 - 运行时配置
# ============================================================

@app.get("/api/config/runtime")
async def get_runtime_config():
    try:
        from server.infra.llm_client.config import LLMRuntimeConfig
        rt = LLMRuntimeConfig.from_env()
        config = {
            "advisor": {
                "api_base": rt.advisor.api_base,
                "model_name": rt.advisor.model_name,
                "temperature": rt.advisor.temperature,
                "max_tokens": rt.advisor.max_tokens,
            },
            "law": {
                "api_base": rt.law.api_base,
                "model_name": rt.law.model_name,
                "temperature": rt.law.temperature,
                "max_tokens": rt.law.max_tokens,
            },
            "enemy": {
                "api_base": rt.enemy.api_base,
                "model_name": rt.enemy.model_name,
                "temperature": rt.enemy.temperature,
                "max_tokens": rt.enemy.max_tokens,
            },
            "max_concurrent": rt.max_concurrent,
            "fallback_enabled": rt.fallback_enabled,
        }
        return ApiResponse.success(config)
    except Exception as e:
        logger.warning(f"获取运行时配置失败: {e}")
        return ApiResponse.success({})


@app.post("/api/config/runtime")
async def update_runtime_config(request: dict):
    """热更新配置，无需重启服务"""
    try:
        config_path = CONFIG_DIR / "llm_runtime.json"
        existing = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        for model_key in ["advisor", "law", "enemy"]:
            if model_key in request:
                existing[model_key] = {**existing.get(model_key, {}), **request[model_key]}

        if "max_concurrent" in request:
            existing["max_concurrent"] = request["max_concurrent"]
        if "fallback_enabled" in request:
            existing["fallback_enabled"] = request["fallback_enabled"]

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        await init_llm_clients()
        # 热更新后同步 LLM 可用性到 RoundEngine，避免 AI 空转
        if _round_engine:
            _round_engine.set_llm_clients(_llm_clients, available=_llm_available)
        return ApiResponse.success(existing, "配置已热更新")
    except Exception as e:
        logger.error(f"配置更新失败: {e}")
        return ApiResponse.server_error(f"配置更新失败: {str(e)}")


@app.post("/api/config/test-llm")
async def test_llm_connection(request: Request):
    """
    真正的 AI 模型连通性测试。
    对每个已配置的模型发送简短测试请求，返回逐模型连通状态、延迟和错误信息。
    """
    import time
    from server.infra.llm_client.config import LLMRuntimeConfig

    try:
        body = await request.json()
    except Exception:
        body = {}
    models_to_test = body.get("models", ["advisor", "law", "enemy"])
    if not isinstance(models_to_test, list):
        models_to_test = ["advisor", "law", "enemy"]

    results = {}
    all_passed = True
    any_configured = False

    try:
        runtime = LLMRuntimeConfig.from_env()
    except Exception as e:
        return ApiResponse.success({
            "passed": False,
            "configured": False,
            "results": {},
            "message": f"配置加载失败: {str(e)}",
        })

    for model_key in models_to_test:
        model_cfg = getattr(runtime, model_key, None)
        if model_cfg is None:
            results[model_key] = {
                "status": "skipped",
                "model_name": "--",
                "latency_ms": 0,
                "error": f"未知模型角色: {model_key}",
            }
            continue

        model_name = getattr(model_cfg, "model_name", "--")
        api_key = getattr(model_cfg, "api_key", "")
        api_base = getattr(model_cfg, "api_base", "")

        if not api_key:
            results[model_key] = {
                "status": "not_configured",
                "model_name": model_name,
                "latency_ms": 0,
                "error": f"未配置API Key",
                "api_base": api_base,
            }
            continue

        any_configured = True
        client = _llm_clients.get(model_key) if _llm_clients else None
        if not client:
            # 客户端尚未初始化，尝试临时构造一个推理请求
            results[model_key] = {
                "status": "warning",
                "model_name": model_name,
                "latency_ms": 0,
                "error": "LLM客户端未初始化，无法测试",
                "api_base": api_base,
            }
            all_passed = False
            continue

        # 发送真实测试请求：使用公开的 chat 方法确保路由正确
        test_prompt = "请用一句简短中文回复：元末逐鹿连接测试成功。"
        t0 = time.time()
        try:
            import asyncio

            # 用各模型角色对应的方法（确保走正确的 model/temperature 配置）
            if model_key == "advisor":
                response = await asyncio.wait_for(
                    client.chat_role(test_prompt, system_prompt="你是连接测试程序。请直接回复：连接正常。"),
                    timeout=15,
                )
            elif model_key == "law":
                response = await asyncio.wait_for(
                    client.chat_strategy(test_prompt, world_json="{}", system_prompt="你是连接测试程序。请直接回复：连接正常。"),
                    timeout=15,
                )
            else:  # enemy
                response = await asyncio.wait_for(
                    client.chat_fast(test_prompt, system_prompt="你是连接测试程序。请直接回复：连接正常。"),
                    timeout=15,
                )

            latency = round((time.time() - t0) * 1000)
            response_text = (response or "").strip()

            if response_text:
                results[model_key] = {
                    "status": "ok",
                    "model_name": model_name,
                    "latency_ms": latency,
                    "response_preview": response_text[:80],
                    "api_base": api_base,
                }
            else:
                results[model_key] = {
                    "status": "no_response",
                    "model_name": model_name,
                    "latency_ms": latency,
                    "error": "模型返回空内容",
                    "api_base": api_base,
                }
                all_passed = False
        except asyncio.TimeoutError:
            results[model_key] = {
                "status": "timeout",
                "model_name": model_name,
                "latency_ms": 15000,
                "error": "请求超时（15秒）",
                "api_base": api_base,
            }
            all_passed = False
        except Exception as e:
            latency = round((time.time() - t0) * 1000)
            results[model_key] = {
                "status": "error",
                "model_name": model_name,
                "latency_ms": latency,
                "error": f"{type(e).__name__}: {str(e)[:200]}",
                "api_base": api_base,
            }
            all_passed = False

    status_map = {
        "ok": "✓ 正常",
        "timeout": "⏱ 超时",
        "error": "✗ 错误",
        "not_configured": "⚙ 未配置",
        "warning": "⚠ 未就绪",
        "no_response": "✗ 无响应",
        "unexpected_response": "⚠ 异常响应",
        "skipped": "⊘ 跳过",
    }
    summary_parts = [f"{model_key}: {status_map.get(r['status'], r['status'])} ({r['latency_ms']}ms)"
                     for model_key, r in results.items()]
    message = "; ".join(summary_parts) if any_configured else "所有模型均未配置API Key"

    return ApiResponse.success({
        "passed": all_passed and any_configured,
        "configured": any_configured,
        "results": results,
        "message": message,
    })


# ============================================================
# AI 语音合成（势力角色配音生成）
# ============================================================
from server.services.tts_service import (
    generate_faction_voice,
    generate_all_faction_voices,
    list_available_voices,
    get_voice_config,
    get_voice_text,
    FACTION_VOICE_CONFIG,
)


@app.post("/api/audio/generate-voice")
async def api_generate_faction_voice(request: Request):
    """为指定势力生成 AI 配音 MP3"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    faction_id = body.get("faction_id", "")
    force = body.get("force", False)

    if not faction_id:
        return ApiResponse.bad_request("缺少 faction_id 参数")

    result = await generate_faction_voice(faction_id, force=force)
    return ApiResponse.success(result)


@app.post("/api/audio/generate-all-voices")
async def api_generate_all_voices(request: Request):
    """批量生成全部九大势力的 AI 配音"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    force = body.get("force", False)

    results = await generate_all_faction_voices(force=force)
    generated = sum(1 for r in results if r.get("generated"))
    cached = sum(1 for r in results if r.get("cached"))
    errors = sum(1 for r in results if r.get("error"))

    return ApiResponse.success({
        "total": len(results),
        "generated": generated,
        "cached": cached,
        "errors": errors,
        "results": results,
    })


@app.get("/api/audio/voice-status")
async def api_voice_status():
    """查看所有势力配音文件状态"""
    voices = list_available_voices()
    ready = sum(1 for v in voices if v["status"] == "ready")
    return ApiResponse.success({
        "total": len(voices),
        "ready": ready,
        "missing": len(voices) - ready,
        "voices": voices,
    })


@app.get("/api/audio/voice-config")
async def api_voice_config():
    """查看势力音色配置和台词"""
    configs = {}
    for faction_id, cfg in FACTION_VOICE_CONFIG.items():
        configs[faction_id] = {
            "role": cfg["role"],
            "voice": cfg["voice"],
            "rate": cfg["rate"],
            "pitch": cfg["pitch"],
            "desc": cfg.get("desc", ""),
            "text": get_voice_text(faction_id),
        }
    return ApiResponse.success(configs)


@app.get("/api/config/default")
async def get_default_config():
    from server.infra.llm_client.config import (
        HUNYUAN_API_BASE, MODEL_ROLE, MODEL_STRATEGY, MODEL_FAST,
        TEMP_ROLE, TEMP_STRATEGY, TEMP_FAST, MAX_CONCURRENT_AGENTS,
    )
    return ApiResponse.success({
        "advisor": {
            "api_base": HUNYUAN_API_BASE,
            "model_name": MODEL_ROLE,
            "temperature": TEMP_ROLE,
            "max_tokens": 4096,
        },
        "law": {
            "api_base": HUNYUAN_API_BASE,
            "model_name": MODEL_STRATEGY,
            "temperature": TEMP_STRATEGY,
            "max_tokens": 8192,
        },
        "enemy": {
            "api_base": HUNYUAN_API_BASE,
            "model_name": MODEL_FAST,
            "temperature": TEMP_FAST,
            "max_tokens": 2048,
        },
        "max_concurrent": MAX_CONCURRENT_AGENTS,
        "fallback_enabled": True,
    })


# ============================================================
# API 端点 - 游戏控制（核心链路）
# ============================================================

@app.post("/api/game/init")
async def init_game(request: dict):
    """
    链路1: 开局初始化（3.1: 集成模式管理）
    
    参数:
        faction_id: 历史势力ID（如 ruler_zhuyuan）
        mode: player_turn / ai_watch
        custom_faction: 自创王朝参数（可选）
    
    返回: 完整 world_state + 初始地图数据
    """
    # P3: 关键模块验证失败则拒绝开局
    if not _critical_modules_ok:
        return ApiResponse.server_error(
            f"服务启动不完整，以下关键模块加载失败，请检查日志后重启: {'; '.join(_critical_module_errors)}"
        )
    global _world_state, _round_engine, _pending_commands, _round_snapshots
    
    faction_id = _safe_get_str(request, "faction_id")
    mode = _safe_get_str(request, "mode", "player_turn")
    custom_faction = request.get("custom_faction")

    if not faction_id and not custom_faction:
        return ApiResponse.bad_request("请选择开局势力")

    # 自创势力：使用 custom_faction 中的 faction_id 作为 player_faction_id
    is_custom = bool(custom_faction)
    if is_custom and not faction_id:
        faction_id = custom_faction.get("faction_id", "custom_player")

    # 校验 faction_id 是否存在于势力配置中（自创势力跳过校验）
    if not is_custom and faction_id and faction_id not in _factions_config.get("factions", {}):
        return ApiResponse.error(404, f"势力 {faction_id} 不存在，可选势力: {list(_factions_config.get('factions', {}).keys())}")

    # 3.1: 校验模式合法性
    if mode not in ("player_turn", "ai_watch"):
        return ApiResponse.bad_request(f"无效的游戏模式: {mode}，仅支持 player_turn / ai_watch")

    try:
        # 重置所有管理器状态
        reset_round_lock()
        reset_mode_manager()
        reset_responsibility_tracker()
        
        # 重置智能体调度器（清空Agent缓存 + 事件总线）
        orch = _get_orchestrator()
        orch.reset_for_new_game()

        # 重置全局Token消耗计数器
        try:
            from server.infra.llm_client import reset_global_token_usage
            reset_global_token_usage()
        except Exception as e:
            logger.warning(f"Token计数器重置失败（非致命）: {e}")
        
        # 初始化模式管理器
        mode_mgr = get_mode_manager()
        mode_mgr.init_game(mode, faction_id)
        
        initializer = get_initializer()
        _world_state = initializer.create_world(
            player_faction_id=faction_id,
            game_mode=mode,
            custom_faction=custom_faction,
        )
        _round_engine = RoundEngine(_world_state, _factions_config)
        _round_engine.set_llm_clients(_llm_clients, available=_llm_available)
        _pending_commands = []
        _round_snapshots = []

        # 3.2: 初始化领地邻接图（供寻路和攻击邻接查询使用）
        try:
            from server.core.territory_graph import init_territory_graph
            init_territory_graph(_world_state)
        except Exception as tg_err:
            logger.warning(f"[开局] 领地邻接图初始化失败（非致命）: {tg_err}")

        player = _world_state.get_player_faction()
        world_dict = _world_state.model_dump()
        # 情报脱敏：开局时所有势力对玩家都是未知的
        world_dict = _mask_world_state_for_player(world_dict)

        # 3.1: 返回模式信息
        mode_info = mode_mgr.get_mode_info()

        # P3: 复用 world_dict 中的 factions/tiles/relations 避免重复 model_dump
        return ApiResponse.success({
            "world_state": world_dict,
            "player_faction": player.model_dump() if player else None,
            "player_faction_id": _world_state.player_faction_id,  # 核心规则：玩家操控势力ID
            "factions": world_dict.get("factions", {}),
            "tiles": world_dict.get("tiles", {}),
            "relations": world_dict.get("relations", {}),
            "events_log": _world_state.events_log,
            "mode_info": mode_info,  # 3.1
        }, f"开局成功 — {player.name if player else faction_id}（{mode_info['mode_label']}）")
    except Exception as e:
        logger.error(f"开局失败: {e}", exc_info=True)
        return ApiResponse.server_error(f"开局失败: {str(e)}")


@app.post("/api/game/restart")
async def restart_game():
    """重置本局（3.1: 同步重置所有管理器）"""
    global _world_state, _round_engine, _pending_commands, _round_snapshots
    _world_state = None
    _round_engine = None
    _pending_commands = []
    _round_snapshots = []
    
    # 重置所有管理器
    reset_round_lock()
    reset_mode_manager()
    reset_responsibility_tracker()
    reset_ending_engine()
    
    # 重置智能体调度器
    orch = _get_orchestrator()
    orch.reset_for_new_game()
    
    return ApiResponse.success(None, "对局已重置")


@app.get("/api/agent/stats")
async def get_agent_stats():
    """获取所有智能体运行统计（含Token消耗明细）"""
    try:
        orch = _get_orchestrator()
        stats = orch.get_stats()

        # 补充全局Token统计
        if _llm_available:
            from server.infra.llm_client import get_global_token_usage
            g = get_global_token_usage()
            stats["global_token_consumption"] = {
                "total_tokens": g.total_tokens,
                "prompt_tokens": g.prompt_tokens,
                "completion_tokens": g.completion_tokens,
            }
            # 每客户端明细
            per_client = {}
            for key in ("advisor", "law", "enemy"):
                c = _llm_clients.get(key)
                if c and hasattr(c, "get_token_stats"):
                    per_client[key] = c.get_token_stats()
            stats["per_client_tokens"] = per_client

        return ApiResponse.success(stats)
    except Exception as e:
        return ApiResponse.error(500, f"获取Agent统计失败: {e}")


@app.get("/api/game/status")
async def get_game_status():
    """获取游戏运行状态 + 完整世界状态（3.1: 含模式信息）"""
    if not _world_state:
        return ApiResponse.success({
            "running": True,
            "game_active": False,
            "current_round": 0,
            "current_year": 1351,
            "current_month": 4,
            "current_season": "春",
            "game_mode": "player_turn",
            "living_factions": 0,
        })

    world_dict = _world_state.model_dump()
    # 情报脱敏：对非己方势力隐藏敏感数据
    world_dict = _mask_world_state_for_player(world_dict)
    mode_info = get_mode_manager().get_mode_info()
    
    # 2026-07-15 修复: 添加顶层 player_faction 字段，方便前端直接使用
    player_faction_data = None
    player_fid = _world_state.player_faction_id
    if player_fid and player_fid in _world_state.factions:
        pf = _world_state.factions[player_fid]
        player_faction_data = {
            "faction_id": pf.faction_id,
            "name": pf.name,
            "title": pf.title,
            "is_alive": pf.is_alive,
            "capital_tile": pf.capital_tile,
            "treasury": pf.treasury,
            "grain": pf.grain,
            "troops": pf.total_troops,                    # 2026-07-15: 修复字段名 → 与前端/文档一致
            "total_troops": pf.total_troops,
            "total_population": pf.total_population,
            "horses": pf.horses,
            "arms": pf.arms,
            "reputation": pf.reputation,
            "morale": getattr(pf, "popular_support", pf.realm_stability),  # 2026-07-15: 修复 → 民心
            "authority": pf.court_stability,              # 2026-07-15: 修复 → 朝纲
            "popular_support": getattr(pf, "popular_support", pf.realm_stability),
            "court_stability": pf.court_stability,
            "realm_stability": pf.realm_stability,
            "tile_count": pf.tile_count,
            "color": pf.color,
            "ruler_name": pf.ruler_name,
        }
    
    # 2026-07-15 修复: 展开外交关系为前端友好格式
    player_fid = _world_state.player_faction_id
    faction_names = {
        fid: f.name for fid, f in _world_state.factions.items()
    }
    diplomatic_relations = []
    if player_fid:
        for key, rel in _world_state.relations.items():
            a, b = key.split("|")
            if player_fid in (a, b):
                other = b if a == player_fid else a
                diplomatic_relations.append({
                    "target_faction_id": other,
                    "target_name": faction_names.get(other, other),
                    "stance": rel.stance.value if hasattr(rel.stance, 'value') else str(rel.stance),
                    "attitude": rel.attitude,
                    "relation_key": key,
                })
    
    return ApiResponse.success({
        "running": True,
        "game_active": True,
        "current_round": _world_state.current_round,
        "current_year": _world_state.current_year,
        "current_month": _world_state.current_month,
        "current_season": _world_state.current_season,
        "phase": "player_turn" if mode_info.get("player_faction_id") else "ai_turn",
        "world_state": world_dict,
        "player_faction_id": _world_state.player_faction_id,  # 核心规则
        "player_faction": player_faction_data,  # 2026-07-15: 顶层玩家势力数据
        "diplomatic_relations": diplomatic_relations,  # 2026-07-15: 展开的外交关系
        "pending_commands": len(_pending_commands),
        "snapshots_count": len(_round_snapshots),
        "mode_info": mode_info,  # 3.1
    })


# ============================================================
# API 端点 - 指令提交（链路2）
# ============================================================

@app.post("/api/game/command")
async def submit_command(request: dict):
    """
    链路2: 统一指令提交（核心规则：玩家只能操控自身势力，禁止越权）
    
    格式:
    {
      "action": "march | spy | trade | law | recruit | develop | ...",
      "params": { ... },
      "faction_id": "玩家势力ID（必填，用于归属校验）"
    }
    
    所有指令不立即执行，统一在「回合推进」批量执行
    """
    global _pending_commands

    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    # ---- 安全校验 (IOA/AgentGuard/DataValidator) ----
    validator = get_validator()
    guard = get_agent_guard()
    detector = get_anomaly_detector()
    ok, err, clean = validator.validate_game_command(request)
    if not ok:
        logger.warning(f"[Security] 指令Schema校验失败: {err}")
        return ApiResponse.bad_request(err)

    faction_id = request.get("faction_id", "")
    action = clean.get("action", "")
    params = clean.get("params", {})
    ok, reason, risk = guard.validate_player_action(faction_id, action, params)
    if not ok:
        logger.warning(f"[Security] Agent行为拦截: faction={faction_id} action={action} risk={risk:.0f} reason={reason}")
        return ApiResponse.forbidden(f"操作被安全策略拦截: {reason}")
    guard.record_action(faction_id, action, params)
    detector.record_behavior(faction_id, action)
    detector.comprehensive_check(faction_id, action)
    get_ioa_engine().record_session(faction_id)
    # ---- 安全校验结束 ----

    # 模式检查 —— ai_watch模式下不允许提交指令
    mode_mgr = get_mode_manager()
    if not mode_mgr.can_player_submit_command():
        return ApiResponse.forbidden("观战模式下不可提交指令，请以玩家模式开局")

    # 核心规则：指令归属校验 —— 玩家只能向自身势力下发政令
    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")
    
    request_faction_id = request.get("faction_id", "")
    if request_faction_id and request_faction_id != player.faction_id:
        return ApiResponse.forbidden(
            f"无权操控其他势力！你只能对己方势力「{player.name}」下达政令"
        )

    # 注意: params 和 action 已在安全校验阶段从 clean dict 提取（见上方 ~L851-852），
    # 不要用 request.get() 再次覆盖清洗后的值，否则安全校验失效。
    if not action:
        return ApiResponse.bad_request("缺少 action 字段")

    # action 中文别名映射（玩家可用中文下达政令）
    _action_aliases = {
        "内政": "develop", "发展农业": "develop", "农业": "develop",
        "军事": "march", "行军": "march", "出征": "march",
        "外交": "diplomacy", "通商": "trade", "贸易": "trade",
        "征兵": "recruit", "募兵": "recruit", "招兵": "recruit",
        "间谍": "spy", "细作": "spy", "谍报": "spy",
        "筑城": "fortify", "城防": "fortify", "加固": "fortify",
        "赈灾": "relief", "救济": "relief", "救灾": "relief",
        "税政": "tax", "征税": "tax", "税收": "tax",
        "建造": "build", "修建": "build",
        "分封": "enfeoff", "赦免": "amnesty", "大赦": "amnesty",
        "买马": "buy_horses", "训练": "train_troops", "练兵": "train_troops",
        "律令": "law", "法令": "law",
        "侦查": "scout", "斥候": "scout",
        "肃清": "purge", "清洗": "purge",
    }
    if action in _action_aliases:
        action = _action_aliases[action]

    # 参数校验（基础）
    valid_actions = [
        "march", "spy", "trade", "law", "recruit", "develop",
        "fortify", "relief", "diplomacy", "tax", "build",
        "enfeoff", "purge", "amnesty", "scout",
        "buy_horses", "train_troops",
        # AI Agent 工具调用映射（collect_tax = AI智能体征税工具）
        "collect_tax",
        # 2026-07-15 修复: 补充缺失的合法指令类型（与 agent_guard.py 同步）
        "attack", "train", "patrol", "mobilize", "raid", "ambush",
        "transport", "garrison", "transfer", "governor",
        "marriage", "tribute", "pledge", "vassal",
        "counter_spy", "sabotage", "bribe", "assassinate",
        "survey", "move_capital", "decree", "conscript",
    ]
    if action not in valid_actions:
        return ApiResponse.bad_request(f"未知指令类型: {action}，支持: {valid_actions}")

    # 3.1: 操作锁预校验（提前告知玩家本回合是否已执行同类操作）
    op_lock = get_round_lock()
    player = _world_state.get_player_faction()
    lock_warning = None
    if player:
        fid = player.faction_id
        lock_map = {
            "march": "行军", "tax": "税政", "diplomacy": "外交",
            "develop": "开发", "recruit": "征兵", "fortify": "城防",
            "relief": "赈灾", "build": "建造", "enfeoff": "分封",
            "buy_horses": "买马", "train_troops": "训练",
        }
        # 简单检查（不阻塞提交，实际执行时才严格校验）
        tile_id = params.get("tile_id", "")
        from_tile = params.get("from_tile", "")
        if action == "march" and from_tile:
            if op_lock.check_march_lock(fid, from_tile, params.get("to_tile", "")):
                lock_warning = f"该部队本回合已行军，指令将在回合结算时被拒绝"
        elif action == "buy_horses":
            # buy_horses 是势力级别操作，检查势力锁
            from server.core.round_lock import LockCategory
            if op_lock.check_faction_lock(fid, LockCategory.BUY_HORSES):
                lock_warning = f"买马操作本回合已执行，指令将在结算时被拒绝"
        elif tile_id:
            lock_cat_map = {
                "develop": "develop", "recruit": "recruit", 
                "fortify": "build", "relief": "relief", "build": "build",
                "train_troops": "train_troops",
            }
            if action in lock_cat_map:
                from server.core.round_lock import LockCategory
                cat = LockCategory(lock_cat_map[action])
                if op_lock.check_tile_lock(tile_id, cat):
                    lock_warning = f"该地块的{lock_map.get(action, action)}操作本回合已执行，指令将在结算时被拒绝"

    async with _state_lock:
        command = {
            "id": f"cmd_{len(_pending_commands)}_{action}",
            "action": action,
            "params": params,
            "submitted_at": _world_state.current_round if _world_state else 0,
        }
        _pending_commands.append(command)
        pending_count = len(_pending_commands)

    response_data = {
        "command_id": command["id"],
        "pending_count": pending_count,
    }
    if lock_warning:
        response_data["warning"] = lock_warning

    return ApiResponse.success(response_data, f"指令「{action}」已纳入待办" + (f"（⚠{lock_warning}）" if lock_warning else ""))


@app.get("/api/game/commands")
async def get_pending_commands():
    """查看待执行指令队列"""
    # 2026-07-15 修复: 为每条指令补齐 command_id（提交时已有 id，但确保返回时有）
    result = []
    for i, cmd in enumerate(_pending_commands):
        entry = dict(cmd)
        if not entry.get("command_id"):
            entry["command_id"] = entry.get("id", f"cmd_{i}")
        result.append(entry)
    return ApiResponse.success({
        "pending_commands": result,
        "count": len(result),
    })


# 3.1 新增端点
@app.get("/api/game/mode-info")
async def get_mode_info():
    """获取当前游戏模式信息"""
    mode_mgr = get_mode_manager()
    return ApiResponse.success(mode_mgr.get_mode_info())


@app.get("/api/game/operation-locks")
async def get_operation_locks():
    """获取当前回合操作锁状态"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    
    op_lock = get_round_lock()
    player = _world_state.get_player_faction()
    
    if not player:
        return ApiResponse.success({"locked_actions": [], "cooling_tiles": {}})
    
    locked_actions = op_lock.get_faction_locked_actions(player.faction_id)
    cooling_tiles = {}
    for tile_id in _world_state.get_faction_tiles(player.faction_id):
        cooling = op_lock.get_tile_cooling_actions(tile_id.tile_id)
        if cooling:
            cooling_tiles[tile_id.tile_id] = cooling
    
    return ApiResponse.success({
        "round": _world_state.current_round,
        "faction_id": player.faction_id,
        "locked_actions": locked_actions,
        "cooling_tiles": cooling_tiles,
    })


@app.get("/api/game/responsibility-stats")
async def get_responsibility_stats():
    """获取权责追踪统计"""
    from server.core.responsibility import get_responsibility_tracker
    tracker = get_responsibility_tracker()
    return ApiResponse.success(tracker.get_stats())


@app.post("/api/game/commands/clear")
async def clear_commands():
    """清空指令队列"""
    global _pending_commands
    count = len(_pending_commands)
    _pending_commands = []
    return ApiResponse.success(None, f"已清空 {count} 条待办指令")


# ============================================================
# API 端点 - 回合推进（链路3 - 游戏心跳）
# ============================================================

@app.post("/api/game/advance-turn")
async def advance_turn(request: dict = None):
    """
    链路3: 回合推进 - 8阶段完整执行（3.2: 唯一回合入口 + 模式检查）
    
    固化时序（对标文明6）:
    ① 指令校验(含操作锁去重) → ② 执行政令 → ③ AI推演(跳过玩家势力)
                                          ↓
    ④ 事件记录 ← ⑤ 数值结算 ← ⑥ 刷新世界(含外交自动调整)
                                          ↓
    ⑦ 回放快照 → ⑧ 自动存档(含结局判定)
    """
    global _pending_commands, _round_snapshots

    if not _world_state or not _round_engine:
        return ApiResponse.forbidden("请先开局")

    # 3.1: 模式检查
    mode_mgr = get_mode_manager()
    if not mode_mgr.can_player_advance_turn():
        return ApiResponse.forbidden("观战模式下不可推进回合")

    async with _state_lock:
        # 检查是否已经 Game Over（含结局判定）
        ending = _check_ending()
        if ending and ending.get("is_game_over"):
            return ApiResponse.success({
                "game_over": True,
                "message": ending.get("description", "游戏已结束"),
                "ending": ending,
                "world_state": _world_state.model_dump(),
            })

        # 收集玩家指令（如果有）
        player_edict = None
        if _pending_commands:
            player_edict = json.dumps(_pending_commands, ensure_ascii=False)

    try:
        # ---- 回合开始时清空圣旨上下文（保证跨回合不混淆） ----
        try:
            from server.core.edict_nlp import get_edict_context
            get_edict_context().clear_turn()
        except ImportError:
            logger.debug("edict_nlp 模块未加载，跳过圣旨上下文清理")
        except Exception as e:
            logger.warning(f"清理圣旨上下文失败（不影响回合流程）: {type(e).__name__}: {e}")

        # 执行完整8阶段回合（在锁外执行，避免长时间持锁）
        round_summary = await _round_engine.execute_round(player_edict)

        async with _state_lock:
            # 3.2 修复: 回合成功后清空 pending_commands，防止跨回合重复执行
            _pending_commands = []
            engine_snapshot = round_summary.pop("_snapshot", None)
            snapshot = engine_snapshot or {
                "round": _world_state.current_round,
                "year": _world_state.current_year,
                "month": _world_state.current_month,
                "season": _world_state.current_season,
                "factions": {
                    fid: {
                        "name": f.name,
                        "treasury": f.treasury,
                        "grain": f.grain,
                        "total_troops": f.total_troops,
                        "total_population": f.total_population,
                        "tile_count": len(_world_state.get_faction_tiles(fid)),
                        "is_alive": f.is_alive,
                    }
                    for fid, f in _world_state.factions.items()
                },
            }
            _round_snapshots.append(snapshot)

            # P2: 防止事件日志和快照无限增长 → OOM
            MAX_EVENTS_LOG = 2000
            MAX_SNAPSHOTS = 50
            if len(_world_state.events_log) > MAX_EVENTS_LOG:
                _world_state.events_log = _world_state.events_log[-MAX_EVENTS_LOG:]
            if len(_round_snapshots) > MAX_SNAPSHOTS:
                _round_snapshots = _round_snapshots[-MAX_SNAPSHOTS:]

            # 检查结局条件（从引擎阶段⑧获取）
            ending = round_summary.get("phases", {}).get("auto_save", {}).get("ending")
            if not ending:
                ending = _check_ending()

            # P2: 锁内只检查是否需要自动存档，实际文件 I/O 放到锁外
            auto_save = round_summary.get("phases", {}).get("auto_save", {})
            should_auto_save = auto_save.get("should_auto_save") and not auto_save.get("game_ending")

            # 返回完整世界状态（脱敏后）
            world_dict = _world_state.model_dump()
            world_dict = _mask_world_state_for_player(world_dict)
            # 2026-07-15 修复: 收集本回合新事件，按严重度排序（major > minor > routine）
            all_round_events = [e for e in _world_state.events_log if e.get("round") == _world_state.current_round]
            severity_order = {"major": 0, "minor": 1, "routine": 2}
            all_round_events.sort(key=lambda e: severity_order.get(e.get("severity", "routine"), 3))
            # 限制返回事件数（前端不需要全部488条），优先返回严重事件
            new_events = all_round_events[:30]

            # 3.1: 获取操作锁状态和模式信息
            op_lock = get_round_lock()
            player = _world_state.get_player_faction()
            locked_actions = []
            cooling_tiles = {}
            if player:
                locked_actions = op_lock.get_faction_locked_actions(player.faction_id)
                for tile in _world_state.get_faction_tiles(player.faction_id):
                    cooling = op_lock.get_tile_cooling_actions(tile.tile_id)
                    if cooling:
                        cooling_tiles[tile.tile_id] = cooling

            mode_info = mode_mgr.get_mode_info()

            # P3修复: 锁内预序列化存档数据，避免锁外 _auto_save_world() 读取 _world_state 时的竞态条件
            auto_save_payload = None
            if should_auto_save:
                try:
                    # 序列化军团和武将（存储在 __dict__ 中，Pydantic model_dump 不包含）
                    all_generals = _world_state.__dict__.get("_generals", {})
                    generals_save: dict[str, list[dict]] = {}
                    for fid, gens in all_generals.items():
                        generals_save[fid] = [g.model_dump() if hasattr(g, 'model_dump') else g for g in gens]
                    all_legions = _world_state.__dict__.get("_legions", {})
                    legions_save: dict[str, list[dict]] = {}
                    for fid, legs in all_legions.items():
                        legions_save[fid] = [l.model_dump() if hasattr(l, 'model_dump') else l for l in legs]

                    auto_save_payload = {
                        "world_state": _world_state.model_dump(),
                        "round": _world_state.current_round,
                        "year": _world_state.current_year,
                        "month": _world_state.current_month,
                        "season": str(_world_state.current_season),
                        "player_faction": player.faction_id if player else "",
                        "faction_name": _factions_config.get("factions", {}).get(
                            player.faction_id if player else "", {}
                        ).get("name", player.name if player else ""),
                        "snapshots_count": len(_round_snapshots),
                        "_generals": generals_save,
                        "_legions": legions_save,
                    }
                except Exception as e:
                    logger.error(f"自动存档预序列化失败: {type(e).__name__}: {e}")

        # P2修复: 自动存档 I/O 移到锁外，避免磁盘操作阻塞所有 API 请求
        if auto_save_payload:
            try:
                _auto_save_world(auto_save_payload)
            except Exception as e:
                logger.error(f"自动存档失败（不影响回合结算）: {type(e).__name__}: {e}")

        return ApiResponse.success({
            "current_round": _world_state.current_round,
            "current_year": _world_state.current_year,
            "current_month": _world_state.current_month,
            "current_season": _world_state.current_season,
            "phase": round_summary.get("current_phase", "settlement"),  # 2026-07-15: 修复 → 返回当前阶段名
            "round_summary": round_summary,
            "world_state": world_dict,
            "new_events": new_events,
            "pending_commands_cleared": True,
            "snapshot": snapshot,
            "ending": ending,
            # 3.1 新增
            "mode_info": mode_info,
            "locked_actions": locked_actions,
            "cooling_tiles": cooling_tiles,
            "responsibility_stats": round_summary.get("responsibility_stats", {}),
            # 地盘变更（本回合新产生的）
            "tile_changes": [c for c in _world_state.tile_changes if c.get("round") == _world_state.current_round],
        }, f"第 {_world_state.current_round} 回合执行完毕")
    except asyncio.TimeoutError:
        logger.error("回合执行超时（300秒），可能有死锁")
        return ApiResponse.server_error("回合执行超时，请稍后重试")
    except Exception as e:
        logger.error(f"回合推进失败: {e}", exc_info=True)
        # 3.2 修复: 回合失败时保留 pending_commands（不清空），让玩家可以重试
        return ApiResponse.server_error(f"回合推进异常: {str(e)[:300]}")


def _check_ending() -> dict | None:
    """
    检查结局条件（3.3 四大结局系统）
    委托给 EndingEngine 处理
    """
    engine = get_ending_engine()
    if not engine:
        return None
    result = engine.check_all_endings()
    return result


# 存档目录（与 auto_save 及 save/load API 共用）
SAVE_DIR = PROJECT_DIR / "data" / "archives"
SAVE_DIR.mkdir(parents=True, exist_ok=True)


def _auto_save_world(payload: dict = None):
    """自动存档（不覆盖手动存档槽，保留最近 backup_keep_count 个）

    P2修复：使用原子写入（先写临时文件再改名），防止写盘中途崩溃导致存档损坏。
    P3修复：接收调用方在锁内预序列化的 payload，避免锁外读取 _world_state 时的竞态条件。
    调用方应确保在锁外调用此函数，避免文件 I/O 阻塞状态锁。
    """
    temp_path = None
    final_path = None
    try:
        # P3: 优先使用调用方传入的预序列化数据（已在锁内生成，无竞态风险）
        if payload:
            world_dict = payload["world_state"]
            current_round = payload["round"]
            faction_name = payload.get("faction_name", "")
            player_faction = payload.get("player_faction", "")
            snapshots_count = payload.get("snapshots_count", 0)
            # 计算领土（从 world_dict 获取，不依赖 _world_state）
            territory = 0
            try:
                factions = world_dict.get("factions", {})
                pf = factions.get(player_faction, {}) if player_faction else {}
                territory = len(pf.get("tiles", []))
            except Exception:
                territory = 0
        else:
            # 兼容旧调用（无 payload 时回退到直接读取，有竞态风险但维持可用性）
            if not _world_state:
                return
            player = _world_state.get_player_faction()
            faction_name = ""
            if player:
                faction_name = _factions_config.get("factions", {}).get(player.faction_id, {}).get("name", player.name)
            player_faction = player.faction_id if player else ""
            current_round = _world_state.current_round
            territory = len(_world_state.get_faction_tiles(player.faction_id)) if player else 0
            world_dict = _world_state.model_dump()
            snapshots_count = len(_round_snapshots)

        # 提取 _generals / _legions（从 payload 或回退读取）
        generals_save = {}
        legions_save = {}
        if payload:
            generals_save = payload.get("_generals", {})
            legions_save = payload.get("_legions", {})
        elif _world_state:
            try:
                all_generals = _world_state.__dict__.get("_generals", {})
                for fid, gens in all_generals.items():
                    generals_save[fid] = [g.model_dump() if hasattr(g, 'model_dump') else g for g in gens]
                all_legions = _world_state.__dict__.get("_legions", {})
                for fid, legs in all_legions.items():
                    legions_save[fid] = [l.model_dump() if hasattr(l, 'model_dump') else l for l in legs]
            except Exception:
                pass

        save_data = {
            "slot": -1,
            "round": current_round,
            "year": payload.get("year", _world_state.current_year) if payload else (_world_state.current_year if _world_state else 1),
            "month": payload.get("month", _world_state.current_month) if payload else (_world_state.current_month if _world_state else 1),
            "season": payload.get("season", str(_world_state.current_season)) if payload else (str(_world_state.current_season) if _world_state else "spring"),
            "player_faction": player_faction,
            "faction_name": faction_name,
            "territory_count": territory,
            "note": f"自动存档 - 第{current_round}回合",
            "saved_at": datetime.now().isoformat(),
            "world_state": world_dict,
            "snapshots_count": snapshots_count,
            "version": "3.2",
            "_generals": generals_save,
            "_legions": legions_save,
        }
        filename = f"auto_round{current_round}.json"

        # P2: 原子写入 — 先写 .tmp 再 rename，防止崩溃产生损坏文件
        temp_path = SAVE_DIR / (filename + ".tmp")
        final_path = SAVE_DIR / filename
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        # Windows 上需要先删目标再 rename
        if final_path.exists():
            final_path.unlink()
        temp_path.rename(final_path)
        logger.info(f"自动存档: {filename}")

        # 清理旧自动存档（保留最近 N 个）
        keep_count = _game_const.get("save", {}).get("backup_keep_count", 5)
        auto_files = sorted(SAVE_DIR.glob("auto_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        for old in auto_files[keep_count:]:
            try:
                old.unlink()
                logger.info(f"清理旧自动存档: {old.name}")
            except (OSError, PermissionError) as e:
                logger.debug(f"清理旧存档 {old.name} 失败: {e}")
    except Exception as e:
        logger.warning(f"自动存档失败: {type(e).__name__}: {e}")
        # P2: 清理残留临时文件
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


# ============================================================
# API 端点 - 圣旨解析（保留兼容旧版）
# ============================================================

@app.post("/api/edict/parse")
async def parse_edict(request: dict):
    """解析玩家圣旨（旧版兼容）"""
    # P3: 安全获取字符串参数，防御非字符串类型导致崩溃
    edict_text = _safe_get_str(request, "edict_text") or _safe_get_str(request, "text") or _safe_get_str(request, "command")
    faction_id = _safe_get_str(request, "faction_id")

    if not edict_text:
        return ApiResponse.bad_request("圣旨内容不能为空")

    # ---- 安全校验: 清洗文本 + Prompt注入防御 ----
    validator = get_validator()
    ok, cleaned_text, err = validator.validate_edict_text(edict_text)
    if not ok:
        logger.warning(f"[Security] 圣旨解析安全拦截: faction={faction_id} reason={err}")
        return ApiResponse.forbidden(f"圣旨内容触发安全策略: {err}")
    get_ioa_engine().record_session(faction_id)
    edict_text = cleaned_text
    # ---- 安全校验结束 ----

    # 核心规则：指令归属校验 —— 玩家只能向自身势力下发政令
    if _world_state:
        player = _world_state.get_player_faction()
        if player and faction_id and faction_id != player.faction_id:
            return ApiResponse.forbidden(
                f"无权操控其他势力！你只能对己方势力「{player.name}」下达政令"
            )

    if _llm_available:
        try:
            client = _llm_clients.get("advisor")
            if not client:
                return ApiResponse.server_error("AI顾问未配置")
            prompt = (
                f"解析以下圣旨意图并提取关键参数：\n"
                f"圣旨内容：「{edict_text}」\n\n"
                f"请以JSON格式返回：{{\"intent\":\"内政/军事/外交/细作/朝堂\","
                f"\"params\":{{\"action\":\"具体行动\"}},\"confidence\":0.0~1.0}}"
            )
            result = await client.chat_role(
                prompt=prompt,
                system_prompt="你是圣旨解析官，负责解读圣旨意图。",
                temperature=0.5,
            )
            import re as _re
            json_match = _re.search(r'\{[\s\S]*\}', result)
            if json_match:
                parsed = json.loads(json_match.group())
                return ApiResponse.success({
                    "intent": parsed.get("intent", "内政"),
                    "params": parsed.get("params", {}),
                    "confidence": parsed.get("confidence", 0.8),
                    "resource_check": {"valid": True, "warnings": []},
                    "narrative": f"圣旨「{edict_text[:30]}...」已颁行，各司遵办。",
                    "faction_id": faction_id,
                    "ai_parsed": True,
                })
        except Exception as e:
            logger.warning(f"AI圣旨解析失败: {e}")

    # 降级
    return ApiResponse.success({
        "intent": "内政",
        "params": {"action": "general"},
        "confidence": 0.5,
        "resource_check": {"valid": True, "warnings": []},
        "narrative": f"圣旨「{edict_text[:30]}...」已颁行，各司遵办。",
        "faction_id": faction_id,
        "ai_parsed": False,
    })


# ============================================================
# API 端点 - 圣旨执行（AI 推演 · 新核心）
# ============================================================

@app.post("/api/edict/execute")
async def execute_edict(request: dict):
    """
    圣旨执行 - AI 推演核心接口

    玩家用自然语言输入圣旨 → AI 解析为操作指令 → 直接执行到游戏状态

    请求格式:
    {
      "edict_text": "征兵三千，加固应天城防，向陈友谅宣战",
      "faction_id": "ruler_zhuyuan"
    }

    返回:
    {
      "ai_analysis": { "intent_analysis": "", "narrative": "", ... },
      "execution": { "executed": [...], "failed": [...], ... },
      "world_state": { ... },  // 更新后的世界状态
      "tile_changes": [...]     // 本回合地块变更
    }
    """
    global _pending_commands

    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    edict_text = request.get("edict_text", "").strip() or request.get("text", "").strip()
    if not edict_text:
        return ApiResponse.bad_request("圣旨内容不能为空")

    # ---- 安全校验: 圣旨文本清洗 + Prompt注入防御 ----
    validator = get_validator()
    guard = get_agent_guard()
    detector = get_anomaly_detector()
    faction_id = request.get("faction_id", "")
    ok, cleaned_text, err = validator.validate_edict_text(edict_text)
    if not ok:
        logger.warning(f"[Security] 圣旨安全拦截: faction={faction_id} reason={err}")
        return ApiResponse.forbidden(f"圣旨内容触发安全策略: {err}")
    # 记录行为
    guard.record_action(faction_id, "edict", {"edict_text": cleaned_text[:200]})
    detector.comprehensive_check(faction_id, "edict")
    get_ioa_engine().record_session(faction_id)
    # ---- 安全校验结束 ----

    # 核心规则：指令归属校验
    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")

    request_faction_id = request.get("faction_id", "")
    if request_faction_id and request_faction_id != player.faction_id:
        return ApiResponse.forbidden(
            f"无权操控其他势力！你只能对己方势力「{player.name}」下达政令"
        )

    # 构建世界状态字典
    world_dict = _world_state.model_dump()

    # AI 推演
    ai_analysis = {
        "intent_analysis": "",
        "narrative": "",
        "commands": [],
        "invalid_commands": [],
        "summary": "",
        "ai_generated": False,
    }

    if _llm_available:
        try:
            from server.core.edict_engine import call_ai_edict
            advisor_client = _llm_clients.get("advisor")
            if not advisor_client:
                return ApiResponse.server_error("AI顾问未配置")
            
            # 构建圣旨历史上下文（最近10条）
            edict_history = []
            for d in _world_state.decrees[-10:]:
                edict_history.append({
                    "round": d.get("round", 0),
                    "text": d.get("text", ""),
                    "executed": d.get("executed_count", 0),
                    "failed": d.get("failed_count", 0),
                })
            
            ai_analysis = await call_ai_edict(
                edict_text=cleaned_text,
                world_state=world_dict,
                llm_client=advisor_client,
                edict_history=edict_history,
            )
        except Exception as e:
            logger.error(f"AI圣旨推演失败: {e}", exc_info=True)
            ai_analysis["intent_analysis"] = f"AI推演异常: {str(e)[:100]}"
            ai_analysis["summary"] = "AI服务暂时不可用，请稍后重试或使用手动指令"

    # 执行 AI 解析出的指令
    execution = {
        "executed": [],
        "failed": [],
        "total_executed": 0,
        "total_failed": 0,
    }

    if ai_analysis.get("commands") and _round_engine:
        from server.core.edict_engine import execute_edict_commands
        execution = execute_edict_commands(
            commands=ai_analysis["commands"],
            world_state_obj=_world_state,
            round_engine=_round_engine,
        )

        # 写入圣旨到治理日志
        _world_state.decrees.append({
            "id": f"decree_{_world_state.current_round}_{len(_world_state.decrees)}",
            "round": _world_state.current_round,
            "year": _world_state.current_year,
            "month": _world_state.current_month,
            "faction_id": player.faction_id,
            "text": cleaned_text,
            "ai_narrative": ai_analysis.get("narrative", ""),
            "commands_count": len(ai_analysis.get("commands", [])),
            "executed_count": execution["total_executed"],
            "failed_count": execution["total_failed"],
            "timestamp": _world_state.updated_at or "",
        })

        _world_state.governance_logs.append({
            "round": _world_state.current_round,
            "title": "颁布圣旨",
            "description": cleaned_text,
            "narrative": ai_analysis.get("narrative", f"圣旨「{edict_text[:50]}」已颁行"),
            "commands_executed": execution["total_executed"],
            "commands_failed": execution["total_failed"],
        })

        # 记录事件
        _world_state.events_log.append({
            "event_id": f"edict_{_world_state.current_round}_{len(_world_state.events_log)}",
            "event_type": "edict",
            "severity": "major",
            "round": _world_state.current_round,
            "title": "圣旨颁行",
            "description": ai_analysis.get("narrative", edict_text[:100]),
            "faction_id": player.faction_id,
            "tile_id": "",
            "effects": {
                "commands_executed": execution["total_executed"],
                "commands_failed": execution["total_failed"],
            },
            "narrative": ai_analysis.get("narrative", ""),
        })

        _world_state.mark_updated()

        # ---- 3.1: 记录圣旨上下文（多轮对话连贯性） ----
        try:
            from server.core.edict_nlp import get_edict_context
            ctx = get_edict_context()
            executed_actions = [
                e.get("action", "") for e in execution.get("executed", [])
            ]
            ctx.record_edict(
                text=cleaned_text,
                actions=executed_actions,
                intent=ai_analysis.get("intent_analysis", ""),
                summary=ai_analysis.get("summary", ""),
            )
        except Exception:
            pass

    # ============================================================
    # 全局推演：圣旨颁布后，推演天下各势力的反应
    # ============================================================
    global_deduction = {
        "global_narrative": "",
        "faction_reactions": [],
        "diplomatic_shifts": [],
        "event_triggers": [],
        "economic_ripples": "",
        "strategic_advice": "",
        "summary": "",
    }

    if _llm_available and execution["total_executed"] > 0:
        try:
            from server.core.global_deduction import run_global_deduction
            advisor_client = _llm_clients.get("advisor")
            if advisor_client:
                global_deduction = await run_global_deduction(
                    edict_text=edict_text,
                    ai_analysis=ai_analysis,
                    execution=execution,
                    world_state_obj=_world_state,
                    llm_client=advisor_client,
                )
                logger.info(f"全局推演完成: {global_deduction.get('summary', '')}")
        except Exception as e:
            logger.error(f"全局推演失败: {e}", exc_info=True)
            global_deduction["summary"] = f"全局推演异常: {str(e)[:50]}"

    # 构建返回数据
    updated_world = _world_state.model_dump()
    tile_changes = [
        c for c in _world_state.tile_changes
        if c.get("round") == _world_state.current_round
    ]

    # 3.1: 获取操作锁状态
    op_lock = get_round_lock()
    locked_actions = op_lock.get_faction_locked_actions(player.faction_id) if player else []
    cooling_tiles = {}
    if player:
        for t in _world_state.get_faction_tiles(player.faction_id):
            cooling = op_lock.get_tile_cooling_actions(t.tile_id)
            if cooling:
                cooling_tiles[t.tile_id] = cooling

    return ApiResponse.success({
        "edict_text": edict_text,
        "ai_analysis": {
            "intent_analysis": ai_analysis.get("intent_analysis", ""),
            "narrative": ai_analysis.get("narrative", ""),
            "edict_language": ai_analysis.get("edict_language", f"奉天承运皇帝，诏曰：{edict_text}钦此。"),
            "summary": ai_analysis.get("summary", ""),
            "commands_count": len(ai_analysis.get("commands", [])),
            "invalid_count": len(ai_analysis.get("invalid_commands", [])),
            "ai_generated": ai_analysis.get("ai_generated", False),
        },
        "execution": execution,
        "global_deduction": global_deduction,
        "world_state": updated_world,
        "tile_changes": tile_changes,
        "locked_actions": locked_actions,
        "cooling_tiles": cooling_tiles,
    }, ai_analysis.get("narrative", f"圣旨「{edict_text[:30]}...」已颁行"))


# ============================================================
# API 端点 - 统一圣旨自然语言处理（3.2 重构版）
# ============================================================

@app.post("/api/edict/nl-process")
async def nl_process_edict(request: dict):
    """
    统一圣旨自然语言处理管道（3.2 重构版）。

    单次调用完成：意图识别 → 实体提取 → 前置校验 → AI解析 → 指令拆解 → 执行/入队。

    支持的输入形式：
    - 白话文：「在应天征兵三千，然后派兵攻打张士诚的高邮」
    - 文言口语：「着应天府募兵三千，加固城防」
    - 长篇战略：「先征兵固守应天，次与方国珍结盟，待秋收出师北伐陈友谅，同时发展内政储备粮草」
    - 批量圣旨：「征兵三千；与陈友谅宣战；大赦天下」
    - 撤回指令：「撤回前旨」「作废征讨陈友谅的命令」

    请求格式:
    {
      "edict_text": "自然语言圣旨文本",
      "faction_id": "ruler_zhuyuan",
      "direct_execute": true,    // 是否直接执行（false=仅解析不入队）
      "use_ai": true             // 是否使用AI解析
    }
    """
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    edict_text = (request.get("edict_text", "") or request.get("text", "")).strip()
    if not edict_text:
        return ApiResponse.bad_request("圣旨内容不能为空")

    # 安全校验
    validator = get_validator()
    guard = get_agent_guard()
    faction_id = request.get("faction_id", "")
    ok, cleaned_text, err = validator.validate_edict_text(edict_text)
    if not ok:
        return ApiResponse.forbidden(f"圣旨内容触发安全策略: {err}")
    guard.record_action(faction_id, "nl_edict", {"edict_text": cleaned_text[:200]})

    # 归属校验
    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")
    if faction_id and faction_id != player.faction_id:
        return ApiResponse.forbidden(f"无权操控其他势力")

    direct_execute = request.get("direct_execute", True)
    use_ai = request.get("use_ai", _llm_available)

    # 构建世界状态字典
    world_dict = _world_state.model_dump()
    world_dict["player_faction_id"] = player.faction_id

    # 获取 edict 历史
    edict_history = []
    for d in _world_state.decrees[-10:]:
        edict_history.append({
            "round": d.get("round", 0),
            "text": d.get("text", ""),
            "executed": d.get("executed_count", 0),
            "failed": d.get("failed_count", 0),
        })

    # 获取 LLM 客户端
    llm_client = _llm_clients.get("advisor") if use_ai else None

    from server.core.unified_edict_engine import (
        process_unified_edict, split_multi_edict, batch_process_edicts,
    )

    # 检测是否为批量/长篇
    sub_texts = split_multi_edict(cleaned_text)

    if len(sub_texts) > 1 and direct_execute:
        # 批量处理
        result = await batch_process_edicts(
            texts=sub_texts,
            world_state=world_dict,
            world_state_obj=_world_state if direct_execute else None,
            round_engine=_round_engine if direct_execute else None,
            llm_client=llm_client,
            pending_commands=_pending_commands,
            use_ai=use_ai,
        )
    else:
        # 单条处理
        result = await process_unified_edict(
            edict_text=cleaned_text,
            world_state=world_dict,
            world_state_obj=_world_state if direct_execute else None,
            round_engine=_round_engine if direct_execute else None,
            llm_client=llm_client,
            pending_commands=_pending_commands,
            edict_history=edict_history,
            use_ai=use_ai,
        )

    # 写入治理日志
    if result.get("commands") and direct_execute:
        _world_state.decrees.append({
            "id": f"decree_{_world_state.current_round}_{len(_world_state.decrees)}",
            "round": _world_state.current_round,
            "year": _world_state.current_year,
            "month": _world_state.current_month,
            "faction_id": player.faction_id,
            "text": cleaned_text,
            "ai_narrative": result.get("ai_analysis", {}).get("narrative", ""),
            "commands_count": len(result.get("commands", [])),
            "executed_count": result.get("execution", {}).get("total_executed", 0),
            "failed_count": result.get("execution", {}).get("total_failed", 0),
            "timestamp": _world_state.updated_at or "",
        })

        _world_state.governance_logs.append({
            "round": _world_state.current_round,
            "title": "颁布圣旨（NL）",
            "description": cleaned_text,
            "narrative": result.get("ai_analysis", {}).get("narrative", f"圣旨已颁行"),
            "commands_executed": result.get("execution", {}).get("total_executed", 0),
            "commands_failed": result.get("execution", {}).get("total_failed", 0),
        })

        _world_state.mark_updated()

        # 记录圣旨上下文
        try:
            from server.core.edict_nlp import get_edict_context
            ctx = get_edict_context()
            executed_actions = [
                e.get("action", "") for e in result.get("execution", {}).get("executed", [])
            ]
            ctx.record_edict(
                text=cleaned_text,
                actions=executed_actions,
                intent=result.get("ai_analysis", {}).get("intent_analysis", ""),
                summary=result.get("ai_analysis", {}).get("summary", ""),
            )
        except Exception:
            pass

    # 未直接执行的指令入队
    if not direct_execute and result.get("commands"):
        for cmd in result["commands"]:
            _pending_commands.append(cmd)

    return ApiResponse.success({
        "edict_text": cleaned_text,
        "classification": result.get("classification", {}),
        "entities": result.get("entities", {}),
        "validation": result.get("validation", []),
        "commands": result.get("commands", []),
        "commands_count": len(result.get("commands", [])),
        "decomposed_steps": result.get("decomposed_steps", []),
        "ai_analysis": result.get("ai_analysis", {}),
        "execution": result.get("execution", {}),
        "edict_language": result.get("edict_language", ""),
        "error_prompt": result.get("error_prompt", ""),
        "missing_info": result.get("missing_info", {}),
        "summary": result.get("summary", ""),
        "is_cancel": result.get("is_cancel", False),
        "needs_clarification": result.get("needs_clarification", False),
        "route_to_advisor": result.get("route_to_advisor", False),
        "pending_count": len(_pending_commands),
    }, result.get("ai_analysis", {}).get("narrative", "圣旨已颁行"))


@app.post("/api/edict/nl-validate")
async def nl_validate_edict(request: dict):
    """
    仅校验圣旨（不解执行，不入队）。

    用于输入过程中的实时校验和提示。
    """
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    edict_text = (request.get("edict_text", "") or request.get("text", "")).strip()
    if not edict_text:
        return ApiResponse.bad_request("圣旨内容不能为空")

    world_dict = _world_state.model_dump()
    player = _world_state.get_player_faction()
    if player:
        world_dict["player_faction_id"] = player.faction_id

    from server.core.unified_edict_engine import (
        process_unified_edict, classify_edict_intent, extract_edict_entities,
        EdictValidator, EdictResponseFormatter, EdictIntentCategory,
    )

    entity = extract_edict_entities(edict_text, world_dict)
    classification = classify_edict_intent(edict_text, entity)

    # 撤回检测
    if classification["primary"] == EdictIntentCategory.CANCEL:
        primary_val = classification["primary"].value if hasattr(classification["primary"], 'value') else str(classification["primary"])
        return ApiResponse.success({
            "edict_text": edict_text,
            "is_cancel": True,
            "classification": {
                "primary": primary_val,
                "confidence": classification.get("confidence", 0.5),
            },
            "summary": "此旨将撤回前令，确认后即刻施行。",
        })

    # 信息缺失检测
    missing = {}
    sub_intents = classification.get("sub_intents", [])
    from server.core.unified_edict_engine import EdictSubIntent

    if EdictSubIntent.MARCH in sub_intents and not entity.tile_ids:
        missing["to_tile"] = True
    if EdictSubIntent.WAR in sub_intents and not entity.faction_ids:
        missing["target_faction"] = True
    tile_actions = [EdictSubIntent.RECRUIT, EdictSubIntent.FARM, EdictSubIntent.FORTIFY,
                    EdictSubIntent.RELIEF, EdictSubIntent.BUILD, EdictSubIntent.DEVELOP]
    if any(si in sub_intents for si in tile_actions) and not entity.tile_ids:
        missing["tile_id"] = True

    error_prompt = ""
    needs_clarification = False
    if missing:
        needs_clarification = True
        error_prompt = EdictResponseFormatter.format_missing_info(missing)

    return ApiResponse.success({
        "edict_text": edict_text,
        "classification": {
            "primary": classification["primary"].value if hasattr(classification["primary"], 'value') else str(classification["primary"]),
            "sub_intents": [si.value for si in sub_intents],
            "confidence": classification["confidence"],
        },
        "entities": {
            "faction_ids": entity.faction_ids,
            "tile_ids": entity.tile_ids,
            "numbers": entity.numbers,
        },
        "missing_info": missing,
        "error_prompt": error_prompt,
        "needs_clarification": needs_clarification,
    })


@app.post("/api/edict/nl-cancel")
async def nl_cancel_commands(request: dict):
    """撤回/清空指定指令"""
    global _pending_commands

    cancel_all = request.get("cancel_all", False)
    cancel_ids = request.get("command_ids", [])
    cancel_text = request.get("cancel_text", "")

    if cancel_all:
        count = len(_pending_commands)
        _pending_commands = []
        return ApiResponse.success(None, f"已撤回全部 {count} 条待办指令，钦此。")

    if cancel_text:
        # 模糊匹配撤回
        removed = []
        kept = []
        for cmd in _pending_commands:
            label = cmd.get("label", "") + str(cmd.get("params", {}))
            if any(kw in label for kw in cancel_text.split()):
                removed.append(cmd)
            else:
                kept.append(cmd)
        _pending_commands = kept
        return ApiResponse.success({
            "removed_count": len(removed),
            "remaining_count": len(kept),
        }, f"已撤回 {len(removed)} 条相关指令")

    if cancel_ids:
        removed = []
        kept = []
        for i, cmd in enumerate(_pending_commands):
            if str(i) in cancel_ids or cmd.get("id") in cancel_ids:
                removed.append(cmd)
            else:
                kept.append(cmd)
        _pending_commands = kept
        return ApiResponse.success({
            "removed_count": len(removed),
            "remaining_count": len(kept),
        }, f"已撤回 {len(removed)} 条指令")

    return ApiResponse.bad_request("请指定要撤回的指令")


@app.get("/api/edict/nl-config")
async def get_edict_llm_config():
    """获取圣旨解析专用LLM配置"""
    try:
        from server.infra.llm_client.config import LLMRuntimeConfig
        rt = LLMRuntimeConfig.from_env()
        edict_cfg = {
            "api_base": rt.edict.api_base if hasattr(rt, 'edict') else rt.advisor.api_base,
            "model_name": rt.edict.model_name if hasattr(rt, 'edict') else rt.advisor.model_name,
            "temperature": rt.edict.temperature if hasattr(rt, 'edict') else rt.advisor.temperature,
            "max_tokens": rt.edict.max_tokens if hasattr(rt, 'edict') else rt.advisor.max_tokens,
            "available": _llm_available,
        }
        return ApiResponse.success(edict_cfg)
    except Exception as e:
        return ApiResponse.success({"available": False, "error": str(e)})


@app.post("/api/edict/nl-config")
async def update_edict_llm_config(request: dict):
    """热更新圣旨解析专用LLM配置（即时生效，无需重启）"""
    try:
        config_path = CONFIG_DIR / "llm_runtime.json"
        existing = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        existing["edict"] = {
            "api_base": request.get("api_base", existing.get("edict", {}).get("api_base", "")),
            "model_name": request.get("model_name", existing.get("edict", {}).get("model_name", "")),
            "temperature": request.get("temperature", existing.get("edict", {}).get("temperature", 0.4)),
            "max_tokens": request.get("max_tokens", existing.get("edict", {}).get("max_tokens", 4096)),
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        # 热重载
        from server.infra.llm_client.config import LLMRuntimeConfig
        LLMRuntimeConfig.reload()

        global _llm_clients, _llm_available
        try:
            from server.infra.llm_client.hunyuan_client import get_global_clients
            _llm_clients = await get_global_clients()
            runtime = LLMRuntimeConfig.from_env()
            _llm_available = bool(runtime.advisor.api_key or runtime.edict.api_key
                                  if hasattr(runtime, 'edict') else runtime.advisor.api_key)
        except Exception:
            pass

        return ApiResponse.success(existing["edict"], "圣旨解析模型配置已热更新，即时生效。")
    except Exception as e:
        return ApiResponse.server_error(f"配置更新失败: {str(e)}")


# ============================================================
# API 端点 - AI 决策/朝堂/战斗/外交/灾害/战略（链路4）
# ============================================================

@app.post("/api/faction/ai-decision")
async def faction_ai_decision(request: dict):
    """NPC势力AI决策（路由到A2群雄殿）"""
    faction_id = request.get("faction_id", "")

    # ---- 安全校验: AOI决策参数 + NPC行为风控 ----
    guard = get_agent_guard()
    detector = get_anomaly_detector()
    validator = get_validator()
    ok, err, clean = validator.validate_ai_decision_params(request)
    if not ok:
        logger.warning(f"[Security] AI决策参数校验失败: faction={faction_id} err={err}")
    # 记录行为
    guard.record_action(faction_id, "ai_decision", {"request": str(request)[:200]})
    detector.record_behavior(faction_id, "ai_decision")
    # ---- 安全校验结束 ----

    if _llm_available:
        try:
            orch = _get_orchestrator()
            result = await orch.agent_chat(
                faction_id=faction_id,
                user_message="请制定本回合战略决策。",
                chat_mode="ruler",
                world_state=request,
                clients=_llm_clients,
            )

            # ---- NPC决策结果安全校验 ----
            decision_ok, decision_reason, decision_risk = guard.validate_npc_decision(
                faction_id, request.get("faction_name", faction_id), {"result": result[:500]}
            )
            if not decision_ok and decision_risk >= 60:
                logger.warning(f"[Security] NPC决策拦截: faction={faction_id} risk={decision_risk:.0f} reason={decision_reason}")
                return ApiResponse.success({
                    "faction_id": faction_id,
                    "decisions": [],
                    "narrative": "该势力本回合决策被安全策略拦截。",
                    "ai_generated": False,
                    "security_blocked": True,
                })
            get_ioa_engine().record_ai_call("advisor", 0, True)
            # ---- NPC决策校验结束 ----

            return ApiResponse.success({
                "faction_id": faction_id,
                "decisions": [{"type": "ai_auto", "summary": result[:300]}],
                "narrative": result[:500],
                "ai_generated": True,
                "agent": "A2_warlord",
            })
        except Exception as e:
            logger.warning(f"AI决策失败: {e}")
    return ApiResponse.success({
        "faction_id": faction_id,
        "decisions": [],
        "narrative": "该势力本回合按兵不动。",
        "ai_generated": False,
    })


@app.post("/api/court/monthly-settlement")
async def court_monthly_settlement(request: dict):
    """朝堂派系月度结算（路由到A1廷议辩论）"""
    if _llm_available:
        try:
            orch = _get_orchestrator()
            result = await orch.a1_court_debate(
                faction_id=request.get("faction_id", ""),
                topic="朝堂派系月度结算，汇报各派系动向。",
                world_state=request,
                clients=_llm_clients,
            )
            return ApiResponse.success({
                "faction_id": request.get("faction_id", ""),
                "stability_change": 0,
                "faction_changes": {},
                "events": [{"narrative": result.get("debate_result", "")[:300]}],
                "ai_generated": True,
                "agent": "A1_advisor",
            })
        except Exception as e:
            logger.warning(f"AI朝堂结算失败: {e}")
    return ApiResponse.success({
        "faction_id": request.get("faction_id", ""),
        "stability_change": 0,
        "faction_changes": {},
        "events": [],
        "ai_generated": False,
    })


@app.post("/api/court/conflict")
async def court_conflict(request: dict):
    """朝堂冲突事件（路由到A1廷议辩论）"""
    if _llm_available:
        try:
            orch = _get_orchestrator()
            event_type = request.get("event_type", "冲突")
            result = await orch.a1_court_debate(
                faction_id=request.get("faction_id", ""),
                topic=f"朝堂发生{event_type}事件，请模拟廷议辩论。",
                world_state=request,
                clients=_llm_clients,
            )
            return ApiResponse.success({
                "event_type": event_type,
                "narrative": result.get("debate_result", "")[:500],
                "effects": {},
                "ai_generated": True,
                "agent": "A1_advisor",
            })
        except Exception as e:
            logger.warning(f"AI朝堂冲突失败: {e}")
    return ApiResponse.success({
        "event_type": request.get("event_type", ""),
        "narrative": "朝堂之上，一片肃然。",
        "effects": {},
        "ai_generated": False,
    })


@app.post("/api/battle/resolve")
async def resolve_battle(request: dict):
    """
    [已废弃 v3.2] 战斗结算 — 请使用 /api/march/resolve 行军结算
    本端点保留仅用于向后兼容，前端组件中已无调用。
    """
    # P1修复: 类型安全校验 — 前端可能传入 dict/str 等非预期类型导致 TypeError
    attacker_troops = request.get('attacker_troops', 0)
    defender_troops = request.get('defender_troops', 0)
    # 强制转为 int，安全处理各种异常类型
    try:
        attacker_troops = int(attacker_troops) if not isinstance(attacker_troops, (dict, list)) else 0
    except (TypeError, ValueError):
        attacker_troops = 0
    try:
        defender_troops = int(defender_troops) if not isinstance(defender_troops, (dict, list)) else 0
    except (TypeError, ValueError):
        defender_troops = 0
    # 兵力合法性校验
    if attacker_troops < 1 and defender_troops < 1:
        return ApiResponse.error(400, "攻守双方至少需要一处有兵力")
    attacker_troops = max(attacker_troops, 0)
    defender_troops = max(defender_troops, 0)
    terrain = str(request.get('terrain', '平原'))
    is_siege = bool(request.get('is_siege', False))
    
    # 数值结算（使用 MarchEngine 的逻辑）
    terrain_factor = 1.0
    if terrain in ('山地', '丘陵'): terrain_factor = 1.3
    elif terrain == '森林': terrain_factor = 1.15
    elif terrain == '河流': terrain_factor = 0.85
    
    siege_factor = 1.5 if is_siege else 1.0
    defender_advantage = terrain_factor * siege_factor
    
    # 随机波动 0.7~1.3
    import random
    luck = random.uniform(0.7, 1.3)
    
    attacker_power = attacker_troops * luck
    defender_power = defender_troops * defender_advantage * random.uniform(0.8, 1.2)
    
    if attacker_power > defender_power:
        ratio = defender_power / max(attacker_power, 1)
        a_loss = int(attacker_troops * (0.1 + 0.3 * (1 - ratio)))
        d_loss = int(defender_troops * (0.3 + 0.4 * (1 - ratio)))
        result = "victory"
    elif attacker_power * 1.2 > defender_power:
        a_loss = int(attacker_troops * (0.2 + random.uniform(0, 0.2)))
        d_loss = int(defender_troops * (0.15 + random.uniform(0, 0.2)))
        result = "stalemate"
    else:
        ratio = attacker_power / max(defender_power, 1)
        a_loss = int(attacker_troops * (0.3 + 0.4 * (1 - ratio)))
        d_loss = int(defender_troops * (0.1 + 0.3 * (1 - ratio)))
        result = "defeat"
    
    a_loss = min(a_loss, attacker_troops - 1) if attacker_troops > 1 else a_loss
    d_loss = min(d_loss, defender_troops - 1) if defender_troops > 1 else d_loss
    # P2: 确保损失数非负且不超过兵力
    a_loss = max(0, min(a_loss, attacker_troops))
    d_loss = max(0, min(d_loss, defender_troops))
    
    narrative = ""
    ai_generated = False
    if _llm_available:
        try:
            client = _llm_clients.get("enemy")
            if client:
                prompt = (
                    f"战斗结算：{request.get('attacker_faction','?')} 攻 {request.get('defender_faction','?')}\n"
                    f"攻方兵力：{attacker_troops}，损失：{a_loss} | 守方兵力：{defender_troops}，损失：{d_loss}\n"
                    f"地形：{terrain} | 是否攻城：{is_siege} | 结果：{result}\n"
                    f"请以古文（军中司马口吻）记录此战。"
                )
                narrative = await client.chat_fast(
                    prompt=prompt,
                    system_prompt="你是军中司马，负责记录战况与伤亡。",
                    temperature=0.7,
                )
                ai_generated = True
        except Exception as e:
            logger.warning(f"AI战斗叙事生成失败: {e}")
    
    return ApiResponse.success({
        "result": result,
        "attacker_losses": a_loss,
        "defender_losses": d_loss,
        "attacker_remaining": max(0, attacker_troops - a_loss),
        "defender_remaining": max(0, defender_troops - d_loss),
        "narrative": narrative[:500] if narrative else f"攻方损失{a_loss}人，守方损失{d_loss}人。",
        "ai_generated": ai_generated,
    })


@app.post("/api/diplomacy/action")
async def diplomacy_action(request: dict):
    """外交行动（增强版：AI 判断 + 数值落地）
    
    对于结盟/停战/联姻/通商/附庸等需要对方同意的外交行动，
    通过 AI 判断目标势力的接受意愿，然后自动执行。
    宣战/纳贡/取消附庸/关闭贸易等单方面行动直接执行。
    """
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    faction_a, faction_b = _get_diplo_parties(request)
    if not faction_a or not faction_b:
        return ApiResponse.bad_request("请指定外交双方势力（faction_a/faction_id 和 faction_b/target_faction）")
    action = request.get("action_type") or request.get("action", "外交")

    # 单方面行动：直接执行，无需 AI 判断
    unilateral_actions = {"war", "declare_war", "tribute", "vassal_cancel", "trade_close", "cancel_vassal"}
    if action in unilateral_actions:
        return await _execute_diplomacy_action(faction_a, faction_b, action)

    # 需要对方同意的行动：通过 AI 判断
    if _llm_available and _world_state:
        try:
            orch = _get_orchestrator()
            # 构建详细的 AI 判定 prompt
            target_faction = _world_state.get_faction(faction_b) if _world_state else None
            source_faction = _world_state.get_faction(faction_a) if _world_state else None

            key = _world_state.relation_key(faction_a, faction_b)
            rel = _world_state.relations.get(key) if _world_state else None

            action_labels = {
                "alliance": "结盟", "truce": "停战", "trade": "通商",
                "marriage": "联姻", "vassal_offer": "提议附庸",
            }
            action_label = action_labels.get(action, action)

            ai_prompt = (
                f"【外交判定】{source_faction.name if source_faction else faction_a}"
                f"向{target_faction.name if target_faction else faction_b}提出「{action_label}」。\n"
                f"当前关系：{rel.stance.value if rel else 'neutral'}，"
                f"好感度：{rel.attitude if rel else 0}/100\n"
                f"请以目标势力君主的口吻判断是否接受此提议。\n"
                f"输出格式：第一行写 ACCEPT 或 REJECT，第二行写理由（古文风格，20字以内）。"
            )

            ai_result = await orch.a1_strategic_advice(
                faction_id=faction_b,
                question=ai_prompt,
                world_state=_world_state.model_dump() if hasattr(_world_state, 'model_dump') else {},
                clients=_llm_clients,
            )
            ai_response = ai_result.get("response", "") if ai_result else ""

            # 解析 AI 判定
            accepted = ai_response.strip().upper().startswith("ACCEPT") if ai_response else None
            ai_reason = ai_response.replace("ACCEPT", "").replace("REJECT", "").strip()[:100] if ai_response else ""

            # 如果 AI 不可用或解析失败，用数值规则兜底
            if accepted is None:
                attitude = rel.attitude if rel else 0
                stance = rel.stance.value if rel else "neutral"
                accepted = _rule_based_diplomacy_accept(action, attitude, stance)

            if not accepted:
                return ApiResponse.success({
                    "success": False,
                    "status": "rejected",
                    "action": action,
                    "message": ai_reason or f"「{target_faction.name if target_faction else faction_b}」拒绝了{action_label}提议",
                    "ai_generated": bool(ai_response),
                    "agent": "A1_advisor",
                })

            # AI 接受了，执行外交操作
            result = await _execute_diplomacy_action(faction_a, faction_b, action)
            result["ai_reason"] = ai_reason
            result["ai_generated"] = bool(ai_response)
            return ApiResponse.success(result)

        except Exception as e:
            logger.warning(f"AI外交判定失败: {e}，降级为数值判定")
            # 降级：数值规则判定
            if _world_state:
                key = _world_state.relation_key(faction_a, faction_b)
                rel = _world_state.relations.get(key)
                attitude = rel.attitude if rel else 0
                stance = rel.stance.value if rel else "neutral"
                accepted = _rule_based_diplomacy_accept(action, attitude, stance)
                if not accepted:
                    return ApiResponse.success({
                        "success": False, "status": "rejected", "action": action,
                        "message": f"对方拒绝了{action}提议（好感度不足）",
                        "ai_generated": False,
                    })

    # 无 AI 时直接执行
    result = await _execute_diplomacy_action(faction_a, faction_b, action)
    return ApiResponse.success(result)


def _rule_based_diplomacy_accept(action: str, attitude: int, stance: str) -> bool:
    """数值规则：判断外交提议是否被接受（AI 不可用时的兜底逻辑）"""
    import random
    # 基础接受概率 = 好感度/100
    base_chance = max(0, min(1.0, attitude / 100.0))

    # 各行动修正
    modifiers = {
        "alliance": 0.8,      # 结盟需要较高好感
        "truce": 1.2,         # 停战较容易接受
        "trade": 1.1,         # 通商容易接受
        "marriage": 0.7,      # 联姻需要较高好感
        "vassal_offer": 0.4,  # 附庸很难接受
    }
    modifier = modifiers.get(action, 1.0)

    # 当前关系修正
    stance_bonus = {
        "alliance": 0.3, "neutral": 0.0, "truce": 0.1, "vassal": 0.5, "war": -0.5,
    }
    bonus = stance_bonus.get(stance, 0.0)

    chance = min(0.95, base_chance * modifier + bonus)
    return random.random() < chance


async def _execute_diplomacy_action(faction_a: str, faction_b: str, action: str) -> dict:
    """执行外交操作（数值落地）"""
    if not _world_state:
        return {"success": False, "message": "请先开局"}

    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)

    action_map = {
        "war": ("change_stance", [faction_a, faction_b, "war", "主动宣战"]),
        "declare_war": ("change_stance", [faction_a, faction_b, "war", "主动宣战"]),
        "alliance": ("change_stance", [faction_a, faction_b, "alliance", "缔结同盟"]),
        "truce": ("change_stance", [faction_a, faction_b, "truce", "签订停战"]),
        "trade": ("open_trade", [faction_a, faction_b]),
        "marriage": ("propose_marriage", [faction_a, faction_b]),
        "vassal_offer": ("offer_vassal", [faction_a, faction_b]),
        "vassal_cancel": ("cancel_vassal", [faction_a, faction_b]),
        "cancel_vassal": ("cancel_vassal", [faction_a, faction_b]),
        "trade_close": ("close_trade", [faction_a, faction_b]),
        "tribute": ("_tribute", [faction_a, faction_b]),
    }

    mapping = action_map.get(action)
    if not mapping:
        return {"success": False, "message": f"未知外交行动: {action}"}

    method_name, args = mapping

    if method_name == "_tribute":
        # 纳贡：扣钱 + 好感
        faction = _world_state.get_faction(faction_a)
        if not faction:
            return {"success": False, "message": "势力不存在"}
        if faction.treasury < 500:
            return {"success": False, "message": "银两不足（需要500）"}
        faction.treasury -= 500
        key = _world_state.relation_key(faction_a, faction_b)
        rel = _world_state.relations.get(key)
        if rel:
            rel.attitude = min(100, rel.attitude + 10)
        return {"success": True, "message": f"向{faction_b}纳贡500银两，好感+10"}

    method = getattr(engine, method_name, None)
    if not method:
        return {"success": False, "message": f"引擎方法不存在: {method_name}"}

    result = method(*args)
    return result


@app.post("/api/disaster/forecast")
async def disaster_forecast(request: dict):
    """灾害预判"""
    if _llm_available:
        try:
            client = _llm_clients.get("enemy")
            if not client:
                return ApiResponse.server_error("AI决策引擎未配置")
            season = request.get("season", "春")
            di = request.get("disaster_index", 0)
            prompt = f"当前季节：{season}，灾厄指数：{di}。\n判定是否发生天灾/瘟疫/祥瑞，以钦天监口吻描述。"
            result = await client.chat_fast(
                prompt=prompt,
                system_prompt="你是钦天监，观测天象灾异，以古文描述。",
                temperature=0.7,
            )
            return ApiResponse.success({
                "faction_id": request.get("faction_id", ""),
                "disaster_index": di,
                "forecast": result[:300],
                "risks": [],
                "ai_generated": True,
            })
        except Exception as e:
            logger.warning(f"AI灾害预判失败: {e}")
    return ApiResponse.success({
        "faction_id": request.get("faction_id", ""),
        "disaster_index": 0,
        "forecast": "近期无重大灾荒之兆。",
        "risks": [],
        "ai_generated": False,
    })


@app.post("/api/strategy/analyze")
async def strategy_analyze(request: dict):
    """AI战略推演分析"""
    faction_id = request.get("faction_id", "")
    if _llm_available:
        try:
            client = _llm_clients.get("law")
            if not client:
                return ApiResponse.server_error("AI战略分析未配置")
            world_json = json.dumps(request, ensure_ascii=False, indent=2)
            prompt = (
                f"请对 {faction_id} 进行全局战略分析：\n"
                f"1. 当前威胁评估\n2. 战略机遇识别\n3. 具体行动建议\n"
                f"请以军师/谋士口吻输出，文言白话皆可。"
            )
            result = await client.chat_strategy(
                prompt=prompt,
                world_json=world_json,
                system_prompt="你是当世第一谋士，精通天下大势与兵法国策。",
                temperature=0.6,
            )
            # 从 AI 返回文本中解析结构化字段
            threats, opportunities, recommendations = _parse_strategy_result(result)
            return ApiResponse.success({
                "faction_id": faction_id,
                "threats": threats,
                "opportunities": opportunities,
                "recommendations": recommendations,
                "narrative": result[:1000],
                "ai_generated": True,
            })
        except Exception as e:
            logger.warning(f"AI战略分析失败: {e}")
    return ApiResponse.success({
        "faction_id": faction_id,
        "threats": [],
        "opportunities": [],
        "recommendations": [],
        "narrative": "暂无战略分析。",
        "ai_generated": False,
    })


# ============================================================
# 全局调度器（延迟初始化）
# ============================================================

_orchestrator = None
_orchestrator_init_lock = asyncio.Lock()  # 防止延迟初始化的竞态条件


async def _get_orchestrator_async():
    """异步安全的延迟初始化 orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        async with _orchestrator_init_lock:
            if _orchestrator is None:  # 双重检查
                from server.agent.orchestrator import get_orchestrator
                _orchestrator = get_orchestrator()
    return _orchestrator


def _mask_world_state_for_player(world_dict: dict) -> dict:
    """对 world_state 中的 factions 进行情报脱敏处理

    P3修复：添加异常保护，脱敏失败时返回原始数据（降级但不中断流程）
    3.2修复：player_faction_id 为空时不脱敏（尚未选择势力），已选势力时对己方完全可见
    """
    if not _world_state:
        return world_dict
    player_fid = _world_state.player_faction_id
    if not player_fid:
        # 尚未选择势力，不脱敏
        return world_dict

    try:
        masked_factions = _world_state.mask_factions_for_player(player_fid)
        result = dict(world_dict)
        result["factions"] = masked_factions
        return result
    except Exception as e:
        logger.error(f"势力情报脱敏失败（降级返回原始数据）: {type(e).__name__}: {e}")
        return world_dict


def _get_orchestrator():
    """同步获取 orchestrator（首次调用时延迟初始化，非线程安全但FastAPI单线程足够）"""
    global _orchestrator
    if _orchestrator is None:
        from server.agent.orchestrator import get_orchestrator
        _orchestrator = get_orchestrator()
    return _orchestrator


# ============================================================
# API 端点 - AI 智能体对话（八大智能体架构）
# ============================================================

@app.post("/api/agent/chat")
async def agent_chat_endpoint(request: dict):
    """Agent自由对话 - 根据 chat_mode 路由到 A1/A3"""
    if not _llm_available:
        return ApiResponse.error(503, "AI服务不可用，请配置API Key")

    faction_id = request.get("faction_id", "")
    message = request.get("message", "")
    chat_mode = request.get("chat_mode", "ruler")

    try:
        orch = _get_orchestrator()
        response = await orch.agent_chat(
            faction_id=faction_id,
            user_message=message,
            chat_mode=chat_mode,
            world_state=request.get("world_state"),
            clients=_llm_clients,
        )
        return ApiResponse.success({
            "faction_id": faction_id,
            "chat_mode": chat_mode,
            "response": response,
        })
    except Exception as e:
        logger.error(f"Agent对话失败: {e}")
        return ApiResponse.server_error(f"对话失败: {str(e)}")


@app.post("/api/agent/strategic-advice")
async def strategic_advice(request: dict):
    """A1 谋策阁 - 谋臣AI策略建议（支持指定NPC对话）
    
    通用模式（npc_id 为空）：首席谋臣使用专业战略模板分析天下大势
    NPC模式（npc_id 指定）：与具体历史文臣进行个性化对话
    """
    if not _llm_available:
        return ApiResponse.error(503, "AI服务不可用")

    npc_id = request.get("npc_id", "")
    try:
        orch = _get_orchestrator()
        result = await orch.a1_strategic_advice(
            faction_id=request.get("faction_id", ""),
            question=request.get("question", "请分析当前天下大势"),
            world_state=request.get("world_state", {}),
            clients=_llm_clients,
            npc_id=npc_id,
            conversation_history=request.get("conversation_history"),
        )
        return ApiResponse.success({
            "advisor": result.get("npc_name") or result.get("advisor", "首席谋臣"),
            "npc_id": result.get("npc_id", ""),
            "npc_title": result.get("npc_title", ""),
            "role": result.get("role", ""),
            "role_label": result.get("role_label", ""),
            "response": result.get("response", ""),
            "round": result.get("round") or request.get("round", 0),
            "year": result.get("year"),
            "season": result.get("season"),
            "agent": "A1_advisor",
            "category": result.get("category", "A1_advisor"),
        })
    except Exception as e:
        return ApiResponse.server_error(f"谋臣献策失败: {str(e)}")


@app.get("/api/agent/npcs")
async def list_npcs(role: str = "", faction_id: str = ""):
    """获取可用 NPC 文臣列表（可按角色类型或势力过滤）"""
    from server.agent.a1_advisor import A1AdvisorAgent
    npcs = A1AdvisorAgent.list_npcs(role_filter=role, faction_id=faction_id)
    return ApiResponse.success({"npcs": npcs, "count": len(npcs)})


@app.get("/api/agent/npc/{npc_id}")
async def get_npc_detail(npc_id: str):
    """获取单个 NPC 文臣详情"""
    from server.agent.a1_advisor import A1AdvisorAgent
    npc = A1AdvisorAgent.get_npc(npc_id)
    if not npc:
        return ApiResponse.not_found(f"NPC '{npc_id}' 不存在")
    return ApiResponse.success(npc)


@app.get("/api/agent/faction-advisers/{faction_id}")
async def get_faction_advisers(faction_id: str):
    """获取指定势力的谋士团信息（含成员列表和势力描述）"""
    from server.agent.a1_advisor import A1AdvisorAgent
    adviser_info = A1AdvisorAgent.get_faction_adviser_info(faction_id)
    advisers = A1AdvisorAgent.list_faction_advisers(faction_id)
    return ApiResponse.success({
        "faction_id": faction_id,
        "faction_info": adviser_info,
        "advisers": advisers,
        "count": len(advisers),
    })


@app.post("/api/agent/npc-chat")
async def npc_chat(request: dict):
    """与指定 NPC 文臣对话（每个 NPC 对接腾讯云混元 AI，通过 Orchestrator 统一调度）"""
    if not _llm_available:
        return ApiResponse.error(503, "AI服务不可用")

    npc_id = request.get("npc_id", "")
    faction_id = request.get("faction_id", "")
    message = request.get("message", "")
    conversation_history = request.get("conversation_history")

    if not npc_id:
        return ApiResponse.bad_request("请指定 NPC ID")
    if not message:
        return ApiResponse.bad_request("请输入对话内容")

    try:
        # 通过 Orchestrator 统一管理，支持模型覆盖和指标统计
        orch = _get_orchestrator()
        result = await orch.a1_strategic_advice(
            faction_id=faction_id,
            question=message,
            world_state=request.get("world_state", {}),
            clients=_llm_clients,
            npc_id=npc_id,
            conversation_history=conversation_history,
        )
        # orchestrator.a1_strategic_advice 在有 npc_id 时会路由到 chat_with_npc
        # 返回格式：{"npc_id":..., "npc_name":..., "response":..., ...} 或 {"response":..., ...}
        return ApiResponse.success({
            "npc_id": result.get("npc_id", npc_id),
            "npc_name": result.get("npc_name", ""),
            "npc_title": result.get("npc_title", ""),
            "role": result.get("role", ""),
            "role_label": result.get("role_label", ""),
            "response": result.get("response", ""),
            "agent": "A1_advisor",
        })
    except Exception as e:
        return ApiResponse.server_error(f"NPC对话失败: {str(e)}")


@app.post("/api/agent/court-debate")
async def court_debate(request: dict):
    """多 NPC 廷议辩论 - 多名文臣同框各抒己见"""
    if not _llm_available:
        return ApiResponse.error(503, "AI服务不可用")

    topic = request.get("topic", "")
    faction_id = request.get("faction_id", "")
    npc_ids = request.get("npc_ids")

    if not topic:
        return ApiResponse.bad_request("请输入廷议议题")

    try:
        from server.agent.a1_advisor import A1AdvisorAgent
        agent = A1AdvisorAgent(faction_id=faction_id)
        result = await agent.court_debate_multi(
            topic=topic,
            faction_id=faction_id,
            world_state=request.get("world_state", {}),
            clients=_llm_clients,
            npc_ids=npc_ids,
        )
        if "error" in result:
            return ApiResponse.bad_request(result["error"])
        return ApiResponse.success({
            "topic": result["topic"],
            "opinions": result["opinions"],
            "summary": result["summary"],
            "npc_count": result["npc_count"],
            "agent": "A1_advisor",
        })
    except Exception as e:
        return ApiResponse.server_error(f"廷议失败: {str(e)}")


# ============================================================
# API 端点 - 谋士对话上下文管理（3.3 新增）
# ============================================================

@app.get("/api/agent/conversations")
async def get_all_conversations(faction_id: str = ""):
    """获取所有活跃的谋士对话上下文（供前端同步）"""
    from server.agent.conversation_manager import get_conversation_manager
    mgr = get_conversation_manager()
    all_conv = mgr.get_all_conversations()
    if faction_id:
        all_conv = {
            k: v for k, v in all_conv.items()
            if v.get("faction_id") == faction_id
        }
    return ApiResponse.success({
        "conversations": all_conv,
        "stats": mgr.get_stats(),
    })


@app.get("/api/agent/conversations/{npc_id}")
async def get_npc_conversation(npc_id: str, faction_id: str = ""):
    """获取指定 NPC 的对话历史"""
    from server.agent.conversation_manager import get_conversation_manager
    mgr = get_conversation_manager()
    history = mgr.get_conversation_history(npc_id=npc_id, faction_id=faction_id)
    session = mgr.get_session(npc_id=npc_id, faction_id=faction_id)
    return ApiResponse.success({
        "npc_id": npc_id,
        "faction_id": faction_id,
        "history": history,
        "turn_count": session.turn_count if session else 0,
    })


@app.post("/api/agent/conversations/{npc_id}/clear")
async def clear_npc_conversation(npc_id: str, request: dict = None):
    """清除指定 NPC 的对话历史"""
    faction_id = (request or {}).get("faction_id", "")
    from server.agent.conversation_manager import get_conversation_manager
    mgr = get_conversation_manager()
    mgr.clear_session(npc_id=npc_id, faction_id=faction_id)
    return ApiResponse.success(None, f"已清除 {npc_id} 的对话历史")


@app.post("/api/agent/conversations/clear-all")
async def clear_all_conversations(request: dict = None):
    """清除全部/指定势力的所有对话历史"""
    faction_id = (request or {}).get("faction_id", "")
    from server.agent.conversation_manager import get_conversation_manager
    mgr = get_conversation_manager()
    if faction_id:
        mgr.clear_all_for_faction(faction_id)
        return ApiResponse.success(None, f"已清除 {faction_id} 的全部对话")
    else:
        mgr.clear_all()
        return ApiResponse.success(None, "已清除全部对话历史")


@app.post("/api/agent/conversations/sync")
async def sync_conversations(request: dict):
    """同步前后端对话上下文（客户端上传本地历史，服务端合并）"""
    from server.agent.conversation_manager import get_conversation_manager
    mgr = get_conversation_manager()
    conversations = request.get("conversations", {})
    if conversations:
        mgr.load_conversations(conversations)
    return ApiResponse.success({
        "stats": mgr.get_stats(),
    })


# ============================================================
# API 端点 - 律法 / 审讯
# ============================================================

@app.post("/api/agent/law-chat")
async def law_chat(request: dict):
    """A3 律法堂 - 律法审讯对话（手动前端调用）"""
    if not _llm_available:
        return ApiResponse.error(503, "AI服务不可用")

    try:
        orch = _get_orchestrator()
        prisoner = request.get("prisoner_name", "囚犯")
        question = request.get("question", "")
        result = await orch.a3_interrogate(
            faction_id=request.get("faction_id", ""),
            prisoner_name=prisoner,
            question=question,
            world_state=request.get("world_state", {}),
            clients=_llm_clients,
        )
        return ApiResponse.success({
            "prisoner": prisoner,
            "response": result.get("verdict", result.get("response", "")),
            "agent": "A3_law",
        })
    except Exception as e:
        return ApiResponse.server_error(f"审讯失败: {str(e)}")


@app.post("/api/agent/event-generate")
async def event_generate(request: dict):
    """A5 司天台 - 随机事件AI生成（手动前端调用）"""
    if not _llm_available:
        return ApiResponse.error(503, "AI服务不可用")

    try:
        orch = _get_orchestrator()
        result = await orch.a5_generate_events(
            round_num=request.get("round", 0),
            season=request.get("season", "春"),
            disaster_index=request.get("disaster_index", 0),
            world_state=request.get("world_state", {}),
            clients=_llm_clients,
        )
        return ApiResponse.success({
            "events_text": result.get("events_text", ""),
            "events": result.get("events", []),
            "ai_generated": result.get("ai_generated", True),
            "agent": "A5_event",
        })
    except Exception as e:
        return ApiResponse.server_error(f"事件生成失败: {str(e)}")


@app.post("/api/agent/tool-call")
async def agent_tool_call_endpoint(request: dict):
    """Agent FunctionCall工具调用（真实执行）- 兼容保留"""
    if not _llm_available:
        return ApiResponse.error(503, "AI服务不可用")

    try:
        from server.agent.tool_agent import CoreToolAgent
        agent = CoreToolAgent(clients=_llm_clients, world=_world_state)
        world_json = json.dumps(request.get("world_state", {}), ensure_ascii=False, indent=2)
        result = await agent.execute_with_tools(
            prompt=request.get("prompt", ""),
            faction_id=request.get("faction_id", ""),
            world_json=world_json,
            world_state=_world_state,
            system_prompt="你是元末乱世中的一方霸主，可以调用各种政令工具。",
            available_tools=request.get("tools"),
        )
        return ApiResponse.success(result)
    except Exception as e:
        logger.error(f"ToolAgent调用失败: {e}")
        return ApiResponse.server_error(f"工具调用失败: {str(e)}")


@app.get("/api/agent/tools")
async def list_tools(category: str = ""):
    """获取可用工具列表"""
    from server.agent.tool_agent import CoreToolAgent
    agent = CoreToolAgent()
    tools = agent.get_tool_definitions(category if category else None)
    return ApiResponse.success({
        "count": len(tools),
        "category": category or "all",
        "tools": tools,
    })


@app.post("/api/agent/auto-step")
async def agent_auto_step(request: dict):
    """完整自动推演一回合（通过Orchestrator调度A2/A4/A5/A6/A7/A8）"""
    if not _llm_available:
        return ApiResponse.error(503, "AI服务不可用")

    try:
        orch = _get_orchestrator()
        summary = await orch.run_full_auto_step(
            world_state=request.get("world_state", {}),
            faction_configs=_factions_config,
            clients=_llm_clients,
        )
        return ApiResponse.success(summary)
    except Exception as e:
        logger.error(f"自动推演失败: {e}")
        return ApiResponse.server_error(f"推演失败: {str(e)}")


@app.get("/api/agent/status")
async def agent_status():
    """Agent/LLM运行状态（八大智能体架构）"""
    orch = _get_orchestrator()
    agent_list = orch.get_agent_list()
    stats = orch.get_stats()

    return ApiResponse.success({
        "ai_available": _llm_available,
        "architecture": "8-agent",
        "models": {
            "advisor": getattr(_llm_clients.get("advisor"), "model_name", None),
            "law": getattr(_llm_clients.get("law"), "model_name", None),
            "enemy": getattr(_llm_clients.get("enemy"), "model_name", None),
        } if _llm_available else None,
        "fallback_mode": getattr(_llm_clients.get("enemy"), "fallback_mode", False) if _llm_available else False,
        "agents": agent_list,
        "stats": stats,
        "tool_count": 34,
        "max_concurrent": 20,
    })


@app.get("/api/agent/dashboard")
async def agent_dashboard():
    """全局AI智能体监控面板 - 返回所有Agent的详细运行数据"""
    orch = _get_orchestrator()
    agent_list = orch.get_agent_list()
    stats = orch.get_stats()
    event_bus = orch.event_bus

    # 构建每个Agent的详细状态
    agents_detail = []
    for a in agent_list:
        detail = {
            "key": a["key"],
            "name": a["name"],
            "model_group": a["model_group"],
            "trigger": a["trigger"],
            "description": a["description"],
            "player_only": a["player_only"],
            "config": a.get("config", {}),
            "alive": True,  # 默认存活
            "circuit_state": "CLOSED",
            "call_count": 0,
            "avg_latency": 0,
        }
        # 查找该agent的统计数据
        agent_stats = stats.get("agents", {})
        for agent_id, agent_stat in agent_stats.items():
            if a["key"].lower() in agent_id.lower() or agent_id.lower().startswith(a["key"].lower()):
                detail["circuit_state"] = agent_stat.get("circuit_state", "CLOSED")
                detail["call_count"] = agent_stat.get("call_count", 0)
                detail["avg_latency"] = agent_stat.get("avg_latency", 0)
                detail["alive"] = agent_stat.get("alive", True)
                detail["memories"] = agent_stat.get("memories", {})
                break
        agents_detail.append(detail)

    # 事件总线摘要
    event_bus_summary = {
        "pending_events": len(event_bus._pending_events) if event_bus else 0,
        "archived_events": len(event_bus._event_archive) if event_bus else 0,
        "recent_round": _world_state.current_round if _world_state else 0,
    }

    # 圣旨统计
    edict_stats = {
        "total_decrees": len(_world_state.decrees) if _world_state else 0,
        "last_edicts": [{
            "round": d.get("round"),
            "text": d.get("text", "")[:80],
            "executed": d.get("executed_count", 0),
            "failed": d.get("failed_count", 0),
        } for d in (_world_state.decrees[-5:] if _world_state else [])],
    }

    return ApiResponse.success({
        "ai_available": _llm_available,
        "architecture": "8-agent (A1~A8)",
        "model_groups": {
            "advisor": {"function": "chat_role", "agents": "A1/A2/A3/A7"},
            "law": {"function": "chat_strategy", "agents": "A6/A8"},
            "enemy": {"function": "chat_fast", "agents": "A4/A5"},
        } if _llm_available else None,
        "global_stats": {
            "total_calls": stats.get("total_calls", 0),
            "avg_latency": stats.get("avg_latency", 0),
            "total_agents": len(agents_detail),
            "active_agents": sum(1 for a in agents_detail if a.get("alive", False)),
            "degraded_agents": sum(1 for a in agents_detail if a.get("circuit_state") == "OPEN"),
        },
        "agents": agents_detail,
        "event_bus": event_bus_summary,
        "edict_stats": edict_stats,
    "edict_action_count": 20,  # 圣旨可用操作类型总数
})


# ============================================================
# API 端点 - 存档/读档/回放（链路5）
# ============================================================


def _resolve_faction_name(faction_id: str) -> str:
    """将 faction_id 解析为中文势力名"""
    if not faction_id:
        return "未知"
    cfg = _factions_config.get("factions", {}).get(faction_id, {})
    return cfg.get("name", faction_id)


@app.get("/api/save/list")
async def list_saves():
    """列出所有存档（含自动存档）"""
    try:
        saves = []
        auto_saves = []
        for f in sorted(SAVE_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
                faction_id = meta.get("player_faction", "")
                entry = {
                    "filename": f.name,
                    "slot": meta.get("slot", 0),
                    "round": meta.get("round", 0),
                    "year": meta.get("year", 1351),
                    "month": meta.get("month", 1),
                    "season": meta.get("season", ""),
                    "faction": faction_id,
                    "faction_name": meta.get("faction_name") or _resolve_faction_name(faction_id),
                    "note": meta.get("note", ""),
                    "saved_at": meta.get("saved_at", ""),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "territory_count": meta.get("territory_count", 0),
                    "version": meta.get("version", ""),
                    "is_auto": meta.get("slot") == -1 or f.name.startswith("auto_"),
                }
                if entry["is_auto"]:
                    auto_saves.append(entry)
                else:
                    saves.append(entry)
            except Exception as e:
                logger.warning(f"读取存档元数据失败 {f.name}: {e}")
                saves.append({"filename": f.name, "slot": 0, "round": 0, "faction_name": "损坏", "is_auto": False})
        return ApiResponse.success({
            "saves": saves,
            "auto_saves": auto_saves,
            "total_count": len(saves) + len(auto_saves),
        })
    except Exception as e:
        return ApiResponse.server_error(f"读取存档列表失败: {str(e)}")


@app.post("/api/save/save")
@app.post("/api/game/save")  # 2026-07-15: 兼容别名，玩家直觉路径
async def save_game(request: dict):
    """手动存档（P2修复：原子写入 + 路径穿越防御）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    slot = request.get("slot", 0)
    name = request.get("name", "")
    note = request.get("note", "")

    try:
        # P2: 锁内只读取数据，序列化在锁内完成（model_dump 在锁外可能并发修改）
        async with _state_lock:
            player = _world_state.get_player_faction()
            faction_name = ""
            territory = 0
            if player:
                faction_name = _factions_config.get("factions", {}).get(player.faction_id, {}).get("name", player.name)
                territory = len(_world_state.get_faction_tiles(player.faction_id))
            # 序列化军团和武将（存储在 __dict__ 中，Pydantic model_dump 不包含）
            all_generals = _world_state.__dict__.get("_generals", {})
            generals_save: dict[str, list[dict]] = {}
            for fid, gens in all_generals.items():
                generals_save[fid] = [g.model_dump() if hasattr(g, 'model_dump') else g for g in gens]
            all_legions = _world_state.__dict__.get("_legions", {})
            legions_save: dict[str, list[dict]] = {}
            for fid, legs in all_legions.items():
                legions_save[fid] = [l.model_dump() if hasattr(l, 'model_dump') else l for l in legs]
            save_data = {
                "slot": slot,
                "round": _world_state.current_round,
                "year": _world_state.current_year,
                "month": _world_state.current_month,
                "season": str(_world_state.current_season),
                "player_faction": player.faction_id if player else "",
                "faction_name": faction_name,
                "territory_count": territory,
                "note": note,
                "saved_at": datetime.now().isoformat(),
                "world_state": _world_state.model_dump(),
                "snapshots_count": len(_round_snapshots),
                "version": "3.2",
                "_generals": generals_save,
                "_legions": legions_save,
            }
            current_round = _world_state.current_round
            # P2: 防路径穿越 — 仅取文件名部分
            if name:
                safe_name = Path(name).name
                if not safe_name:
                    safe_name = f"save_slot{slot}_round{current_round}.json"
                elif not safe_name.endswith('.json'):
                    safe_name = safe_name + '.json'
                filename = safe_name
            else:
                filename = f"save_slot{slot}_round{current_round}.json"

        # P2: 文件 I/O 在锁外，使用原子写入
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = SAVE_DIR / (filename + ".tmp")
        final_path = SAVE_DIR / filename
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        if final_path.exists():
            final_path.unlink()
        temp_path.rename(final_path)

        return ApiResponse.success({
            "slot": slot,
            "filename": filename,
            "round": current_round,
        }, f"存档成功 - 第{current_round}回合")
    except json.JSONEncodeError as e:
        logger.error(f"存档序列化失败: {e}")
        # P3: 清理残留临时文件
        if 'temp_path' in dir() and temp_path.exists():
            try: temp_path.unlink()
            except Exception: pass
        return ApiResponse.server_error(f"存档数据序列化失败，请重试")
    except OSError as e:
        logger.error(f"存档写入失败: {e}")
        if 'temp_path' in dir() and temp_path.exists():
            try: temp_path.unlink()
            except Exception: pass
        return ApiResponse.server_error(f"存档写入磁盘失败: {e}")
    except Exception as e:
        logger.error(f"存档失败: {e}", exc_info=True)
        if 'temp_path' in dir() and temp_path.exists():
            try: temp_path.unlink()
            except Exception: pass
        return ApiResponse.server_error(f"存档失败: {str(e)[:300]}")


@app.post("/api/save/load")
async def load_game(request: dict):
    """读档 - 覆盖当前世界状态（P2修复：路径穿越防御 + 原子状态恢复）"""
    global _world_state, _round_engine, _pending_commands, _round_snapshots

    slot = request.get("slot", 0)
    filename = request.get("filename", "")
    save_name = request.get("save_name", "")

    # 兼容 save_name 参数
    if save_name:
        filename = save_name if save_name.endswith('.json') else save_name + '.json'

    # P2: 防路径穿越 — 仅取文件名部分
    if filename:
        safe_name = Path(filename).name
        if not safe_name:
            return ApiResponse.bad_request("无效的存档文件名")
        save_path = SAVE_DIR / safe_name
    else:
        matches = list(SAVE_DIR.glob(f"save_slot{slot}_*.json"))
        if not matches:
            return ApiResponse.error(404, f"未找到存档槽 {slot}")
        save_path = sorted(matches, key=lambda x: x.stat().st_mtime, reverse=True)[0]

    # P2: 额外安全校验 — 确保最终路径在 SAVE_DIR 内
    try:
        save_path = save_path.resolve()
        SAVE_DIR_resolved = SAVE_DIR.resolve()
        if not str(save_path).startswith(str(SAVE_DIR_resolved)):
            logger.warning(f"读档路径穿越尝试: {filename} → {save_path}")
            return ApiResponse.forbidden("不允许访问该路径")
    except Exception:
        return ApiResponse.bad_request("无效的存档路径")

    if not save_path.exists():
        return ApiResponse.error(404, f"存档文件不存在: {save_path.name}")

    # P2: 保存旧状态，读档失败时回滚
    old_state = None
    old_engine = None
    old_commands = None
    old_snapshots = None

    try:
        with open(save_path, "r", encoding="utf-8") as f:
            save_data = json.load(f)

        # 版本校验
        save_version = save_data.get("version", "unknown")
        if save_version != "3.2":
            logger.warning(f"存档版本不兼容: 存档版本 {save_version}, 当前版本 3.2")

        world_dict = save_data.get("world_state", {})
        if not world_dict:
            return ApiResponse.server_error("存档数据为空，无法加载")

        # P2: 备份旧状态
        old_state = _world_state
        old_engine = _round_engine
        old_commands = list(_pending_commands)
        old_snapshots = list(_round_snapshots)
        # P3: 深拷贝旧状态的内部字典，防止后续覆盖 __dict__ 时污染回滚数据
        old_generals = None
        old_legions = None
        if old_state is not None:
            try:
                old_generals = dict(old_state.__dict__.get("_generals", {}))
                old_legions = dict(old_state.__dict__.get("_legions", {}))
            except Exception:
                old_generals = {}
                old_legions = {}

        # 读档状态覆盖（加锁）
        async with _state_lock:
            try:
                _world_state = WorldState(**world_dict)
            except Exception as e:
                logger.error(f"WorldState 重建失败: {e}")
                raise ValueError(f"存档数据损坏（WorldState重建失败）: {e}")

            _round_engine = RoundEngine(_world_state, _factions_config)
            _round_engine.set_llm_clients(_llm_clients, available=_llm_available)
            _pending_commands = []
            _round_snapshots = []

            # 恢复军团和武将数据
            from server.models.generals import General, Legion
            generals_raw = save_data.get("_generals", {})
            legions_raw = save_data.get("_legions", {})
            _world_state.__dict__["_generals"] = {}
            _world_state.__dict__["_legions"] = {}

            # P2: 逐个恢复武将/军团，单个损坏不影响整体
            failed_generals = 0
            for fid, gen_list in generals_raw.items():
                restored = []
                for g in gen_list:
                    try:
                        restored.append(General(**g))
                    except Exception as e:
                        failed_generals += 1
                        logger.warning(f"读档跳过损坏武将 {g.get('name', '?')}: {e}")
                _world_state.__dict__["_generals"][fid] = restored

            failed_legions = 0
            for fid, leg_list in legions_raw.items():
                restored = []
                for l in leg_list:
                    try:
                        restored.append(Legion(**l))
                    except Exception as e:
                        failed_legions += 1
                        logger.warning(f"读档跳过损坏军团 {l.get('name', '?')}: {e}")
                _world_state.__dict__["_legions"][fid] = restored

            total_gens = sum(len(v) for v in _world_state.__dict__['_generals'].values())
            total_legs = sum(len(v) for v in _world_state.__dict__['_legions'].values())
            if failed_generals or failed_legions:
                logger.warning(
                    f"读档完成（部分数据跳过）: 武将 {total_gens} 人 (跳过 {failed_generals}), "
                    f"军团 {total_legs} 支 (跳过 {failed_legions})"
                )
            else:
                logger.info(f"读档恢复武将: {total_gens} 人, 军团: {total_legs} 支")

            player_faction_id = _world_state.player_faction_id
            game_mode = _world_state.game_mode if hasattr(_world_state, 'game_mode') else "player_turn"
            reset_mode_manager()
            mode_mgr = get_mode_manager()
            mode_mgr.init_game(game_mode, player_faction_id)
            logger.info(f"读档完成: 玩家势力={player_faction_id}, 模式={game_mode}")

            return ApiResponse.success({
                "world_state": _world_state.model_dump(),
                "round": _world_state.current_round,
                "save_version": save_version,
            }, f"读档成功 - 第{_world_state.current_round}回合")

    except ValueError as e:
        logger.error(f"读档数据损坏: {e}")
        # P3: 回滚旧状态（含内部字典恢复）
        if old_state is not None:
            _world_state = old_state
            _round_engine = old_engine
            _pending_commands = old_commands or []
            _round_snapshots = old_snapshots or []
            if old_generals is not None:
                _world_state.__dict__["_generals"] = old_generals
            if old_legions is not None:
                _world_state.__dict__["_legions"] = old_legions
        return ApiResponse.server_error(f"存档数据损坏: {e}")
    except Exception as e:
        logger.error(f"读档失败: {e}", exc_info=True)
        # P3: 回滚旧状态（含内部字典恢复）
        if old_state is not None:
            _world_state = old_state
            _round_engine = old_engine
            _pending_commands = old_commands or []
            _round_snapshots = old_snapshots or []
            if old_generals is not None:
                _world_state.__dict__["_generals"] = old_generals
            if old_legions is not None:
                _world_state.__dict__["_legions"] = old_legions
        return ApiResponse.server_error(f"读档失败: {str(e)[:300]}")


@app.delete("/api/save/delete")
async def delete_save(request: dict):
    """删除存档（P2修复：路径穿越防御 + 异常处理）"""
    filename = request.get("filename", "") or request.get("save_name", "")
    if not filename:
        return ApiResponse.bad_request("缺少 filename 或 save_name")
    # 自动补全 .json 后缀
    if not filename.endswith('.json'):
        filename = filename + '.json'

    # P2: 防路径穿越
    safe_name = Path(filename).name
    if not safe_name:
        return ApiResponse.bad_request("无效的存档文件名")
    save_path = SAVE_DIR / safe_name

    # P2: 路径安全校验
    try:
        if save_path.resolve() != (SAVE_DIR / safe_name).resolve():
            return ApiResponse.forbidden("不允许访问该路径")
    except Exception:
        return ApiResponse.bad_request("无效的存档路径")

    if not save_path.exists():
        return ApiResponse.error(404, "存档文件不存在")

    try:
        save_path.unlink()
        logger.info(f"删除存档: {safe_name}")
        return ApiResponse.success(None, f"存档 {safe_name} 已删除")
    except PermissionError:
        return ApiResponse.server_error(f"文件被占用，无法删除 {safe_name}")
    except OSError as e:
        return ApiResponse.server_error(f"删除失败: {e}")


@app.post("/api/save/clear-all")
async def clear_all_saves():
    """清空所有存档文件（P2修复：不再静默吞错误）"""
    try:
        files = list(SAVE_DIR.glob("*.json"))
        deleted = 0
        failed = 0
        for f in files:
            try:
                f.unlink()
                deleted += 1
            except (OSError, PermissionError) as e:
                failed += 1
                logger.warning(f"清空存档: 删除 {f.name} 失败: {e}")
        logger.info(f"清空存档: 成功 {deleted}, 失败 {failed}")
        if failed > 0:
            return ApiResponse.success(
                {"deleted_count": deleted, "failed_count": failed},
                f"已清空 {deleted} 个存档（{failed} 个失败）"
            )
        return ApiResponse.success({"deleted_count": deleted}, f"已清空 {deleted} 个存档")
    except Exception as e:
        logger.error(f"清空存档异常: {e}", exc_info=True)
        return ApiResponse.server_error(f"清空存档失败: {str(e)}")


@app.post("/api/save/export")
async def export_save(request: dict):
    """导出指定存档为可下载的 JSON（用于跨设备迁移）"""
    filename = request.get("filename", "") or request.get("save_name", "")
    if not filename:
        return ApiResponse.bad_request("请指定要导出的存档文件名")
    if not filename.endswith('.json'):
        filename = filename + '.json'

    # P3修复: 防路径穿越 — 仅取文件名部分
    safe_name = Path(filename).name
    if not safe_name:
        return ApiResponse.bad_request("无效的存档文件名")
    save_path = SAVE_DIR / safe_name
    # 路径安全校验
    try:
        if save_path.resolve() != (SAVE_DIR / safe_name).resolve():
            return ApiResponse.forbidden("不允许访问该路径")
    except Exception:
        return ApiResponse.bad_request("无效的存档路径")

    if not save_path.exists():
        return ApiResponse.error(404, f"存档文件不存在: {safe_name}")

    try:
        with open(save_path, "r", encoding="utf-8") as f:
            save_data = json.load(f)
        # 返回完整存档数据，前端负责触发浏览器下载
        return ApiResponse.success({
            "filename": safe_name,
            "save_data": save_data,
            "size_kb": round(save_path.stat().st_size / 1024, 1),
        }, f"导出成功: {safe_name}")
    except Exception as e:
        return ApiResponse.server_error(f"导出失败: {str(e)}")


@app.post("/api/save/import")
async def import_save(request: dict):
    """导入存档（从外部 JSON 数据写入）"""
    save_data = request.get("save_data")
    if not save_data:
        return ApiResponse.bad_request("缺少 save_data 字段")

    filename = request.get("filename", "")
    if not filename:
        # 自动生成文件名
        slot = save_data.get("slot", 0)
        round_num = save_data.get("round", 0)
        filename = f"imported_slot{slot}_round{round_num}.json"

    if not filename.endswith('.json'):
        filename = filename + '.json'

    # 防止路径穿越
    safe_name = Path(filename).name
    save_path = SAVE_DIR / safe_name

    # 如果已存在同名文件，追加序号
    counter = 1
    while save_path.exists():
        stem = Path(safe_name).stem
        save_path = SAVE_DIR / f"{stem}_{counter}.json"
        counter += 1

    try:
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        logger.info(f"存档导入成功: {save_path.name}")
        return ApiResponse.success({
            "filename": save_path.name,
            "round": save_data.get("round", 0),
            "faction_name": save_data.get("faction_name", ""),
        }, f"存档导入成功: {save_path.name}")
    except Exception as e:
        return ApiResponse.server_error(f"导入失败: {str(e)}")


@app.post("/api/save/quick-save")
async def quick_save(request: dict):
    """快速存档：自动查找空闲槽位保存（方便游戏内一键存档）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    note = request.get("note", "")
    try:
        async with _state_lock:
            player = _world_state.get_player_faction()
            faction_name = ""
            territory = 0
            if player:
                faction_name = _factions_config.get("factions", {}).get(player.faction_id, {}).get("name", player.name)
                territory = len(_world_state.get_faction_tiles(player.faction_id))

            all_generals = _world_state.__dict__.get("_generals", {})
            generals_save: dict[str, list[dict]] = {}
            for fid, gens in all_generals.items():
                generals_save[fid] = [g.model_dump() if hasattr(g, 'model_dump') else g for g in gens]
            all_legions = _world_state.__dict__.get("_legions", {})
            legions_save: dict[str, list[dict]] = {}
            for fid, legs in all_legions.items():
                legions_save[fid] = [l.model_dump() if hasattr(l, 'model_dump') else l for l in legs]

            # 查找空闲槽位（0-9 中第一个未使用的）
            existing_slots = set()
            for f in SAVE_DIR.glob("save_slot*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        existing_slots.add(json.load(fh).get("slot", -1))
                except Exception:
                    pass
            auto_slot = next((i for i in range(10) if i not in existing_slots), 0)
            if auto_slot in existing_slots:
                auto_slot = 0  # 全部占满则覆盖槽0

            current_round = _world_state.current_round
            save_data = {
                "slot": auto_slot,
                "round": current_round,
                "year": _world_state.current_year,
                "month": _world_state.current_month,
                "season": str(_world_state.current_season),
                "player_faction": player.faction_id if player else "",
                "faction_name": faction_name,
                "territory_count": territory,
                "note": note or f"快速存档 - 第{current_round}回合",
                "saved_at": datetime.now().isoformat(),
                "world_state": _world_state.model_dump(),
                "snapshots_count": len(_round_snapshots),
                "version": "3.2",
                "_generals": generals_save,
                "_legions": legions_save,
            }

            filename = f"save_slot{auto_slot}_round{current_round}.json"
            # 删除该槽位的旧文件
            for old in SAVE_DIR.glob(f"save_slot{auto_slot}_*.json"):
                try:
                    old.unlink()
                except Exception:
                    pass

        # P3: 原子写入 — 先写 .tmp 再 rename，防止崩溃损坏存档
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = SAVE_DIR / (filename + ".tmp")
        final_path = SAVE_DIR / filename
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        if final_path.exists():
            final_path.unlink()
        temp_path.rename(final_path)

        return ApiResponse.success({
            "slot": auto_slot,
            "filename": filename,
            "round": current_round,
        }, f"快速存档成功 - 槽{auto_slot + 1} 第{current_round}回合")
    except Exception as e:
        logger.error(f"快速存档失败: {e}", exc_info=True)
        # P3: 清理残留临时文件
        temp_path = SAVE_DIR / (filename + ".tmp") if 'filename' in dir() else None
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return ApiResponse.server_error(f"快速存档失败: {str(e)}")


@app.get("/api/save/replay-snapshots")
async def get_replay_snapshots():
    """获取回放快照列表"""
    return ApiResponse.success({
        "snapshots": _round_snapshots,
        "count": len(_round_snapshots),
    })


@app.get("/api/save/replay-snapshot/{round_num}")
async def get_replay_snapshot(round_num: int):
    """获取指定回合的快照"""
    for s in _round_snapshots:
        if s["round"] == round_num:
            return ApiResponse.success(s)
    return ApiResponse.error(404, f"未找到第{round_num}回合快照")


# ============================================================
# API 端点 - 地块操作
# ============================================================

@app.get("/api/map/tile/{tile_id}")
async def get_tile_detail(tile_id: str):
    """获取地块详情"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    tile = _world_state.get_tile(tile_id)
    if not tile:
        return ApiResponse.error(404, f"地块 {tile_id} 不存在")

    faction = _world_state.get_faction(tile.faction_id)
    return ApiResponse.success({
        "tile": tile.model_dump(),
        "owner": faction.model_dump() if faction else None,
        "available_actions": _get_tile_actions(tile),
    })


@app.get("/api/map/tiles")
async def get_all_tiles():
    """获取全量地图地块数据"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    return ApiResponse.success({
        "tiles": {k: v.model_dump() for k, v in _world_state.tiles.items()},
        "factions": {k: {"faction_id": v.faction_id, "name": v.name, "color": v.color} for k, v in _world_state.factions.items()},
        "relations": {k: v.model_dump() for k, v in _world_state.relations.items()},
        "count": len(_world_state.tiles),
    })


# ---- 静态地图数据缓存 ----
_static_map_cache: dict | None = None
_static_map_cache_time: float = 0.0


def _load_static_map() -> dict:
    """加载 map_final.json 静态地图数据（带文件级缓存）"""
    global _static_map_cache, _static_map_cache_time
    map_path = SERVER_DIR / "data" / "map" / "map_final.json"
    if not map_path.exists():
        return {}
    mtime = map_path.stat().st_mtime
    if _static_map_cache and _static_map_cache_time >= mtime:
        return _static_map_cache
    with open(map_path, "r", encoding="utf-8") as f:
        _static_map_cache = json.load(f)
        _static_map_cache_time = mtime
    return _static_map_cache


@app.get("/api/map/static")
async def get_static_map():
    """获取静态地图基底数据（496 府州级六边形格子、三级行政层级、初始势力归属）
    
    与 /api/map/tiles 不同，本端点不依赖游戏开局状态，
    返回 map_final.json 的完整内容（含 col/row/q/r 坐标、行省/路/府州层级、特殊标记）。
    """
    data = _load_static_map()
    if not data:
        return ApiResponse.error(404, "静态地图数据未生成，请先运行 generate_map.py")
    return ApiResponse.success(data)


@app.get("/api/map/static-full")
async def get_static_map_full():
    """获取完整静态地图（含海域地块，v4.1）
    
    优先返回 map_full.json（约 1,328 个格子，含海域），
    若不存在则回退到 map_final.json。
    """
    # 优先加载完整地图
    full_path = MAP_DATA_DIR / "map_full.json"
    if full_path.exists():
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ApiResponse.success(data)
        except Exception as e:
            logger.warning(f"加载 map_full.json 失败: {e}")

    # 回退到仅陆地地图
    data = _load_static_map()
    if not data:
        return ApiResponse.error(404, "静态地图数据未生成")
    return ApiResponse.success(data)


# ---- 边界线数据缓存 ----
_boundary_cache: dict | None = None
_boundary_cache_time: float = 0.0


def _load_boundaries() -> dict:
    """加载 boundaries.json 边界线数据（带文件级缓存）"""
    global _boundary_cache, _boundary_cache_time
    path = SERVER_DIR / "data" / "map" / "boundaries.json"
    if not path.exists():
        return {}
    mtime = path.stat().st_mtime
    if _boundary_cache and _boundary_cache_time >= mtime:
        return _boundary_cache
    import json
    with open(path, "r", encoding="utf-8") as f:
        _boundary_cache = json.load(f)
        _boundary_cache_time = mtime
    return _boundary_cache


@app.get("/api/map/boundaries")
async def get_boundaries():
    """获取三级行政区划边界线数据（行省/路/府州边界）"""
    data = _load_boundaries()
    if not data:
        return ApiResponse.error(404, "边界数据未生成，请先运行 generate_map.py")
    return ApiResponse.success(data)


# ---- 图层配置缓存 ----
_layer_config_cache: dict | None = None
_layer_config_cache_time: float = 0.0


def _load_layer_config() -> dict:
    """加载 layer_config.json 图层配置（带文件级缓存）"""
    global _layer_config_cache, _layer_config_cache_time
    path = SERVER_DIR / "data" / "map" / "layer_config.json"
    if not path.exists():
        return {}
    mtime = path.stat().st_mtime
    if _layer_config_cache and _layer_config_cache_time >= mtime:
        return _layer_config_cache
    import json
    with open(path, "r", encoding="utf-8") as f:
        _layer_config_cache = json.load(f)
        _layer_config_cache_time = mtime
    return _layer_config_cache


@app.get("/api/map/layer-config")
async def get_layer_config():
    """获取地图图层系统配置（势力配色/行政边界样式/迷雾/缩放级别）"""
    data = _load_layer_config()
    if not data:
        return ApiResponse.error(404, "图层配置未生成，请先运行 generate_map.py")
    return ApiResponse.success(data)


@app.post("/api/map/pathfind")
async def pathfind_route(request: dict):
    """A*寻路（CK3风格）：基于领地邻接图计算两个地块之间的最优行军路径"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from_tile = request.get("from_tile", "")
    to_tile = request.get("to_tile", "")
    faction_id = request.get("faction_id", "")
    has_navy = request.get("has_navy", False)

    from_t = _world_state.get_tile(from_tile)
    to_t = _world_state.get_tile(to_tile)
    if not from_t or not to_t:
        return ApiResponse.error(404, "地块不存在")

    # 获取当前季节
    season = _world_state.current_season.value if hasattr(_world_state.current_season, 'value') else str(_world_state.current_season)

    # 收集阻塞领地（不可通行的敌对领地等）
    blocked = set()
    for tid, t in _world_state.tiles.items():
        # 敌对关隘不可通行
        if t.tile_type.value == "pass" and t.faction_id and t.faction_id != faction_id:
            blocked.add(tid)

    # 使用 TerritoryGraph 进行领地级寻路
    from server.core.territory_graph import get_territory_graph
    graph = get_territory_graph()

    path = graph.find_path(
        start_id=from_tile,
        end_id=to_tile,
        season=season,
        has_navy=has_navy,
        blocked_territories=blocked,
    )

    if not path:
        # 回退：尝试旧版六边形A*（兼容可能仍使用hex_格式的旧数据）
        fallback_path = _a_star_pathfind(from_t, to_t, _world_state, blocked, faction_id)
        if fallback_path:
            return ApiResponse.success({
                "path": fallback_path,
                "reachable": True,
                "steps": len(fallback_path) - 1,
                "total_cost": len(fallback_path),
                "grain_estimate": len(fallback_path) * request.get("troops", 100) * 0.02,
                "pathfinding_method": "hex_fallback",
            })
        return ApiResponse.success({"path": [], "reachable": False, "message": "无可行路径（可能因河流阻隔、关隘封锁或冬季未至）"})

    # 计算路程消耗
    total_cost = 0.0
    barriers_encountered = []
    for i in range(1, len(path)):
        cost_info = graph.calculate_march_cost(path[i-1], path[i], season, has_navy)
        total_cost += cost_info.total_cost
        if cost_info.barrier_mult > 1.0:
            barriers = graph.get_barriers_between(path[i-1], path[i])
            for b in barriers:
                barriers_encountered.append({
                    "barrier_id": b.barrier_id,
                    "name": b.name,
                    "type": b.barrier_type.value,
                })

    # 路径地块详细信息
    path_details = []
    for pid in path:
        t = _world_state.get_tile(pid)
        if t:
            path_details.append({
                "tile_id": pid,
                "tile_name": t.tile_name,
                "faction_id": t.faction_id,
                "tile_type": t.tile_type.value if hasattr(t.tile_type, 'value') else str(t.tile_type),
            })

    return ApiResponse.success({
        "path": path,
        "path_details": path_details,
        "reachable": True,
        "steps": len(path) - 1,
        "total_cost": round(total_cost, 1),
        "grain_estimate": round(total_cost * request.get("troops", 100) * 0.02, 1),
        "barriers_encountered": barriers_encountered,
        "pathfinding_method": "ck3_territory_graph",
    })


def _a_star_pathfind(start_tile, end_tile, world, blocked: set, faction_id: str) -> list:
    """A* 寻路算法（六边形网格 - 保留作为回退方案）"""
    import heapq

    # 六边形距离启发式
    def hex_dist(t1, t2):
        return max(abs(t1.q - t2.q), abs(t1.r - t2.r), abs((t1.q + t1.r) - (t2.q + t2.r)))

    # 六边形6方向偏移
    HEX_DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

    # 构建坐标→tile_id映射
    coord_to_id = {}
    for tid, t in world.tiles.items():
        coord_to_id[(t.q, t.r)] = tid

    # 如果没有有效的六边形坐标数据，返回空
    if not coord_to_id:
        return []

    open_set = []
    heapq.heappush(open_set, (0, start_tile.tile_id))
    came_from = {}
    g_score = {start_tile.tile_id: 0}
    f_score = {start_tile.tile_id: hex_dist(start_tile, end_tile)}

    while open_set:
        _, current_id = heapq.heappop(open_set)
        if current_id == end_tile.tile_id:
            # 重建路径
            path = [end_tile.tile_id]
            while current_id in came_from:
                current_id = came_from[current_id]
                path.append(current_id)
            return list(reversed(path))

        current = world.get_tile(current_id)
        if not current:
            continue

        for dq, dr in HEX_DIRS:
            nq, nr = current.q + dq, current.r + dr
            neighbor_id = coord_to_id.get((nq, nr))
            if not neighbor_id or neighbor_id in blocked:
                continue
            neighbor = world.get_tile(neighbor_id)
            if not neighbor:
                continue

            # 移动代价：地形 + 是否敌对
            terrain_cost = {"mountain": 3, "water": 999, "desert": 2, "grassland": 1}.get(
                neighbor.tile_type.value, 1)
            if neighbor.faction_id and neighbor.faction_id != faction_id and neighbor.faction_id != current.faction_id:
                terrain_cost *= 2  # 穿过敌方领土代价翻倍

            tentative_g = g_score.get(current_id, 999) + terrain_cost
            if tentative_g < g_score.get(neighbor_id, 999):
                came_from[neighbor_id] = current_id
                g_score[neighbor_id] = tentative_g
                f_score[neighbor_id] = tentative_g + hex_dist(neighbor, end_tile)
                heapq.heappush(open_set, (f_score[neighbor_id], neighbor_id))

    return []  # 无路径


def _get_tile_actions(tile) -> list[str]:
    """获取地块可用操作列表"""
    actions = ["view_detail"]
    if tile.tile_type in [TileType.FARMLAND, TileType.CITY, TileType.GRASSLAND, TileType.PORT]:
        actions.extend(["develop_land", "recruit_troops", "fortify"])
    elif tile.tile_type in [TileType.MOUNTAIN, TileType.PASS, TileType.COAST, TileType.DESERT]:
        actions.extend(["recruit_troops", "fortify"])
    if tile.tile_type == TileType.COAST:
        actions.append("build_port")
    if tile.is_capital:
        actions.append("court_session")
    return actions


# ============================================================
# API 端点 - 地图图片渲染（古风水墨舆图）
# ============================================================

@app.get("/api/map/render")
async def render_map_image(refresh: bool = False):
    """
    生成古风水墨风格元末势力分布地图PNG
    
    基于真实GeoJSON行省/路府边界 + 城池坐标数据，
    使用PIL渲染1400×1100古风水墨风格地图底图。
    
    Query:
        refresh: 是否强制重新生成（默认使用缓存）
    
    Returns:
        image/png 地图图片
    """
    import os
    from fastapi.responses import Response
    
    # 缓存路径
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache_path = cache_dir / "yuanmo_map_render.png"
    
    # 检查缓存
    if not refresh and cache_path.exists():
        # 检查数据文件是否比缓存新
        map_data_dir = Path(__file__).parent.parent / "frontend" / "public" / "data" / "map"
        cache_mtime = cache_path.stat().st_mtime
        needs_regenerate = False
        for data_file in ["provinces.geojson", "prefectures.geojson", "cities.json", "factions.json"]:
            df_path = map_data_dir / data_file
            if df_path.exists() and df_path.stat().st_mtime > cache_mtime:
                needs_regenerate = True
                break
        
        if not needs_regenerate:
            logger.info("[map/render] 返回缓存地图")
            return Response(content=cache_path.read_bytes(), media_type="image/png")
    
    try:
        from server.utils.map_renderer import render_map_png
        png_data = render_map_png()
        
        # 写入缓存
        cache_path.write_bytes(png_data)
        logger.info(f"[map/render] 地图已生成并缓存 ({len(png_data)} bytes)")
        
        return Response(content=png_data, media_type="image/png")
    except ImportError as e:
        logger.warning(f"[map/render] Pillow未安装: {e}")
        return ApiResponse.error(500, "地图渲染引擎未安装(Pillow)，请运行: pip install Pillow")
    except Exception as e:
        logger.error(f"[map/render] 渲染失败: {e}")
        return ApiResponse.error(500, f"地图渲染失败: {str(e)}")


@app.get("/api/map/render/status")
async def map_render_status():
    """查询地图渲染状态"""
    cache_path = Path(__file__).parent / "cache" / "yuanmo_map_render.png"
    return ApiResponse.success({
        "cached": cache_path.exists(),
        "cache_size": cache_path.stat().st_size if cache_path.exists() else 0,
        "cache_mtime": cache_path.stat().st_mtime if cache_path.exists() else None,
    })




# ============================================================
# API 端点 - 谍报细作（系统3）
# ============================================================

@app.post("/api/spy/deploy")
async def deploy_spy(request: dict):
    """派遣细作"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import SpyEngine
    engine = SpyEngine(_world_state)
    result = engine.deploy_spy(
        owner_faction=request.get("owner_faction", ""),
        target_faction=request.get("target_faction", ""),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/spy/action")
async def spy_action(request: dict):
    """执行谍报行动"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import SpyEngine
    engine = SpyEngine(_world_state)
    result = engine.spy_action(
        owner_faction=request.get("owner_faction", ""),
        target_faction=request.get("target_faction", ""),
        action_type=request.get("action_type", "intel"),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.get("/api/spy/networks/{faction_id}")
async def get_spy_networks(faction_id: str):
    """获取势力谍报网络"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    networks = [
        v.model_dump() for k, v in _world_state.spy_networks.items()
        if v.owner_faction == faction_id or v.target_faction == faction_id
    ]
    return ApiResponse.success({"faction_id": faction_id, "networks": networks, "count": len(networks)})




# ============================================================
# API 端点 - 外交通商（系统5）
# ============================================================

def _get_diplo_parties(request: dict) -> tuple[str, str]:
    """兼容多种前端参数格式，返回 (faction_a, faction_b)"""
    a = request.get("faction_a") or request.get("faction_id") or request.get("from_faction") or ""
    b = request.get("faction_b") or request.get("target_faction") or request.get("to_faction") or ""
    return a, b

@app.post("/api/diplomacy/change-stance")
async def change_diplomatic_stance(request: dict):
    """改变外交姿态"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    faction_a, faction_b = _get_diplo_parties(request)
    result = engine.change_stance(
        faction_a=faction_a,
        faction_b=faction_b,
        new_stance=request.get("new_stance") or request.get("stance", "neutral"),
        reason=request.get("reason", ""),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/diplomacy/trade")
async def open_trade_route(request: dict):
    """开通贸易"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    faction_a, faction_b = _get_diplo_parties(request)
    result = engine.open_trade(
        faction_a=faction_a,
        faction_b=faction_b,
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/diplomacy/marriage")
async def propose_marriage(request: dict):
    """联姻"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    faction_a, faction_b = _get_diplo_parties(request)
    result = engine.propose_marriage(
        from_faction=faction_a,
        to_faction=faction_b,
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.get("/api/diplomacy/relations/{faction_id}")
async def get_faction_relations(faction_id: str):
    """获取势力所有外交关系"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        relations = []
        for key, rel in _world_state.relations.items():
            if rel.faction_a == faction_id or rel.faction_b == faction_id:
                other = rel.faction_b if rel.faction_a == faction_id else rel.faction_a
                other_f = _world_state.get_faction(other)
                relations.append({
                    "key": key,
                    "other": other,
                    "other_name": other_f.name if other_f else other,
                    "other_color": other_f.color if other_f else "#666666",
                    "stance": rel.stance.value,
                    "attitude": rel.attitude,
                    "trade_active": rel.trade_active,
                    "treaty_expiry": rel.treaty_expiry,
                    "coalition_id": rel.coalition_id,
                })
        return ApiResponse.success({"faction_id": faction_id, "relations": relations, "count": len(relations)})
    except Exception as e:
        logger.error(f"获取外交关系失败: {e}", exc_info=True)
        return ApiResponse.server_error(f"获取外交关系失败: {str(e)}")


@app.get("/api/diplomacy/summary/{faction_id}")
async def get_diplomatic_summary(faction_id: str):
    """获取势力外交摘要（含联邦、附庸、同盟、通商等）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    summary = engine.get_diplomatic_summary(faction_id)
    return ApiResponse.success(summary)


# ============================================================
# API 端点 - 联邦/联盟（系统5增强）
# ============================================================

@app.post("/api/diplomacy/coalition/create")
async def create_coalition(request: dict):
    """创建联邦/联盟"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    result = engine.form_coalition(
        founder_faction=request.get("founder_faction", ""),
        name=request.get("name", "天下同盟"),
        member_factions=request.get("member_factions", []),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/diplomacy/coalition/join")
async def join_coalition(request: dict):
    """加入联邦"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    result = engine.join_coalition(
        faction_id=request.get("faction_id", ""),
        coalition_id=request.get("coalition_id", ""),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/diplomacy/coalition/leave")
async def leave_coalition(request: dict):
    """退出联邦"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    result = engine.leave_coalition(
        faction_id=request.get("faction_id", ""),
        coalition_id=request.get("coalition_id", ""),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/diplomacy/coalition/dissolve")
async def dissolve_coalition(request: dict):
    """解散联邦"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    result = engine.dissolve_coalition(
        faction_id=request.get("faction_id", ""),
        coalition_id=request.get("coalition_id", ""),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.get("/api/diplomacy/coalitions")
async def list_coalitions():
    """列出所有联邦"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    coalitions = []
    for cid, members in _world_state.coalitions.items():
        member_names = []
        for m in members:
            f = _world_state.get_faction(m)
            member_names.append({"faction_id": m, "name": f.name if f else m, "color": f.color if f else "#666"})
        coalitions.append({
            "coalition_id": cid,
            "members": member_names,
            "member_count": len(members),
        })
    return ApiResponse.success({"coalitions": coalitions, "count": len(coalitions)})


@app.post("/api/diplomacy/trade/close")
async def close_trade_route(request: dict):
    """关闭贸易路线"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    faction_a, faction_b = _get_diplo_parties(request)
    result = engine.close_trade(
        faction_a=faction_a,
        faction_b=faction_b,
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/diplomacy/tribute")
async def demand_tribute(request: dict):
    """宗主索要朝贡"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    faction_a, faction_b = _get_diplo_parties(request)
    result = engine.demand_tribute(
        suzerain=request.get("suzerain") or request.get("suzerain_faction") or faction_a,
        vassal=request.get("vassal") or request.get("vassal_faction") or faction_b,
        amount=request.get("amount", 200),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/diplomacy/vassal/offer")
async def offer_vassal(request: dict):
    """提议附庸"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    faction_a, faction_b = _get_diplo_parties(request)
    result = engine.offer_vassal(
        suzerain=request.get("suzerain") or request.get("suzerain_faction") or faction_a,
        target=request.get("target") or request.get("vassal_faction") or faction_b,
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/diplomacy/vassal/cancel")
async def cancel_vassal(request: dict):
    """取消附庸关系"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    faction_a, faction_b = _get_diplo_parties(request)
    result = engine.cancel_vassal(
        suzerain=request.get("suzerain") or request.get("suzerain_faction") or faction_a,
        vassal=request.get("vassal") or request.get("vassal_faction") or faction_b,
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/diplomacy/peace")
async def sign_peace_treaty(request: dict):
    """签订停战条约"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import DiplomacyEngine
    engine = DiplomacyEngine(_world_state)
    faction_a, faction_b = _get_diplo_parties(request)
    result = engine.sign_peace_treaty(
        faction_a=faction_a,
        faction_b=faction_b,
        duration=request.get("duration"),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


# ============================================================
# API 端点 - 朝堂律法（系统2/4）
# ============================================================

@app.post("/api/court/appoint")
async def appoint_official(request: dict):
    """任命官员"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import CourtEngine
    engine = CourtEngine(_world_state)
    result = engine.appoint_official(
        faction_id=request.get("faction_id", ""),
        name=request.get("name", ""),
        position=request.get("position", "幕僚"),
        ability=request.get("ability", 50),
        loyalty=request.get("loyalty", 60),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/court/dismiss")
async def dismiss_official(request: dict):
    """罢免官员"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import CourtEngine
    engine = CourtEngine(_world_state)
    result = engine.dismiss_official(official_id=request.get("official_id", ""))
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/court/execute")
async def execute_official(request: dict):
    """处决官员"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import CourtEngine
    engine = CourtEngine(_world_state)
    result = engine.execute_official(official_id=request.get("official_id", ""))
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.post("/api/court/prisoner")
async def handle_prisoner(request: dict):
    """处置俘虏"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import CourtEngine
    engine = CourtEngine(_world_state)
    result = engine.handle_prisoner(
        prisoner_id=request.get("prisoner_id", ""),
        action=request.get("action", "imprison"),
    )
    return ApiResponse.success(result) if result["success"] else ApiResponse.bad_request(result["message"])


@app.get("/api/court/officials/{faction_id}")
async def get_faction_officials(faction_id: str):
    """获取势力官员列表"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        officials = [
            off.model_dump() for oid, off in _world_state.officials.items()
            if off.faction_id == faction_id
        ]
        prisoners = [
            p.model_dump() for pid, p in _world_state.prisoners.items()
            if p.held_by == faction_id
        ]
        return ApiResponse.success({
            "faction_id": faction_id,
            "officials": officials,
            "prisoners": prisoners,
            "count": len(officials),
        })
    except Exception as e:
        logger.error(f"获取官员列表失败: {e}", exc_info=True)
        return ApiResponse.server_error(f"获取官员列表失败: {str(e)}")


@app.get("/api/court/policies")
async def get_policies():
    """获取国策树数据"""
    import json
    from pathlib import Path
    policy_path = Path(__file__).parent / "data" / "policies.json"
    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            policies = json.load(f)
        return ApiResponse.success(policies.get("policies", {}))
    except Exception as e:
        return ApiResponse.server_error(f"国策数据加载失败: {str(e)}")


@app.get("/api/court/overview/{faction_id}")
async def get_court_overview(faction_id: str):
    """获取朝堂总览数据"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    faction = _world_state.factions.get(faction_id)
    if not faction:
        return ApiResponse.not_found(f"势力 {faction_id} 不存在")

    try:
        officials_count = sum(1 for off in _world_state.officials.values() if off.faction_id == faction_id)
        prisoners_count = sum(1 for p in _world_state.prisoners.values() if p.held_by == faction_id)
        decrees_count = len(_world_state.decrees)
        purges_count = len(_world_state.purges)
        exiled_count = len(_world_state.exiled_officials)

        # 派系忠诚度汇总
        faction_loyalty_summary = {}
        for oid, off in _world_state.officials.items():
            if off.faction_id == faction_id and off.faction_affiliation:
                aff = off.faction_affiliation
                if aff not in faction_loyalty_summary:
                    faction_loyalty_summary[aff] = {"count": 0, "avg_loyalty": 0, "total_loyalty": 0}
                faction_loyalty_summary[aff]["count"] += 1
                faction_loyalty_summary[aff]["total_loyalty"] += off.loyalty
        for aff in faction_loyalty_summary:
            s = faction_loyalty_summary[aff]
            s["avg_loyalty"] = s["total_loyalty"] // max(1, s["count"])

        return ApiResponse.success({
            "faction_id": faction_id,
            "faction_name": faction.name,
            "court_stability": faction.court_stability,
            "realm_stability": faction.realm_stability,
            "development_level": faction.development_level,
            "reputation": faction.reputation,
            "treasury": faction.treasury,
            "grain": faction.grain,
            "officials_count": officials_count,
            "prisoners_count": prisoners_count,
            "decrees_count": decrees_count,
            "purges_count": purges_count,
            "exiled_count": exiled_count,
            "unlocked_policies": faction.unlocked_policies,
            "buffs": faction.buffs,
            "debuffs": faction.debuffs,
            "faction_loyalty_summary": faction_loyalty_summary,
            "personality_tags": faction.personality_tags,
        })
    except Exception as e:
        logger.error(f"获取朝堂总览失败: {e}", exc_info=True)
        return ApiResponse.server_error(f"获取朝堂总览失败: {str(e)}")


@app.post("/api/court/decree")
async def issue_decree(request: dict):
    """颁布敕令"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    # 兼容多种参数格式：text / decree_type / params.content
    decree_text = request.get("text", "")
    if not decree_text:
        decree_type = request.get("decree_type", "")
        params_content = (request.get("params") or {}).get("content", "")
        decree_text = params_content or decree_type

    faction_id = request.get("faction_id", "")

    if not decree_text:
        return ApiResponse.bad_request("敕令内容不能为空")

    decree = {
        "id": f"decree_{_world_state.current_round}_{len(_world_state.decrees)}",
        "round": _world_state.current_round,
        "year": _world_state.current_year,
        "month": _world_state.current_month,
        "faction_id": faction_id,
        "text": decree_text,
        "timestamp": _world_state.updated_at or "",
    }
    _world_state.decrees.append(decree)

    # 写入治理日志
    _world_state.governance_logs.append({
        "round": _world_state.current_round,
        "title": "颁布敕令",
        "description": decree_text,
        "narrative": f"第{_world_state.current_round}回合，{_world_state.get_faction(faction_id).name if _world_state.get_faction(faction_id) else faction_id}颁布敕令：{decree_text}",
    })

    return ApiResponse.success({"decree": decree, "total_decrees": len(_world_state.decrees)})


@app.post("/api/court/unlock-policy")
async def unlock_policy_endpoint(request: dict):
    """解锁国策"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    policy_id = request.get("policy_id", "")
    faction_id = request.get("faction_id", "")

    if not policy_id:
        return ApiResponse.bad_request("国策ID不能为空")

    faction = _world_state.factions.get(faction_id)
    if not faction:
        return ApiResponse.not_found(f"势力 {faction_id} 不存在")

    if policy_id in faction.unlocked_policies:
        return ApiResponse.bad_request("该国策已解锁")

    # 从 policies.json 自动获取 cost（优先使用请求中的 cost，否则查配置）
    cost = request.get("cost")
    if cost is None:
        from pathlib import Path
        import json
        try:
            policy_path = Path(__file__).parent / "data" / "policies.json"
            with open(policy_path, "r", encoding="utf-8") as f:
                policies_data = json.load(f)
            for cat in policies_data.get("policies", {}).values():
                for branch in cat.get("branches", []):
                    for tier in branch.get("tiers", []):
                        if tier["id"] == policy_id:
                            cost = tier.get("cost", 0)
                            break
        except Exception:
            cost = 500  # 默认消耗
    cost = cost or 500

    if faction.treasury < cost:
        return ApiResponse.bad_request(f"银两不足（需要{cost}，现有{faction.treasury}）")

    if policy_id in faction.unlocked_policies:
        return ApiResponse.bad_request("该国策已解锁")

    faction.treasury -= cost
    faction.unlocked_policies.append(policy_id)

    # 应用国策效果
    from pathlib import Path
    import json
    try:
        policy_path = Path(__file__).parent / "data" / "policies.json"
        with open(policy_path, "r", encoding="utf-8") as f:
            policies_data = json.load(f)

        # 查找国策效果
        for cat in policies_data.get("policies", {}).values():
            for branch in cat.get("branches", []):
                for tier in branch.get("tiers", []):
                    if tier["id"] == policy_id:
                        effects = tier.get("effects", {})
                        for key, val in effects.items():
                            if key == "realm_stability":
                                faction.realm_stability = min(100, faction.realm_stability + val)
                            elif key == "court_stability":
                                faction.court_stability = min(100, faction.court_stability + val)
                            elif key == "reputation":
                                faction.reputation = min(100, faction.reputation + val)
                            elif key == "development_level":
                                faction.development_level += val
                        break
    except Exception as e:
        logger.warning(f"应用国策效果失败: {e}")

    _world_state.governance_logs.append({
        "round": _world_state.current_round,
        "title": f"采纳国策: {policy_id}",
        "description": f"{faction.name}采纳国策{policy_id}，花费银{cost}两",
        "narrative": f"第{_world_state.current_round}回合，{faction.name}采纳国策，花费银{cost}两。",
    })

    return ApiResponse.success({
        "policy_id": policy_id,
        "cost": cost,
        "treasury_remaining": faction.treasury,
        "unlocked_policies": faction.unlocked_policies,
    })


@app.get("/api/court/policy-overview/{faction_id}")
async def get_policy_overview(faction_id: str):
    """获取国策总览聚合数据（军事/外交/荒政/谍报/物资 五大维度）
    
    替代前端多处分散查询，一次返回 PolicyPanel 所需的全部数据。
    所有数据以当前 world_state 为唯一来源，保证全局一致性。
    """
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    faction = _world_state.factions.get(faction_id)
    if not faction:
        return ApiResponse.not_found(f"势力 {faction_id} 不存在")
    from server.models.world_state import Building, BuildingType

    # ---- 辅助函数 ----
    def _build_troop_entry(t: TileState) -> dict:
        bld = t.buildings or {}
        return {
            "tile_id": t.tile_id,
            "tile_name": t.tile_name,
            "troops": t.troops,
            "morale": t.morale,
            "fortification": t.fortification,
            "elite_ratio": round(t.elite_ratio * 100, 1),
            "garrison_resting": t.garrison_resting,
            "has_barracks": any(b.building_type == "barracks" for b in bld.values() if isinstance(b, Building)),
            "has_armory": t.armory > 0,
            "has_stable": t.stable > 0,
        }

    owner_tiles = _world_state.get_faction_tiles(faction_id)

    # ===== 1. 军事 =====
    military: dict = {
        "total_troops": faction.total_troops or sum(t.troops for t in owner_tiles),
        "troops_by_tile": [_build_troop_entry(t) for t in owner_tiles if t.troops > 0],
        "tiles_without_troops": [{
            "tile_id": t.tile_id,
            "tile_name": t.tile_name,
            "troops": 0,
            "fortification": t.fortification,
            "is_frontline": False,  # 前端自行判断
        } for t in owner_tiles if t.troops <= 0],
        "sieges_as_attacker": [],
        "sieges_as_defender": [],
        "prisoners_held": [],
        "prisoners_captured": [],
    }
    # 围城
    for sid, siege in _world_state.siege_states.items():
        siege_data = siege.model_dump() if hasattr(siege, "model_dump") else siege
        info = {
            "siege_id": siege_data.get("siege_id", sid),
            "tile_id": siege_data.get("tile_id", ""),
            "attacker_faction": siege_data.get("attacker_faction", ""),
            "defender_faction": siege_data.get("defender_faction", ""),
            "siege_rounds": siege_data.get("siege_rounds", 0),
            "attacker_troops": siege_data.get("attacker_troops", 0),
            "defender_troops": siege_data.get("defender_troops", 0),
            "wall_damage": siege_data.get("wall_damage", 0),
            "state": siege_data.get("state", "sieging"),
        }
        tile = _world_state.tiles.get(info["tile_id"])
        if tile:
            info["tile_name"] = tile.tile_name
            info["region"] = getattr(tile, "region", "")
        att_name = ""
        def_name = ""
        if info["attacker_faction"] in _world_state.factions:
            att_name = _world_state.factions[info["attacker_faction"]].name
        if info["defender_faction"] in _world_state.factions:
            def_name = _world_state.factions[info["defender_faction"]].name
        info["attacker_name"] = att_name
        info["defender_name"] = def_name
        if info["attacker_faction"] == faction_id:
            military["sieges_as_attacker"].append(info)
        if info["defender_faction"] == faction_id:
            military["sieges_as_defender"].append(info)
    # 俘虏
    for pid, prisoner in _world_state.prisoners.items():
        pdata = prisoner.model_dump() if hasattr(prisoner, "model_dump") else prisoner
        pinfo = {
            "prisoner_id": pdata.get("prisoner_id", pid),
            "name": pdata.get("name", ""),
            "captured_from": pdata.get("captured_from", ""),
            "rank": pdata.get("rank", "general"),
            "captured_round": pdata.get("captured_round", 0),
            "held_by": pdata.get("held_by", ""),
        }
        if pinfo["held_by"] == faction_id:
            military["prisoners_held"].append(pinfo)
        if pinfo["captured_from"] == faction_id:
            military["prisoners_captured"].append(pinfo)
    # 瘟疫（从地块灾难中提取）
    plague_tiles = []
    for t in owner_tiles:
        for d in (t.disasters or []):
            d_str = str(d)
            if "plague" in d_str.lower():
                plague_tiles.append({"tile_id": t.tile_id, "tile_name": t.tile_name, "severity": "活跃"})
    military["plague_tiles"] = plague_tiles

    # ===== 2. 外交 =====
    diplomacy: dict = {
        "relations": [],
        "treaties": [],
        "coalitions": [],
        "vassals_of_mine": [],
        "my_suzerain": None,
    }
    for rkey, rel in _world_state.relations.items():
        rdata = rel.model_dump() if hasattr(rel, "model_dump") else rel
        a, b = rdata.get("faction_a", ""), rdata.get("faction_b", "")
        if a != faction_id and b != faction_id:
            continue
        other_id = b if a == faction_id else a
        other_f = _world_state.factions.get(other_id)
        diplomacy["relations"].append({
            "faction_id": other_id,
            "faction_name": other_f.name if other_f else other_id,
            "color": other_f.color if other_f else "#666",
            "stance": rdata.get("stance", "neutral"),
            "attitude": rdata.get("attitude", 50),
            "treaty_expiry": rdata.get("treaty_expiry", 0),
            "trade_active": rdata.get("trade_active", False),
            "coalition_id": rdata.get("coalition_id", ""),
            "is_alive": other_f.is_alive if other_f else True,
        })
    # 条约
    for treaty in _world_state.alliance_treaties:
        tdata = treaty.model_dump() if hasattr(treaty, "model_dump") else treaty
        factions_in = tdata.get("factions", [])
        if faction_id in factions_in:
            diplomacy["treaties"].append({
                "treaty_id": tdata.get("treaty_id", ""),
                "treaty_type": tdata.get("treaty_type", ""),
                "parties": [(_world_state.factions[f].name if f in _world_state.factions else f) for f in factions_in if f != faction_id],
                "signed_round": tdata.get("signed_round", 0),
                "expires_round": tdata.get("expires_round", 0),
                "terms": tdata.get("terms", {}),
            })
    # 联盟/附庸
    for cid, members in _world_state.coalitions.items():
        if faction_id in members:
            diplomacy["coalitions"].append({
                "coalition_id": cid,
                "members": [(_world_state.factions[m].name if m in _world_state.factions else m) for m in members if m != faction_id],
            })
    for vid, suzerain_id in _world_state.vassal_relations.items():
        if vid == faction_id:
            suz = _world_state.factions.get(suzerain_id)
            diplomacy["my_suzerain"] = {"faction_id": suzerain_id, "name": suz.name if suz else suzerain_id}
        if suzerain_id == faction_id:
            vassal_f = _world_state.factions.get(vid)
            diplomacy["vassals_of_mine"].append({"faction_id": vid, "name": vassal_f.name if vassal_f else vid})

    # ===== 3. 荒政 =====
    civil: dict = {
        "disaster_index": _world_state.disaster_index,
        "active_disasters": [],
        "total_population": faction.total_population or sum(t.population for t in owner_tiles),
        "total_grain": faction.grain,
        "avg_refugee_ratio": round(
            sum(t.refugee_ratio for t in owner_tiles) / max(1, len(owner_tiles)) * 100, 1
        ),
        "weather": _world_state.weather if _world_state.weather else {},
        "development_level": faction.development_level,
        "realm_stability": faction.realm_stability,
        "court_stability": faction.court_stability,
        "tile_disasters": [],
    }
    for t in owner_tiles:
        if t.disasters:
            for d in t.disasters:
                civil["tile_disasters"].append({
                    "tile_id": t.tile_id,
                    "tile_name": t.tile_name,
                    "disaster_type": str(d),
                    "population": t.population,
                })
    # 全局活跃灾害
    for d in (_world_state.disasters or []):
        ddata = d.model_dump() if hasattr(d, "model_dump") else d
        civil["active_disasters"].append({
            "type": ddata.get("type", ""),
            "title": ddata.get("title") or ddata.get("type", ""),
            "description": ddata.get("description", ""),
            "severity": ddata.get("severity", 0),
            "affected_tiles": ddata.get("affected_tiles", []),
        })

    # ===== 4. 谍报 =====
    spy: dict = {
        "networks": [],
        "intel_reports": [],
        "false_intel_planted": [],
    }
    for nid, network in _world_state.spy_networks.items():
        ndata = network.model_dump() if hasattr(network, "model_dump") else network
        if ndata.get("owner_faction") == faction_id:
            target_f = _world_state.factions.get(ndata.get("target_faction", ""))
            spy["networks"].append({
                "network_id": nid,
                "target_faction_id": ndata.get("target_faction", ""),
                "target_faction_name": target_f.name if target_f else ndata.get("target_faction", ""),
                "spies_count": ndata.get("spies_count", 0),
                "infiltration": ndata.get("infiltration", 0),
                "action_points": ndata.get("action_points", 0),
                "discovered": ndata.get("discovered", False),
            })
    for intel in (_world_state.spy_intel or []):
        idata = intel.model_dump() if hasattr(intel, "model_dump") else intel
        if idata.get("owner_faction") == faction_id or idata.get("source_faction") == faction_id:
            spy["intel_reports"].append({
                "intel_id": idata.get("intel_id", ""),
                "target_name": idata.get("target_name") or idata.get("title", ""),
                "content": idata.get("content") or idata.get("description", ""),
                "round": idata.get("round", 0),
                "reliability": idata.get("reliability", "未知"),
            })
    for false_intel in (_world_state.planted_false_intel or []):
        fi = false_intel.model_dump() if hasattr(false_intel, "model_dump") else false_intel
        if fi.get("owner_faction") == faction_id:
            spy["false_intel_planted"].append({
                "target_faction": fi.get("target_faction", ""),
                "content": fi.get("content", ""),
                "round": fi.get("round", 0),
            })

    # ===== 5. 物资 =====
    resources: dict = {
        "treasury": faction.treasury,
        "grain": faction.grain,
        "arms": faction.arms,
        "horses": faction.horses,
        "territory_count": len(owner_tiles),
        "workshops": [],
        "granaries": [],
        "trade_routes": [],
        "sea_related": [],
    }
    # 工坊/粮仓/军械所/马场 — 从建筑注册表 + 地块建筑
    for tid, t in _world_state.tiles.items():
        if t.faction_id != faction_id:
            continue
        bld = t.buildings or {}
        for bid, b in bld.items():
            btype = b.building_type if hasattr(b, "building_type") else b.get("building_type", "")
            blevel = b.level if hasattr(b, "level") else b.get("level", 1)
            entry = {
                "building_id": bid,
                "tile_id": tid,
                "tile_name": t.tile_name,
                "type": str(btype),
                "level": blevel,
            }
            if btype == "workshop":
                resources["workshops"].append(entry)
            elif btype == "granary":
                resources["granaries"].append(entry)
    # 建筑注册表
    for bid, b in _world_state.building_registry.items():
        if b.faction_id != faction_id:
            continue
        btype = b.building_type if hasattr(b, "building_type") else b.get("building_type", "")
        if btype == "workshop":
            tile = _world_state.tiles.get(b.tile_id)
            resources["workshops"].append({
                "building_id": bid,
                "tile_id": b.tile_id,
                "tile_name": tile.tile_name if tile else b.tile_id,
                "type": "workshop",
                "level": b.level if hasattr(b, "level") else b.get("level", 1),
            })
    # 通商路线
    for route in (_world_state.trade_routes or []):
        rdata = route.model_dump() if hasattr(route, "model_dump") else route
        a_id = rdata.get("faction_a", "")
        b_id = rdata.get("faction_b", "")
        if faction_id in (a_id, b_id):
            other_id = b_id if a_id == faction_id else a_id
            other_f = _world_state.factions.get(other_id)
            resources["trade_routes"].append({
                "route_id": rdata.get("route_id", ""),
                "partner": other_f.name if other_f else other_id,
                "active": rdata.get("active", True),
                "income": rdata.get("income", 0),
            })
    # 海策/码头
    for tid, t in _world_state.tiles.items():
        if t.faction_id != faction_id:
            continue
        bld = t.buildings or {}
        for bid, b in bld.items():
            btype = b.building_type if hasattr(b, "building_type") else b.get("building_type", "")
            if btype == "dock":
                resources["sea_related"].append({
                    "type": "dock",
                    "building_id": bid,
                    "tile_id": tid,
                    "tile_name": t.tile_name,
                    "level": b.level if hasattr(b, "level") else b.get("level", 1),
                })
        if t.is_port:
            has_dock = any(
                b.building_type == "dock" if hasattr(b, "building_type") else b.get("building_type") == "dock"
                for b in bld.values()
            )
            if not has_dock:
                resources["sea_related"].append({
                    "type": "port_undeveloped",
                    "tile_id": tid,
                    "tile_name": t.tile_name,
                    "level": 0,
                })

    return ApiResponse.success({
        "faction_id": faction_id,
        "faction_name": faction.name,
        "round": _world_state.current_round,
        "year": _world_state.current_year,
        "season": str(_world_state.current_season),
        "military": military,
        "diplomacy": diplomacy,
        "civil": civil,
        "spy": spy,
        "resources": resources,
    })
    """获取势力俘虏列表"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    prisoners = [
        p.model_dump() for pid, p in _world_state.prisoners.items()
        if p.held_by == faction_id
    ]
    return ApiResponse.success({"faction_id": faction_id, "prisoners": prisoners, "count": len(prisoners)})


# ============================================================
# API 端点 - 行军/战斗（系统1）
# ============================================================

@app.post("/api/march/resolve")
async def resolve_march_endpoint(request: dict):
    """行军/战斗结算（支持粮草参数）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.settle_engine import MarchEngine
        engine = MarchEngine(_world_state)
        result = engine.resolve_march(
            from_tile=request.get("from_tile", ""),
            to_tile=request.get("to_tile", ""),
            troops=request.get("troops", 0),
            attacker_faction=request.get("attacker_faction") or request.get("faction_id", ""),
            grain=request.get("grain", 0),
        )
        if isinstance(result, dict):
            return ApiResponse.success(result) if result.get("success") else ApiResponse.bad_request(result.get("message", "行军失败"))
        return ApiResponse.success({"result": result})
    except Exception as e:
        logger.error(f"行军结算异常: {e}", exc_info=True)
        return ApiResponse.server_error(f"行军结算失败: {str(e)}")


@app.post("/api/march/path")
async def get_march_path(request: dict):
    """获取行军路径（简化为直达）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from_tile = request.get("from_tile", "")
    to_tile = request.get("to_tile", "")
    from_t = _world_state.get_tile(from_tile)
    to_t = _world_state.get_tile(to_tile)
    if not from_t or not to_t:
        return ApiResponse.error(404, "地块不存在")
    
    terrain_mult = {"mountain": 2.0, "water": 1.5, "desert": 1.3}.get(
        to_t.tile_type.value if hasattr(to_t.tile_type, 'value') else str(to_t.tile_type), 1.0)
    
    return ApiResponse.success({
        "path": [from_tile, to_tile],
        "turns_required": max(1, int(terrain_mult)),
        "grain_cost_estimate": int(request.get("troops", 100) * 0.02 * terrain_mult),
    })


@app.get("/api/march/neighbors/{tile_id}")
async def get_attackable_neighbors(tile_id: str, faction_id: str = ""):
    """获取地块周围可攻击的相邻地块"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import MarchEngine
    engine = MarchEngine(_world_state)
    neighbors = engine.get_attackable_neighbors(tile_id, faction_id)
    return ApiResponse.success({
        "tile_id": tile_id,
        "neighbors": neighbors,
        "count": len(neighbors),
    })


# ============================================================
# API 端点 - 征伐AI（宣战/战争状态/全链路）
# ============================================================

@app.post("/api/war/declare")
async def declare_war_endpoint(request: dict):
    """
    正式宣战 — 触发全链路征伐AI联动

    接收宣战请求后：
    ① 全局外交AI判定所有NPC势力倾向
    ② 敌方军事AI生成反制战术
    ③ 民生治理AI调整双方内政
    ④ 叛乱灾害AI评估动乱风险
    
    返回全链路AI推演摘要
    """
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    
    attacker = request.get("attacker_faction", "") or request.get("faction_id", "")
    defender = request.get("defender_faction", "") or request.get("target_faction", "")
    reason = request.get("reason", "兴兵讨伐")
    casus_belli = request.get("casus_belli", "conquest")
    war_goal_tiles = request.get("war_goal_tiles", [])
    
    if not attacker or not defender:
        return ApiResponse.bad_request("请指定攻方和守方势力")
    
    atk_faction = _world_state.factions.get(attacker)
    dff_faction = _world_state.factions.get(defender)
    
    if not atk_faction or not dff_faction:
        return ApiResponse.bad_request("势力不存在")
    
    if not atk_faction.is_alive or not dff_faction.is_alive:
        return ApiResponse.bad_request("势力已覆灭")

    try:
        # 1. 设置外交关系为战争
        from server.core.settle_engine import MarchEngine
        march = MarchEngine(_world_state)
        march._ensure_war_stance(attacker, defender)

        # 2. 清理同盟/附庸关系
        key = _world_state.relation_key(attacker, defender)
        rel = _world_state.relations.get(key)
        if rel:
            rel.alliance_active = False
            rel.trade_active = False
            rel.coalition_active = False
            # 附庸关系破裂
            if rel.vassal_suzerain:
                rel.vassal_suzerain = None

        # 3. 写入宣战事件
        _world_state.events_log.append({
            "round": _world_state.current_round,
            "year": getattr(_world_state, 'current_year', 1),
            "month": getattr(_world_state, 'current_month', 1),
            "event_type": "war_declaration",
            "severity": "critical",
            "attacker": attacker,
            "defender": defender,
            "narrative": f"{atk_faction.name}正式向{dff_faction.name}宣战！理由：{reason}",
            "reason": reason,
        })

        # 4. 触发征伐全链路AI（如果有LLM客户端）
        war_result = {
            "status": "war_declared",
            "attacker": attacker,
            "attacker_name": atk_faction.name,
            "defender": defender,
            "defender_name": dff_faction.name,
            "reason": reason,
            "casus_belli": casus_belli,
            "war_goal_tiles": war_goal_tiles,
            "diplomacy_ai": None,
            "military_ai": None,
            "civil_ai": None,
            "rebellion_ai": None,
        }

        # 异步触发AI联动（如果LLM客户端可用）
        if _round_engine and hasattr(_round_engine, '_war_orchestrator'):
            orchestrator = _round_engine._war_orchestrator
            if orchestrator:
                import asyncio
                try:
                    cb_config = {}
                    try:
                        from server.war.casus_belli import CasusBelli, CB_CONFIG
                        cb_enum = CasusBelli(casus_belli)
                        cb_config = CB_CONFIG.get(cb_enum, {})
                    except (ValueError, KeyError, ImportError):
                        pass

                    ctx = await asyncio.wait_for(
                        orchestrator.on_war_declared(
                            attacker, defender, reason,
                            casus_belli=casus_belli,
                            war_goal_tiles=war_goal_tiles,
                            can_seize_territory=cb_config.get("can_seize_territory", True),
                            can_demand_tribute=cb_config.get("can_demand_tribute", False),
                            can_enforce_vassal=cb_config.get("can_enforce_vassal", False),
                            war_score_multiplier=cb_config.get("war_score_multiplier", 1.0),
                        ),
                        timeout=30.0,
                    )
                    war_result["war_id"] = ctx.war_id
                    war_result["diplomacy_ai"] = {
                        "attacker_allies": ctx.attacker_allies,
                        "defender_allies": ctx.defender_allies,
                        "backstabbers": ctx.backstabbers,
                        "neutrals": ctx.neutrals,
                    }
                    war_result["military_ai"] = ctx.military_counter
                    war_result["civil_ai"] = ctx.civil_adjustments
                    war_result["rebellion_ai"] = ctx.rebellion_risks
                    war_result["war_score"] = ctx.get_war_score().get_status()
                except asyncio.TimeoutError:
                    war_result["ai_timeout"] = True
                except Exception as e:
                    logger.warning(f"征伐AI联动非致命错误: {e}")

        return ApiResponse.success(war_result)

    except Exception as e:
        logger.error(f"宣战失败: {e}", exc_info=True)
        return ApiResponse.server_error(f"宣战失败: {str(e)}")


@app.get("/api/war/status")
async def get_war_status(attacker: str = "", defender: str = ""):
    """获取两方之间的战争状态摘要"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    round_engine = getattr(app.state, 'round_engine', None)
    wars = []

    if _round_engine and hasattr(_round_engine, '_war_orchestrator'):
        orchestrator = _round_engine._war_orchestrator
        if orchestrator:
            for war_id, ctx in orchestrator.active_wars.items():
                if (not attacker or ctx.attacker_faction == attacker or
                    ctx.defender_faction == attacker):
                    if (not defender or ctx.defender_faction == defender or
                        ctx.attacker_faction == defender):
                        wars.append({
                            "war_id": war_id,
                            "attacker": ctx.attacker_faction,
                            "defender": ctx.defender_faction,
                            "stage": ctx.stage.value,
                            "declared_round": ctx.declared_round,
                            "duration": _world_state.current_round - ctx.declared_round,
                            "casus_belli": ctx.casus_belli,
                            "casus_belli_name": ctx.casus_belli_name,
                            "war_score": ctx.get_war_score().get_status(),
                            "attacker_allies": ctx.attacker_allies,
                            "defender_allies": ctx.defender_allies,
                            "backstabbers": ctx.backstabbers,
                            "battles_this_war": len(ctx.battle_settlements),
                            "territory_changes": len(ctx.territory_changes),
                            "recent_stratagems": [
                                {"type": s.get("type"), "narrative": s.get("narrative")}
                                for s in ctx.stratagem_actions[-5:]
                            ],
                        })

    return ApiResponse.success({
        "active_wars": wars,
        "total_active": len(wars),
    })


@app.get("/api/war/active")
async def get_active_wars():
    """获取所有活跃战争列表（简化版，供前端轮询）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    active = []

    if _round_engine and hasattr(_round_engine, '_war_orchestrator'):
        orchestrator = _round_engine._war_orchestrator
        if orchestrator:
            # 使用新的摘要方法获取含战争分数的完整列表
            try:
                active = orchestrator.get_all_active_wars_summary()
            except Exception:
                # 回退到旧格式
                for war_id, ctx in orchestrator.active_wars.items():
                    atk_name = (_world_state.factions.get(ctx.attacker_faction) or
                                type('', (), {'name': ctx.attacker_faction})()).name
                    dff_name = (_world_state.factions.get(ctx.defender_faction) or
                                type('', (), {'name': ctx.defender_faction})()).name
                    active.append({
                        "war_id": war_id,
                        "attacker": ctx.attacker_faction,
                        "attacker_name": atk_name,
                        "defender": ctx.defender_faction,
                        "defender_name": dff_name,
                        "stage": ctx.stage.value,
                        "round": ctx.declared_round,
                        "allies_attacker": len(ctx.attacker_allies),
                        "allies_defender": len(ctx.defender_allies),
                        "backstabbers": len(ctx.backstabbers),
                    })

    return ApiResponse.success({
        "wars": active,
        "count": len(active),
    })


# ============================================================
# 战争系统 v3.0：Casus Belli / 战争分数 / 和平谈判
# ============================================================

@app.get("/api/war/cb-list")
async def get_cb_list(faction_id: str = "", target_faction_id: str = ""):
    """获取对目标势力可用的宣战理由列表"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    if not faction_id or not target_faction_id:
        return ApiResponse.bad_request("请提供 faction_id 和 target_faction_id")

    try:
        from server.war.casus_belli import get_available_cb_list
        cb_list = get_available_cb_list(_world_state, faction_id, target_faction_id)
        return ApiResponse.success({"cb_list": cb_list, "target": target_faction_id})
    except ImportError as e:
        return ApiResponse.server_error(f"CB系统加载失败: {e}")
    except Exception as e:
        logger.error(f"获取CB列表失败: {e}", exc_info=True)
        return ApiResponse.server_error(str(e))


@app.get("/api/war/score")
async def get_war_score(war_id: str = "", attacker: str = "", defender: str = ""):
    """获取指定战争的分数与状态"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    if not _round_engine or not hasattr(_round_engine, '_war_orchestrator'):
        return ApiResponse.success({"war_score": None, "message": "无战争编排器"})

    orchestrator = _round_engine._war_orchestrator
    if not orchestrator:
        return ApiResponse.success({"war_score": None})

    ctx = None
    if war_id:
        ctx = orchestrator.get_war_context_by_id(war_id)
    elif attacker and defender:
        ctx = orchestrator.get_war_context(attacker, defender)

    if not ctx:
        return ApiResponse.success({"war_score": None, "message": "未找到活跃战争"})

    ws = ctx.get_war_score()
    return ApiResponse.success({
        "war_id": ctx.war_id,
        "attacker": ctx.attacker_faction,
        "defender": ctx.defender_faction,
        "casus_belli": ctx.casus_belli,
        "casus_belli_name": ctx.casus_belli_name,
        "war_score": ws.get_status(),
        "recent_events": ws.get_recent_events(15),
    })


@app.post("/api/war/peace/propose")
async def propose_peace_endpoint(request: dict):
    """发起和平提议"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    war_id = request.get("war_id", "")
    terms = request.get("terms", [])
    tile_ids = request.get("tile_ids", [])
    reparation_amount = request.get("reparation_amount", 0)
    is_from_attacker = request.get("is_from_attacker", True)

    if not war_id or not terms:
        return ApiResponse.bad_request("请提供 war_id 和 terms")

    if not _round_engine or not hasattr(_round_engine, '_war_orchestrator'):
        return ApiResponse.server_error("无战争编排器")

    orchestrator = _round_engine._war_orchestrator
    if not orchestrator:
        return ApiResponse.server_error("无战争编排器")

    ctx = orchestrator.get_war_context_by_id(war_id)
    if not ctx:
        return ApiResponse.bad_request("未找到该战争")

    try:
        from server.war.peace_negotiation import PeaceNegotiationEngine
        engine = PeaceNegotiationEngine(_world_state)
        ws = ctx.get_war_score()

        # 构造提议
        proposal = engine.propose_peace(
            war_score_tracker=ws,
            terms=terms,
            is_from_attacker=is_from_attacker,
            tile_ids=tile_ids,
            reparation_amount=reparation_amount,
        )

        # AI 评估
        receiving_id = ctx.defender_faction if is_from_attacker else ctx.attacker_faction
        offering_id = ctx.attacker_faction if is_from_attacker else ctx.defender_faction
        accepted, reason, score = engine.evaluate_acceptance(
            proposal, ws.get_status(), offering_id, receiving_id,
        )

        if accepted:
            # 执行和平
            result = engine.execute_peace(
                proposal, ctx.attacker_faction, ctx.defender_faction,
            )
            # 结束战争
            orchestrator.end_war(ctx.attacker_faction, ctx.defender_faction)
            return ApiResponse.success({
                "accepted": True,
                "reason": reason,
                "acceptance_score": score,
                "execution": result,
            })
        else:
            return ApiResponse.success({
                "accepted": False,
                "reason": reason,
                "acceptance_score": score,
            })

    except ImportError as e:
        return ApiResponse.server_error(f"和平谈判系统加载失败: {e}")
    except Exception as e:
        logger.error(f"和平提议失败: {e}", exc_info=True)
        return ApiResponse.server_error(str(e))


@app.post("/api/war/peace/available-terms")
async def get_available_peace_terms(request: dict):
    """获取当前战争分数下可用和平条款"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    war_id = request.get("war_id", "")
    if not war_id:
        return ApiResponse.bad_request("请提供 war_id")

    orchestrator = _round_engine._war_orchestrator if (
        _round_engine and hasattr(_round_engine, '_war_orchestrator')
    ) else None
    if not orchestrator:
        return ApiResponse.server_error("无战争编排器")

    ctx = orchestrator.get_war_context_by_id(war_id)
    if not ctx:
        return ApiResponse.bad_request("未找到该战争")

    try:
        from server.war.peace_negotiation import PeaceNegotiationEngine
        engine = PeaceNegotiationEngine(_world_state)
        ws = ctx.get_war_score()
        available = engine.get_available_terms(
            ws,
            can_seize_territory=ctx.can_seize_territory,
            can_demand_tribute=ctx.can_demand_tribute,
            can_enforce_vassal=ctx.can_enforce_vassal,
        )
        return ApiResponse.success({
            "war_id": war_id,
            "war_score": ws.get_status(),
            "available_terms": available,
        })
    except ImportError as e:
        return ApiResponse.server_error(f"和平谈判系统加载失败: {e}")
    except Exception as e:
        logger.error(f"获取和平条款失败: {e}", exc_info=True)
        return ApiResponse.server_error(str(e))


@app.post("/api/war/peace/evaluate")
async def evaluate_peace_endpoint(request: dict):
    """预评估和平提议是否会被接受（不执行）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    war_id = request.get("war_id", "")
    terms = request.get("terms", [])
    is_from_attacker = request.get("is_from_attacker", True)
    tile_ids = request.get("tile_ids", [])

    if not war_id or not terms:
        return ApiResponse.bad_request("请提供 war_id 和 terms")

    orchestrator = _round_engine._war_orchestrator if (
        _round_engine and hasattr(_round_engine, '_war_orchestrator')
    ) else None
    if not orchestrator:
        return ApiResponse.server_error("无战争编排器")

    ctx = orchestrator.get_war_context_by_id(war_id)
    if not ctx:
        return ApiResponse.bad_request("未找到该战争")

    try:
        from server.war.peace_negotiation import PeaceNegotiationEngine
        engine = PeaceNegotiationEngine(_world_state)
        ws = ctx.get_war_score()
        proposal = engine.propose_peace(ws, terms, is_from_attacker, tile_ids)
        receiving_id = ctx.defender_faction if is_from_attacker else ctx.attacker_faction
        offering_id = ctx.attacker_faction if is_from_attacker else ctx.defender_faction
        accepted, reason, score = engine.evaluate_acceptance(
            proposal, ws.get_status(), offering_id, receiving_id,
        )
        return ApiResponse.success({
            "accepted": accepted,
            "reason": reason,
            "acceptance_score": score,
        })
    except Exception as e:
        logger.error(f"和平评估失败: {e}", exc_info=True)
        return ApiResponse.server_error(str(e))


# ============================================================
# 地图图层数据
# ============================================================

@app.get("/api/map/layers/data")
async def get_layers_data(faction_id: str = ""):
    """获取全量图层数据，供前端14层渲染系统使用

    单次返回：
    - tiles: 地块状态（驻防/灾害/建筑/归属）
    - fog_visible: 当前势力可见地块ID列表
    - march_routes: 活跃行军路线
    - supply_lines: 补给线
    - diplomacy: 外交关系连线（附庸/同盟/战争/贸易）
    - claims: 法理宣称地块
    - water_routes: 水域航道
    - buildings: 城建建筑
    - disasters: 灾害数据
    """
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    ws = _world_state
    player_fid = faction_id or ws.player_faction_id

    # 1. 地块状态聚合
    tiles_data = {}
    for tid, t in ws.tiles.items():
        tiles_data[tid] = {
            "faction_id": t.faction_id,
            "troops": t.troops,
            "garrison_resting": getattr(t, 'garrison_resting', False),
            "fortification": getattr(t, 'fortification', 0),
            "granary": getattr(t, 'granary', 0),
            "stable": getattr(t, 'stable', 0),
            "armory": getattr(t, 'armory', 0),
            "is_capital": t.is_capital,
            "is_port": t.is_port,
            "disasters": [d.value if hasattr(d, 'value') else str(d) for d in (getattr(t, 'disasters', []) or [])],
            "morale": getattr(t, 'morale', 50),
            "population": t.population,
        }

    # 2. 迷雾可见地块
    fog_visible = []
    for tid, t in ws.tiles.items():
        if t.faction_id == player_fid:
            fog_visible.append(tid)
        # 己方地块邻接也可见
        if t.faction_id == player_fid:
            for nid in getattr(t, 'neighbors', []) or []:
                if nid in ws.tiles and nid not in fog_visible:
                    fog_visible.append(nid)
        # 谍报渗透可见
        from server.core.settle_engine import SpyEngine
        spy = SpyEngine(ws)
        spy_nets = getattr(ws, 'spy_networks', {}) or {}
        if tid in spy_nets:
            fog_visible.append(tid)

    # 3. 行军路线（从 events_log 中提取）
    march_routes = []
    for evt in (getattr(ws, 'events_log', []) or [])[-50:]:
        if evt.get('event_type') in ('march', 'army_mobilized', 'battle'):
            path = evt.get('path') or evt.get('march_path') or []
            if path and len(path) >= 2:
                march_routes.append({
                    "id": f"march_{evt.get('round', 0)}_{len(march_routes)}",
                    "type": "retreat" if "retreat" in str(evt.get('narrative', '')).lower() else "march",
                    "path": path,
                    "factionId": evt.get('faction_id', ''),
                    "color": None,
                })

    # 4. 补给线（从 trade_routes 或 war orchestrator 中提取）
    supply_lines = []
    if _round_engine and hasattr(_round_engine, '_war_orchestrator'):
        orch = _round_engine._war_orchestrator
        if orch:
            for war_id, ctx in (getattr(orch, 'active_wars', {}) or {}).items():
                for sl in getattr(ctx, 'supply_lines', []) or []:
                    supply_lines.append({
                        "id": f"supply_{war_id}_{len(supply_lines)}",
                        "path": sl.get('path', []) if isinstance(sl, dict) else [],
                        "broken": sl.get('broken', False) if isinstance(sl, dict) else False,
                    })

    # 5. 外交关系
    diplomacy = []
    # 附庸
    vassals = getattr(ws, 'vassal_relations', {}) or {}
    for vassal, suzerain in vassals.items():
        diplomacy.append({"from": suzerain, "to": vassal, "type": "vassal"})
    # 同盟/战争/贸易
    relations = getattr(ws, 'relations', {}) or {}
    for key, rel in relations.items():
        parts = key.split('_', 1)
        a, b = parts[0], parts[1] if len(parts) > 1 else ''
        if hasattr(rel, 'stance'):
            stance = rel.stance.value if hasattr(rel.stance, 'value') else str(rel.stance)
            if stance == 'alliance':
                diplomacy.append({"from": a, "to": b, "type": "alliance"})
            elif stance == 'war':
                diplomacy.append({"from": a, "to": b, "type": "war"})
        if hasattr(rel, 'trade_active') and rel.trade_active:
            diplomacy.append({"from": a, "to": b, "type": "trade"})

    # 6. 法理宣称
    claims = []
    for tid, t in ws.tiles.items():
        # 玩家势力曾拥但已失去的地块 = 法理宣称
        old_fid = getattr(t, 'original_faction_id', None) or getattr(t, 'claim_by_faction', None)
        if old_fid == player_fid and t.faction_id != player_fid:
            claims.append(tid)

    # 7. 水域航道
    water_routes = []
    port_tiles = [tid for tid, t in ws.tiles.items() if t.is_port]
    for port_tid in port_tiles:
        water_routes.append({"id": f"water_{port_tid}", "path": [port_tid]})

    # 8. 城建建筑
    buildings = {}
    for tid, t in ws.tiles.items():
        bld = []
        f = getattr(t, 'fortification', 0)
        g = getattr(t, 'granary', 0)
        s = getattr(t, 'stable', 0)
        a = getattr(t, 'armory', 0)
        if f > 0: bld.append({"type": "wall", "level": min(5, max(1, f // 3))})
        if g > 0: bld.append({"type": "granary", "level": min(5, max(1, g // 2))})
        if s > 0: bld.append({"type": "stable", "level": min(5, max(1, s // 2))})
        if a > 0: bld.append({"type": "workshop", "level": min(5, max(1, a // 2))})
        if t.is_port: bld.append({"type": "port", "level": 1})
        if bld: buildings[tid] = bld

    # 9. 灾害数据
    disasters = {}
    for tid, t in ws.tiles.items():
        d_list = getattr(t, 'disasters', []) or []
        if d_list:
            disasters[tid] = [
                {
                    "type": d.value if hasattr(d, 'value') else str(d),
                    "severity": 0.6,
                }
                for d in d_list
            ]
    # 叛军所在的地块标记为 rebellion
    rebels = getattr(ws, 'rebel_armies', {}) or {}
    for rid, r in rebels.items():
        rtid = r.tile_id if hasattr(r, 'tile_id') else r.get('tile_id', '')
        if rtid and rtid in ws.tiles:
            if rtid not in disasters:
                disasters[rtid] = []
            disasters[rtid].append({"type": "rebellion", "severity": 0.7})

    return ApiResponse.success({
        "tiles": tiles_data,
        "fog_visible": fog_visible,
        "march_routes": march_routes,
        "supply_lines": supply_lines,
        "diplomacy": diplomacy,
        "claims": claims,
        "water_routes": water_routes,
        "buildings": buildings,
        "disasters": disasters,
    })









# ============================================================
# API 端点 - 征兵/军事
# ============================================================

@app.get("/api/military/recruit-info/{tile_id}")
async def get_recruit_info(tile_id: str, faction_id: str = ""):
    """获取地块征兵信息（成本、限制等）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    tile = _world_state.tiles.get(tile_id)
    if not tile:
        return ApiResponse.not_found(f"地块 {tile_id} 不存在")

    faction = _world_state.factions.get(faction_id) if faction_id else None
    cost_per = 3 if tile.tile_type.value in ('city', 'port') else 2
    max_recruit = int(tile.population * 0.15)
    max_garrison = 5000 + tile.fortification * 2000
    arms_needed = max(0, max_recruit // 3)

    # 检查马场
    has_stable = False
    if faction:
        for t in _world_state.get_faction_tiles(faction_id):
            if getattr(t, 'stable', 0) > 0:
                has_stable = True
                break

    return ApiResponse.success({
        "tile_id": tile_id,
        "tile_name": tile.tile_name,
        "population": tile.population,
        "troops": tile.troops,
        "morale": tile.morale,
        "fortification": tile.fortification,
        "max_recruit": max_recruit,
        "max_garrison": max_garrison,
        "cost_per_soldier": cost_per,
        "arms_available": faction.arms if faction else 0,
        "arms_needed_for_max": arms_needed,
        "has_stable": has_stable,
        "horses": faction.horses if faction else 0,
        "treasury": faction.treasury if faction else 0,
        "grain": faction.grain if faction else 0,
    })


# ============================================================
# API 端点 - 藩镇（系统9）
# ============================================================

@app.get("/api/vassal/check/{faction_id}")
async def check_vassal_rebellion(faction_id: str):
    """检查藩镇叛乱风险"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.settle_engine import CourtEngine
    engine = CourtEngine(_world_state)
    result = engine.check_vassal_rebellion(faction_id)
    return ApiResponse.success({
        "faction_id": faction_id,
        "rebellion_risk": result,
    })


# ============================================================
# API 端点 - 工坊经济（系统6）
# ============================================================

@app.get("/api/economy/workshops/{faction_id}")
async def get_workshops(faction_id: str):
    """获取势力工坊信息"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    tiles = _world_state.get_faction_tiles(faction_id)
    workshops = []
    for t in tiles:
        ws = []
        if t.granary > 0:
            ws.append({"type": "granary", "level": t.granary})
        if t.water_works > 0:
            ws.append({"type": "water_works", "level": t.water_works})
        if t.clinic > 0:
            ws.append({"type": "clinic", "level": t.clinic})
        if t.is_port:
            ws.append({"type": "port", "level": 1})
        if getattr(t, 'stable', 0) > 0:
            ws.append({"type": "stable", "level": getattr(t, 'stable', 0)})
        if getattr(t, 'armory', 0) > 0:
            ws.append({"type": "armory", "level": getattr(t, 'armory', 0)})
        if ws:
            workshops.append({"tile_id": t.tile_id, "tile_name": t.tile_name, "workshops": ws})
    
    return ApiResponse.success({
        "faction_id": faction_id,
        "workshops": workshops,
        "total": sum(len(w["workshops"]) for w in workshops),
    })


# ============================================================
# API 端点 - 结局/统计（3.3 四大结局系统）
# ============================================================

@app.get("/api/game/ending")
async def get_ending():
    """获取结局信息（增强版：含演出数据、对话、渐进提示）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    
    ending = _check_ending()
    player = _world_state.get_player_faction()
    stats = {}
    if player:
        player_tiles = _world_state.get_faction_tiles(player.faction_id)
        player_conquered = [c for c in _world_state.tile_changes if c.get("new_faction_id") == player.faction_id]
        player_lost = [c for c in _world_state.tile_changes if c.get("old_faction_id") == player.faction_id]
        stats = {
            "total_rounds": _world_state.current_round,
            "final_treasury": player.treasury,
            "final_troops": player.total_troops,
            "final_population": player.total_population,
            "tiles_held": len(player_tiles),
            "tiles_conquered": len(player_conquered),
            "tiles_lost": len(player_lost),
            "battles_fought": sum(1 for e in _world_state.events_log if e.get("event_type") == "battle"),
            "officials_count": sum(1 for o in _world_state.officials.values() if o.faction_id == player.faction_id),
        }
    return ApiResponse.success({
        "ending": ending,
        "statistics": stats,
        "governance_logs": _world_state.governance_logs[-50:] if hasattr(_world_state, 'governance_logs') else [],
    })


@app.get("/api/game/endings/config")
async def get_endings_config():
    """获取所有结局的配置数据（供前端演出使用）"""
    return ApiResponse.success({
        "endings": export_ending_configs(),
        "tier_info": {
            "bad": {"label": "霸业陨落", "description": "众叛亲离，霸业成空", "color": "#8B0000"},
            "normal": {"label": "偏安存续", "description": "山河破碎，独善其身", "color": "#B8860B"},
            "good": {"label": "天下归心", "description": "一统四海，天命所归", "color": "#DAA520"},
            "true": {"label": "盛世新朝", "description": "万世太平，光耀千古", "color": "#FFD700"},
        },
    })


@app.get("/api/game/endings/progress")
async def get_endings_progress():
    """获取所有结局的当前进度状态（每个结局的触发条件满足情况）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    
    engine = get_ending_engine()
    if not engine:
        return ApiResponse.server_error("结局引擎未初始化")
    
    progress = engine.get_all_ending_progress()
    return ApiResponse.success(progress)


@app.get("/api/game/endings/history")
async def get_endings_history():
    """获取结局达成历史"""
    engine = get_ending_engine()
    if not engine:
        return ApiResponse.success({"history": []})
    
    return ApiResponse.success({
        "history": engine.get_ending_history(),
    })


@app.get("/api/game/endings/legacy")
async def get_endings_legacy():
    """获取传承数据（新周目可用）"""
    engine = get_ending_engine()
    if not engine:
        return ApiResponse.success({"legacy": {}})
    
    return ApiResponse.success({
        "legacy": engine.get_legacy_data(),
    })


# ============================================================
# API 端点 - 地盘/领土
# ============================================================

@app.get("/api/territory/changes/{faction_id}")
async def get_territory_changes(faction_id: str, limit: int = 50):
    """获取势力地盘变更记录"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    # 筛选该势力相关的地盘变更
    all_changes = _world_state.tile_changes
    faction_changes = [
        c for c in all_changes
        if c.get("old_faction_id") == faction_id or c.get("new_faction_id") == faction_id
    ]

    # 按回合倒序
    faction_changes.sort(key=lambda x: x.get("round", 0), reverse=True)
    faction_changes = faction_changes[:limit]

    # 统计
    gained = [c for c in faction_changes if c.get("new_faction_id") == faction_id]
    lost = [c for c in faction_changes if c.get("old_faction_id") == faction_id and c.get("new_faction_id") != faction_id]

    return ApiResponse.success({
        "faction_id": faction_id,
        "total_changes": len(faction_changes),
        "gained": len(gained),
        "lost": len(lost),
        "changes": faction_changes,
    })


@app.get("/api/territory/summary/{faction_id}")
async def get_territory_summary(faction_id: str):
    """获取势力领土摘要"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    faction = _world_state.factions.get(faction_id)
    if not faction:
        return ApiResponse.not_found(f"势力 {faction_id} 不存在")

    tiles = _world_state.get_faction_tiles(faction_id)
    capital = next((t for t in tiles if t.is_capital), None)

    # 按地区分组
    regions: dict[str, list] = {}
    for t in tiles:
        region = t.region or "未知"
        if region not in regions:
            regions[region] = []
        regions[region].append({
            "tile_id": t.tile_id,
            "tile_name": t.tile_name,
            "tile_type": t.tile_type.value if hasattr(t.tile_type, 'value') else str(t.tile_type),
            "population": t.population,
            "troops": t.troops,
            "fortification": t.fortification,
            "is_capital": t.is_capital,
            "morale": t.morale,
        })

    # 最近地盘变更
    recent_changes = [
        c for c in _world_state.tile_changes
        if c.get("old_faction_id") == faction_id or c.get("new_faction_id") == faction_id
    ][-20:]

    return ApiResponse.success({
        "faction_id": faction_id,
        "faction_name": faction.name,
        "total_tiles": len(tiles),
        "total_population": sum(t.population for t in tiles),
        "total_troops": sum(t.troops for t in tiles),
        "capital": {
            "tile_id": capital.tile_id,
            "tile_name": capital.tile_name,
        } if capital else None,
        "regions": regions,
        "recent_changes": recent_changes,
        "borders": [],  # 预留边境数据
    })


@app.get("/api/territory/global-changes")
async def get_global_territory_changes(round_num: int = 0, limit: int = 30):
    """获取全局地盘变更（最近N回合）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    changes = _world_state.tile_changes
    if round_num > 0:
        changes = [c for c in changes if c.get("round") == round_num]

    changes.sort(key=lambda x: x.get("round", 0), reverse=True)
    changes = changes[:limit]

    # 按回合分组
    grouped: dict[int, list] = {}
    for c in changes:
        r = c.get("round", 0)
        if r not in grouped:
            grouped[r] = []
        grouped[r].append(c)

    return ApiResponse.success({
        "total_changes": len(_world_state.tile_changes),
        "recent_changes": changes,
        "grouped_by_round": grouped,
    })


@app.get("/api/territory/tile-history/{tile_id}")
async def get_tile_history(tile_id: str):
    """获取单个地块的归属变更历史"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    tile = _world_state.tiles.get(tile_id)
    if not tile:
        return ApiResponse.not_found(f"地块 {tile_id} 不存在")

    changes = [c for c in _world_state.tile_changes if c.get("tile_id") == tile_id]
    changes.sort(key=lambda x: x.get("round", 0))

    current_faction = ""
    if tile.faction_id:
        f = _world_state.factions.get(tile.faction_id)
        current_faction = f.name if f else tile.faction_id

    return ApiResponse.success({
        "tile_id": tile_id,
        "tile_name": tile.tile_name,
        "current_faction_id": tile.faction_id,
        "current_faction_name": current_faction,
        "change_count": len(changes),
        "changes": changes,
    })


# ============================================================
# API 端点 - 面板数据（royal/sea/medical/culture）
# ============================================================

@app.get("/api/panel/royal/{faction_id}")
async def get_royal_panel(faction_id: str):
    """皇子宗室面板数据"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    faction = _world_state.factions.get(faction_id)
    if not faction:
        return ApiResponse.not_found(f"势力 {faction_id} 不存在")

    heirs = getattr(faction, 'heirs', []) or []
    ruler_name = faction.ruler_name or faction.name
    ruler_age = getattr(faction, 'ruler_age', 40)

    # 计算继承风险
    grown_heirs = [h for h in heirs if h.get('age', 0) >= 16]
    risk_level = "low"
    if ruler_age > 55 and not grown_heirs:
        risk_level = "high"
    elif ruler_age > 50 and len(grown_heirs) <= 1:
        risk_level = "medium"

    return ApiResponse.success({
        "faction_id": faction_id,
        "faction_name": faction.name,
        "ruler_name": ruler_name,
        "ruler_age": ruler_age,
        "heirs": heirs,
        "heir_count": len(heirs),
        "grown_heirs": len(grown_heirs),
        "succession_risk": risk_level,
        "heir_designated": bool(getattr(faction, 'heir_designated', False)),
    })


@app.get("/api/panel/medical/{faction_id}")
async def get_medical_panel(faction_id: str):
    """疲病伤病面板数据"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    tiles = _world_state.get_faction_tiles(faction_id)
    if not tiles:
        return ApiResponse.not_found(f"势力 {faction_id} 无领地")

    clinics = sum(t.clinic or 0 for t in tiles)
    active_disasters = set()
    total_disaster_count = 0
    for t in tiles:
        for d in (t.disasters or []):
            active_disasters.add(d.value if hasattr(d, 'value') else str(d))
            total_disaster_count += 1

    # 瘟疫风险计算
    base_plague = total_disaster_count * 15 + max(0, 20 - clinics * 3)
    # 夏季瘟疫风险提高
    if _world_state.current_season.value == "夏":
        base_plague += 10
    plague_risk = min(100, base_plague)

    # 伤病率
    injury_rate = max(0, min(30, 10 - clinics * 2 + _world_state.disaster_index * 2))

    # 总伤病人数估算
    total_pop = sum(t.population for t in tiles)
    injured_count = int(total_pop * injury_rate / 100)

    return ApiResponse.success({
        "faction_id": faction_id,
        "clinics": clinics,
        "plague_risk": plague_risk,
        "injury_rate": injury_rate,
        "injured_population": injured_count,
        "active_disasters": list(active_disasters),
        "disaster_index": _world_state.disaster_index,
    })


@app.get("/api/panel/sea/{faction_id}")
async def get_sea_panel(faction_id: str):
    """海策远洋面板数据"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    tiles = _world_state.get_faction_tiles(faction_id)

    ports = sum(1 for t in tiles if t.is_port)
    port_tiles = [{"tile_id": t.tile_id, "tile_name": t.tile_name} for t in tiles if t.is_port]

    # 船队规模
    fleet_size = ports * 3
    # 贸易收入
    trade_income = ports * 80
    if _world_state.current_season.value == "冬":
        trade_income = int(trade_income * 0.5)
    elif _world_state.current_season.value == "夏":
        trade_income = int(trade_income * 1.25)

    # 航线数
    routes = min(ports, 5) if ports > 0 else 0

    # 港口建筑等级
    port_levels = {}
    for t in tiles:
        if t.is_port and t.fortification > 0:
            port_levels[t.tile_id] = t.fortification

    return ApiResponse.success({
        "faction_id": faction_id,
        "ports": ports,
        "port_tiles": port_tiles,
        "fleet_size": fleet_size,
        "trade_income": trade_income,
        "routes": routes,
        "port_levels": port_levels,
        "season": _world_state.current_season.value,
    })


@app.get("/api/panel/culture/{faction_id}")
async def get_culture_panel(faction_id: str):
    """民俗国史面板数据"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    # 年号
    era_name = "至正"
    year_label = f"至正{_world_state.current_year - 1340}年"

    # 收集该势力相关的重要事件
    faction_events = [
        e for e in _world_state.events_log
        if e.get("faction_id") == faction_id
    ]
    faction_events.sort(key=lambda x: x.get("round", 0), reverse=True)

    # 治理日志
    gov_logs = _world_state.governance_logs[-20:]

    # 国史数据
    history_count = len(_world_state.events_log)
    decrees_count = len(_world_state.decrees)
    battles_count = sum(1 for e in _world_state.events_log if e.get("event_type") == "battle")

    # 近期大事
    recent_events = [
        {
            "round": e.get("round", 0),
            "title": e.get("title", e.get("description", "")),
            "description": e.get("description", ""),
            "category": e.get("event_type", e.get("category", "")),
        }
        for e in faction_events[:20]
    ]

    return ApiResponse.success({
        "faction_id": faction_id,
        "era_name": era_name,
        "year_label": year_label,
        "current_round": _world_state.current_round,
        "current_year": _world_state.current_year,
        "current_season": _world_state.current_season.value,
        "history_count": history_count,
        "decrees_count": decrees_count,
        "battles_count": battles_count,
        "recent_events": recent_events,
        "governance_logs": gov_logs[-10:],
        "tile_changes_count": len(_world_state.tile_changes),
    })


# ============================================================
# API 端点 - 国史系统
# ============================================================

@app.get("/api/history/{faction_id}")
async def get_national_history(faction_id: str):
    """获取势力国史（所有历史事件、治理日志、圣旨记录）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    faction = _world_state.get_faction(faction_id)
    faction_name = faction.name if faction else faction_id

    # 收集该势力相关的所有事件
    faction_events = [
        e for e in _world_state.events_log
        if e.get("faction_id") == faction_id
    ]
    faction_events.sort(key=lambda x: x.get("round", 0), reverse=True)

    # 圣旨记录
    decrees = [
        d for d in _world_state.decrees
        if d.get("faction_id") == faction_id
    ]

    # 治理日志
    gov_logs = _world_state.governance_logs[-30:]

    # 地块变更
    tile_changes = [
        c for c in _world_state.tile_changes
        if c.get("faction_id") == faction_id
    ]

    # 战役记录
    battles = [
        e for e in _world_state.events_log
        if e.get("event_type") == "battle" and (
            e.get("attacker_faction") == faction_id or e.get("defender_faction") == faction_id
        )
    ]

    # 格式化事件列表
    formatted_events = []
    for e in faction_events[:50]:
        formatted_events.append({
            "round": e.get("round", 0),
            "year": e.get("year", _world_state.current_year),
            "title": e.get("title", ""),
            "description": e.get("description", ""),
            "event_type": e.get("event_type", ""),
            "severity": e.get("severity", "normal"),
            "narrative": e.get("narrative", ""),
        })

    return ApiResponse.success({
        "faction_id": faction_id,
        "faction_name": faction_name,
        "events_count": len(faction_events),
        "decrees_count": len(decrees),
        "battles_count": len(battles),
        "tile_changes_count": len(tile_changes),
        "governance_logs_count": len(gov_logs),
        "events": formatted_events,
        "decrees": decrees[-20:],
        "battles": battles[-20:],
        "governance_logs": gov_logs[-10:],
        "current_round": _world_state.current_round,
        "current_year": _world_state.current_year,
    })


@app.get("/api/panel/weather")
async def get_weather():
    """获取当前天气信息"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    weather = _world_state.weather or {}
    return ApiResponse.success({
        "weather": weather,
        "season": _world_state.current_season.value,
        "year": _world_state.current_year,
        "month": _world_state.current_month,
    })


# ============================================================
# API 端点 - 高级功能（3.2 新增）
# ============================================================

# --- 叛军系统 ---

@app.get("/api/rebel/list")
async def list_rebels():
    """获取所有活跃叛军"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    rebels = []
    for rid, rebel in _world_state.rebel_armies.items():
        tile = _world_state.get_tile(rebel.tile_id)
        rebels.append({
            "rebel_id": rebel.rebel_id,
            "tile_id": rebel.tile_id,
            "tile_name": tile.tile_name if tile else "未知",
            "troops": rebel.troops,
            "leader": rebel.leader,
            "cause": rebel.cause,
            "spawned_round": rebel.spawned_round,
            "age": _world_state.current_round - rebel.spawned_round,
        })
    return ApiResponse.success({"rebels": rebels, "total": len(rebels)})


@app.post("/api/rebel/suppress")
async def suppress_rebellion(req: Request):
    """镇压叛军"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    faction_id = data.get("faction_id", "")
    rebel_id = data.get("rebel_id", "")
    troops = data.get("troops", 0)

    from server.core.advanced_features import RebelEngine
    engine = RebelEngine(_world_state, _game_const)
    result = engine.suppress_rebellion(faction_id, rebel_id, troops)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


# --- 伏击/劫掠系统 ---

@app.post("/api/march/ambush")
async def attempt_ambush(req: Request):
    """伏击"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    attacker = data.get("attacker_faction", "")
    target = data.get("target_faction", "")
    tile_id = data.get("tile_id", "")
    troops = data.get("troops", 0)

    from server.core.advanced_features import AmbushRaidEngine
    engine = AmbushRaidEngine(_world_state, _game_const)
    result = engine.attempt_ambush(attacker, target, tile_id, troops)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


@app.post("/api/march/raid")
async def raid_supply(req: Request):
    """劫掠补给线（需要派遣兵力，细作情报影响成功率，被发现影响好感度）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    raider = data.get("raider_faction", "")
    target = data.get("target_faction", "")
    troops = data.get("troops", 0)

    from server.core.advanced_features import AmbushRaidEngine
    engine = AmbushRaidEngine(_world_state, _game_const)
    result = engine.raid_supply_line(raider, target, troops)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


@app.post("/api/march/border_raid")
async def border_raid(req: Request):
    """边境劫掠"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    raider = data.get("raider_faction", "")
    target = data.get("target_faction", "")
    troops = data.get("troops", 0)

    from server.core.advanced_features import AmbushRaidEngine
    engine = AmbushRaidEngine(_world_state, _game_const)
    result = engine.border_raid(raider, target, troops)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


# --- 附庸吞并 ---

@app.post("/api/diplomacy/vassal/annex")
async def annex_vassal(req: Request):
    """吞并附庸"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    suzerain = data.get("suzerain_id", "")
    vassal = data.get("vassal_id", "")

    from server.core.advanced_features import VassalAnnexEngine
    engine = VassalAnnexEngine(_world_state, _game_const)
    result = engine.annex_vassal(suzerain, vassal)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


@app.get("/api/diplomacy/vassal/check_independence/{suzerain_id}/{vassal_id}")
async def check_vassal_independence(suzerain_id: str, vassal_id: str):
    """检查附庸独立战争"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    from server.core.advanced_features import VassalAnnexEngine
    engine = VassalAnnexEngine(_world_state, _game_const)
    result = engine.check_vassal_independence(suzerain_id, vassal_id)
    return ApiResponse.success(result or {"independence_declared": False})


# --- 高级谍报系统 ---

@app.post("/api/spy/double_agent")
async def turn_double_agent(req: Request):
    """策反双面间谍"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    owner = data.get("owner_faction", "")
    target = data.get("target_faction", "")

    from server.core.advanced_features import AdvancedSpyEngine
    engine = AdvancedSpyEngine(_world_state, _game_const)
    result = engine.turn_double_agent(owner, target)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


@app.post("/api/spy/false_intel")
async def plant_false_intel(req: Request):
    """植入假情报"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    planter = data.get("planter_faction", "")
    target = data.get("target_faction", "")
    intel_type = data.get("intel_type", "军事")
    fake_data = data.get("fake_data", {})

    from server.core.advanced_features import AdvancedSpyEngine
    engine = AdvancedSpyEngine(_world_state, _game_const)
    result = engine.plant_false_intel(planter, target, intel_type, fake_data)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


@app.post("/api/spy/counter")
async def counter_spy(req: Request):
    """反间行动"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    owner = data.get("owner_faction", "")
    target = data.get("target_faction", "")

    from server.core.advanced_features import AdvancedSpyEngine
    engine = AdvancedSpyEngine(_world_state, _game_const)
    result = engine.counter_spy(owner, target)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


# --- 高级外交 ---

@app.post("/api/diplomacy/hostage/send")
async def send_hostage(req: Request):
    """派遣质子"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    sender = data.get("sender_faction", "")
    receiver = data.get("receiver_faction", "")

    from server.core.advanced_features import AdvancedDiplomacyEngine
    engine = AdvancedDiplomacyEngine(_world_state, _game_const)
    result = engine.send_hostage(sender, receiver)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


@app.post("/api/diplomacy/hostage/recall")
async def recall_hostage(req: Request):
    """召回质子"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    sender = data.get("sender_faction", "")
    receiver = data.get("receiver_faction", "")

    from server.core.advanced_features import AdvancedDiplomacyEngine
    engine = AdvancedDiplomacyEngine(_world_state, _game_const)
    result = engine.recall_hostage(sender, receiver)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


# --- 宗室高级功能 ---

@app.post("/api/royal/move_capital")
async def move_capital(req: Request):
    """迁都"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    faction_id = data.get("faction_id", "")
    new_tile_id = data.get("new_tile_id", "")

    from server.core.advanced_features import RoyalAdvancedEngine
    engine = RoyalAdvancedEngine(_world_state, _game_const)
    result = engine.move_capital(faction_id, new_tile_id)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


@app.get("/api/court/capital-candidates/{faction_id}")
async def get_capital_candidates(faction_id: str):
    """获取可选都城列表（含战略评估）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    faction = _world_state.factions.get(faction_id)
    if not faction:
        return ApiResponse.not_found(f"势力 {faction_id} 不存在")

    current_capital_id = faction.capital_tile or getattr(faction, 'capital', '')
    current_tile = _world_state.get_tile(current_capital_id) if current_capital_id else None

    candidates = []
    for t in _world_state.tiles.values():
        if t.faction_id != faction_id:
            continue
        if t.tile_id == current_capital_id:
            continue
        if t.tile_type not in ("city", "capital", "town", "fort"):
            continue

        # 综合评分（0~100）
        pop_score = min(100, (t.population or 0) / 5000 * 100) if t.population else 0
        fort_score = (t.fortification or 0) * 10
        morale_score = t.morale if hasattr(t, 'morale') else 50
        order_score = t.public_order if hasattr(t, 'public_order') else 50
        economy_score = (t.elite_ratio or 0) * 200 if hasattr(t, 'elite_ratio') else 30

        # 地理位置价值
        location_bonus = 0
        tile_name = (t.tile_name or "").lower()
        if any(kw in tile_name for kw in ["京", "都", "阳", "安", "州"]):
            location_bonus += 10
        if t.is_port:
            location_bonus += 8  # 港口城市便利

        composite_score = int(
            pop_score * 0.25 + fort_score * 0.20 + morale_score * 0.20 +
            order_score * 0.15 + economy_score * 0.10 + location_bonus * 0.10
        )

        # 战略评价
        if composite_score >= 75:
            grade = "上上"
            advice = "迁都于此，可固国本"
        elif composite_score >= 55:
            grade = "中"
            advice = "堪为新都，中规中矩"
        elif composite_score >= 35:
            grade = "下"
            advice = "勉强可用，非长久之地"
        else:
            grade = "下下"
            advice = "不宜为国都，建议另选"

        # 对比当前都城
        advantages = []
        disadvantages = []
        if current_tile:
            if t.population > (current_tile.population or 0):
                advantages.append(f"人口(+{t.population - current_tile.population})")
            else:
                disadvantages.append(f"人口({t.population} vs {current_tile.population})")
            if t.fortification > (current_tile.fortification or 0):
                advantages.append(f"城防(+{t.fortification - current_tile.fortification})")
            elif t.fortification < (current_tile.fortification or 0):
                disadvantages.append(f"城防弱({t.fortification} vs {current_tile.fortification})")
            t_morale = t.morale if hasattr(t, 'morale') else 50
            ct_morale = current_tile.morale if hasattr(current_tile, 'morale') else 50
            if t_morale > ct_morale + 10:
                advantages.append("民心更高")
            elif t_morale < ct_morale - 10:
                disadvantages.append("民心更低")
            if t.is_port and not getattr(current_tile, 'is_port', False):
                advantages.append("可通海路")
            if getattr(t, 'stable', 0) > getattr(current_tile, 'stable', 0):
                advantages.append("马场优良")

        candidates.append({
            "tile_id": t.tile_id,
            "tile_name": t.tile_name,
            "tile_type": t.tile_type,
            "population": t.population,
            "fortification": t.fortification,
            "morale": t.morale if hasattr(t, 'morale') else 50,
            "public_order": t.public_order if hasattr(t, 'public_order') else 50,
            "troops": t.troops if hasattr(t, 'troops') else 0,
            "is_port": t.is_port,
            "stable": getattr(t, 'stable', 0),
            "armory": getattr(t, 'armory', 0),
            "composite_score": composite_score,
            "grade": grade,
            "advice": advice,
            "advantages": advantages,
            "disadvantages": disadvantages,
        })

    candidates.sort(key=lambda c: c["composite_score"], reverse=True)

    # 当前都城信息
    current_info = None
    if current_tile:
        current_info = {
            "tile_id": current_tile.tile_id,
            "tile_name": current_tile.tile_name,
            "population": current_tile.population,
            "fortification": current_tile.fortification,
            "morale": current_tile.morale if hasattr(current_tile, 'morale') else 50,
            "public_order": current_tile.public_order if hasattr(current_tile, 'public_order') else 50,
            "troops": current_tile.troops if hasattr(current_tile, 'troops') else 0,
            "is_port": current_tile.is_port,
        }

    # 谋士建议（最佳选择）
    top_advice = ""
    if candidates:
        best = candidates[0]
        if best["composite_score"] >= 70:
            top_advice = f"谋士团一致认为：{best['tile_name']}（评级{best['grade']}）为最佳迁都之选。{best['advice']}。"
        elif best["composite_score"] >= 50:
            top_advice = f"谋士团建议：{best['tile_name']}（评级{best['grade']}）可作为新都考量。但需权衡利弊。"
        else:
            top_advice = "谋士团认为：当前可选城池均不理想，建议继续开疆拓土后再议迁都之事。"

    return ApiResponse.success({
        "faction_id": faction_id,
        "current_capital": current_info,
        "candidates": candidates,
        "total_candidates": len(candidates),
        "adviser_recommendation": top_advice,
        "move_cost": 10000,
    })


@app.get("/api/court/capital-history/{faction_id}")
async def get_capital_history(faction_id: str):
    """获取势力迁都历史"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    history = [d for d in _world_state.capital_history if d.get("faction_id") == faction_id]
    history.sort(key=lambda x: (x.get("round", 0), x.get("record_id", "")), reverse=True)
    faction = _world_state.factions.get(faction_id)
    current_capital_id = faction.capital_tile or getattr(faction, 'capital', '') if faction else ""
    current_tile = _world_state.get_tile(current_capital_id) if current_capital_id else None
    return ApiResponse.success({
        "faction_id": faction_id,
        "current_capital": current_tile.tile_name if current_tile else current_capital_id,
        "total_moves": len(history),
        "history": history,
    })


@app.post("/api/royal/sacrifice")
async def perform_sacrifice(req: Request):
    """祭祀天地"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    faction_id = data.get("faction_id", "")

    from server.core.advanced_features import RoyalAdvancedEngine
    engine = RoyalAdvancedEngine(_world_state, _game_const)
    result = engine.perform_sacrifice(faction_id)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


# --- 官员系统 ---

@app.post("/api/court/recruit_officials")
async def recruit_officials(req: Request):
    """科举选拔官员"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    faction_id = data.get("faction_id", "")
    count = data.get("count", 1)

    from server.core.advanced_features import OfficialAdvancedEngine
    engine = OfficialAdvancedEngine(_world_state, _game_const)
    result = engine.recruit_officials(faction_id, count)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])


# --- 廷议决议落实 ---

@app.post("/api/court/apply-debate-result")
async def apply_debate_result(req: Request):
    """廷议决议落实 - 君主对廷议结果做出裁决并影响朝纲"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    faction_id = data.get("faction_id", "")
    topic = data.get("topic", "")
    summary = data.get("summary", "")
    resolution = data.get("resolution", "accept_consensus")  # accept_consensus | partial_accept | table_discussion | override_decision
    override_text = data.get("override_text", "")
    debate_npcs = data.get("debate_npcs", [])  # [{npc_id, npc_name, role_label}, ...]

    faction = _world_state.factions.get(faction_id)
    if not faction:
        return ApiResponse.not_found(f"势力 {faction_id} 不存在")

    # 决议效果映射
    resolution_effects = {
        "accept_consensus": {"court_stability": 8, "realm_stability": 3, "label": "采纳众议", "desc": "从善如流，朝野归心"},
        "partial_accept": {"court_stability": 3, "realm_stability": 0, "label": "择善而从", "desc": "取其精华，去其糟粕"},
        "table_discussion": {"court_stability": -2, "realm_stability": 0, "label": "容后再议", "desc": "此事不急，容后再议"},
        "override_decision": {"court_stability": -5, "realm_stability": 2, "label": "乾纲独断", "desc": "朕意已决，无需再议"},
    }

    effects = resolution_effects.get(resolution, resolution_effects["accept_consensus"])
    old_stability = faction.court_stability
    faction.court_stability = max(0, min(100, faction.court_stability + effects["court_stability"]))
    faction.realm_stability = max(0, min(100, faction.realm_stability + effects["realm_stability"]))

    # 影响参与的官员忠诚度
    loyalty_changes = {}
    for npc_info in debate_npcs:
        npc_id = npc_info.get("npc_id", "")
        npc_name = npc_info.get("npc_name", "")
        if not npc_id or not npc_name:
            continue
        # 根据决议类型计算忠诚变化
        if resolution == "accept_consensus":
            loyalty_delta = 3
        elif resolution == "override_decision":
            loyalty_delta = -4
        else:
            loyalty_delta = 0
        loyalty_changes[npc_id] = {"name": npc_name, "delta": loyalty_delta}
        # 更新官员记录中的忠诚度
        for off in _world_state.officials.values():
            if off.name == npc_name:
                off.loyalty = max(0, min(100, off.loyalty + loyalty_delta))
                break

    # 记录廷议历史
    debate_record = {
        "debate_id": f"debate_{_world_state.current_round}_{len(_world_state.debate_history) + 1}",
        "round": _world_state.current_round,
        "faction_id": faction_id,
        "topic": topic,
        "summary": summary[:200] if summary else "",
        "resolution": effects["label"],
        "resolution_type": resolution,
        "override_text": override_text,
        "npc_count": len(debate_npcs),
        "stability_change": faction.court_stability - old_stability,
        "year": _world_state.current_year,
        "season": _world_state.current_season.value if hasattr(_world_state.current_season, 'value') else str(_world_state.current_season),
    }
    _world_state.debate_history.append(debate_record)

    # 记录到事件日志
    _world_state.events_log.append({
        "round": _world_state.current_round,
        "event_type": "court_debate_resolved",
        "faction_id": faction_id,
        "faction_name": faction.name,
        "topic": topic,
        "resolution": effects["label"],
        "desc": effects["desc"],
        "stability_change": faction.court_stability - old_stability,
    })

    logger.info(f"[朝堂] {faction.name} 廷议「{topic}」→ {effects['label']}，朝纲 {old_stability}→{faction.court_stability}")

    return ApiResponse.success({
        "resolution": effects["label"],
        "desc": effects["desc"],
        "court_stability": faction.court_stability,
        "stability_change": faction.court_stability - old_stability,
        "loyalty_changes": loyalty_changes,
        "debate_record": debate_record,
    })


@app.get("/api/court/debate-history/{faction_id}")
async def get_debate_history(faction_id: str):
    """获取势力廷议历史"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    history = [d for d in _world_state.debate_history if d.get("faction_id") == faction_id]
    history.sort(key=lambda x: (x.get("round", 0), x.get("debate_id", "")), reverse=True)
    return ApiResponse.success({
        "faction_id": faction_id,
        "total_debates": len(history),
        "history": history,
    })


# --- 海战 ---

@app.post("/api/march/naval_battle")
async def naval_battle(req: Request):
    """海战"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    data = await req.json()
    attacker = data.get("attacker_faction", "")
    defender = data.get("defender_faction", "")
    atk_troops = data.get("attacker_troops", 0)
    def_troops = data.get("defender_troops", 0)
    tile_id = data.get("tile_id", "")

    from server.core.advanced_features import WorldAdvancedEngine
    engine = WorldAdvancedEngine(_world_state, _game_const)
    result = engine.naval_battle(attacker, defender, atk_troops, def_troops, tile_id)
    return ApiResponse.success(result) if result["success"] else ApiResponse.error(400, result["message"])




# ============================================================
# API 端点 - 城建基建系统（3.0 新增）
# ============================================================

@app.get("/api/building/available/{tile_id}")
async def get_available_buildings(tile_id: str):
    """获取地块可建造建筑列表"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.building_system import BuildingEngine
    engine = BuildingEngine(_world_state)
    available = engine.get_available_buildings(tile_id)
    existing = engine.get_tile_buildings(tile_id)
    return ApiResponse.success({"tile_id": tile_id, "available": available, "existing": existing})


@app.post("/api/building/construct")
async def construct_building(request: dict):
    """建造建筑"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    tile_id = request.get("tile_id", "")
    building_type_str = request.get("building_type", "")
    faction_id = request.get("faction_id", "")

    # 权限校验
    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")
    if faction_id != player.faction_id:
        return ApiResponse.forbidden(f"无权操控其他势力！")

    try:
        from server.models.world_state import BuildingType
        building_type = BuildingType(building_type_str)
    except ValueError:
        return ApiResponse.bad_request(f"无效建筑类型: {building_type_str}")

    from server.core.building_system import BuildingEngine
    engine = BuildingEngine(_world_state)
    result = engine.construct_building(tile_id, building_type, faction_id)
    if result["success"]:
        return ApiResponse.success(result)
    return ApiResponse.error(400, result["message"])


@app.post("/api/building/upgrade")
async def upgrade_building(request: dict):
    """升级建筑"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    building_id = request.get("building_id", "")
    faction_id = request.get("faction_id", "")

    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")
    if faction_id != player.faction_id:
        return ApiResponse.forbidden(f"无权操控其他势力！")

    from server.core.building_system import BuildingEngine
    engine = BuildingEngine(_world_state)
    result = engine.upgrade_building(building_id, faction_id)
    if result["success"]:
        return ApiResponse.success(result)
    return ApiResponse.error(400, result["message"])


@app.post("/api/building/demolish")
async def demolish_building(request: dict):
    """拆除建筑"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    building_id = request.get("building_id", "")
    faction_id = request.get("faction_id", "")

    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")
    if faction_id != player.faction_id:
        return ApiResponse.forbidden(f"无权操控其他势力！")

    from server.core.building_system import BuildingEngine
    engine = BuildingEngine(_world_state)
    result = engine.demolish_building(building_id, faction_id)
    if result["success"]:
        return ApiResponse.success(result)
    return ApiResponse.error(400, result["message"])


# ============================================================
# API 端点 - 国策系统（3.0 新增）
# ============================================================

@app.get("/api/policy/available")
async def get_available_policies():
    """获取所有可用国策列表"""
    from server.models.world_state import PolicyType
    from server.core.policy_system import POLICY_CONFIG
    policies = []
    for pt, config in POLICY_CONFIG.items():
        policies.append({
            "type": pt.value,
            "name": config["name"],
            "description": config["description"],
            "unlock_cost": config["unlock_cost"],
            "effects": config["effects"],
            "conflicts_with": [c.value for c in config.get("conflicts_with", [])],
        })
    return ApiResponse.success({"policies": policies})


@app.get("/api/policy/active/{faction_id}")
async def get_active_policies(faction_id: str):
    """获取势力当前激活的国策"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.policy_system import PolicyEngine
    engine = PolicyEngine(_world_state)
    policies = engine.get_faction_policies(faction_id)
    return ApiResponse.success({"faction_id": faction_id, "active_policies": policies})


@app.post("/api/policy/activate")
async def activate_policy(request: dict):
    """激活国策"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    faction_id = request.get("faction_id", "")
    policy_str = request.get("policy", "")

    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")
    if faction_id != player.faction_id:
        return ApiResponse.forbidden(f"无权操控其他势力！")

    try:
        from server.models.world_state import PolicyType
        policy_type = PolicyType(policy_str)
    except ValueError:
        return ApiResponse.bad_request(f"无效国策: {policy_str}")

    from server.core.policy_system import PolicyEngine
    engine = PolicyEngine(_world_state)
    result = engine.activate_policy(faction_id, policy_type)
    if result["success"]:
        return ApiResponse.success(result)
    return ApiResponse.error(400, result["message"])


@app.post("/api/policy/deactivate")
async def deactivate_policy(request: dict):
    """废除国策"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    faction_id = request.get("faction_id", "")
    policy_str = request.get("policy", "")

    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")
    if faction_id != player.faction_id:
        return ApiResponse.forbidden(f"无权操控其他势力！")

    try:
        from server.models.world_state import PolicyType
        policy_type = PolicyType(policy_str)
    except ValueError:
        return ApiResponse.bad_request(f"无效国策: {policy_str}")

    from server.core.policy_system import PolicyEngine
    engine = PolicyEngine(_world_state)
    result = engine.deactivate_policy(faction_id, policy_type)
    if result["success"]:
        return ApiResponse.success(result)
    return ApiResponse.error(400, result["message"])


@app.get("/api/supply/status/{tile_id}")
async def get_supply_status(tile_id: str):
    """查询地块补给状态"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.supply_system import SupplyEngine
    engine = SupplyEngine(_world_state)
    status = engine.get_supply_status(tile_id)
    if status:
        return ApiResponse.success({"tile_id": tile_id, "supply": status})
    return ApiResponse.success({"tile_id": tile_id, "supply": None, "message": "该地块无部队或补给信息"})


@app.get("/api/supply/summary/{faction_id}")
async def get_supply_summary(faction_id: str):
    """获取势力补给摘要"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    from server.core.supply_system import SupplyEngine
    engine = SupplyEngine(_world_state)
    summary = engine.get_faction_supply_summary(faction_id)
    return ApiResponse.success({"faction_id": faction_id, "summary": summary})


# ============================================================
# API 端点 - 批量建造 / 批量征兵（3.0 新增快捷操作）
# ============================================================

@app.post("/api/building/batch-construct")
async def batch_construct_buildings(request: dict):
    """批量建造建筑"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    tile_ids = request.get("tile_ids", [])
    building_type_str = request.get("building_type", "")
    faction_id = request.get("faction_id", "")

    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")
    if faction_id != player.faction_id:
        return ApiResponse.forbidden(f"无权操控其他势力！")

    try:
        from server.models.world_state import BuildingType
        building_type = BuildingType(building_type_str)
    except ValueError:
        return ApiResponse.bad_request(f"无效建筑类型: {building_type_str}")

    from server.core.building_system import BuildingEngine
    engine = BuildingEngine(_world_state)

    results = []
    total_cost = 0
    for tile_id in tile_ids:
        r = engine.construct_building(tile_id, building_type, faction_id)
        results.append({"tile_id": tile_id, "success": r["success"], "message": r["message"]})
        if r["success"]:
            total_cost += r.get("cost", 0)

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count

    return ApiResponse.success({
        "building_type": building_type_str,
        "tiles_processed": len(tile_ids),
        "success_count": success_count,
        "fail_count": fail_count,
        "total_cost": total_cost,
        "results": results,
    })


@app.post("/api/military/batch-recruit")
async def batch_recruit_troops(request: dict):
    """批量征兵"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    recruitments = request.get("recruitments", [])  # [{tile_id, amount}, ...]
    faction_id = request.get("faction_id", "")

    player = _world_state.get_player_faction()
    if not player:
        return ApiResponse.forbidden("未找到玩家势力")
    if faction_id != player.faction_id:
        return ApiResponse.forbidden(f"无权操控其他势力！")

    results = []
    total_recruited = 0
    total_grain_cost = 0

    for item in recruitments:
        tile_id = item.get("tile_id", "")
        amount = item.get("amount", 0)

        tile = _world_state.tiles.get(tile_id)
        if not tile:
            results.append({"tile_id": tile_id, "success": False, "message": "地块不存在", "recruited": 0})
            continue
        if tile.faction_id != faction_id:
            results.append({"tile_id": tile_id, "success": False, "message": "非己方领地", "recruited": 0})
            continue

        max_recruit = int(tile.population * 0.05)
        actual = min(amount, max_recruit)
        grain_cost = int(actual * 0.5)

        if player.grain < grain_cost:
            actual = int(player.grain / 0.5)
            grain_cost = int(actual * 0.5)

        if actual <= 0:
            results.append({"tile_id": tile_id, "success": False, "message": "资源不足以征兵", "recruited": 0})
            continue

        player.grain -= grain_cost
        tile.troops += actual
        tile.population = max(0, tile.population - actual)
        total_recruited += actual
        total_grain_cost += grain_cost

        results.append({
            "tile_id": tile_id,
            "success": True,
            "message": f"征兵{actual}人",
            "recruited": actual,
            "grain_cost": grain_cost,
        })

    return ApiResponse.success({
        "total_recruited": total_recruited,
        "total_grain_cost": total_grain_cost,
        "results": results,
    })


@app.get("/api/tiles/owned/{faction_id}")
async def get_owned_tiles_summary(faction_id: str):
    """获取势力所有地块摘要（供批量操作面板使用）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    tiles_summary = []
    for tile_id, tile in _world_state.tiles.items():
        if tile.faction_id == faction_id:
            tiles_summary.append({
                "tile_id": tile_id,
                "tile_name": tile.tile_name,
                "tile_type": tile.tile_type.value if hasattr(tile.tile_type, 'value') else str(tile.tile_type),
                "population": tile.population,
                "troops": tile.troops,
                "grain": tile.grain,
                "morale": tile.morale,
                "is_capital": tile.is_capital,
                "is_port": tile.is_port,
                "fortification": tile.fortification,
                "buildings": {bid: {"type": b.building_type.value, "level": b.level} 
                              for bid, b in tile.buildings.items()} if hasattr(tile, 'buildings') else {},
                "public_order": getattr(tile, 'public_order', 50),
            })
    return ApiResponse.success({"faction_id": faction_id, "tiles_count": len(tiles_summary), "tiles": tiles_summary})


# ============================================================
# API 端点 - 武将系统（3.2 新增）
# ============================================================

@app.get("/api/generals/{faction_id}")
async def get_faction_generals(faction_id: str):
    """获取势力所有武将"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    generals = _world_state.__dict__.get("_generals", {}).get(faction_id, [])
    return ApiResponse.success({"generals": [g.model_dump() if hasattr(g, 'model_dump') else g for g in generals]})


@app.get("/api/talent/market")
async def get_talent_market():
    """
    人才市场 - 浏览当前可招募的流浪武将
    每回合自动刷新候选池（复用已生成的流浪武将）
    """
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    from server.core.general_engine import GeneralEngine
    engine = GeneralEngine(_world_state)

    # 获取当前流浪武将池（faction_id == "_wandering"）
    wandering = _world_state.__dict__.get("_generals", {}).get("_wandering", [])

    # 如果流浪武将不足，自动补充
    if len(wandering) < 5:
        new_talents = engine.generate_wandering_talents(8 - len(wandering))
        _world_state.__dict__.setdefault("_generals", {}).setdefault("_wandering", []).extend(new_talents)
        wandering = _world_state.__dict__["_generals"]["_wandering"]

    return ApiResponse.success({
        "talents": [g.model_dump() if hasattr(g, 'model_dump') else g for g in wandering],
        "total": len(wandering),
    })


@app.post("/api/talent/recruit")
async def recruit_talent(req: Request):
    """
    人才市场 - 招募一名流浪武将
    参数: { faction_id, general_id }
    """
    if not _world_state:
        return ApiResponse.forbidden("请先开局")

    data = await req.json()
    faction_id = data.get("faction_id", "")
    general_id = data.get("general_id", "")

    if not faction_id or not general_id:
        return ApiResponse.bad_request("请指定势力和武将")

    from server.core.general_engine import GeneralEngine
    engine = GeneralEngine(_world_state)
    result = engine.recruit_talent(faction_id, general_id, cost_silver=500)

    if result["success"]:
        return ApiResponse.success(result)
    return ApiResponse.error(400, result["message"])


@app.get("/api/legions/{faction_id}")
async def get_faction_legions(faction_id: str):
    """获取势力所有军团"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    legions = _world_state.__dict__.get("_legions", {}).get(faction_id, [])
    return ApiResponse.success({"legions": [l.model_dump() if hasattr(l, 'model_dump') else l for l in legions]})


@app.post("/api/legion/create")
async def create_legion(request: dict):
    """创建军团"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.general_engine import GeneralEngine
        from server.models.generals import LegionFormation

        faction_id = request.get("faction_id", "")
        commander_id = request.get("commander_id", "")
        name = request.get("name", "新军团")
        unit_composition = request.get("unit_composition", {})
        formation_str = request.get("formation", "balanced")

        engine = GeneralEngine(_world_state)

        # 查找武将
        all_generals = _world_state.__dict__.get("_generals", {}).get(faction_id, [])
        commander = None
        for g in all_generals:
            if g.general_id == commander_id:
                commander = g
                break
        if not commander:
            return ApiResponse.bad_request(f"武将 {commander_id} 不存在")

        formation = LegionFormation(formation_str)
        legion = engine.create_legion(name, faction_id, commander, unit_composition, formation=formation)

        # 存储军团
        if "_legions" not in _world_state.__dict__:
            _world_state.__dict__["_legions"] = {}
        _world_state.__dict__["_legions"].setdefault(faction_id, []).append(legion)

        return ApiResponse.success({"legion": legion.model_dump(), "message": f"军团{name}组建成功"})
    except ValueError as e:
        return ApiResponse.bad_request(str(e))
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/legion/autonomous")
async def set_legion_autonomous(request: dict):
    """设置军团委任自主作战"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    legion_id = request.get("legion_id", "")
    enabled = request.get("enabled", False)
    priority = request.get("priority", "defensive")

    all_legions = _world_state.__dict__.get("_legions", {})
    for fid, legions in all_legions.items():
        for legion in legions:
            if legion.legion_id == legion_id:
                from server.core.general_engine import GeneralEngine
                engine = GeneralEngine(_world_state)
                engine.set_legion_autonomous(legion, enabled, priority)
                return ApiResponse.success({"legion_id": legion_id, "is_autonomous": enabled, "message": "设置成功"})

    return ApiResponse.not_found("军团不存在")


@app.post("/api/general/assign")
async def assign_general_to_legion(request: dict):
    """将武将分配给军团"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    general_id = request.get("general_id", "")
    legion_id = request.get("legion_id", "")

    all_generals = _world_state.__dict__.get("_generals", {})
    all_legions = _world_state.__dict__.get("_legions", {})

    target_general = None
    for fid, gens in all_generals.items():
        for g in gens:
            if g.general_id == general_id:
                target_general = g
                break

    target_legion = None
    for fid, legions in all_legions.items():
        for l in legions:
            if l.legion_id == legion_id:
                target_legion = l
                break

    if not target_general or not target_legion:
        return ApiResponse.not_found("武将或军团不存在")

    # 如果武将已有旧军团，从旧军团中移除
    old_legion_id = target_general.assigned_legion_id
    if old_legion_id and old_legion_id != legion_id:
        for fid, legions in all_legions.items():
            for l in legions:
                if l.legion_id == old_legion_id:
                    if l.commander_id == general_id:
                        l.commander_id = ""
                    if general_id in l.sub_commander_ids:
                        l.sub_commander_ids.remove(general_id)
                    break

    # 如果军团已有主将，新武将作为副将添加
    if target_legion.commander_id and target_legion.commander_id != general_id:
        # 军团已有主将 → 作为副将
        if general_id not in target_legion.sub_commander_ids:
            target_legion.sub_commander_ids.append(general_id)
        assign_type = "副将"
    else:
        # 无主将或就是此武将 → 任命为主将
        target_legion.commander_id = general_id
        # 如果之前是副将，从副将列表中移除
        if general_id in target_legion.sub_commander_ids:
            target_legion.sub_commander_ids.remove(general_id)
        assign_type = "主将"

    target_general.is_assigned = True
    target_general.assigned_legion_id = legion_id
    target_general.assigned_tile = target_legion.current_tile

    return ApiResponse.success({"message": f"{target_general.name}已出任{target_legion.name}{assign_type}", "assign_type": assign_type})


@app.post("/api/legion/disband")
async def disband_legion(request: dict):
    """解散军团"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    legion_id = request.get("legion_id", "")

    all_legions = _world_state.__dict__.get("_legions", {})
    all_generals = _world_state.__dict__.get("_generals", {})

    for fid, legions in all_legions.items():
        for i, legion in enumerate(legions):
            if legion.legion_id == legion_id:
                # 释放主将
                if legion.commander_id:
                    for gens in all_generals.values():
                        for g in gens:
                            if g.general_id == legion.commander_id:
                                g.is_assigned = False
                                g.assigned_legion_id = ""
                                break
                # 释放副将
                for sid in legion.sub_commander_ids:
                    for gens in all_generals.values():
                        for g in gens:
                            if g.general_id == sid:
                                g.is_assigned = False
                                g.assigned_legion_id = ""
                                break
                legion_name = legion.name
                del legions[i]
                return ApiResponse.success({"message": f"军团「{legion_name}」已解散"})

    return ApiResponse.not_found("军团不存在")


@app.post("/api/legion/remove-subcommander")
async def remove_subcommander_from_legion(request: dict):
    """从军团中移除副将"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    legion_id = request.get("legion_id", "")
    general_id = request.get("general_id", "")

    all_legions = _world_state.__dict__.get("_legions", {})
    all_generals = _world_state.__dict__.get("_generals", {})

    for fid, legions in all_legions.items():
        for legion in legions:
            if legion.legion_id == legion_id:
                if general_id in legion.sub_commander_ids:
                    legion.sub_commander_ids.remove(general_id)
                    # 释放武将
                    for gens in all_generals.values():
                        for g in gens:
                            if g.general_id == general_id:
                                g.is_assigned = False
                                g.assigned_legion_id = ""
                                break
                    return ApiResponse.success({"message": "副将已移除"})
                return ApiResponse.bad_request("该武将不是此军团副将")

    return ApiResponse.not_found("军团不存在")


# ============================================================
# API 端点 - 外交权谋（3.2 新增）
# ============================================================

@app.post("/api/diplomacy/strategic-position")
async def analyze_strategic_position(request: dict):
    """分析战略位置（远交近攻策略）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.diplomacy_deep import DeepDiplomacyEngine
        engine = DeepDiplomacyEngine(_world_state)
        result = engine.analyze_strategic_position(request.get("faction_id", ""))
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/diplomacy/discord")
async def sow_discord(request: dict):
    """发动离间计"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.diplomacy_deep import DeepDiplomacyEngine
        from server.models.generals import DiscordType
        engine = DeepDiplomacyEngine(_world_state)
        result = engine.sow_discord(
            request.get("schemer_faction", ""),
            (request.get("target_a", ""), request.get("target_b", "")),
            DiscordType(request.get("discord_type", "sow_discord")),
        )
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/diplomacy/coopt")
async def attempt_coopt(request: dict):
    """招安/招降势力"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.diplomacy_deep import DeepDiplomacyEngine
        from server.models.generals import CooptType
        engine = DeepDiplomacyEngine(_world_state)
        result = engine.attempt_coopt(
            request.get("coopter_faction", ""),
            request.get("target_faction", ""),
            CooptType(request.get("coopt_type", "offer_title")),
        )
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.get("/api/diplomacy/recommendations/{faction_id}")
async def get_diplomatic_recommendations(faction_id: str):
    """获取外交行动推荐"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.diplomacy_deep import DeepDiplomacyEngine
        engine = DeepDiplomacyEngine(_world_state)
        result = engine.recommend_diplomatic_actions(faction_id)
        return ApiResponse.success({"recommendations": result})
    except Exception as e:
        return ApiResponse.server_error(str(e))


# ============================================================
# API 端点 - 历史剧情锚点（3.2 新增）
# ============================================================

@app.get("/api/history/anchors/{faction_id}")
async def get_history_anchors(faction_id: str):
    """获取历史剧情锚点"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        # 懒初始化锚点引擎
        if "_history_anchor_engine" not in _world_state.__dict__:
            from server.core.history_anchors import HistoryAnchorEngine
            _world_state.__dict__["_history_anchor_engine"] = HistoryAnchorEngine(_world_state)

        engine = _world_state.__dict__["_history_anchor_engine"]
        triggered = engine.check_all_anchors()  # 每回合检查
        existing = engine.get_triggered_anchors()

        return ApiResponse.success({
            "triggered": existing,
            "available": triggered,
            "narratives": engine.get_anchor_narratives(),
        })
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/history/choose-branch")
async def choose_history_branch(request: dict):
    """选择历史剧情分支"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        if "_history_anchor_engine" not in _world_state.__dict__:
            from server.core.history_anchors import HistoryAnchorEngine
            _world_state.__dict__["_history_anchor_engine"] = HistoryAnchorEngine(_world_state)

        engine = _world_state.__dict__["_history_anchor_engine"]
        result = engine.choose_branch(
            request.get("anchor_id", ""),
            request.get("branch_id", ""),
            request.get("faction_id", ""),
        )
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.server_error(str(e))


# ============================================================
# API 端点 - 兵种克制数据（3.2 新增）
# ============================================================

@app.get("/api/military/unit-types")
async def get_unit_types():
    """获取兵种克制数据（供前端参考）"""
    from server.models.generals import UNIT_COUNTER_MATRIX, UNIT_TERRAIN_MATRIX, UNIT_BASE_STATS
    return ApiResponse.success({
        "counter_matrix": UNIT_COUNTER_MATRIX,
        "terrain_matrix": UNIT_TERRAIN_MATRIX,
        "base_stats": UNIT_BASE_STATS,
    })


# ============================================================
# API 端点 - 全链路AI智能体（3.2 新增）
# ============================================================

@app.get("/api/ai/snapshot/{faction_id}")
async def get_ai_snapshot(faction_id: str):
    """获取AI沙盘快照（统一JSON接口）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.ai_interface import AIInterface
        iface = AIInterface(_world_state)
        snapshot = iface.build_snapshot(player_faction_id=faction_id)
        return ApiResponse.success(snapshot.model_dump())
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.get("/api/ai/faction-detail/{faction_id}")
async def get_faction_ai_detail(faction_id: str):
    """获取单势力AI详细数据"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.ai_interface import AIInterface
        iface = AIInterface(_world_state)
        detail = iface.build_faction_snapshot(faction_id)
        return ApiResponse.success(detail)
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/civil/analyze")
async def civil_ai_analyze(request: dict):
    """文官内政AI - 全面分析"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.civil_ai import CivilAI
        ai = CivilAI(_world_state)
        result = ai.analyze_faction(request.get("faction_id", ""))
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/civil/build-plan")
async def civil_ai_build_plan(request: dict):
    """文官内政AI - 城建计划"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.civil_ai import CivilAI
        ai = CivilAI(_world_state)
        budget = request.get("budget", 0)
        plan = ai.generate_build_plan(request.get("faction_id", ""), budget)
        return ApiResponse.success(plan.model_dump())
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/civil/resource-plan")
async def civil_ai_resource_plan(request: dict):
    """文官内政AI - 资源调配方案"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.civil_ai import CivilAI
        ai = CivilAI(_world_state)
        result = ai.generate_resource_plan(request.get("faction_id", ""))
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/civil/auto")
async def civil_ai_auto(request: dict):
    """文官内政AI - 自动执行（按委任等级）"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.civil_ai import CivilAI
        from server.models.ai_protocol import DelegationLevel
        ai = CivilAI(_world_state)
        level_str = request.get("delegation_level", "advisory")
        level = DelegationLevel(level_str)
        result = ai.generate_auto_commands(request.get("faction_id", ""), level)

        # 校验
        from server.core.ai_validator import AIValidator
        validator = AIValidator(_world_state)
        report = validator.validate_command_set(result)

        return ApiResponse.success({
            "command_set": result.model_dump(),
            "validation": report.model_dump(),
        })
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/tactical/path")
async def tactical_ai_path(request: dict):
    """战术AI - 最优行军路径"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.tactical_ai import TacticalAI
        ai = TacticalAI(_world_state)
        result = ai.find_optimal_path(
            request.get("from_tile", ""),
            request.get("to_tile", ""),
            request.get("faction_id", ""),
            request.get("avoid_enemy", True),
            request.get("prefer_supply", True),
        )
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/tactical/battle-predict")
async def tactical_ai_battle_predict(request: dict):
    """战术AI - 战损推演"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.tactical_ai import TacticalAI
        ai = TacticalAI(_world_state)
        result = ai.predict_battle(
            request.get("from_tile", ""),
            request.get("tile_id", ""),
            request.get("troops", 0),
            request.get("faction_id", ""),
        )
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/tactical/garrison")
async def tactical_ai_garrison(request: dict):
    """战术AI - 驻防优先级"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.tactical_ai import TacticalAI
        ai = TacticalAI(_world_state)
        result = ai.garrison_priority(request.get("faction_id", ""))
        return ApiResponse.success({"priorities": result})
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/tactical/plan")
async def tactical_ai_plan(request: dict):
    """战术AI - 战术作战规划"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.tactical_ai import TacticalAI
        ai = TacticalAI(_world_state)
        result = ai.plan_tactical_operation(
            request.get("faction_id", ""),
            request.get("tile_id", ""),
        )
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/faction/decisions")
async def faction_ai_decisions(request: dict):
    """群雄敌对AI - 生成势力决策"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.faction_ai_enhanced import FactionAIEngine
        engine = FactionAIEngine(_world_state, _factions_config)
        personality = request.get("personality", "steady")
        result = engine.generate_decisions(request.get("faction_id", ""), personality)

        # 校验
        from server.core.ai_validator import AIValidator
        validator = AIValidator(_world_state)
        report = validator.validate_command_set(result)

        return ApiResponse.success({
            "command_set": result.model_dump(),
            "validation": report.model_dump(),
        })
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/nl-command")
async def nl_command_route(request: dict):
    """自然语言指令路由 - 统一NL操控所有AI模块"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        from server.core.nl_command_router import NLCommandRouter
        from server.models.ai_protocol import NLCommandRequest
        router = NLCommandRouter(_world_state)
        # 2026-07-15 修复: route() 接收 NLCommandRequest 对象，非两个独立字符串参数
        nl_request = NLCommandRequest(
            text=request.get("text", ""),
            faction_id=request.get("faction_id", ""),
            context=request.get("context", {}),
            preferred_agents=request.get("preferred_agents", []),
        )
        route_result = router.route(nl_request)

        # 本地解析指令
        command_set = router.parse_locally(request.get("text", ""), request.get("faction_id", ""))

        # 校验
        from server.core.ai_validator import AIValidator
        validator = AIValidator(_world_state)
        report = validator.validate_command_set(command_set) if command_set.commands else None

        return ApiResponse.success({
            "route": route_result,
            "command_set": command_set.model_dump(),
            "validation": report.model_dump() if report else None,
        })
    except Exception as e:
        logger.error(f"NL命令路由失败: {type(e).__name__}: {e}", exc_info=True)
        return ApiResponse.server_error(str(e))


@app.post("/api/ai/delegation/config")
async def get_delegation_config(request: dict):
    """获取/设置委任配置"""
    if not _world_state:
        return ApiResponse.forbidden("请先开局")
    try:
        fid = request.get("faction_id", "")
        # 存储委任配置
        if "domains" in request:
            _world_state.__dict__[f"_delegation_{fid}"] = request["domains"]

        existing = _world_state.__dict__.get(f"_delegation_{fid}", {})
        return ApiResponse.success({"faction_id": fid, "domains": existing})
    except Exception as e:
        return ApiResponse.server_error(str(e))


@app.get("/api/ai/agents/status")
async def get_agents_status():
    """获取AI智能体集群状态"""
    try:
        from server.agent.orchestrator import get_orchestrator
        orch = get_orchestrator()
        stats = orch.get_stats()
        agent_list = orch.get_agent_list()
        return ApiResponse.success({
            "stats": stats,
            "agents": agent_list,
        })
    except Exception as e:
        return ApiResponse.server_error(str(e))


# ============================================================
# 根路径
# ============================================================

@app.get("/")
async def root():
    return ApiResponse.success({
        "name": "元末逐鹿 3.0 API",
        "version": "3.0.0",
        "docs": "/docs",
        "health": "/api/health",
    })


# ---- 前端静态资源托管（CloudStudio 单端口部署） ----
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
    logger.info(f"前端静态资源已挂载: {_frontend_dist}")
else:
    logger.warning(f"前端目录不存在: {_frontend_dist}，将仅提供 API 服务")

# ============================================================
# 启动入口
# ============================================================

def start():
    import uvicorn
    logger.info("启动元末逐鹿 3.0 API 服务器...")
    uvicorn.run(
        "server.api_server:app",
        host="0.0.0.0",
        port=8800,
        reload=False,
        log_level="info",
        timeout_keep_alive=120,       # 3.2: 长连接保持时间（秒）
        limit_concurrency=50,         # 3.2: 最大并发连接数
        limit_max_requests=1000,      # 3.2: worker 处理最大请求数后重启（防内存泄漏）
        backlog=128,                  # 3.2: 最大等待队列
    )


if __name__ == "__main__":
    start()
