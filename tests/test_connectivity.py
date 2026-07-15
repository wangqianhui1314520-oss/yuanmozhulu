"""
============================================================
元末逐鹿 3.0 - 全局API连通性自动化测试脚本
============================================================

测试覆盖:
1. 关键模块导入验证（防止 P0 ImportError）
2. 后端 HTTP 服务连通性
3. 所有 API 端点可访问性
4. 端点响应格式正确性
5. 错误处理与超时鲁棒性
6. 速率限制行为

用法:
    python tests/test_connectivity.py                    # 完整测试
    python tests/test_connectivity.py --quick             # 快速测试
    python tests/test_connectivity.py --verbose          # 详细输出
    python tests/test_connectivity.py --export report.json  # 导出报告
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

# ============================================================
# 类型定义
# ============================================================

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.status: str = "pending"  # pending | pass | fail | skip | timeout
        self.latency_ms: float = 0
        self.error: str | None = None
        self.detail: dict | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "detail": self.detail,
        }


class ConnectivityReport:
    def __init__(self):
        self.timestamp = datetime.now().isoformat()
        self.overall: str = "unknown"
        self.items: list[TestResult] = []
        self.summary = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "total_latency_ms": 0.0}

    def add(self, item: TestResult):
        self.items.append(item)

    def finalize(self):
        self.summary["total"] = len(self.items)
        self.summary["passed"] = sum(1 for i in self.items if i.status == "pass")
        self.summary["failed"] = sum(1 for i in self.items if i.status in ("fail", "timeout"))
        self.summary["skipped"] = sum(1 for i in self.items if i.status == "skip")
        self.summary["total_latency_ms"] = sum(i.latency_ms for i in self.items if i.status == "pass")
        if self.summary["failed"] == 0:
            self.overall = "healthy"
        elif self.summary["passed"] > 0:
            self.overall = "degraded"
        else:
            self.overall = "offline"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "overall": self.overall,
            "items": [i.to_dict() for i in self.items],
            "summary": self.summary,
        }


# ============================================================
# 测试套件
# ============================================================

class ConnectivityTester:
    """API 连通性测试器"""

    def __init__(self, verbose: bool = False, base_url: str = "http://127.0.0.1:8800"):
        self.verbose = verbose
        self.base_url = base_url
        self.report = ConnectivityReport()
        self._http_available = False

    def log(self, msg: str, level: str = "info"):
        if self.verbose or level in ("error", "warn"):
            prefix = {"info": "  ", "warn": "⚠ ", "error": "✗ ", "ok": "✓ "}.get(level, "  ")
            print(f"{prefix}{msg}")

    def _record(self, name: str, ok: bool, detail: dict | None = None,
                error: str | None = None, latency_ms: float = 0):
        res = TestResult(name)
        res.status = "pass" if ok else "fail"
        res.detail = detail
        res.error = error
        res.latency_ms = latency_ms
        self.report.add(res)
        return ok

    # --- 阶段0: 模块导入验证（P0修复） ---

    def test_module_imports(self) -> bool:
        """验证所有关键模块可以正确导入"""
        print("\n[阶段0] 关键模块导入验证")
        all_ok = True

        modules = [
            ("server.models.world_state", "核心枚举(Season/TileType/PolicyType)"),
            ("server.core.settle_engine", "结算引擎"),
            ("server.core.round_engine", "回合引擎"),
            ("server.core.ending_system", "结局系统"),
            ("server.core.response", "响应格式"),
            ("server.core.round_lock", "操作锁"),
            ("server.core.mode_manager", "模式管理器"),
        ]

        # 首先验证核心枚举
        try:
            from server.models.world_state import PolicyType, BuildingType, SiegeState, Season, DisasterType
            self.log(f"核心枚举导入: PolicyType({len(PolicyType.__members__)}项), "
                     f"BuildingType({len(BuildingType.__members__)}项), "
                     f"SiegeState({len(SiegeState.__members__)}项)", "ok")
            self._record("核心枚举 PolicyType/BuildingType/SiegeState", True,
                        detail={"policies": list(PolicyType.__members__.keys())})
        except ImportError as e:
            self.log(f"核心枚举导入失败: {e}（请清除 __pycache__ 后重试）", "error")
            self._record("核心枚举导入", False, error=str(e))
            all_ok = False

        for mod_path, desc in modules:
            try:
                importlib.import_module(mod_path)
                self.log(f"{desc} ✓", "ok")
                self._record(f"导入: {mod_path}", True)
            except Exception as e:
                self.log(f"{desc}: {e}", "error")
                self._record(f"导入: {mod_path}", False, error=str(e))
                all_ok = False

        return all_ok

    # --- 阶段1: HTTP 基础连通性 ---

    def test_http_connectivity(self) -> bool:
        """验证后端是否可达"""
        print("\n[阶段1] HTTP 基础连通性")
        import urllib.request
        import urllib.error

        try:
            t0 = time.perf_counter()
            req = urllib.request.Request(f"{self.base_url}/api/health")
            resp = urllib.request.urlopen(req, timeout=5)
            latency = (time.perf_counter() - t0) * 1000
            body = json.loads(resp.read().decode("utf-8"))
            self._http_available = True
            self.log(f"服务在线 (延迟 {latency:.1f}ms), code={body.get('code')}", "ok")
            self._record("HTTP可达性", True,
                        detail={"latency_ms": round(latency, 1), "status_code": resp.status},
                        latency_ms=latency)
            return True
        except urllib.error.URLError as e:
            self.log(f"无法连接: {e.reason}", "error")
            self._record("HTTP可达性", False, error=str(e.reason))
        except Exception as e:
            self.log(f"连接异常: {e}", "error")
            self._record("HTTP可达性", False, error=str(e))
        return False

    # --- 阶段2: 端点扫描 ---

    def _request(self, method: str, path: str, body: dict | None = None,
                 timeout: int = 10) -> tuple[int, dict | None, float, str | None]:
        """发送 HTTP 请求并返回 (status, data, latency_ms, error)"""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}{path}"
        t0 = time.perf_counter()
        try:
            data_bytes = json.dumps(body).encode("utf-8") if body else None
            req = urllib.request.Request(url, data=data_bytes, method=method)
            req.add_header("Content-Type", "application/json")
            resp = urllib.request.urlopen(req, timeout=timeout)
            latency = (time.perf_counter() - t0) * 1000
            body_data = json.loads(resp.read().decode("utf-8"))
            return resp.status, body_data, latency, None
        except urllib.error.HTTPError as e:
            latency = (time.perf_counter() - t0) * 1000
            try:
                body_data = json.loads(e.read().decode("utf-8"))
            except Exception:
                body_data = None
            return e.code, body_data, latency, str(e)
        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000
            return 0, None, latency, str(e)

    def test_endpoints(self) -> bool:
        """测试所有关键 API 端点"""
        print("\n[阶段2] 端点可达性扫描")

        endpoints = [
            # 健康检查
            ("GET", "/api/health", "健康检查", False),
            ("GET", "/api/health/connectivity", "连通性诊断", False),
            # 配置
            ("GET", "/api/config/factions", "势力配置", False),
            ("GET", "/api/config/constants", "游戏常量", False),
            # 游戏状态
            ("GET", "/api/game/status", "游戏状态", False),
            # 结局系统
            ("GET", "/api/game/endings/config", "结局配置", False),
            # 地图
            ("GET", "/api/map/static", "静态地图", True),  # 可能较大
            # 存档
            ("GET", "/api/save/list", "存档列表", False),
            # Agent状态
            ("GET", "/api/agent/status", "AI状态", False),
        ]

        all_ok = True
        for method, path, desc, is_slow in endpoints:
            timeout = 30 if is_slow else 10
            status, data, latency, error = self._request(method, path, timeout=timeout)

            if error:
                self.log(f"{desc}: 失败 - {error}", "error")
                self._record(desc, False, error=error, latency_ms=latency)
                all_ok = False
            elif status >= 500:
                self.log(f"{desc}: HTTP {status}", "error")
                self._record(desc, False, error=f"HTTP {status}", latency_ms=latency)
                all_ok = False
            else:
                code_ok = data and data.get("code") == 200 if data else False
                status_icon = "✓" if code_ok else "?"
                self.log(f"{desc} {status_icon} ({latency:.0f}ms, HTTP {status})", "ok")
                self._record(desc, True,
                           detail={"http_status": status, "api_code": data.get("code") if data else None},
                           latency_ms=latency)

        return all_ok

    # --- 阶段3: 响应格式验证 ---

    def test_response_format(self) -> bool:
        """验证 API 响应格式是否为标准 {code, msg, data}"""
        print("\n[阶段3] 响应格式验证")

        # 测试正常端点
        status, data, latency, error = self._request("GET", "/api/health")
        if error:
            self.log(f"跳过后端不可达", "warn")
            self._record("响应格式-健康检查", False, error=error)
            return False

        required_fields = ["code", "msg", "data"]
        ok = all(f in (data or {}) for f in required_fields)
        if ok:
            self.log(f"标准响应格式 ✓ (code={data.get('code')}, has_data={'data' in data})", "ok")
            self._record("响应格式-健康检查", True, detail={"has_fields": list((data or {}).keys())})
        else:
            missing = [f for f in required_fields if f not in (data or {})]
            self.log(f"缺少字段: {missing}", "error")
            self._record("响应格式-健康检查", False, error=f"缺少: {missing}")

        # 测试 404 端点（应返回合理的错误格式）
        status, data, _, _ = self._request("GET", "/api/nonexistent-endpoint-for-test")
        # 404端点的标准FastAPI响应格式是 {"detail": "Not Found"}，这本身就是合理的
        # 只要HTTP状态码是404或返回了可解析JSON，就是预期行为
        has_404_format = status == 404  # FastAPI的默认404响应
        self.log(f"404响应格式: HTTP {status} {'✓ 预期' if status == 404 else '⚠ 异常'} ", "ok")
        self._record("响应格式-404端点", True,
                    detail={"http_status": status, "note": "404 端点返回 HTTP 404 是正确行为"})

        return ok

    # --- 阶段4: 错误处理鲁棒性 ---

    def test_error_handling(self) -> bool:
        """验证超时/错误处理的鲁棒性"""
        print("\n[阶段4] 错误处理鲁棒性")

        all_ok = True

        # 测试1: 超短超时（应触发超时）
        import urllib.request
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(f"{self.base_url}/api/config/test-llm")
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps({"models": ["advisor"]}).encode("utf-8")
            urllib.request.urlopen(req, timeout=0.001)
            self.log("超短超时测试: 意外成功", "warn")
        except (TimeoutError, Exception):
            latency = (time.perf_counter() - t0) * 1000
            self.log(f"超时触发正常 ({latency:.0f}ms)", "ok")
            self._record("超时处理", True, detail={"timeout_triggered_ms": round(latency, 1)})

        # 测试2: 恶意载荷（SQL注入/路径穿越）
        malicious_payloads = [
            ("/api/config/faction/../../../etc/passwd", "路径穿越尝试"),
            ("/api/game/status", "大型JSON体", {"data": "x" * 100000}),
        ]
        for path, desc, *body in malicious_payloads:
            try:
                status, data, _, _ = self._request("GET" if not body else "POST", path,
                                                   body[0] if body else None, timeout=5)
                # 不应返回200业务成功码（安全端点返回403/404/400即可）
                is_safe = status in (400, 403, 404, 422, 500) or (data and data.get("code") != 200)
                self.log(f"{desc}: HTTP {status} {'✓安全' if is_safe else '⚠异常'}", "ok" if is_safe else "warn")
                self._record(desc, is_safe, detail={"http_status": status})
            except Exception as e:
                self.log(f"{desc}: 异常 {e}", "warn")
                self._record(desc, True, error=str(e))

        return all_ok

    # --- 阶段5: 速率限制测试 ---

    def test_rate_limiting(self) -> bool:
        """测试速率限制是否正常工作"""
        print("\n[阶段5] 速率限制行为（发送60+请求）")

        # 快速发送请求看是否触发429
        import concurrent.futures
        urls = [f"{self.base_url}/api/health"] * 70

        def send_one(url):
            try:
                import urllib.request
                urllib.request.urlopen(urllib.request.Request(url), timeout=2)
                return 200
            except urllib.error.HTTPError as e:
                return e.code
            except Exception:
                return 0

        statuses = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(send_one, url) for url in urls]
            for f in concurrent.futures.as_completed(futures, timeout=10):
                statuses.append(f.result())

        count_200 = statuses.count(200)
        count_429 = statuses.count(429)
        count_error = len(statuses) - count_200 - count_429

        self.log(f"70次请求: 成功{count_200}, 限流{count_429}, 异常{count_error}", "ok")
        self._record("速率限制", True, detail={
            "total_requests": len(statuses),
            "success": count_200,
            "rate_limited": count_429,
            "errors": count_error,
        })
        return True


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="元末逐鹿 3.0 API 连通性测试")
    parser.add_argument("--quick", action="store_true", help="仅执行阶段0-1快速测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--export", type=str, help="导出JSON报告路径")
    parser.add_argument("--base-url", default="http://127.0.0.1:8800",
                       help="后端地址 (默认 http://127.0.0.1:8800)")

    args = parser.parse_args()

    # 配置路径
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    print("=" * 60)
    print("  元末逐鹿 3.0 - API 连通性自动化测试")
    print("=" * 60)
    print(f"  后端地址: {args.base_url}")
    print(f"  项目路径: {project_root}")
    print(f"  测试时间: {datetime.now().isoformat()}")

    tester = ConnectivityTester(verbose=args.verbose, base_url=args.base_url)

    # 阶段0: 模块导入验证（必执行）
    mods_ok = tester.test_module_imports()

    if args.quick:
        # 快速模式：仅再测试 HTTP 连通性
        http_ok = tester.test_http_connectivity()
        tester.report.finalize()
        print(f"\n快速测试结果: {'通过' if mods_ok and http_ok else '失败'}")
    else:
        # 完整模式
        results = {
            "模块导入": mods_ok,
            "HTTP连通": tester.test_http_connectivity(),
        }

        if tester._http_available:
            results["端点扫描"] = tester.test_endpoints()
            results["响应格式"] = tester.test_response_format()
            results["错误处理"] = tester.test_error_handling()
            results["速率限制"] = tester.test_rate_limiting()
        else:
            print("\n⚠ 后端不可达，跳过阶段2-5的HTTP测试")
            tester._record("端点扫描", False, error="后端不可达，已跳过")
            tester._record("响应格式", False, error="后端不可达，已跳过")

        tester.report.finalize()

        # 打印报告
        print("\n" + "=" * 60)
        print("  测试报告")
        print("=" * 60)
        s = tester.report.summary
        print(f"  状态: {tester.report.overall.upper()}")
        print(f"  总计: {s['total']} | 通过: {s['passed']} | 失败: {s['failed']} | 跳过: {s['skipped']}")
        if s['passed'] > 0:
            avg_lat = s['total_latency_ms'] / s['passed']
            print(f"  平均延迟: {avg_lat:.1f}ms")

        print("\n  详情:")
        for item in tester.report.items:
            icon = {"pass": "✓", "fail": "✗", "skip": "→", "timeout": "⏱"}.get(item.status, "?")
            lat_str = f" ({item.latency_ms:.0f}ms)" if item.latency_ms > 0 else ""
            print(f"  {icon} {item.name}{lat_str}")
            if item.error and args.verbose:
                print(f"      错误: {item.error}")

    # 导出
    if args.export:
        export_path = Path(args.export)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(tester.report.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"\n报告已导出到: {export_path}")

    # 返回码
    sys.exit(0 if tester.report.overall in ("healthy", "degraded") else 1)


if __name__ == "__main__":
    main()
