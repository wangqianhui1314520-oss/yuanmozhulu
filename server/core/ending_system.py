"""
四大结局系统 - 结构化结局配置与渐进式演出引擎
==================================================
设计理念：
- 四层递进结局（霸业陨落 → 偏安存续 → 天下归心 → 盛世新朝）
- 每层结局含：触发条件、状态检查、演出逻辑、专属对话、反馈
- 坏结局到好结局的渐进机制
- 结局达成后提供存档解锁/隐藏线索提示
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any
from server.models.world_state import WorldState, FactionState, DiplomaticStance, TileType

# ================================================================
# 结局等级枚举
# ================================================================

class EndingTier(str, Enum):
    """结局等级"""
    BAD = "bad"           # 霸业陨落
    NORMAL = "normal"     # 偏安存续
    GOOD = "good"         # 天下归心
    TRUE = "true"         # 盛世新朝


# ================================================================
# 结局配置数据类
# ================================================================

@dataclass
class EndingConfig:
    """单个结局的完整配置"""
    ending_id: str
    tier: EndingTier
    title: str
    subtitle: str
    is_game_over: bool = True

    # ---- 触发条件 ----
    conditions: dict = field(default_factory=dict)  # 结构化条件

    # ---- 演出逻辑 ----
    scenes: list[dict] = field(default_factory=list)  # 演出分镜
    music: str = ""        # 背景音乐标识
    visual_style: str = ""  # CSS视觉风格类名

    # ---- 专属对话 ----
    epilogue: str = ""                # 主结局叙词
    historian_comment: str = ""       # 史官评语
    npc_dialogues: list[dict] = field(default_factory=list)  # NPC专属对话
    player_monologue: str = ""        # 玩家内心独白

    # ---- 游戏反馈 ----
    statistics_bonus: dict = field(default_factory=dict)  # 统计加成标签
    achievements: list[str] = field(default_factory=list)  # 解锁成就

    # ---- 渐进机制 ----
    next_tier_hint: str = ""           # 提示如何达成更好结局
    unlock_reward: dict = field(default_factory=dict)  # 解锁奖励
    legacy_data: dict = field(default_factory=dict)    # 传承数据（新周目可用）


# ================================================================
# 四大结局配置
# ================================================================

ENDING_CONFIGS: dict[str, EndingConfig] = {
    # ===========================================================
    # 结局一：霸业陨落（BAD ENDING）
    # ===========================================================
    "doom_of_the_tyrant": EndingConfig(
        ending_id="doom_of_the_tyrant",
        tier=EndingTier.BAD,
        title="霸业陨落",
        subtitle="众叛亲离，霸业成空",
        is_game_over=True,

        conditions={
            "type": "destruction",
            "description": "势力覆灭或民怨沸腾导致政权崩溃",
            "required": {
                "is_alive": False,  # 玩家势力灭亡（直接触发）
            },
            "alternative": {
                # 即使存活，满足以下全部条件也会触发
                "reputation_max": 20,
                "realm_stability_max": 25,
                "all_hostile": True,     # 所有存活势力皆为敌对
            },
            "priority": 1,  # 最高优先级检测
        },

        scenes=[
            {
                "id": "scene_dark_throne",
                "type": "visual_fade",
                "duration": 3.0,
                "narrative": "大殿之内，宫灯摇曳。",
                "visual": "ending-dark-throne",
            },
            {
                "id": "scene_betrayal",
                "type": "dialogue_sequence",
                "duration": 5.0,
                "narrative": "士卒离散，百姓揭竿。最后的亲信也在深夜悄然离去……",
                "visual": "ending-betrayal",
            },
            {
                "id": "scene_fall",
                "type": "final_scroll",
                "duration": 4.0,
                "narrative": "曾经煊赫一时的霸业，终究化为一纸青史中的叹息。",
                "visual": "ending-scroll-close",
            },
        ],
        music="tragic_horn",
        visual_style="ending-tier-bad",

        epilogue=(
            "至正乱世，豪杰并起。卿本有逐鹿之志，然治国乏术，驭下无方。"
            "苛政猛于虎，民心尽失；猜忌甚于敌，良将离散。"
            "昔日金戈铁马，今朝黄土一抔。"
            "史官载曰：『虽有雄才，不修仁德，终致覆亡。』"
        ),
        historian_comment=(
            "太史公曰：得天下易，守天下难。不施仁政，不恤民力，"
            "虽一时称雄，终为天下笑。后人当以此为鉴。"
        ),
        npc_dialogues=[
            {
                "speaker": "脱脱",
                "text": "主公……末将已无力回天。城外尽是敌军，城中粮草只余三日。",
                "emotion": "despair",
            },
            {
                "speaker": "刘基",
                "text": "臣早已进谏，不可苛待百姓。今民心已去，悔之晚矣……",
                "emotion": "regret",
            },
            {
                "speaker": "无名老卒",
                "text": "将军，快走吧！叛军已攻破南门！",
                "emotion": "panic",
            },
        ],
        player_monologue=(
            "我望着远方燃烧的城池，耳边尽是喊杀之声。"
            "这一生，我选错了路。若有来世……"
        ),

        statistics_bonus={
            "label": "暴君值",
            "value_calc": "tyranny_score",
        },
        achievements=["first_blood", "witness_destruction"],

        next_tier_hint=(
            "【天命启示】暴政终将反噬。下一次，尝试：\n"
            "1. 保持声望在50以上（体察民情、开仓赈灾）\n"
            "2. 避免同时与所有势力为敌\n"
            "3. 关注朝堂稳定度，勿让权臣坐大"
        ),
        unlock_reward={
            "type": "legacy_policy",
            "policy_id": "benevolent_rule",
            "name": "仁政遗训",
            "description": "新周目开局声望+10，朝堂稳定度+10",
        },
        legacy_data={
            "lesson_learned": "tyranny_fails",
            "next_game_bonus": {"reputation": 10, "court_stability": 10},
        },
    ),

    # ===========================================================
    # 结局二：偏安存续（NORMAL ENDING）
    # ===========================================================
    "survival_corner": EndingConfig(
        ending_id="survival_corner",
        tier=EndingTier.NORMAL,
        title="偏安存续",
        subtitle="山河破碎，独善其身",
        is_game_over=True,

        conditions={
            "type": "survival",
            "description": "在乱世中幸存但未能一统天下",
            "required": {
                "is_alive": True,
                "territory_ratio_max": 0.20,      # 领地不超过20%
                "min_round": 150,                   # 坚持150回合以上
                "treasury_min": 8000,
            },
            "alternative": {
                # 时间耗尽
                "round_max": 240,
            },
            "priority": 2,
        },

        scenes=[
            {
                "id": "scene_peaceful_town",
                "type": "visual_fade",
                "duration": 3.0,
                "narrative": "偏安一隅的城池，炊烟袅袅。",
                "visual": "ending-peaceful-town",
            },
            {
                "id": "scene_elder_talk",
                "type": "dialogue_sequence",
                "duration": 4.0,
                "narrative": "老人们围坐在城门口，讲述着当年群雄逐鹿的故事。",
                "visual": "ending-elders",
            },
            {
                "id": "scene_scholar_writing",
                "type": "final_scroll",
                "duration": 3.0,
                "narrative": "史官提笔，在竹简上写下：『虽未一统，然保境安民，亦有功于社稷。』",
                "visual": "ending-scroll-moderate",
            },
        ],
        music="melancholy_flute",
        visual_style="ending-tier-normal",

        epilogue=(
            "天下大局已定。卿虽据守一方，然民生殷实，城池稳固。"
            "百姓得以休养生息，商旅往来不绝。"
            "在这片乱世中，你所守护的这方净土，已胜过多少枭雄的功业。"
            "史官载曰：『守土安民，虽偏安而无愧。后世称其为小中兴之主。』"
        ),
        historian_comment=(
            "太史公曰：不争天下者，未必无大志。守一方平安，养一方生民，"
            "功在当代，利在千秋。然若能进取，或可成就更大功业。"
        ),
        npc_dialogues=[
            {
                "speaker": "徐达",
                "text": "主公，天下已定，群雄各有疆域。我们……当真不再进取了吗？",
                "emotion": "contemplative",
            },
            {
                "speaker": "李善长",
                "text": "如今民生渐复，国库充盈。主公仁德，百姓安居。此亦是一番功业。",
                "emotion": "content",
            },
            {
                "speaker": "城中老翁",
                "text": "多亏了主公，我们这里没有战火，子孙能平安长大。",
                "emotion": "grateful",
            },
        ],
        player_monologue=(
            "我立于城墙之上，望着远方的烽火与眼前的炊烟。"
            "这一生虽未统一天下，但我守护了这方百姓……也不算虚度。"
        ),

        statistics_bonus={
            "label": "安民值",
            "value_calc": "stewardship_score",
        },

        next_tier_hint=(
            "【天命启示】偏安非终点。下次争衡天下，可尝试：\n"
            "1. 在80回合前扩张至15%以上领土\n"
            "2. 外交合纵，寻找可吞并的弱小势力\n"
            "3. 解锁更多国策以增强国力"
        ),
        unlock_reward={
            "type": "legacy_strategy",
            "strategy_id": "early_expansion",
            "name": "进取图鉴",
            "description": "新周目开局获得额外1000银两、500粮草",
        },
        legacy_data={
            "lesson_learned": "expansion_needed",
            "next_game_bonus": {"treasury": 1000, "grain": 500},
        },
    ),

    # ===========================================================
    # 结局三：天下归心（GOOD ENDING）
    # ===========================================================
    "unification_harmony": EndingConfig(
        ending_id="unification_harmony",
        tier=EndingTier.GOOD,
        title="天下归心",
        subtitle="一统四海，天命所归",
        is_game_over=True,

        conditions={
            "type": "unification",
            "description": "以高声望统一天下",
            "required": {
                "is_alive": True,
                "territory_ratio_min": 0.75,    # 控制75%+领土
                "reputation_min": 65,             # 声望≥65
                "realm_stability_min": 50,        # 全域稳定度≥50
                "living_factions_max": 2,         # 最多1个其他势力存活
            },
            "priority": 3,
        },

        scenes=[
            {
                "id": "scene_grand_ceremony",
                "type": "visual_fade",
                "duration": 3.0,
                "narrative": "登基大典，万民朝拜。钟鼓齐鸣，礼炮震天。",
                "visual": "ending-golden-ceremony",
            },
            {
                "id": "scene_nobles_kneel",
                "type": "dialogue_sequence",
                "duration": 5.0,
                "narrative": "四方诸侯依次跪拜，献上降表与印绶。",
                "visual": "ending-nobles-kneel",
            },
            {
                "id": "scene_proclamation",
                "type": "scroll_reveal",
                "duration": 4.0,
                "narrative": "中书省宣读开国诏书：『朕承天命，扫清六合，一统寰宇……』",
                "visual": "ending-scroll-golden",
            },
            {
                "id": "scene_celebration",
                "type": "celebration",
                "duration": 3.0,
                "narrative": "百姓涌上街头，欢庆太平盛世的到来。",
                "visual": "ending-celebration",
            },
        ],
        music="grand_march",
        visual_style="ending-tier-good",

        epilogue=(
            "太庙之内，香火鼎盛。卿登坛告天，即皇帝位。"
            "国号新立，年号初定。昔日群雄割据的乱世，终在你的手中终结。"
            "四方来贺，万邦来朝。百姓得以重返故土，躬耕陇亩。"
            "史官载曰：『应天顺人，统一宇内。功德巍巍，垂范后世。』"
        ),
        historian_comment=(
            "太史公曰：自古得天下者，非惟武力，更在得人心。"
            "以仁德服众，以法治国，方成一代明君。"
            "然治国如烹小鲜，不可不慎。望后世子孙，持盈守成，毋坠鸿业。"
        ),
        npc_dialogues=[
            {
                "speaker": "刘基",
                "text": "陛下！天下已定，四海归心。此乃天命所归，万民之幸！",
                "emotion": "joyful",
            },
            {
                "speaker": "徐达",
                "text": "末将追随陛下南征北战十余载，今日终见天下一统，此生无憾矣！",
                "emotion": "proud",
            },
            {
                "speaker": "李善长",
                "text": "陛下登基，当颁新政：轻徭薄赋、休养生息。新朝气象，当自今日始。",
                "emotion": "wise",
            },
            {
                "speaker": "大都百姓",
                "text": "万岁！万岁！万万岁！",
                "emotion": "cheering",
            },
        ],
        player_monologue=(
            "我端坐龙椅之上，俯瞰群臣。这一路走来，刀光剑影、权谋博弈。"
            "今日终得天下归心。但我深知，统一只是开始，盛世尚需励精图治。"
        ),

        statistics_bonus={
            "label": "天命值",
            "value_calc": "mandate_score",
        },
        achievements=["unifier", "diplomatic_master"],

        next_tier_hint=(
            "【天命启示】一统天下只是开始。欲达至臻之境，还需：\n"
            "1. 声望达到90以上（广施仁政、大赦天下）\n"
            "2. 全域发展度达80以上（大兴土木、普及教育）\n"
            "3. 解锁全部国策\n"
            "4. 国库充盈至50000银两以上"
        ),
        unlock_reward={
            "type": "hidden_scenario",
            "scenario_id": "golden_age_challenge",
            "name": "盛世挑战",
            "description": "解锁隐藏剧本：以更高难度重新开始",
        },
        legacy_data={
            "lesson_learned": "benevolence_wins",
            "next_game_bonus": {"reputation": 15, "development_level": 10, "treasury": 3000},
        },
    ),

    # ===========================================================
    # 结局四：盛世新朝（TRUE ENDING / PERFECT ENDING）
    # ===========================================================
    "golden_age_dynasty": EndingConfig(
        ending_id="golden_age_dynasty",
        tier=EndingTier.TRUE,
        title="盛世新朝",
        subtitle="万世太平，光耀千古",
        is_game_over=True,

        conditions={
            "type": "golden_age",
            "description": "以极致治理创造黄金盛世",
            "required": {
                "is_alive": True,
                "territory_ratio_min": 0.85,
                "reputation_min": 85,
                "court_stability_min": 75,
                "realm_stability_min": 75,
                "development_level_min": 75,
                "treasury_min": 40000,
                "grain_min": 20000,
                "policies_unlocked_min": 8,       # 至少解锁8项国策
                "living_factions_max": 1,          # 唯一存活势力
                "disaster_count_max": 3,           # 近10回合内灾害不超过3次
            },
            "priority": 4,  # 最高优先级（超越普通统一结局）
        },

        scenes=[
            {
                "id": "scene_celestial_light",
                "type": "visual_fade",
                "duration": 4.0,
                "narrative": "紫气东来，祥云笼罩京师。",
                "visual": "ending-celestial",
            },
            {
                "id": "scene_grand_audience",
                "type": "grand_ceremony",
                "duration": 6.0,
                "narrative": "万国使节齐聚大殿，献上奇珍异宝。四海宾服，八方来朝。",
                "visual": "ending-world-audience",
            },
            {
                "id": "scene_abundant_fields",
                "type": "panorama",
                "duration": 4.0,
                "narrative": "镜头掠过金色的麦田、繁华的市集、书声琅琅的学堂。",
                "visual": "ending-abundance",
            },
            {
                "id": "scene_historians_record",
                "type": "scroll_reveal",
                "duration": 5.0,
                "narrative": "史官以金笔在玉册上书写：『此盛世也，万国来朝，百姓安居。功越三代，德配天地。』",
                "visual": "ending-jade-scroll",
            },
            {
                "id": "scene_legacy",
                "type": "final_panorama",
                "duration": 5.0,
                "narrative": "朝阳升起，照亮了崭新的王朝。新的时代，由此开启。",
                "visual": "ending-sunrise-dynasty",
            },
        ],
        music="imperial_anthem",
        visual_style="ending-tier-true",

        epilogue=(
            "天地为之开阔，日月为之增辉。"
            "卿以一己之力，不仅统一了分裂的山河，更创造了一个前所未有的盛世。"
            "朝有贤臣，野无遗贤。府库充盈，仓廪殷实。"
            "市井之间，胡商云集；学堂之内，书声琅琅。"
            "老有所养，幼有所教。路不拾遗，夜不闭户。"
            "史官以金简玉册载曰："
            "『圣德巍巍，功盖三代。开万世太平之基，创千古未有之业。后世尊为「开天圣祖」。』"
        ),
        historian_comment=(
            "太史公曰：三代以降，未有若此之盛者也。"
            "非惟武功盖世，更以文治安天下。仁德之君，万民之福。"
            "此非人力所能及，实乃天命所归、众望所归。"
            "后世治史者，每论及圣祖之治，无不肃然起敬。其功业，光照千古。"
        ),
        npc_dialogues=[
            {
                "speaker": "刘基",
                "text": "陛下！此非独武功之胜，更是文治之功。万世之后，仍将传颂陛下圣名！",
                "emotion": "awed",
            },
            {
                "speaker": "徐达",
                "text": "陛下知人善任，恩威并施。末将虽统兵百万，亦不过是陛下棋盘上一子耳。",
                "emotion": "humble_proud",
            },
            {
                "speaker": "李善长",
                "text": "陛下开创之盛世，堪比文景之治、贞观之世。老臣得见今日，死而无憾！",
                "emotion": "tearful_joy",
            },
            {
                "speaker": "马皇后",
                "text": "陛下为国操劳半生，今日终于可以歇一歇了。这江山，妾身陪您一同守护。",
                "emotion": "tender",
            },
            {
                "speaker": "波斯使者",
                "text": "伟大的皇帝陛下！我代表波斯国王，向您献上最珍贵的宝石与最诚挚的敬意！",
                "emotion": "reverent",
            },
        ],
        player_monologue=(
            "我站在太极殿最高处，俯瞰这座我亲手缔造的都城。"
            "金瓦在朝阳下熠熠生辉，远处的运河上帆樯如林。"
            "从一介草莽到天下之主，从群雄逐鹿到万国来朝。"
            "这一生，不负苍天，不负黎民，不负己心。"
            "新的时代已经开启。而我，将成为传说。"
        ),

        statistics_bonus={
            "label": "圣祖值",
            "value_calc": "sage_ruler_score",
        },
        achievements=["golden_age", "sage_ruler", "world_diplomat", "master_builder", "true_ending"],

        next_tier_hint="",  # 已达极致，无更上层

        unlock_reward={
            "type": "ultimate_unlock",
            "rewards": [
                {
                    "type": "save_slot",
                    "slot_id": "golden_save",
                    "name": "黄金存档",
                    "description": "解锁特殊存档槽，可随时重温盛世",
                },
                {
                    "type": "hidden_clue",
                    "clue_id": "dynasty_truth",
                    "name": "王朝真相",
                    "description": "揭示隐藏的历史真相：元末乱世的真正幕后推手",
                },
                {
                    "type": "new_game_plus",
                    "mode_id": "ngp_destiny",
                    "name": "天命再临",
                    "description": "解锁新周目特殊模式：继承部分国力重新开始",
                },
                {
                    "type": "art_gallery",
                    "gallery_id": "ending_art",
                    "name": "盛世画廊",
                    "description": "解锁结局概念艺术画廊",
                },
            ],
        },
        legacy_data={
            "lesson_learned": "perfection_achieved",
            "next_game_bonus": {
                "reputation": 25,
                "development_level": 20,
                "treasury": 5000,
                "grain": 3000,
                "court_stability": 15,
                "realm_stability": 15,
            },
            "unlocked_features": ["golden_save_slot", "hidden_lore", "new_game_plus"],
        },
    ),
}


# ================================================================
# 结局引擎
# ================================================================

class EndingEngine:
    """
    四大结局系统引擎
    
    职责：
    1. 每回合检查四大结局触发条件
    2. 管理渐进式结局状态
    3. 提供演出数据给前端
    4. 管理存档解锁与隐藏线索
    """

    def __init__(self, world: WorldState):
        self.world = world
        self._reached_endings: dict[str, dict] = {}  # 已达成的结局
        self._ending_history: list[dict] = []  # 结局达成历史
        self._hints_shown: set[str] = set()  # 已展示过的提示
        self._unlocked_rewards: dict[str, list[str]] = {}  # 已解锁奖励

    def _claimable_tile_count(self) -> int:
        """可被势力占领的地块总数（排除海域等不可占领地块）"""
        return sum(1 for t in self.world.tiles.values()
                   if t.tile_type != TileType.SEA)

    # ================================================================
    # 结局检测
    # ================================================================

    def check_all_endings(self) -> Optional[dict]:
        """
        检查所有结局条件，按优先级返回第一个触发的结局
        
        返回格式：
        {
            "triggered": True/False,
            "ending_id": "...",
            "config": EndingConfig序列化,
            "progression": {...},  # 渐进提示
            "is_game_over": True/False,
        }
        """
        player = self.world.get_player_faction()
        if not player:
            return None

        # 保护：开局前3回合不检查结局，给玩家起步时间
        if self.world.current_round < 3:
            return None

        total_tiles = self._claimable_tile_count()
        player_tiles = self.world.get_faction_tiles(player.faction_id)
        living = self.world.get_living_factions()
        territory_ratio = len(player_tiles) / max(total_tiles, 1)

        # 按优先级排序
        sorted_endings = sorted(
            ENDING_CONFIGS.values(),
            key=lambda e: e.conditions.get("priority", 99)
        )

        for ending in sorted_endings:
            if ending.ending_id in self._reached_endings:
                continue  # 已达成，跳过

            if self._check_ending_conditions(ending, player, player_tiles, territory_ratio, living, total_tiles):
                result = self._build_ending_result(ending, player, territory_ratio, len(player_tiles))
                self._reached_endings[ending.ending_id] = {
                    "round": self.world.current_round,
                    "year": self.world.current_year,
                    "result": result,
                }
                self._ending_history.append({
                    "ending_id": ending.ending_id,
                    "tier": ending.tier.value,
                    "round": self.world.current_round,
                    "year": self.world.current_year,
                    "title": ending.title,
                })
                return result

        # 无结局触发时，检查是否应该给出渐进提示
        self._check_progression_hints(player, territory_ratio, len(player_tiles))

        return None

    def _check_ending_conditions(
        self,
        ending: EndingConfig,
        player: FactionState,
        player_tiles: list,
        territory_ratio: float,
        living: list,
        total_tiles: int,
    ) -> bool:
        """检查单个结局的所有条件"""
        cond = ending.conditions
        req = cond.get("required", {})
        alt = cond.get("alternative", {})

        # 检查主条件
        if req:
            if not self._eval_conditions(req, player, player_tiles, territory_ratio, living, total_tiles):
                # 主条件不满足，检查替代条件
                if alt:
                    return self._eval_conditions(alt, player, player_tiles, territory_ratio, living, total_tiles)
                return False

        return True

    def _eval_conditions(
        self,
        conditions: dict,
        player: FactionState,
        player_tiles: list,
        territory_ratio: float,
        living: list,
        total_tiles: int,
    ) -> bool:
        """评估条件字典"""
        # is_alive
        if "is_alive" in conditions:
            if player.is_alive != conditions["is_alive"]:
                return False

        # territory_ratio_min / max
        if "territory_ratio_min" in conditions:
            if territory_ratio < conditions["territory_ratio_min"]:
                return False
        if "territory_ratio_max" in conditions:
            if territory_ratio > conditions["territory_ratio_max"]:
                return False

        # reputation
        if "reputation_min" in conditions:
            if player.reputation < conditions["reputation_min"]:
                return False
        if "reputation_max" in conditions:
            if player.reputation > conditions["reputation_max"]:
                return False

        # court_stability
        if "court_stability_min" in conditions:
            if player.court_stability < conditions["court_stability_min"]:
                return False
        if "court_stability_max" in conditions:
            if player.court_stability > conditions["court_stability_max"]:
                return False

        # realm_stability
        if "realm_stability_min" in conditions:
            if player.realm_stability < conditions["realm_stability_min"]:
                return False
        if "realm_stability_max" in conditions:
            if player.realm_stability > conditions["realm_stability_max"]:
                return False

        # development_level
        if "development_level_min" in conditions:
            if player.development_level < conditions["development_level_min"]:
                return False

        # treasury / grain
        if "treasury_min" in conditions:
            if player.treasury < conditions["treasury_min"]:
                return False
        if "grain_min" in conditions:
            if player.grain < conditions["grain_min"]:
                return False

        # round
        if "min_round" in conditions:
            if self.world.current_round < conditions["min_round"]:
                return False
        if "round_max" in conditions:
            # round_max 语义：回合数 >= round_max 时该条件满足（触发）
            # 回合数不足时不满足
            if self.world.current_round < conditions["round_max"]:
                return False

        # living factions
        if "living_factions_max" in conditions:
            if len(living) > conditions["living_factions_max"]:
                return False

        # all_hostile
        if conditions.get("all_hostile"):
            for f in living:
                if f.faction_id == player.faction_id:
                    continue
                rel = self.world.get_relation(player.faction_id, f.faction_id)
                if not rel or rel.stance != DiplomaticStance.WAR:
                    return False

        # policies
        if "policies_unlocked_min" in conditions:
            if len(player.unlocked_policies) < conditions["policies_unlocked_min"]:
                return False

        # disaster count (近10回合，仅统计影响玩家势力的灾害)
        if "disaster_count_max" in conditions:
            recent_disasters = [
                e for e in self.world.events_log
                if e.get("event_type") == "disaster"
                and e.get("round", 0) >= self.world.current_round - 10
                and e.get("faction_id") == player.faction_id
            ]
            if len(recent_disasters) > conditions["disaster_count_max"]:
                return False

        return True

    # ================================================================
    # 渐进式提示
    # ================================================================

    def _check_progression_hints(self, player: FactionState, territory_ratio: float, tile_count: int):
        """检查是否应给出渐进提示（引导玩家向更好结局努力）"""
        current_round = self.world.current_round

        # 每30回合检查一次
        hint_key = f"hint_r{current_round // 30 * 30}"
        if hint_key in self._hints_shown:
            return
        self._hints_shown.add(hint_key)

        # 根据当前状态判断最接近哪个结局，给出向上一级努力的提示
        if territory_ratio < 0.15 and current_round < 100:
            # 偏安先行者 → 提示如何达到偏安
            hint = ENDING_CONFIGS["survival_corner"].next_tier_hint
            self.world.events_log.append({
                "event_id": f"progression_hint_{current_round}",
                "event_type": "hint",
                "severity": "info",
                "round": current_round,
                "title": "【天命启示】治国之道",
                "description": hint,
                "faction_id": player.faction_id,
            })
        elif 0.15 <= territory_ratio < 0.5 and player.reputation >= 30:
            # 偏安级别 → 提示如何统一
            hint = ENDING_CONFIGS["unification_harmony"].next_tier_hint
            self.world.events_log.append({
                "event_id": f"progression_hint_{current_round}",
                "event_type": "hint",
                "severity": "info",
                "round": current_round,
                "title": "【天命启示】一统之道",
                "description": hint,
                "faction_id": player.faction_id,
            })
        elif territory_ratio >= 0.5 and player.reputation >= 60:
            # 接近统一级别 → 提示如何达到盛世
            hint = ENDING_CONFIGS["golden_age_dynasty"].next_tier_hint if ENDING_CONFIGS["golden_age_dynasty"].next_tier_hint else ""
            if not hint:
                hint = ENDING_CONFIGS["unification_harmony"].next_tier_hint
            self.world.events_log.append({
                "event_id": f"progression_hint_{current_round}",
                "event_type": "hint",
                "severity": "info",
                "round": current_round,
                "title": "【天命启示】盛世之基",
                "description": hint,
                "faction_id": player.faction_id,
            })

    # ================================================================
    # 结局结果构建
    # ================================================================

    def _build_ending_result(
        self,
        ending: EndingConfig,
        player: FactionState,
        territory_ratio: float,
        tile_count: int,
    ) -> dict:
        """构建完整的结局结果数据"""
        # 计算奖杯统计
        stats = self._calculate_ending_statistics(player, tile_count)

        # 计算与前一级结局的差距
        progression_gap = self._calculate_progression_gap(ending, player)

        # 构建解锁内容
        unlock_info = self._build_unlock_info(ending)

        return {
            "triggered": True,
            "ending_id": ending.ending_id,
            "tier": ending.tier.value,
            "tier_label": {
                "bad": "霸业陨落",
                "normal": "偏安存续",
                "good": "天下归心",
                "true": "盛世新朝",
            }.get(ending.tier.value, "未知"),
            "title": ending.title,
            "subtitle": ending.subtitle,
            "is_game_over": ending.is_game_over,

            # 演出数据
            "performance": {
                "scenes": ending.scenes,
                "music": ending.music,
                "visual_style": ending.visual_style,
            },

            # 叙词与对话
            "narrative": {
                "epilogue": ending.epilogue,
                "historian_comment": ending.historian_comment,
                "npc_dialogues": ending.npc_dialogues,
                "player_monologue": ending.player_monologue,
            },

            # 统计数据
            "statistics": {
                "rounds_played": self.world.current_round,
                "final_year": self.world.current_year,
                "territory_count": tile_count,
                "territory_ratio": round(territory_ratio * 100, 1),
                "reputation": player.reputation,
                "court_stability": player.court_stability,
                "realm_stability": player.realm_stability,
                "development_level": player.development_level,
                "treasury": player.treasury,
                "grain": player.grain,
                "total_troops": player.total_troops,
                "total_population": player.total_population,
                "policies_unlocked": len(player.unlocked_policies),
                "achievements": ending.achievements,
                "bonus_label": ending.statistics_bonus.get("label", ""),
                "bonus_score": stats.get("score", 0),
            },

            # 渐进信息
            "progression": {
                "next_tier_hint": ending.next_tier_hint,
                "current_tier": ending.tier.value,
                "next_tier": self._get_next_tier(ending.tier),
                "gap_analysis": progression_gap,
                "endings_reached": len(self._reached_endings),
                "total_endings": len(ENDING_CONFIGS),
            },

            # 解锁内容
            "unlocks": unlock_info,

            # 传承数据（用于新周目）
            "legacy": ending.legacy_data,
        }

    def _calculate_ending_statistics(self, player: FactionState, tile_count: int) -> dict:
        """计算结局统计数据与评分"""
        score = 0

        # 基础分数
        score += min(player.reputation, 100) * 2
        score += min(player.court_stability, 100)
        score += min(player.realm_stability, 100)
        score += min(player.development_level, 100) * 2
        score += tile_count * 10
        score += player.treasury // 100
        score += player.grain // 200
        score += player.total_population // 500
        score += len(player.unlocked_policies) * 50

        # 战斗统计
        battles_won = sum(1 for e in self.world.events_log
                         if e.get("event_type") == "battle"
                         and e.get("result") == "victory"
                         and e.get("faction_id") == player.faction_id)
        battles_total = sum(1 for e in self.world.events_log
                           if e.get("event_type") == "battle"
                           and e.get("faction_id") == player.faction_id)
        score += battles_won * 20

        return {
            "score": score,
            "battles_won": battles_won,
            "battles_total": battles_total,
            "officials_count": sum(1 for o in self.world.officials.values()
                                   if o.faction_id == player.faction_id),
        }

    def _calculate_progression_gap(self, current_ending: EndingConfig, player: FactionState) -> dict:
        """计算与更好结局的差距"""
        next_tier = self._get_next_tier(current_ending.tier)
        if not next_tier:
            return {"message": "已达最高结局，无需再进步", "gaps": []}

        # 找到下一级的结局配置
        next_ending = None
        for ending in ENDING_CONFIGS.values():
            if ending.tier == next_tier:
                next_ending = ending
                break

        if not next_ending:
            return {"message": "", "gaps": []}

        gaps = []

        # 检查各维度差距
        player_tiles = self.world.get_faction_tiles(player.faction_id)
        territory_ratio = len(player_tiles) / max(self._claimable_tile_count(), 1)

        next_req = next_ending.conditions.get("required", {})
        if "territory_ratio_min" in next_req:
            current_val = round(territory_ratio * 100, 1)
            target_val = round(next_req["territory_ratio_min"] * 100, 1)
            if territory_ratio < next_req["territory_ratio_min"]:
                gaps.append({"dimension": "领土占比", "current": current_val, "target": target_val, "unit": "%"})

        if "reputation_min" in next_req:
            if player.reputation < next_req["reputation_min"]:
                gaps.append({"dimension": "声望", "current": player.reputation, "target": next_req["reputation_min"], "unit": ""})

        if "court_stability_min" in next_req:
            if player.court_stability < next_req["court_stability_min"]:
                gaps.append({"dimension": "朝堂稳定度", "current": player.court_stability, "target": next_req["court_stability_min"], "unit": ""})

        if "realm_stability_min" in next_req:
            if player.realm_stability < next_req["realm_stability_min"]:
                gaps.append({"dimension": "全域稳定度", "current": player.realm_stability, "target": next_req["realm_stability_min"], "unit": ""})

        if "development_level_min" in next_req:
            if player.development_level < next_req["development_level_min"]:
                gaps.append({"dimension": "发展度", "current": player.development_level, "target": next_req["development_level_min"], "unit": ""})

        if "treasury_min" in next_req:
            if player.treasury < next_req["treasury_min"]:
                gaps.append({"dimension": "国库", "current": player.treasury, "target": next_req["treasury_min"], "unit": "银两"})

        if "grain_min" in next_req:
            if player.grain < next_req["grain_min"]:
                gaps.append({"dimension": "粮草", "current": player.grain, "target": next_req["grain_min"], "unit": "石"})

        if "policies_unlocked_min" in next_req:
            if len(player.unlocked_policies) < next_req["policies_unlocked_min"]:
                gaps.append({"dimension": "已解锁国策", "current": len(player.unlocked_policies), "target": next_req["policies_unlocked_min"], "unit": "项"})

        return {
            "message": next_ending.next_tier_hint if next_ending.next_tier_hint else "",
            "gaps": gaps,
            "next_ending_title": next_ending.title,
        }

    def _build_unlock_info(self, ending: EndingConfig) -> dict:
        """构建解锁信息"""
        info = {
            "has_rewards": bool(ending.unlock_reward),
            "rewards": [],
        }

        if not ending.unlock_reward:
            return info

        reward = ending.unlock_reward
        reward_type = reward.get("type", "")

        if reward_type == "ultimate_unlock":
            for r in reward.get("rewards", []):
                info["rewards"].append({
                    "type": r.get("type", ""),
                    "name": r.get("name", ""),
                    "description": r.get("description", ""),
                })
        else:
            info["rewards"].append({
                "type": reward_type,
                "name": reward.get("name", ""),
                "description": reward.get("description", ""),
            })

        return info

    # ================================================================
    # 辅助方法
    # ================================================================

    @staticmethod
    def _get_next_tier(current: EndingTier) -> Optional[EndingTier]:
        """获取下一个结局等级"""
        tier_order = [EndingTier.BAD, EndingTier.NORMAL, EndingTier.GOOD, EndingTier.TRUE]
        try:
            idx = tier_order.index(current)
            if idx < len(tier_order) - 1:
                return tier_order[idx + 1]
        except ValueError:
            pass
        return None

    def get_all_ending_progress(self) -> dict:
        """获取所有结局的进度状态"""
        player = self.world.get_player_faction()
        if not player:
            return {"endings": []}

        player_tiles = self.world.get_faction_tiles(player.faction_id)
        territory_ratio = len(player_tiles) / max(self._claimable_tile_count(), 1)

        progress = []
        for ending in ENDING_CONFIGS.values():
            reached = ending.ending_id in self._reached_endings
            condition_status = self._get_condition_status(ending, player, territory_ratio)

            progress.append({
                "ending_id": ending.ending_id,
                "title": ending.title,
                "subtitle": ending.subtitle,
                "tier": ending.tier.value,
                "tier_label": {
                    "bad": "霸业陨落",
                    "normal": "偏安存续",
                    "good": "天下归心",
                    "true": "盛世新朝",
                }.get(ending.tier.value, "未知"),
                "reached": reached,
                "conditions": condition_status,
            })

        return {"endings": progress}

    def _get_condition_status(self, ending: EndingConfig, player: FactionState, territory_ratio: float) -> dict:
        """获取单个结局的条件满足状态"""
        req = ending.conditions.get("required", {})
        status = {}
        player_tiles = self.world.get_faction_tiles(player.faction_id)
        living = self.world.get_living_factions()

        for key, target in req.items():
            if key == "is_alive":
                status[key] = {"met": player.is_alive == target, "current": player.is_alive, "target": target}
            elif key == "territory_ratio_min":
                status[key] = {"met": territory_ratio >= target, "current": round(territory_ratio * 100, 1), "target": round(target * 100, 1), "unit": "%"}
            elif key == "territory_ratio_max":
                status[key] = {"met": territory_ratio <= target, "current": round(territory_ratio * 100, 1), "target": round(target * 100, 1), "unit": "%"}
            elif key == "reputation_min":
                status[key] = {"met": player.reputation >= target, "current": player.reputation, "target": target}
            elif key == "reputation_max":
                status[key] = {"met": player.reputation <= target, "current": player.reputation, "target": target}
            elif key == "court_stability_min":
                status[key] = {"met": player.court_stability >= target, "current": player.court_stability, "target": target}
            elif key == "realm_stability_min":
                status[key] = {"met": player.realm_stability >= target, "current": player.realm_stability, "target": target}
            elif key == "realm_stability_max":
                status[key] = {"met": player.realm_stability <= target, "current": player.realm_stability, "target": target}
            elif key == "development_level_min":
                status[key] = {"met": player.development_level >= target, "current": player.development_level, "target": target}
            elif key == "treasury_min":
                status[key] = {"met": player.treasury >= target, "current": player.treasury, "target": target, "unit": "银两"}
            elif key == "grain_min":
                status[key] = {"met": player.grain >= target, "current": player.grain, "target": target, "unit": "石"}
            elif key == "min_round":
                status[key] = {"met": self.world.current_round >= target, "current": self.world.current_round, "target": target, "unit": "回合"}
            elif key == "living_factions_max":
                status[key] = {"met": len(living) <= target, "current": len(living), "target": target}
            elif key == "policies_unlocked_min":
                status[key] = {"met": len(player.unlocked_policies) >= target, "current": len(player.unlocked_policies), "target": target}
            elif key == "all_hostile":
                all_hostile = True
                for f in living:
                    if f.faction_id == player.faction_id:
                        continue
                    rel = self.world.get_relation(player.faction_id, f.faction_id)
                    if rel and rel.stance != DiplomaticStance.WAR:
                        all_hostile = False
                        break
                status[key] = {"met": all_hostile, "current": all_hostile, "target": True}
            elif key == "disaster_count_max":
                recent = sum(1 for e in self.world.events_log
                           if e.get("event_type") == "disaster"
                           and e.get("round", 0) >= self.world.current_round - 10)
                status[key] = {"met": recent <= target, "current": recent, "target": target, "unit": "次/10回合"}

        return status

    def get_ending_history(self) -> list[dict]:
        """获取结局达成历史"""
        return self._ending_history

    def get_legacy_data(self) -> dict:
        """获取所有已达成结局的传承数据汇总"""
        legacy = {"bonuses": {}, "lessons": [], "unlocked_features": []}

        for ending_id, data in self._reached_endings.items():
            config = ENDING_CONFIGS.get(ending_id)
            if not config:
                continue

            # 合并加成
            for key, val in config.legacy_data.get("next_game_bonus", {}).items():
                legacy["bonuses"][key] = legacy["bonuses"].get(key, 0) + val

            # 收集经验
            lesson = config.legacy_data.get("lesson_learned")
            if lesson:
                legacy["lessons"].append(lesson)

            # 解锁功能
            for feat in config.legacy_data.get("unlocked_features", []):
                if feat not in legacy["unlocked_features"]:
                    legacy["unlocked_features"].append(feat)

        return legacy


# ================================================================
# 全局单例
# ================================================================

_ending_engine: Optional[EndingEngine] = None


def get_ending_engine(world: Optional[WorldState] = None) -> Optional[EndingEngine]:
    """获取结局引擎单例"""
    global _ending_engine
    if world:
        _ending_engine = EndingEngine(world)
    return _ending_engine


def reset_ending_engine():
    """重置结局引擎"""
    global _ending_engine
    _ending_engine = None


# ================================================================
# 结局配置导出（供前端使用）
# ================================================================

def export_ending_configs() -> dict:
    """导出所有结局配置（不含内部逻辑，仅展示数据）"""
    result = {}
    for ending_id, config in ENDING_CONFIGS.items():
        result[ending_id] = {
            "ending_id": config.ending_id,
            "tier": config.tier.value,
            "title": config.title,
            "subtitle": config.subtitle,
            "is_game_over": config.is_game_over,
            "scenes": config.scenes,
            "music": config.music,
            "visual_style": config.visual_style,
            "epilogue": config.epilogue,
            "historian_comment": config.historian_comment,
            "npc_dialogues": config.npc_dialogues,
            "player_monologue": config.player_monologue,
            "achievements": config.achievements,
            "next_tier_hint": config.next_tier_hint,
            "unlock_reward": config.unlock_reward,
        }
    return result
