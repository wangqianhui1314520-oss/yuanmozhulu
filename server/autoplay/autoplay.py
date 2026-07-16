"""
自动游玩控制器 — 通过游戏 API 完全自动推演
=============================================
用法:
  python -m server.autoplay.autoplay --faction faction_zhuyuanzhang
  python -m server.autoplay.autoplay --max-turns 50 --speed fast
  python -m server.autoplay.autoplay --watch  # 观察模式(AI互啄)

独立性保证:
  - 不修改任何游戏源文件
  - 不依赖浏览器，纯 HTTP API 调用
  - 通过独立的 httpx.AsyncClient 通信
  - 可随时 Ctrl+C 安全停止
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from argparse import ArgumentParser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

# ── 常量 ──────────────────────────────────────────
API_BASE = "http://127.0.0.1:8800"
REQUEST_TIMEOUT = 300       # 单次 API 请求超时（回合推进可慢到数分钟）
AUTOPLAY_DIR = Path(__file__).parent
LOG_DIR = AUTOPLAY_DIR / "logs"

# ── 势力 ID 映射（真实 ID ← 简称）────────────────
FACTION_MAP = {
    "faction_yuan":           ["yuan", "元", "元廷"],
    "faction_zhuyuanzhang":   ["zhu", "zhu_yz", "朱元璋", "西吴"],
    "faction_chenyouliang":   ["chen", "chen_yd", "陈友谅", "陈汉"],
    "faction_zhangshicheng":  ["zhang", "zhang_sc", "张士诚", "大周"],
    "faction_fangguozhen":    ["fang", "fang_gz", "方国珍"],
    "faction_xushouhui":      ["xu", "xushouhui", "徐寿辉", "天完"],
    "faction_mingyuzhen":     ["ming", "ming_yl", "明玉珍", "大夏"],
    "faction_wangbaobao":     ["wang", "王保保", "扩廓帖木儿"],
    "faction_mobei":          ["mobei", "漠北", "漠北诸部"],
}

FACTION_DISPLAY = {
    "faction_yuan":          ("元廷",           "地狱"),
    "faction_zhuyuanzhang":  ("朱元璋(西吴)",    "普通"),
    "faction_chenyouliang":  ("陈友谅(陈汉)",    "困难"),
    "faction_zhangshicheng": ("张士诚(大周)",    "简单"),
    "faction_fangguozhen":   ("方国珍",          "中等"),
    "faction_xushouhui":     ("徐寿辉(天完)",    "困难"),
    "faction_mingyuzhen":    ("明玉珍(大夏)",    "简单"),
    "faction_wangbaobao":    ("王保保",          "中等"),
    "faction_mobei":         ("漠北诸部",        "困难"),
}


def resolve_faction_id(input_id: str) -> str:
    """将用户输入的简称/中文名解析为真实势力ID"""
    # 直接匹配
    if input_id in FACTION_MAP:
        return input_id
    # 别名匹配
    for real_id, aliases in FACTION_MAP.items():
        if input_id.lower() in [a.lower() for a in aliases]:
            return real_id
    # 模糊包含
    for real_id, aliases in FACTION_MAP.items():
        for alias in aliases:
            if alias.lower() in input_id.lower() or input_id.lower() in alias.lower():
                return real_id
    raise ValueError(f"未知势力: {input_id}，可用: {list(FACTION_MAP.keys())}")


# ── 数据结构 ──────────────────────────────────────

@dataclass
class GameState:
    """游戏状态快照"""
    round: int = 0
    year: int = 1351
    month: int = 1
    season: str = "春"
    phase: str = ""
    factions: dict = field(default_factory=dict)
    player_faction_id: str = ""
    player_faction_name: str = ""
    ending: Optional[dict] = None
    events_count: int = 0


@dataclass
class AutoplayStats:
    """自动游玩统计"""
    start_time: float = 0.0
    turns_completed: int = 0
    total_commands: int = 0
    errors: int = 0
    last_error: str = ""


# ── 自动游玩控制器 ────────────────────────────────

class AutoplayController:
    """自动游玩主控制器"""

    def __init__(
        self,
        faction_id: str = "faction_zhuyuanzhang",
        max_turns: int = 0,
        speed: str = "normal",
        watch_mode: bool = False,
    ):
        self.faction_id = faction_id
        self.max_turns = max_turns
        self.speed = speed
        self.watch_mode = watch_mode
        self.running = False
        self.state = GameState()
        self.stats = AutoplayStats()
        self._client: Optional[httpx.AsyncClient] = None
        self._speed_delays = {"fast": 0.0, "normal": 2.0, "slow": 5.0}
        self._player_id = f"autoplay_{int(time.time())}"  # 固定会话ID

        # 观察模式下必须指定一个势力（用于 API 校验），但不提交指令
        if self.watch_mode:
            self._log("⚠️  观察模式：以 player_turn 模式启动但不提交指令，纯观看 AI 互啄")

        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── HTTP 客户端 ────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=API_BASE,
                timeout=httpx.Timeout(REQUEST_TIMEOUT),
                headers={"X-Player-ID": self._player_id},
            )
        return self._client

    async def _api(self, method: str, path: str, **kwargs) -> dict:
        """通用 API 调用"""
        client = await self._get_client()
        resp = await client.request(method, path, **kwargs)
        resp.raise_for_status()
        data = resp.json()
        # API 响应包装在 ApiResponse 里
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    async def _get(self, path: str) -> dict:
        return await self._api("GET", path)

    async def _post(self, path: str, data: dict = None) -> dict:
        return await self._api("POST", path, json=data or {})

    # ── 健康检查 ───────────────────────────────────

    async def check_health(self) -> bool:
        """检查游戏服务器是否在线（接受 ok / degraded 状态）"""
        try:
            client = await self._get_client()
            resp = await client.get("/api/health")
            raw = resp.json()
            # ApiResponse 包装: {"code":200,"data":{...}}
            data = raw.get("data", raw)
            status = data.get("status", "")
            return status in ("ok", "degraded", "healthy")
        except Exception:
            return False

    # ── 游戏初始化 ─────────────────────────────────

    async def init_game(self) -> bool:
        """初始化游戏"""
        display = FACTION_DISPLAY.get(self.faction_id, (self.faction_id, "?"))
        self._log(f"🎮 选择势力: {display[0]} ({display[1]})")
        self._log(f"   势力ID: {self.faction_id}")

        payload = {
            "faction_id": self.faction_id,
            "mode": "player_turn",  # 始终用 player_turn，确保 advance_turn 可用
        }
        try:
            result = await self._post("/api/game/init", data=payload)

            # 解析 world_state
            ws = result.get("world_state", {})
            player = result.get("player_faction", {})
            self.state = GameState(
                round=ws.get("current_round", 1),
                year=ws.get("current_year", 1351),
                month=ws.get("current_month", 1),
                season=str(ws.get("current_season", "春")),
                player_faction_id=result.get("player_faction_id", self.faction_id),
                player_faction_name=player.get("name", self.faction_id),
                factions=ws.get("factions", {}),
            )

            mode_label = result.get("mode_info", {}).get("mode_label", "?")
            live_count = sum(1 for f in self.state.factions.values()
                             if isinstance(f, dict) and f.get("is_alive", False))
            self._log(f"✅ 游戏初始化成功 | {display[0]} | 模式: {mode_label} | 存活势力: {live_count}")
            return True
        except Exception as e:
            self._log(f"❌ 游戏初始化失败: {e}")
            return False

    # ── 策略模板 ──────────────────────────────────

    STRATEGY_TEMPLATES = [
        # 开局阶段
        "稳固根基，发展农业和内政，修筑城防，广积粮草",
        "招募精兵，训练新军，同时派遣间谍探查邻国虚实",
        "安抚百姓，减免赋税，发展商业贸易，充实国库",
        # 发展阶段
        "趁邻国不备，突袭边境薄弱据点，扩张领土",
        "联合盟友，共同进攻强敌，事成后瓜分其地",
        "加强边防守备，修筑烽燧和要塞，同时发展经济",
        # 强势阶段
        "倾全国之兵，发动总攻，一举灭掉最弱的邻国",
        "派使者出使各国，以武力威慑迫使小国称臣纳贡",
        "休整军队，补充粮草，为下一轮大规模扩张做准备",
        # 防守阶段
        "坚守城池，以逸待劳，消耗敌军锐气",
        "征发民兵，加固城防，实行坚壁清野之策",
    ]

    # ── 自动生成指令（NL圣旨方式） ──────────────────

    async def generate_and_submit_edict(self) -> int:
        """
        使用自然语言圣旨 API 让 LLM 自动生成并提交指令
        返回: 本次提交的指令数
        """
        if self.watch_mode:
            return 0

        # 根据回合数选择策略模板
        template = self._pick_strategy()

        dispatcher = FACTION_DISPLAY.get(self.faction_id, (self.faction_id, "?"))
        self._log(f"  📜 圣旨: 「{template[:30]}…」({dispatcher[0]})")

        try:
            result = await self._post("/api/edict/nl-process", data={
                "edict_text": template,
                "faction_id": self.faction_id,
                "direct_execute": True,
                "use_ai": True,
            })

            commands = result.get("commands", [])
            cmd_count = len(commands)

            if cmd_count > 0:
                actions = [c.get("action", "?") for c in commands[:5]]
                more = f" +{cmd_count - 5}" if cmd_count > 5 else ""
                self._log(f"  ✅ 解析: {', '.join(actions)}{more} ({cmd_count}条)")
            else:
                # 指令已被 direct_execute 直接执行，不返回 commands 列表也正常
                self._log(f"  ✅ 已执行（直接执行模式）")
                cmd_count = 1  # 至少算一条

        except httpx.HTTPStatusError as e:
            # 403 Forbidden 常见于 faction_id 不匹配
            self._log(f"  ⚠️ HTTP {e.response.status_code}: {e.response.text[:120]}")
            cmd_count = await self._fallback_commands()
        except Exception as e:
            self._log(f"  ⚠️ NL圣旨失败: {e}，使用规则降级")
            cmd_count = await self._fallback_commands()

        return cmd_count

    def _pick_strategy(self) -> str:
        """根据回合和势力状态选择策略"""
        r = self.state.round
        templates = self.STRATEGY_TEMPLATES

        # 开局前几回合：稳固发展
        if r <= 3:
            return templates[0] if r % 2 == 1 else templates[1]
        # 轮流使用各阶段策略
        idx = r % len(templates)
        return templates[idx]

    async def _fallback_commands(self) -> int:
        """规则降级：不使用LLM，直接提交简单内政指令"""
        cmds = [
            ("develop", {"focus": "agriculture"}),
            ("recruit", {"count": 500}),
        ]
        submitted = 0
        for action, params in cmds:
            try:
                await self._post("/api/game/command", data={
                    "action": action,
                    "params": params,
                    "faction_id": self.faction_id,
                })
                submitted += 1
            except Exception as e:
                self._log(f"  ⚠️ 提交指令失败(action={action}): {e}")
        self._log(f"  🔧 规则降级: 已提交 {submitted} 条基础指令(内政+征兵)")
        return submitted

    # ── 回合推进 ───────────────────────────────────

    async def advance_turn(self) -> bool:
        """推进一个回合"""
        try:
            result = await self._post("/api/game/advance-turn")

            # 更新状态 — 从顶级字段读取
            self.state.round = result.get("current_round", self.state.round + 1)
            self.state.year = result.get("current_year", self.state.year)
            self.state.month = result.get("current_month", self.state.month)
            self.state.season = str(result.get("current_season", self.state.season))
            self.state.phase = result.get("phase", "")

            # 结局判定
            self.state.ending = result.get("ending")

            # 事件与地盘变更
            new_events = result.get("new_events", [])
            tile_changes = result.get("tile_changes", [])
            self.state.events_count += len(new_events)

            # 回合摘要（dict，取 top-level summary 文本）
            round_summary = result.get("round_summary", {})
            summary_text = ""
            if isinstance(round_summary, dict):
                summary_text = round_summary.get("summary", "")
                if not summary_text:
                    # 尝试从 phases 汇总
                    phases = round_summary.get("phases", {})
                    summary_parts = []
                    for phase_name, phase_data in phases.items():
                        if isinstance(phase_data, dict):
                            s = phase_data.get("summary", "")
                            if s:
                                summary_parts.append(s)
                    summary_text = " | ".join(summary_parts[:3])
            elif isinstance(round_summary, str):
                summary_text = round_summary

            # 打印回合信息
            year_label = f"{self.state.year}年{self.state.month}月({self.state.season})"
            phase_info = f" | 阶段:{self.state.phase}" if self.state.phase else ""

            # 快照数据
            snapshot = result.get("snapshot", {})
            fs = snapshot.get("factions", {})
            alive = sum(1 for f in fs.values() if isinstance(f, dict) and f.get("is_alive", True))

            events_info = f" | {len(new_events)}事件" if new_events else ""
            tiles_info = f" | {len(tile_changes)}地变" if tile_changes else ""

            status_line = f"📌 第{self.state.round:>3}回合 [{year_label}] 存活{alive}{events_info}{tiles_info}{phase_info}"
            self._log(status_line)

            if summary_text:
                short = summary_text[:120] + "…" if len(summary_text) > 120 else summary_text
                self._log(f"    └ {short}")

            # 部分失败警告
            if result.get("partial_failure"):
                failed = result.get("failed_phases", [])
                self._log(f"    ⚠️ 部分阶段失败: {failed}")

            # 检查游戏结束
            if self.state.ending and self.state.ending.get("is_game_over"):
                desc = self.state.ending.get("description", "游戏结束")
                self._log(f"🏁 游戏结束! {desc}")
                return False

            return True

        except httpx.HTTPStatusError as e:
            self.stats.errors += 1
            self.stats.last_error = f"HTTP {e.response.status_code}: {e.response.text[:150]}"
            self._log(f"❌ 回合推进 HTTP 错误: {self.stats.last_error}")
            return False
        except Exception as e:
            self.stats.errors += 1
            self.stats.last_error = str(e)
            self._log(f"❌ 回合推进失败: {e}")
            return False

    # ── 主力循环 ───────────────────────────────────

    async def run(self):
        """主运行循环"""
        self.running = True
        self.stats.start_time = time.time()

        # 1. 健康检查
        if not await self.check_health():
            self._log("❌ 游戏服务器未就绪，请先启动: python server.py --frontend")
            return

        # 2. 初始化游戏
        if not await self.init_game():
            return

        display = FACTION_DISPLAY.get(self.faction_id, (self.faction_id, "?"))
        mode_label = "观察(AI互啄)" if self.watch_mode else f"自动游玩({display[0]})"
        self._log(f"🚀 开始 {mode_label} | 速度:{self.speed} | 最大回合:{self.max_turns or '∞'}")
        self._log("─" * 60)

        # 3. 主循环
        while self.running:
            turn_start = time.time()

            # 检查最大回合
            if self.max_turns > 0 and self.stats.turns_completed >= self.max_turns:
                self._log(f"⏹️ 达到最大回合数 {self.max_turns}，停止")
                break

            # 生成并提交指令（使用 NL 圣旨方式）
            submitted = await self.generate_and_submit_edict()
            self.stats.total_commands += submitted

            # 推进回合
            should_continue = await self.advance_turn()
            if not should_continue:
                break

            self.stats.turns_completed += 1

            # 速度控制
            delay = self._speed_delays.get(self.speed, 2.0)
            elapsed = time.time() - turn_start
            if delay > 0:
                # 如果回合本身已经花了很长时间，跳过额外延迟
                if elapsed < delay:
                    await asyncio.sleep(delay - elapsed)
            else:
                # fast 模式也显示耗时
                if elapsed > 5:
                    self._log(f"  ⏱️ 本回合耗时 {elapsed:.1f}s")

        # 4. 结束
        await self._shutdown()

    async def _shutdown(self):
        """安全关闭"""
        self.running = False
        total_time = time.time() - self.stats.start_time
        self._log("─" * 60)

        avg = total_time / max(self.stats.turns_completed, 1)
        self._log(
            f"📊 结束 | 回合:{self.stats.turns_completed} | "
            f"指令:{self.stats.total_commands} | 错误:{self.stats.errors} | "
            f"总耗时:{total_time:.0f}s | 平均:{avg:.1f}s/回合"
        )
        if self.stats.errors:
            self._log(f"  最后一次错误: {self.stats.last_error}")

        # 保存统计
        if self.stats.turns_completed > 0:
            self._save_stats(total_time)

        if self._client:
            await self._client.aclose()
            self._client = None

    def stop(self):
        """外部停止"""
        self.running = False
        self._log("⏹️ 收到停止信号，当前回合结束后退出…")

    # ── 日志与持久化 ──────────────────────────────

    def _log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}", flush=True)

    def _save_stats(self, total_time: float):
        """保存统计到日志文件"""
        log_file = LOG_DIR / f"autoplay_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        display = FACTION_DISPLAY.get(self.faction_id, (self.faction_id, "?"))
        stats_data = {
            "faction_id": self.faction_id,
            "faction_name": display[0],
            "mode": "watch" if self.watch_mode else "play",
            "turns_completed": self.stats.turns_completed,
            "total_commands": self.stats.total_commands,
            "errors": self.stats.errors,
            "total_time_s": round(total_time, 1),
            "avg_time_per_turn_s": round(total_time / max(self.stats.turns_completed, 1), 1),
            "ended_at_year": self.state.year,
            "ending": self.state.ending,
        }
        log_file.write_text(
            json.dumps(stats_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._log(f"📝 统计已保存: {log_file.name}")


# ── CLI 入口 ───────────────────────────────────────

def main():
    parser = ArgumentParser(
        description="元末逐鹿 — 自动游玩控制器",
        epilog="提示: 确保先启动游戏服务器 python server.py --frontend",
    )
    parser.add_argument(
        "--faction", "-f", default="faction_zhuyuanzhang",
        help="玩家势力ID (如 faction_zhuyuanzhang 或 朱元璋/zhu_yz)",
    )
    parser.add_argument(
        "--max-turns", "-n", type=int, default=0,
        help="最大回合数 (0=无限，直到游戏结束)",
    )
    parser.add_argument(
        "--speed", "-s", choices=["fast", "normal", "slow"],
        default="normal",
        help="游玩速度: fast(无等待) / normal(2s) / slow(5s)",
    )
    parser.add_argument(
        "--watch", "-w", action="store_true",
        help="观察模式: 不提交玩家指令，纯观看 AI 势力相互推演",
    )
    parser.add_argument(
        "--list-factions", action="store_true",
        help="列出所有可用势力及其 ID",
    )
    args = parser.parse_args()

    # 列出势力
    if args.list_factions:
        print("\n可用势力 (共 {} 个):\n".format(len(FACTION_DISPLAY)))
        for fid, (name, difficulty) in FACTION_DISPLAY.items():
            aliases = FACTION_MAP.get(fid, [])
            alias_str = " / ".join(aliases[:3]) if aliases else ""
            print(f"  {fid:30s} {name:14s} 难度:{difficulty}")
            if alias_str:
                print(f"  {'':30s} 别名: {alias_str}")
        print()
        return

    # 解析势力 ID
    try:
        resolved_id = resolve_faction_id(args.faction)
    except ValueError as e:
        print(f"❌ {e}")
        print("请使用 --list-factions 查看可用势力")
        sys.exit(1)

    if resolved_id != args.faction:
        print(f"📌 势力 '{args.faction}' → 解析为 {resolved_id}")
    args.faction = resolved_id

    controller = AutoplayController(
        faction_id=args.faction,
        max_turns=args.max_turns,
        speed=args.speed,
        watch_mode=args.watch,
    )

    # 信号处理: 优雅停止
    loop = asyncio.new_event_loop()

    def _stop():
        controller.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass  # Windows 不支持

    try:
        loop.run_until_complete(controller.run())
    except KeyboardInterrupt:
        print("\n⏹️ 手动中断")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
