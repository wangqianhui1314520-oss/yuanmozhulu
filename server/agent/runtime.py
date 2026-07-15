"""
Agent运行时 - 完整自动推演

实现设计文档中的 full_auto_step() 并发模型:
1. RulerAgent ×9  → asyncio.gather() 并发调用 chat_role()
2. MilitaryAgent   → 逐块串行(战斗有依赖)
3. CivilAgent ×436 → batch_execute(并发20, semaphore防过载)
4. SpyAgent        → 串行细作步
5. DiplomacyAgent  → 串行外交步
6. EconomyAgent    → 串行结算
7. EventAgent      → 事件触发
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional

from .base import BaseAgent
from ..infra.llm_client.hunyuan_client import (
    TencentHunyuanClient,
    get_global_clients,
    _concurrency_semaphore,
)

logger = logging.getLogger("yuanmo.agent.runtime")

# 批量执行默认并发数
BATCH_CONCURRENCY = 20


async def full_auto_step(
    world_state: dict,
    faction_configs: dict,
    clients: Optional[dict] = None,
) -> dict:
    """
    完整自动推演一回合
    
    按7个Agent类型分阶段执行，严格遵循设计文档的并发模型。
    
    Args:
        world_state: 当前世界状态
        faction_configs: 势力配置
        clients: LLM客户端（不传则自动获取全局实例）
    
    Returns:
        回合推演摘要
    """
    if clients is None:
        clients = await get_global_clients()

    summary = {
        "round": world_state.get("current_round", 0),
        "phases": {},
    }

    # ============================================================
    # 阶段1: RulerAgent ×9 → asyncio.gather() 并发
    # ============================================================
    logger.info("=== 阶段1: 君主推演 (×9 并发) ===")
    ruler_results = await _phase_ruler_agents(world_state, faction_configs, clients)
    summary["phases"]["rulers"] = {
        "agents_ran": len(ruler_results),
        "results": ruler_results,
    }

    # ============================================================
    # 阶段2: MilitaryAgent → 逐块串行（战斗有依赖）
    # ============================================================
    logger.info("=== 阶段2: 军事推演 (串行) ===")
    military_result = await _phase_military_agent(world_state, faction_configs, clients)
    summary["phases"]["military"] = military_result

    # ============================================================
    # 阶段3: CivilAgent ×436 → batch_execute(并发20)
    # ============================================================
    logger.info("=== 阶段3: 民政推演 (批量并发20) ===")
    civil_results = await _phase_civil_agents(world_state, faction_configs, clients)
    summary["phases"]["civil"] = {
        "tiles_processed": len(civil_results),
        "sample": civil_results[:3] if civil_results else [],
    }

    # ============================================================
    # 阶段4: SpyAgent → 串行细作步
    # ============================================================
    logger.info("=== 阶段4: 细作推演 (串行) ===")
    spy_result = await _phase_spy_agent(world_state, faction_configs, clients)
    summary["phases"]["spy"] = spy_result

    # ============================================================
    # 阶段5: DiplomacyAgent → 串行外交步
    # ============================================================
    logger.info("=== 阶段5: 外交推演 (串行) ===")
    diplomacy_result = await _phase_diplomacy_agent(world_state, faction_configs, clients)
    summary["phases"]["diplomacy"] = diplomacy_result

    # ============================================================
    # 阶段6: EconomyAgent → 串行结算
    # ============================================================
    logger.info("=== 阶段6: 经济结算 (串行) ===")
    economy_result = await _phase_economy_agent(world_state, faction_configs, clients)
    summary["phases"]["economy"] = economy_result

    # ============================================================
    # 阶段7: EventAgent → 事件触发
    # ============================================================
    logger.info("=== 阶段7: 事件触发 ===")
    event_result = await _phase_event_agent(world_state, faction_configs, clients)
    summary["phases"]["events"] = event_result

    logger.info(f"全自动推演完成 (round={summary['round']})")
    return summary


# ============================================================
# 各阶段实现
# ============================================================

async def _phase_ruler_agents(
    world_state: dict,
    faction_configs: dict,
    clients: dict,
) -> list[dict]:
    """
    RulerAgent ×9 → asyncio.gather() 并发调用 chat_role()
    
    每个存活的君主Agent独立推演本回合战略方向。
    """
    factions = faction_configs.get("factions", {})
    living = _get_living_factions(world_state, factions)

    async def ruler_step(faction_id: str, config: dict) -> dict:
        client: TencentHunyuanClient = clients["advisor"]
        personality = config.get("personality", [])
        ruler_name = config.get("ruler_name", faction_id)

        # 组装Prompt: 人设 + 局势 + 记忆
        prompt = _build_ruler_prompt(
            faction_id=faction_id,
            ruler_name=ruler_name,
            personality=personality,
            world_state=world_state,
        )

        system_prompt = _load_agent_prompt("ruler", personality)
        world_json = _world_snapshot_for_faction(world_state, faction_id)

        try:
            response = await client.chat_role(
                prompt=prompt,
                system_prompt=system_prompt,
                world_json=world_json,
                temperature=0.7,
            )
        except Exception as e:
            logger.error(f"君主Agent {faction_id} 推演失败: {e}")
            response = ""

        return {
            "faction_id": faction_id,
            "ruler": ruler_name,
            "decision_summary": response[:200] if response else "（无决策）",
        }

    tasks = [ruler_step(fid, cfg) for fid, cfg in living.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理异常
    cleaned = []
    living_keys = list(living.keys())
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error(f"RulerAgent异常: {r}")
            fid = living_keys[i] if i < len(living_keys) else f"unknown_{i}"
            cleaned.append({"faction_id": fid, "error": str(r)})
        else:
            cleaned.append(r)

    return cleaned


async def _phase_military_agent(
    world_state: dict,
    faction_configs: dict,
    clients: dict,
) -> dict:
    """
    MilitaryAgent → 逐块串行（战斗有依赖关系）
    
    按战斗区域逐块处理，确保因果链正确。
    如果 active_battles 为空，从世界状态中推断当前可能的冲突。
    """
    client: TencentHunyuanClient = clients["enemy"]
    battles = world_state.get("active_battles", [])
    
    # 如果 active_battles 为空，尝试从边境冲突推断战斗
    if not battles:
        battles = _infer_active_battles(world_state, faction_configs)

    results = []
    for battle in battles:
        prompt = _build_battle_prompt(battle, world_state)
        try:
            result = await client.chat_fast(
                prompt=prompt,
                system_prompt="你是军事推演官，以古文输出战斗结果。",
                temperature=0.7,
            )
        except Exception as e:
            logger.error(f"军事推演失败: {e}")
            result = "战局未决。"
        results.append({
            "battle_id": battle.get("id", "?"),
            "result": result[:200],
        })

    return {"battles_resolved": len(results), "results": results}


def _infer_active_battles(world_state: dict, faction_configs: dict) -> list[dict]:
    """从世界状态推断当前可能的战斗（边境冲突等）"""
    import random
    battles = []
    relations = world_state.get("relations", {})
    factions = world_state.get("factions", {})
    tiles = world_state.get("tiles", {})
    
    # 查找处于战争状态的势力对
    war_pairs = set()
    for key, rel in relations.items():
        if isinstance(rel, dict) and rel.get("stance") == "war":
            a = rel.get("faction_a", "")
            b = rel.get("faction_b", "")
            if a and b:
                war_pairs.add((a, b))
    
    # 从 tiles 中找边境冲突（相邻敌对地块）
    if not war_pairs:
        tile_faction_map = {}
        for tid, t in tiles.items():
            fid = t.get("faction_id") or t.get("owner", "")
            if fid:
                tile_faction_map.setdefault(fid, []).append(tid)
        
        for fid_a, tile_ids_a in tile_faction_map.items():
            for fid_b, tile_ids_b in tile_faction_map.items():
                if fid_a >= fid_b:
                    continue
                # 检查是否有相邻地块
                has_adjacent = False
                for ta in tile_ids_a[:3]:  # 采样
                    t = tiles.get(ta, {})
                    neighbors = t.get("neighbors", [])
                    if any(n in tile_ids_b for n in neighbors):
                        has_adjacent = True
                        break
                if has_adjacent:
                    war_pairs.add((fid_a, fid_b))
    
    battle_id = 0
    for a, b in list(war_pairs)[:3]:  # 最多3场战斗
        fa = factions.get(a, {})
        fb = factions.get(b, {})
        battle_id += 1
        battles.append({
            "id": f"battle_{battle_id}",
            "attacker": fa.get("name", a),
            "defender": fb.get("name", b),
            "attacker_troops": fa.get("total_troops", 1000) // 3,
            "defender_troops": fb.get("total_troops", 1000) // 2,
            "terrain": random.choice(["平原", "山地", "丘陵", "森林"]),
            "is_siege": random.random() < 0.3,
        })
    
    return battles


async def _phase_civil_agents(
    world_state: dict,
    faction_configs: dict,
    clients: dict,
) -> list[dict]:
    """
    CivilAgent ×436 → batch_execute(并发20, semaphore防过载)
    
    每个地块一个民政Agent，并发20个一批执行。
    """
    client: TencentHunyuanClient = clients["enemy"]
    tiles = world_state.get("tiles", {})

    semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)

    async def civil_step(tile_id: str, tile_data: dict) -> dict:
        async with semaphore:
            prompt = _build_civil_prompt(tile_id, tile_data, world_state)
            try:
                result = await client.chat_fast(
                    prompt=prompt,
                    system_prompt="你是地方民政官，以古文汇报地方治理。",
                    temperature=0.6,
                )
            except Exception as e:
                logger.error(f"民政Agent {tile_id} 失败: {e}")
                result = ""
            return {"tile_id": tile_id, "result": result[:150]}

    tasks = [civil_step(tid, tdata) for tid, tdata in tiles.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    cleaned = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            cleaned.append({"tile_id": list(tiles.keys())[i] if i < len(tiles) else "?", "error": str(r)})
        else:
            cleaned.append(r)

    return cleaned


async def _phase_spy_agent(
    world_state: dict,
    faction_configs: dict,
    clients: dict,
) -> dict:
    """SpyAgent → 串行细作步"""
    client: TencentHunyuanClient = clients["enemy"]
    spy_networks = world_state.get("spy_networks", {})

    results = []
    for net_id, net_data in spy_networks.items():
        prompt = _build_spy_prompt(net_id, net_data, world_state)
        try:
            result = await client.chat_fast(
                prompt=prompt,
                system_prompt="你是细作头目，以古文汇报情报。",
                temperature=0.8,
            )
        except Exception as e:
            logger.error(f"细作Agent {net_id} 失败: {e}")
            result = ""
        results.append({"network_id": net_id, "intel": result[:200]})

    return {"networks_processed": len(results), "results": results}


async def _phase_diplomacy_agent(
    world_state: dict,
    faction_configs: dict,
    clients: dict,
) -> dict:
    """DiplomacyAgent → 串行外交步"""
    client: TencentHunyuanClient = clients["law"]
    factions = faction_configs.get("factions", {})
    living = _get_living_factions(world_state, factions)

    results = []
    for faction_id in living:
        prompt = _build_diplomacy_prompt(faction_id, world_state)
        world_json = _world_snapshot_for_faction(world_state, faction_id)
        try:
            result = await client.chat_strategy(
                prompt=prompt,
                world_json=world_json,
                system_prompt="你是外交使臣，分析合纵连横之势。",
                temperature=0.6,
            )
        except Exception as e:
            logger.error(f"外交Agent {faction_id} 失败: {e}")
            result = ""
        results.append({"faction_id": faction_id, "diplomacy": result[:300]})

    return {"factions_processed": len(results), "results": results}


async def _phase_economy_agent(
    world_state: dict,
    faction_configs: dict,
    clients: dict,
) -> dict:
    """EconomyAgent → 串行经济结算"""
    client: TencentHunyuanClient = clients["enemy"]
    factions = faction_configs.get("factions", {})

    results = []
    for faction_id in factions:
        prompt = _build_economy_prompt(faction_id, world_state)
        try:
            result = await client.chat_fast(
                prompt=prompt,
                system_prompt="你是户部度支官，以古文核算收支。",
                temperature=0.5,
            )
        except Exception as e:
            logger.error(f"经济Agent {faction_id} 失败: {e}")
            result = ""
        results.append({"faction_id": faction_id, "economy": result[:200]})

    return {"factions_settled": len(results), "results": results}


async def _phase_event_agent(
    world_state: dict,
    faction_configs: dict,
    clients: dict,
) -> dict:
    """EventAgent → 事件触发（天灾/瘟疫/祥瑞等）"""
    client: TencentHunyuanClient = clients["enemy"]

    # 灾害预判
    season = world_state.get("current_season", "春")
    disaster_index = world_state.get("disaster_index", 0)

    prompt = (
        f"当前季节：{season}，灾厄指数：{disaster_index}。\n"
        f"判定本回合是否发生天灾/瘟疫/祥瑞事件，以古文描述。"
    )

    try:
        result = await client.chat_fast(
            prompt=prompt,
            system_prompt="你是钦天监，观测天象灾异。",
            temperature=0.7,
        )
    except Exception as e:
        logger.error(f"事件Agent失败: {e}")
        result = "天象平和，无灾异。"

    return {"narrative": result[:300]}


# ============================================================
# 自由对话接口
# ============================================================

async def agent_chat(
    faction_id: str,
    user_message: str,
    chat_mode: str = "ruler",  # ruler / minister / commoner / court
    world_state: Optional[dict] = None,
    clients: Optional[dict] = None,
) -> str:
    """
    自由对话接口
    
    Args:
        faction_id: 势力ID
        user_message: 用户输入
        chat_mode: 对话模式 (ruler=君主对话, minister=文臣对话, commoner=百姓对话, court=廷议辩论)
        world_state: 世界状态
        clients: LLM客户端
    
    Returns:
        AI回复文本
    """
    if clients is None:
        clients = await get_global_clients()

    client: TencentHunyuanClient = clients["advisor"]
    world_json = ""
    if world_state:
        world_json = _world_snapshot_for_faction(world_state, faction_id)

    # 根据模式选择system prompt
    mode_prompts = {
        "ruler": "你是一方霸主，以帝王口吻应答。",
        "minister": "你是朝廷文臣，以谋士口吻应答。",
        "commoner": "你是市井百姓，以朴实口吻应答。",
        "court": "你是廷议大臣，在朝堂辩论中应答。",
    }
    system_prompt = mode_prompts.get(chat_mode, mode_prompts["ruler"])

    return await client.chat_role(
        prompt=user_message,
        system_prompt=system_prompt,
        world_json=world_json,
        temperature=0.7,
    )


# ============================================================
# 辅助函数
# ============================================================

def _get_living_factions(world_state: dict, faction_configs: dict) -> dict:
    """获取存活势力"""
    living = {}
    for fid, cfg in faction_configs.items():
        faction_state = world_state.get("factions", {}).get(fid, {})
        if faction_state.get("alive", True):
            living[fid] = cfg
    return living


def _world_snapshot_for_faction(world_state: dict, faction_id: str) -> str:
    """为指定势力生成世界局势摘要JSON"""
    faction = world_state.get("factions", {}).get(faction_id, {})

    snapshot = {
        "faction_id": faction_id,
        "faction_name": faction.get("name", faction_id),
        "current_round": world_state.get("current_round", 0),
        "current_year": world_state.get("current_year", 1351),
        "current_season": world_state.get("current_season", "春"),
        "troops": faction.get("troops", 0),
        "treasury": faction.get("treasury", 0),
        "grain": faction.get("grain", 0),
        "reputation": faction.get("reputation", 0),
        "tile_count": faction.get("tile_count", 0),
        "neighbors": faction.get("neighbors", []),
        "relations": world_state.get("relations", {}),
        "active_battles": world_state.get("active_battles", []),
        "disaster_index": world_state.get("disaster_index", 0),
    }

    return json.dumps(snapshot, ensure_ascii=False, indent=2)


def _load_agent_prompt(agent_type: str, personality_tags: list[str]) -> str:
    """
    加载Agent人设Prompt
    
    优先从 agent_prompts/{type}.txt 加载，失败则使用内置模板。
    """
    from pathlib import Path

    prompt_dir = Path(__file__).parent.parent / "agent_prompts"
    prompt_file = prompt_dir / f"{agent_type}.txt"

    if prompt_file.exists():
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        except Exception as e:
            logger.warning(f"读取Agent prompt文件失败 ({agent_type}): {e}，使用默认prompt")
            base_prompt = _default_agent_prompt(agent_type)
    else:
        base_prompt = _default_agent_prompt(agent_type)

    # 追加人格标签
    if personality_tags:
        tags_str = "、".join(personality_tags)
        base_prompt += f"\n\n人格特质：{tags_str}。"

    return base_prompt


def _default_agent_prompt(agent_type: str) -> str:
    """默认Agent人设模板"""
    prompts = {
        "ruler": (
            "你是元末乱世中的一方霸主。你精通权谋韬略，善于审时度势。\n"
            "你的决策需兼顾军事、经济、外交与内政。\n"
            "以帝王口吻思考与决策，文言白话皆可。"
        ),
        "military": (
            "你是军中大将，负责指挥作战。\n"
            "你需根据敌我兵力、地形、天气等因素制定战术。\n"
            "以将领口吻汇报军情。"
        ),
        "civil": (
            "你是地方民政官，负责治理一方土地。\n"
            "你需关注农桑、赋税、民生、治安。\n"
            "以地方官口吻汇报治理情况。"
        ),
        "spy": (
            "你是潜伏敌营的细作头目，负责搜集情报。\n"
            "你需谨慎行事，避免暴露身份。\n"
            "以密报口吻汇报情报。"
        ),
        "diplomacy": (
            "你是外交使臣，负责合纵连横。\n"
            "你需分析各国利害关系，提出外交策略。\n"
            "以使臣口吻分析局势。"
        ),
        "economy": (
            "你是户部度支官，负责财政经济。\n"
            "你需核算收支、管理粮仓、调度物资。\n"
            "以度支官口吻汇报财政。"
        ),
    }
    return prompts.get(agent_type, "你是元末乱世中的一员，以古文风格思考与应答。")


# ============================================================
# Prompt组装辅助函数
# ============================================================

def _build_ruler_prompt(
    faction_id: str,
    ruler_name: str,
    personality: list[str],
    world_state: dict,
) -> str:
    """
    组装君主Prompt = 人设 + 当前局势 + 记忆 + 推演指令
    """
    faction = world_state.get("factions", {}).get(faction_id, {})
    tags = "、".join(personality) if personality else "无特殊"

    return (
        f"你乃{len(personality) if personality else '?'}号君主「{ruler_name}」，"
        f"统领{faction_id}势力。\n"
        f"人格标签：{tags}\n\n"
        f"当前兵力：{faction.get('troops', '?')} | "
        f"国库：{faction.get('treasury', '?')}两 | "
        f"粮草：{faction.get('grain', '?')}石 | "
        f"声望：{faction.get('reputation', '?')}\n"
        f"领地：{faction.get('tile_count', '?')}块\n\n"
        f"请制定本回合战略方向，以君主口吻下达决策。"
    )


def _build_battle_prompt(battle: dict, world_state: dict) -> str:
    """组装战斗推演Prompt"""
    return (
        f"战斗：{battle.get('attacker', '?')} 攻 {battle.get('defender', '?')}\n"
        f"攻方兵力：{battle.get('attacker_troops', '?')} | "
        f"守方兵力：{battle.get('defender_troops', '?')}\n"
        f"地形：{battle.get('terrain', '平原')} | "
        f"是否攻城：{battle.get('is_siege', False)}\n"
        f"请以古文判定此战结果。"
    )


def _build_civil_prompt(tile_id: str, tile_data: dict, world_state: dict) -> str:
    """组装民政推演Prompt"""
    return (
        f"地块：{tile_id}（{tile_data.get('name', '?')}）\n"
        f"所属：{tile_data.get('owner', '无主')} | "
        f"人口：{tile_data.get('population', '?')} | "
        f"发展度：{tile_data.get('development', '?')}\n"
        f"请以地方官口吻汇报本回合治理情况。"
    )


def _build_spy_prompt(net_id: str, net_data: dict, world_state: dict) -> str:
    """组装细作推演Prompt"""
    target = net_data.get("target_faction", "?")
    return (
        f"细作网络：{net_id}，潜伏于{target}\n"
        f"渗透度：{net_data.get('infiltration', '?')} | "
        f"活动点数：{net_data.get('action_points', '?')}\n"
        f"请以密报口吻汇报本回合情报。"
    )


def _build_diplomacy_prompt(faction_id: str, world_state: dict) -> str:
    """组装外交推演Prompt"""
    faction = world_state.get("factions", {}).get(faction_id, {})
    neighbors = faction.get("neighbors", [])
    neighbors_str = "、".join(neighbors) if neighbors else "无邻国"
    return (
        f"势力：{faction_id}\n"
        f"邻国：{neighbors_str}\n"
        f"请分析合纵连横之势，提出外交策略。"
    )


def _build_economy_prompt(faction_id: str, world_state: dict) -> str:
    """组装经济推演Prompt"""
    faction = world_state.get("factions", {}).get(faction_id, {})
    return (
        f"势力：{faction_id}\n"
        f"国库：{faction.get('treasury', '?')}两 | "
        f"粮仓：{faction.get('grain', '?')}石 | "
        f"领地：{faction.get('tile_count', '?')}块\n"
        f"请以户部度支官口吻核算本回合收支。"
    )
