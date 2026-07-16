"""
元末逐鹿 3.0 — 新手教程/引导系统
基于步骤的状态机，引导新玩家了解游戏核心操作

教程步骤：
1. 势力选择 → 2. 沙盘概览 → 3. 颁布政令 → 4. 军事行动
5. 外交谈判 → 6. 科技研究 → 7. 推进回合 → 8. 完成
"""
from __future__ import annotations
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("yuanmo.tutorial")


@dataclass
class TutorialStep:
    id: str
    title: str
    description: str
    target_selector: str  # CSS选择器，高亮目标元素
    position: str = "bottom"  # top/bottom/left/right
    required_action: str = ""  # 玩家需执行的操作
    hint: str = ""


# 教程步骤定义
TUTORIAL_STEPS: list[TutorialStep] = [
    TutorialStep(
        id="faction_select",
        title="第一步：择主而立",
        description="选择一方势力，开始你的争霸之路。各势力各有优劣，点击势力旗帜查看详情。",
        target_selector=".faction-card",
        position="bottom",
        required_action="select_faction",
        hint="点击任意势力旗帜以选择",
    ),
    TutorialStep(
        id="sandbox_overview",
        title="第二步：俯瞰天下",
        description="这是你的疆域沙盘。绿色边框为你的领土，点击任意地块可查看详情。地图上方可切换图层查看地形/行政/外交等信息。",
        target_selector=".map-container",
        position="bottom",
        required_action="click_tile",
        hint="点击一块你的领土试试",
    ),
    TutorialStep(
        id="issue_edict",
        title="第三步：颁布政令",
        description="作为一国之君，你可以颁布自然语言政令。试试输入一条政令，如「招募三千精兵」或「兴修水利」。",
        target_selector=".edict-input",
        position="top",
        required_action="issue_edict",
        hint="在输入框中输入政令并发送",
    ),
    TutorialStep(
        id="military_action",
        title="第四步：调兵遣将",
        description="选中你的地块，可以集结部队、发动进攻。点击目标地块，选择'行军'即可出发。",
        target_selector=".military-panel, .float-panel",
        position="left",
        required_action="send_march",
        hint="选中己方有兵地块，点击相邻敌方地块发起进攻",
    ),
    TutorialStep(
        id="diplomacy",
        title="第五步：纵横捭阖",
        description="打开外交面板，可以遣使通好、结盟、宣战。在乱世中，一个可靠的盟友胜过千军万马。",
        target_selector=".diplomacy-panel, .float-panel",
        position="right",
        required_action="open_diplomacy",
        hint="点击外交按钮打开外交面板",
    ),
    TutorialStep(
        id="tech_research",
        title="第六步：变法图强",
        description="打开科技树（国策）面板，研究内政/军事/外交/经济四大领域的国策，增强国力。",
        target_selector=".tech-tree-panel, .policy-panel",
        position="right",
        required_action="open_tech_tree",
        hint="点击科技树按钮查看可研究的国策",
    ),
    TutorialStep(
        id="advance_turn",
        title="第七步：推进回合",
        description="一切准备就绪后，点击「推进回合」按钮。AI势力将行动，天道运转，天下大势将向前推进。",
        target_selector=".advance-turn-btn",
        position="top",
        required_action="advance_turn",
        hint="点击底部中央的「推进回合」按钮",
    ),
    TutorialStep(
        id="complete",
        title="大业初启",
        description="恭喜！你已掌握治国的基本操作。天下大乱，群雄逐鹿，愿你能在这乱世中成就一番霸业！\n\n各面板可在左侧按钮随时打开。祝君好运！",
        target_selector="",
        position="center",
        required_action="dismiss",
        hint="",
    ),
]


class TutorialManager:
    """教程管理器 — 单例，跟踪玩家教程进度"""

    _instance: Optional["TutorialManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data_path = Path(__file__).parent.parent / "data" / "tutorial_state.json"
        self._state: dict[str, dict] = {}  # faction_id -> {current_step, completed, skipped}
        self._load()

    def _load(self):
        if self._data_path.exists():
            try:
                with open(self._data_path, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
            except Exception:
                logger.warning("教程状态加载失败，从零开始")
                self._state = {}
        else:
            self._state = {}

    def _save(self):
        os.makedirs(self._data_path.parent, exist_ok=True)
        try:
            with open(self._data_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"教程状态保存失败: {e}")

    def get_state(self, faction_id: str) -> dict:
        """获取玩家教程状态"""
        if faction_id not in self._state:
            self._state[faction_id] = {
                "current_step": "faction_select",
                "completed": False,
                "skipped": False,
                "step_index": 0,
                "completed_steps": [],
            }
            self._save()
        return self._state[faction_id]

    def advance_step(self, faction_id: str) -> dict:
        """推进到下一步"""
        state = self.get_state(faction_id)
        current_idx = state.get("step_index", 0)

        # 标记当前步骤完成
        current_step = TUTORIAL_STEPS[current_idx].id if current_idx < len(TUTORIAL_STEPS) else ""
        if current_step and current_step not in state.get("completed_steps", []):
            state.setdefault("completed_steps", []).append(current_step)

        # 推进
        next_idx = current_idx + 1
        if next_idx >= len(TUTORIAL_STEPS):
            state["completed"] = True
            state["current_step"] = ""
            state["step_index"] = len(TUTORIAL_STEPS)
        else:
            state["step_index"] = next_idx
            state["current_step"] = TUTORIAL_STEPS[next_idx].id

        self._save()
        return state

    def skip(self, faction_id: str) -> dict:
        """跳过教程"""
        state = self.get_state(faction_id)
        state["skipped"] = True
        state["completed"] = True
        state["current_step"] = ""
        state["step_index"] = len(TUTORIAL_STEPS)
        self._save()
        return state

    def reset(self, faction_id: str) -> dict:
        """重置教程"""
        self._state[faction_id] = {
            "current_step": "faction_select",
            "completed": False,
            "skipped": False,
            "step_index": 0,
            "completed_steps": [],
        }
        self._save()
        return self._state[faction_id]

    def get_current_step_detail(self, faction_id: str) -> Optional[dict]:
        """获取当前步骤详情（供前端渲染）"""
        state = self.get_state(faction_id)
        if state.get("completed") or state.get("skipped"):
            return None

        idx = state.get("step_index", 0)
        if idx >= len(TUTORIAL_STEPS):
            return None

        step = TUTORIAL_STEPS[idx]
        return {
            "id": step.id,
            "title": step.title,
            "description": step.description,
            "target_selector": step.target_selector,
            "position": step.position,
            "required_action": step.required_action,
            "hint": step.hint,
            "step_index": idx,
            "total_steps": len(TUTORIAL_STEPS),
        }


__all__ = ["TutorialManager", "TutorialStep", "TUTORIAL_STEPS"]
