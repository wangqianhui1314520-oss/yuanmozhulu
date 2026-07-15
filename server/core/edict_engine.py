"""
圣旨推演引擎 - AI驱动的自然语言圣旨解析与执行（3.0 增强版）

核心流程:
1. 接收自然语言圣旨文本 + 完整游戏状态
2. 【NLP预处理】实体提取、意图分类、数字转换
3. 调用 AI 模型（advisor）解析圣旨意图（含预处理提示）
4. AI 返回结构化的操作指令列表（JSON）
5. 【JSON修复】多策略鲁棒解析 + 自动修复
6. 引擎验证并执行所有指令到 world_state
7. 返回执行摘要 + 更新的世界状态

增强特性:
- 集成 edict_nlp 预处理管道（实体提取/意图分类/数字转换）
- Few-shot 示例提示（提升 AI 输出质量）
- 多策略 JSON 鲁棒解析与修复
- 本地回退解析（AI 不可用时仍能识别基本指令）
- 智能参数估计与自动补全
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from typing import Optional

from server.core.edict_nlp import (
    extract_numbers,
    extract_faction_names,
    extract_action_intents,
    build_preprocess_hint,
    parse_edict_locally,
    robust_json_parse,
    repair_json,
    classify_edict,
    cn_num_to_int,
    get_edict_context,
)

logger = logging.getLogger("yuanmo.edict_engine")

# 支持的所有操作类型及其描述（供 AI 参考）
AVAILABLE_ACTIONS = {
    # ===== 军事 (6种) =====
    "recruit": {
        "desc": "征兵 - 在地块上招募士兵，消耗银两和军械",
        "params": ["tile_id", "amount"],
        "costs": "每兵2-3银两（城池3），每3兵消耗1军械",
        "effects": "treasury减少、arms减少、tile.troops增加、tile.population减少、tile.morale-3"
    },
    "buy_horses": {
        "desc": "买马 - 购买战马，需要马场",
        "params": ["amount"],
        "costs": "每匹5银两",
        "effects": "treasury减少、horses增加"
    },
    "train_troops": {
        "desc": "训练 - 训练士兵提升精锐度和士气",
        "params": ["tile_id", "amount"],
        "costs": "每兵1银两，每2兵1粮草",
        "effects": "treasury减少、grain减少、tile.morale+10、tile.elite_ratio增加"
    },
    "march": {
        "desc": "行军/进攻 - 从一地调兵到另一地（若目标为敌方则发生战斗）",
        "params": ["from_tile", "to_tile", "troops"],
        "costs": "每兵2粮草（行军消耗）",
        "effects": "from_tile.troops减少、目标地块可能易主、兵力损耗"
    },
    "fortify": {
        "desc": "加固城防 - 提升地块防御等级",
        "params": ["tile_id"],
        "costs": "300×(当前城防等级+1)银两",
        "effects": "treasury减少、tile.fortification+1"
    },
    "scout": {
        "desc": "侦查 - 侦查目标地块军情",
        "params": ["target_tile"],
        "costs": "无直接消耗",
        "effects": "返回目标地块信息"
    },

    # ===== 内政 (8种) =====
    "develop": {
        "desc": "屯田开发 - 开发地块设施（water水利/granary粮仓/clinic医馆/farmland农田）",
        "params": ["tile_id", "type"],
        "costs": "500银两",
        "effects": "treasury减少、tile相应设施等级+1、development_level+1"
    },
    "build": {
        "desc": "建造 - 建造建筑（granary粮仓/armory军械所/stable马场/port港口/clinic医馆/wall城墙等12种）",
        "params": ["tile_id", "building"],
        "costs": "粮仓250/军械所800/马场600/港口400/医馆200/农田300/工坊500/征兵营350/烽燧200/寺庙400/城墙600/码头400银两",
        "effects": "treasury减少、tile相应建筑+1"
    },
    "relief": {
        "desc": "赈灾 - 救济灾民，恢复民心，消除灾害",
        "params": ["tile_id"],
        "costs": "人口×1%的粮草",
        "effects": "grain减少、tile.morale+10、tile.disasters清空"
    },
    "tax": {
        "desc": "税政 - 调整税率（heavy重税/light减税/normal正常）",
        "params": ["tax_type"],
        "costs": "无直接消耗",
        "effects": "heavy: realm_stability-5, treasury+每回合多收; light: realm_stability+5"
    },
    "convict_labor": {
        "desc": "徭役 - 征发民夫进行大型工程（修路/筑城/开渠），消耗民心换发展度",
        "params": ["tile_id", "project"],
        "costs": "tile.morale-8、tile.population-100",
        "effects": "tile.fortification+2 或 tile.development_level+3、总体发展提升"
    },
    "cultural_policy": {
        "desc": "文教 - 推行文化教育政策（开科举/兴书院/修史书），长期提升声望和人才",
        "params": ["policy_type"],
        "costs": "800银两",
        "effects": "reputation+5、realm_stability+3、解锁新文臣NPC概率提升"
    },
    "sea_policy": {
        "desc": "海策 - 海洋政策（开海贸/禁海/建水师），影响贸易收入和海军实力",
        "params": ["policy_type"],
        "costs": "开海贸收入+200/回合; 建水师1000银两",
        "effects": "港口收入变化、水师战力变化、海外情报获取"
    },
    "medical": {
        "desc": "医政 - 配置医馆加强瘟疫防治，降低人口损耗",
        "params": ["tile_id"],
        "costs": "400银两",
        "effects": "tile.clinic+1、tile.plague_resistance+10、人口自然增长+2%"
    },

    # ===== 外交 (1种) =====
    "diplomacy": {
        "desc": "外交 - 改变外交关系（alliance同盟/war宣战/truce停战/trade通商/marriage联姻/tribute纳贡/vassal附庸）",
        "params": ["target_faction", "diplomacy_type"],
        "costs": "同盟800银/停战300银/通商200银/联姻500银/纳贡500银/附庸1000银/宣战0银",
        "effects": "外交关系变更、treasury可能减少"
    },

    # ===== 细作/特殊军事 (3种) =====
    "spy": {
        "desc": "细作 - 派遣间谍（deploy部署/intel情报/sabotage破坏/assassinate刺杀）",
        "params": ["target_faction", "spy_action"],
        "costs": "200银两",
        "effects": "treasury减少、谍报网络建立"
    },
    "ambush": {
        "desc": "伏击 - 在指定地块设伏，待敌军经过时突袭",
        "params": ["tile_id", "troops"],
        "costs": "每兵1粮草（埋伏消耗）",
        "effects": "伏击成功后敌方兵力损失×1.5、士气重创"
    },
    "plunder": {
        "desc": "劫掠 - 派遣部队劫掠敌方地块，夺取资源",
        "params": ["target_tile", "troops"],
        "costs": "每兵1粮草",
        "effects": "夺取目标银两和粮草、目标地块民心-20、外交关系恶化"
    },

    # ===== 朝堂 (3种) =====
    "enfeoff": {
        "desc": "分封 - 分封官员到地块，提升治理效率",
        "params": ["official_id", "tile_id"],
        "costs": "1000银两",
        "effects": "treasury减少、tile.governor设置、该地块发展速度+15%"
    },
    "amnesty": {
        "desc": "大赦 - 大赦天下，释放囚犯，提升民心",
        "params": [],
        "costs": "无直接消耗",
        "effects": "reputation+10、realm_stability+5、prisoners清空"
    },
    "move_capital": {
        "desc": "迁都 - 将都城迁至指定地块",
        "params": ["tile_id"],
        "costs": "10000银两、500粮草",
        "effects": "treasury减少、grain减少、旧都降级、新都设为capital、realm_stability-10（短期动荡）"
    },
}


def get_season_strategy_hint(world_state: dict) -> str:
    """根据当前季节返回战略提示"""
    season = world_state.get("current_season", "春")
    hints = {
        "春": "春季募兵恢复快（+7%）、人口增长旺盛（×1.6），宜招兵买马、屯田开发。春汛融雪可能引发洪水。",
        "夏": "夏季粮耗略增（×1.1）、洪水蝗灾高发，宜加固水利、储备粮草。海运贸易繁忙（港口收入100银）。",
        "秋": "秋高气爽宜出征（攻方×1.1）、税收最高（×1.3）、粮仓产出大增（×1.8）。是扩张领土的最佳时机！",
        "冬": "严冬耗粮大增（×1.4）、进攻削弱（×0.75）、守城有利（×1.15）。宜休养生息、加固城防、储备粮草。冬季无人口增长，灾害概率上升。",
    }
    return hints.get(season, "根据当前局势相机行事。")


# ================================================================
# 古代圣旨文体模板库 —— 严格遵循明代圣旨格式规范
# ================================================================
EDICT_FORMAT_SPEC = """
## 圣旨文体格式规范（严格遵循）

圣旨并非仅有一种格式。尔需根据政令内容类别，选用恰当的圣旨文体与起首套语，
使每一道圣旨都符合元末明初的真实制书规范。

### 一、圣旨通用三段结构

每道圣旨须包含三大结构层：
1. **起首语**（开宗明义）—— 文体标识 + 帝王自称
2. **正文敕谕**（布告天下）—— 事由缘起 → 处置措施 → 敕命对象 → 施行要求
3. **结尾套语**（收束全篇）—— 固定套语收尾

### 二、圣旨七大文体及其选用规则

#### 甲、诏书 —— 最隆重的布告天下文书
- **适用场景**：大政方针、军事讨伐、改元建制、宣战议和、迁都定鼎、综合施政
- **起首套语**：「奉天承运皇帝，诏曰：」
- **正文特征**：以"朕闻/朕观/朕承天命"起论，陈述缘由后以"今命/特命/着"转承敕令
- **结尾套语**：「布告天下，咸使闻知。」或「钦此。」
- **辞气**：庄严凝重，气吞山河，多用四六骈句

#### 乙、制书 —— 行赏封拜的制度文书
- **适用场景**：册封爵位、任命官职、恩赏功臣、大赦天下
- **起首套语**：「奉天承运皇帝，制曰：」
- **正文特征**：以"朕惟"起论品德功绩，以"特授/册封/进爵"表述任命
- **结尾套语**：「钦哉。」或「钦此。」
- **辞气**：典雅庄重，褒扬为主，多用典故

#### 丙、敕谕 —— 训诫督责的军政权令
- **适用场景**：调兵遣将、军事征伐、边境戍守、戒严整军、斥责警告
- **起首套语**：「奉天承运皇帝，敕曰：」
- **正文特征**：以"朕闻兵者国之大事"起论，语气严切果断
- **结尾套语**：「故敕。」或「钦此。」
- **辞气**：威严刚毅，不容置辩，简短有力

#### 丁、册书 —— 册立封赠的礼仪文书
- **适用场景**：册立储君、册封王侯、追赠谥号、封疆裂土
- **起首套语**：「奉天承运皇帝，册曰：」
- **正文特征**：以"朕惟"起论，详述功绩德望，以"是用册尔为/特册封"宣示
- **结尾套语**：「钦哉。」或「钦此。」
- **辞气**：隆重典雅，多用典故与排比

#### 戊、诰命 —— 封赠诰敕的恩赏文书
- **适用场景**：旌表忠义、恩赏抚恤、赦免减刑、褒奖功勋
- **起首套语**：「奉天承运皇帝，诰曰：」
- **正文特征**：以"朕闻忠臣不恤其身"起论，以"特赐/特旨恩赏"表述
- **结尾套语**：「钦此。」
- **辞气**：温厚和煦，体现天恩浩荡

#### 己、令旨 —— 日常政务的敕令文书
- **适用场景**：内政建设、赋税征收、屯田开发、水利兴修、医馆营造
- **起首套语**：「奉天承运皇帝，令曰：」
- **正文特征**：以"朕念/朕惟民生为本"起论，以"着/命/令"转承
- **结尾套语**：「钦此。」
- **辞气**：平实庄重，务实而具条理

#### 庚、敕命 —— 机密专令的特敕文书
- **适用场景**：密诏行间、派间谍刺探、设伏伏击、劫掠敌境
- **起首套语**：「奉天承运皇帝，密敕：」
- **正文特征**：以"朕惟兵不厌诈"起论，语气机密切要
- **结尾套语**：「钦此。』（或「故密敕。」）
- **辞气**：机密切要，不求铺陈，务求精准

### 三、文体自动选择规则

依圣旨涉及的主要政令类别，按以下优先级择定文体：
1. 涉及 enfeoff / amnesty 任一 → **制书**（制曰）/ **诰命**（诰曰）
2. 涉及 march / fortify / scout / train_troops 为主 → **敕谕**（敕曰）
3. 涉及 diplomacy=war → **诏书**（诏曰）
4. 涉及 develop / build / relief / tax / cultural_policy / medical 为主 → **令旨**（令曰）
5. 涉及 spy / ambush / plunder 任一 → **敕命**（密敕）
6. 涉及 recruit / buy_horses 与军事、内政混合 → **诏书**（诏曰）
7. 涉及 move_capital → **诏书**（诏曰）
8. 外交结盟(diplomacy=alliance / vassal / trade 等) → **诏书**（诏曰）

### 四、正文写作规范

1. **用词须古雅精准**：多用"朕、尔、卿、诸、其、之、者、也、矣、焉、乎"等文言虚词
2. **句式须骈散结合**：重要政令宜用四六骈句，如"征兵于内，固防于外；养民以时，练兵以法"
3. **帝王自称统一**：正文中统一用"朕"，不混用"寡人""孤"等先秦称谓
4. **敕令动词须多样**：不可处处用"命"，宜根据语气交替使用"着、令、敕、命、诏、谕、责成、饬令"等
5. **引经据典自然**：可适当化用"兵者国之大事""民为邦本""居安思危"等经典典故，但不可堆砌
6. **时效修辞**：元末背景可涉及"扫清胡虏""恢复中华""戡乱""鼎新"等时代语境
7. **称谓规范**：势力名称应称为"伪×""×寇""×逆"（敌对）或"×国""×藩"（中立/同盟）

### 五、edict_language 字段输出规范

在 JSON 输出的 edict_language 字段中，必须输出完整的文言圣旨正文：
- **开头**：严格使用匹配的起首套语（诏曰/制曰/敕曰/册曰/诰曰/令曰/密敕）
- **正文**：文言文，完整表述君主意图，150-250字
- **结尾**：严格使用匹配的结尾套语
- **禁止**：不可在白话文前后加圣旨套语，必须全篇文言文
- **禁止**：不可将散文体或白话文塞入圣旨格式
"""


def build_system_prompt(faction_name: str, world_summary: str, edict_history: list = None) -> str:
    """构建 AI 系统提示词（含历史上下文 + 圣旨文体模板库）"""
    actions_by_category = {
        "军事": ["recruit", "buy_horses", "train_troops", "march", "fortify", "scout"],
        "内政": ["develop", "build", "relief", "tax", "convict_labor", "cultural_policy", "sea_policy", "medical"],
        "外交": ["diplomacy"],
        "细作": ["spy", "ambush", "plunder"],
        "朝堂": ["enfeoff", "amnesty", "move_capital"],
    }

    actions_desc = []
    for category, action_names in actions_by_category.items():
        actions_desc.append(f"### {category}")
        for name in action_names:
            info = AVAILABLE_ACTIONS[name]
            actions_desc.append(
                f"- **{name}**: {info['desc']}\n"
                f"  参数: {', '.join(info['params'])}\n"
                f"  消耗: {info['costs']}\n"
                f"  效果: {info['effects']}"
            )

    # 构建历史上下文
    history_context = ""
    if edict_history and len(edict_history) > 0:
        history_lines = []
        for h in edict_history[-5:]:
            history_lines.append(
                f"- 第{h.get('round', '?')}回合「{h.get('text', '')[:60]}」"
                f"→ 执行{h.get('executed', 0)}条，失败{h.get('failed', 0)}条"
            )
        if history_lines:
            history_context = f"""
## 近期圣旨历史
{chr(10).join(history_lines)}

请注意避免重复已执行的指令，若圣旨内容与前序重复，应智能合并或调整策略。
"""

    return f"""你是元末乱世中的尚书省首辅兼翰林学士，精通六朝骈文与唐宋诏敕，深谙明代圣旨制书轨范。
你的使命是：承君主之意，撰庙堂之文。每一道圣旨都必须如出自翰林院真正学士之手。

当前你辅佐的势力是「{faction_name}」。你需要像一个真正的首辅大臣一样思考：权衡利弊、量力而行、审时度势。

## 当前天下局势
{world_summary}
{history_context}
{EDICT_FORMAT_SPEC}

## 📖 Few-shot 多文体示例

### 示例1：军事征伐 → 敕谕体（敕曰）
圣旨：「征兵三千，加固应天城防，再派兵三千攻打张士诚的高邮」
→ 应解析为：
```json
{{"intent_analysis": "此旨意在扩军备战，巩固都城后主动出击。需征兵、固防、出征三项。主军事，选敕谕体。", "narrative": "臣谨领圣意。拟于应天征兵三千，加固城防以固根本；而后调精兵三千出师高邮。然府库需备银九千余两，粮六千石，恳请陛下明鉴。", "resource_assessment": "征兵三千需银六千两、军械千件；行军三千需粮六千石；加固城防需银三百两起。总计约需银万余两。", "edict_language": "奉天承运皇帝，敕曰：朕闻兵者国之大事，死生之地，存亡之道。今观天下未定，贼寇环伺，不可不察。着大都督府于应天征募精兵三千，加固城垣，以备不虞。复命征南将军率虎贲三千，出师高邮，讨伐张逆士诚。各部整军砺卒，限期克日，毋得迁延贻误。故敕。", "commands": [{{"action": "recruit", "params": {{"tile_id": "应天", "amount": 3000}}, "reason": "扩充京师守备", "priority": "high"}}, {{"action": "fortify", "params": {{"tile_id": "应天"}}, "reason": "加固都城防御", "priority": "high"}}, {{"action": "march", "params": {{"from_tile": "应天", "to_tile": "高邮", "troops": 3000}}, "reason": "讨伐张士诚", "priority": "high"}}], "risk_warning": "同时征兵与出征耗资巨大，若府库不足则建议分步执行", "follow_up_suggestion": "出兵后关注陈友谅动向", "summary": "应天征兵三千、加固城防、出兵三千讨伐张士诚——敕谕体"}}
```

### 示例2：内政建设 → 令旨体（令曰）
圣旨：「在应天建造一座粮仓和一座军械所」
→ 应解析为：
```json
{{"intent_analysis": "充实京师仓储与军备，属内政建设。纯内政，选令旨体。粮仓+军械所共需银1600两。", "narrative": "臣领旨。拟于应天建粮仓、军械所各一，以实仓储、充军备。共需银一千六百两。", "resource_assessment": "粮仓800银、军械所800银，合计1600银。", "edict_language": "奉天承运皇帝，令曰：朕惟仓储乃国之命脉，军备为战之本，二者不可偏废。今命工部于应天监造粮仓、军械所各一，务于三月内竣工。所费银一千六百两，着户部如数拨付，不得减省。钦此。", "commands": [{{"action": "build", "params": {{"tile_id": "应天", "building": "granary"}}, "reason": "建造粮仓储备粮草", "priority": "medium"}}, {{"action": "build", "params": {{"tile_id": "应天", "building": "armory"}}, "reason": "建造军械所补充装备", "priority": "medium"}}], "risk_warning": "", "follow_up_suggestion": "粮仓建成后可屯田开发", "summary": "应天建造粮仓、军械所各一——令旨体"}}
```

### 示例3：外交宣战结盟 → 诏书体（诏曰）
圣旨：「派使臣与方国珍结盟，同时向陈友谅宣战」
→ 应解析为：
```json
{{"intent_analysis": "远交近攻之策。结盟方国珍可牵制陈友谅侧翼。外交大事，选诏书体。", "narrative": "臣谨领圣意。遣使臣赴方国珍处议盟，以固东面之势；传缴讨伐陈友谅。此乃远交近攻之良策。", "resource_assessment": "结盟不需额外开支，宣战亦无直接消耗。但开战后粮草消耗大增。", "edict_language": "奉天承运皇帝，诏曰：朕观陈友谅僭号称帝，据江汉而窥天下，荼毒生民，罪在不赦。今命礼部遣使东赴方国珍处，约为同盟，共谋戡乱。复诏大都督府传缴天下，声讨陈逆之罪，克日兴师问罪。凡我臣民，咸使闻知。钦此。", "commands": [{{"action": "diplomacy", "params": {{"target_faction": "方国珍", "diplomacy_type": "alliance"}}, "reason": "与方国珍结盟", "priority": "high"}}, {{"action": "diplomacy", "params": {{"target_faction": "陈友谅", "diplomacy_type": "war"}}, "reason": "正式讨伐陈友谅", "priority": "high"}}], "risk_warning": "两面外交需防方国珍首鼠两端", "follow_up_suggestion": "宣战后立即集结兵力于边境", "summary": "与方国珍结盟、向陈友谅宣战——诏书体"}}
```

### 示例4：恩赏大赦 → 诰命体（诰曰）
圣旨：「大赦天下，免除今年赋税」
→ 应解析为：
```json
{{"intent_analysis": "收拢民心之策。大赦+免税双管齐下，属恩赏恤民，选诰命体。", "narrative": "臣遵旨。大赦天下可收人心，免赋税可养民力。此乃王道之政。", "resource_assessment": "大赦需仪式开销约200银；免赋税将损失本回合税收收入。但民心可大幅提升。", "edict_language": "奉天承运皇帝，诰曰：朕闻天心仁爱，以恤民为本。连年兵革，生灵涂炭，朕心恻然。今特颁恩旨，大赦天下，除谋逆不赦外，余皆释之。今年赋税悉数蠲免，与民休息。布告遐迩，咸使闻知。钦此。", "commands": [{{"action": "amnesty", "params": {{}}, "reason": "大赦天下收拢民心", "priority": "high"}}, {{"action": "tax", "params": {{"tax_policy": "exempt"}}, "reason": "免除赋税养民", "priority": "high"}}], "risk_warning": "免赋税将严重影响府库收入，建议提前储备", "follow_up_suggestion": "民心回升后可适当募兵", "summary": "大赦天下、蠲免今年赋税——诰命体"}}
```

### 示例5：全面扩军备战 → 敕谕体（敕曰）
圣旨：「加强军备」
→ 应解析为：
```json
{{"intent_analysis": "模糊指令，解读为扩充军事实力。主军事，选敕谕体。根据当前资源适度征兵+买马+训练。", "narrative": "臣遵旨。军备之道，不外扩兵、购马、训练三事。今择其要者行之。", "resource_assessment": "根据府库状况选择合适规模。若银两充足则全做，若不足则优先征兵。", "edict_language": "奉天承运皇帝，敕曰：朕观边患未已，战守之备不可一日废弛。着大都督府征募新兵，以实营伍；市易战马，以壮骑军；整训士卒，以精其技。各营厉兵秣马，毋得怠忽。故敕。", "commands": [{{"action": "recruit", "params": {{"tile_id": "应天", "amount": 1000}}, "reason": "扩充兵力", "priority": "high"}}, {{"action": "buy_horses", "params": {{"amount": 200}}, "reason": "补充战马", "priority": "medium"}}, {{"action": "train_troops", "params": {{"tile_id": "应天", "amount": 1000}}, "reason": "提升军队战力", "priority": "medium"}}], "risk_warning": "", "follow_up_suggestion": "", "summary": "征兵一千、购马二百、训练军队——敕谕体"}}
```

## 可用政令类型（共{len(AVAILABLE_ACTIONS)}种）
{chr(10).join(actions_desc)}

## 输出格式
你必须以严格的JSON格式输出，不得有任何多余文字：

```json
{{
  "intent_analysis": "对圣旨的深度分析（含军事/经济/外交/民生四维度，100字以内）",
  "narrative": "以古文口吻的批复，体现首辅风范（100字以内）",
  "resource_assessment": "当前资源评估和建议分配",
  "edict_language": "完整的文言圣旨正文。严格根据政令类别选择文体（诏曰/制曰/敕曰/册曰/诰曰/令曰/密敕），遵循起首套语→正文敕谕→结尾套语的三段结构。全篇文言文，150-250字。",
  "commands": [
    {{
      "action": "操作类型",
      "params": {{"参数名": "参数值"}},
      "reason": "执行此指令的战略理由（30字以内）",
      "priority": "high|medium|low"
    }}
  ],
  "risk_warning": "若圣旨存在冒险之处，需在此警示君主（可选，30字以内）",
  "follow_up_suggestion": "建议下一回合的行动方向（可选，40字以内）",
  "summary": "圣旨执行摘要（50字以内）"
}}
```

## 核心规则（严格遵守）
1. 每个 command 的 action 必须严格来自上述可用政令类型，不得编造新类型
2. params 必须包含该 action 所需的所有必填参数，参数值需与游戏实际数据匹配（地块名/势力名）
3. 如果圣旨内容模糊（如"加强军备"），合理分解为多条具体指令
4. 如果圣旨要求的行为没有对应操作类型，用最接近的替代（如"开仓放粮"→ relief）
5. 合理估计数值（"大量征兵"→ 1000-3000人，"倾国之力"→ 3000-5000人，"少许"→ 300-800人）
6. 严格不超过游戏机制限制（征兵≤5000、买马≤1000、行军≤10000、建筑每类每地块1次）
7. 同一地块同类操作只生成一次（不可对同一地块 recruit 两次）
8. 优先选择玩家已拥有的地块作为操作目标
9. **智能资源分配**：根据府库余额调整指令规模，国库空虚时缩减规模或建议加税/劫掠
10. 遇到敌方地块操作，需确认目标势力存在且 tile_id 正确
11. 参数中的 faction 名称/tile_id 要与游戏实际数据名称匹配（参考用户提示中的己方地块列表）
12. commands 数组至少1条（除非圣旨完全无法理解），最多不超过8条
13. priority：主动进攻/宣战=high，日常建设=medium，辅助性操作=low
14. **edict_language 必须根据政令类别选择正确的圣旨文体**：军事用「敕曰」、内政用「令曰」、恩赏用「诰曰」/「制曰」、外交宣战用「诏曰」、细作用「密敕」。严禁一律使用「诏曰」！全文须为地道文言文，结尾套语须与起首文体匹配。

## 四季战略要诀
- **春**（恢复率+7%、人口×1.6）：募兵恢复快，宜招兵买马、屯田开发。春汛融雪可能引发洪水
- **夏**（粮耗×1.1、洪蝗高发）：宜加固水利、储备粮草。海运贸易繁忙（港口收入100银）
- **秋**（攻方×1.1、税收×1.3、粮仓产出×1.8）：最佳扩张时机！宜出兵征伐、征收赋税
- **冬**（粮耗×1.4、攻方×0.75、守方×1.15）：宜休养生息、加固城防、储备粮草。民心每回合-3

## 进阶策略指引
- **多线作战时**：优先加固边境城防，不宜四面出击
- **国库充盈时**（>5000银）：考虑迁都、大兴土木或大规模扩军
- **国库空虚时**（<1000银）：建议减税养民或对富庶邻国用兵劫掠
- **民心低落时**（<30）：优先赈灾、大赦或减税，暂缓征兵徭役
- **军力强盛时**（>5000兵）：积极对外扩张、劫掠或迫使邻国纳贡
- **身陷重围时**：以外交分化敌人，不宜多线作战"""


def build_user_prompt(edict_text: str, world_state: dict) -> str:
    """构建用户提示词（含完整游戏状态 + NLP预处理提示）"""
    player_faction_id = world_state.get("player_faction_id", "")
    factions = world_state.get("factions", {})
    tiles = world_state.get("tiles", {})

    # 玩家势力信息
    player = factions.get(player_faction_id, {})
    player_tiles = {
        tid: t for tid, t in tiles.items()
        if t.get("faction_id") == player_faction_id
    }

    # 其他势力摘要
    other_factions = []
    for fid, f in factions.items():
        if fid != player_faction_id and f.get("is_alive", False):
            other_factions.append(
                f"{f.get('name', fid)}({fid}): "
                f"兵力{f.get('total_troops', 0)} "
                f"人口{f.get('total_population', 0)} "
                f"城池{f.get('tile_count', 0)}"
            )

    # 玩家地块摘要（增加更多细节）
    tile_summary = []
    for tid, t in player_tiles.items():
        detail = (
            f"  {t.get('tile_name', tid)}({tid}): "
            f"类型{t.get('tile_type', '?')} "
            f"兵力{t.get('troops', 0)} "
            f"人口{t.get('population', 0)} "
            f"民心{t.get('morale', 50)} "
            f"城防{t.get('fortification', 0)}"
            f" 发展度{t.get('development_level', 0)}"
        )
        if t.get('stable', 0) > 0:
            detail += f" 马场{t.get('stable', 0)}"
        if t.get('armory', 0) > 0:
            detail += f" 军械所{t.get('armory', 0)}"
        if t.get('granary', 0) > 0:
            detail += f" 粮仓{t.get('granary', 0)}"
        if t.get('clinic', 0) > 0:
            detail += f" 医馆{t.get('clinic', 0)}"
        if t.get('is_port'):
            detail += " [港口]"
        if t.get('is_capital'):
            detail += " [都城]"
        if t.get('disasters'):
            detail += f" ⚠灾害:{','.join(t.get('disasters', []))}"
        tile_summary.append(detail)

    # 外交关系
    relations = world_state.get("relations", {})
    diplomacy_summary = []
    for key, rel in relations.items():
        a, b = key.split("|") if "|" in key else ("", "")
        if a == player_faction_id or b == player_faction_id:
            other = b if a == player_faction_id else a
            other_f = factions.get(other, {})
            diplomacy_summary.append(
                f"  vs {other_f.get('name', other)}: "
                f"{rel.get('stance', 'neutral')} "
                f"(态度{rel.get('attitude', 0)})"
            )

    # NLP预处理提示
    nlp_hint = build_preprocess_hint(edict_text, world_state)

    prompt = f"""## 圣旨内容
「{edict_text}」

## 玩家势力状态
名称: {player.get('name', '未知')} ({player_faction_id})
银两: {player.get('treasury', 0)}
粮草: {player.get('grain', 0)}
军械: {player.get('arms', 0)}
战马: {player.get('horses', 0)}
总兵力: {player.get('total_troops', 0)}
总人口: {player.get('total_population', 0)}
民心: {player.get('realm_stability', 50)}
声望: {player.get('reputation', 50)}
发展度: {player.get('development_level', 20)}
当前回合: {world_state.get('current_round', 0)}
当前时间: {world_state.get('current_year', 1351)}年{world_state.get('current_month', 1)}月 ({world_state.get('current_season', '春')})

季节战略提示:
{get_season_strategy_hint(world_state)}

## 己方地块
{chr(10).join(tile_summary) if tile_summary else '无'}

## 其他势力
{chr(10).join(other_factions) if other_factions else '无'}

## 外交关系
{chr(10).join(diplomacy_summary) if diplomacy_summary else '无'}

{nlp_hint}

请根据以上信息（包括预处理分析提示），将圣旨解析为具体的操作指令列表。
重要：edict_language 必须根据政令类别选择正确的圣旨文体（诏曰/敕曰/制曰/诰曰/令曰/密敕），严格遵循三段结构（起首套语→正文敕谕→结尾套语），全篇地道文言文。严禁一律使用「诏曰」！"""
    return prompt


def parse_ai_response(text: str) -> dict:
    """多策略鲁棒解析 AI 返回的 JSON（使用增强 NLP 模块）"""
    if not text:
        return {}
    return robust_json_parse(text)


def validate_commands(commands: list, world_state: dict) -> tuple[list, list]:
    """
    验证 AI 返回的指令列表
    返回: (valid_commands, invalid_commands)
    """
    valid = []
    invalid = []
    player_fid = world_state.get("player_faction_id", "")
    player = world_state.get("factions", {}).get(player_fid, {})
    tiles = world_state.get("tiles", {})

    for cmd in commands:
        action = cmd.get("action", "")
        params = cmd.get("params", {})

        if action not in AVAILABLE_ACTIONS:
            invalid.append({**cmd, "error": f"未知操作类型: {action}"})
            continue

        # 参数校验
        required_params = AVAILABLE_ACTIONS[action]["params"]
        for p in required_params:
            if p not in params:
                invalid.append({**cmd, "error": f"缺少必要参数: {p}"})
                break
        else:
            # 地块归属校验
            tile_id = params.get("tile_id") or params.get("from_tile")
            if tile_id and tile_id in tiles:
                tile = tiles[tile_id]
                # Bug #17修复: plunder/ambush加入非己方地块白名单
                if tile.get("faction_id") != player_fid and action not in ("march", "spy", "scout", "diplomacy", "plunder", "ambush"):
                    invalid.append({**cmd, "error": f"地块{tile_id}不属于己方"})
                    continue

            # 数值范围校验
            amount = params.get("amount", 0)
            if action == "recruit" and amount > 5000:
                params["amount"] = 5000  # 自动修正
            if action == "buy_horses" and amount > 1000:
                params["amount"] = 1000
            # Bug #21修复: train_troops加入上限检查
            if action == "train_troops" and amount > 3000:
                params["amount"] = 3000

            valid.append(cmd)

    return valid, invalid


def build_world_summary(world_state: dict) -> str:
    """构建简短的世界局势摘要"""
    factions = world_state.get("factions", {})
    player_fid = world_state.get("player_faction_id", "")
    player = factions.get(player_fid, {})
    tiles = world_state.get("tiles", {})

    living = [f for f in factions.values() if f.get("is_alive", False)]
    player_tiles = [t for t in tiles.values() if t.get("faction_id") == player_fid]

    total_troops_all = sum(f.get("total_troops", 0) for f in living)
    player_troops = sum(t.get("troops", 0) for t in player_tiles)

    summary = (
        f"当前{world_state.get('current_year', 1351)}年{world_state.get('current_month', 1)}月"
        f"({world_state.get('current_season', '春')})，第{world_state.get('current_round', 0)}回合。\n"
        f"天下{len(living)}路势力并存，总兵力约{total_troops_all}人。\n"
        f"「{player.get('name', '玩家')}」势力占据{len(player_tiles)}座城池，"
        f"拥兵{player_troops}人，府库银{player.get('treasury', 0)}两，"
        f"粮{player.get('grain', 0)}石。"
    )

    # 添加交战状态
    relations = world_state.get("relations", {})
    wars = []
    for key, rel in relations.items():
        if rel.get("stance") == "war":
            a, b = key.split("|") if "|" in key else ("", "")
            fa = factions.get(a, {})
            fb = factions.get(b, {})
            wars.append(f"{fa.get('name', a)} vs {fb.get('name', b)}")

    if wars:
        summary += f"\n当前交战: {'、'.join(wars[:5])}"

    return summary


async def call_ai_edict(
    edict_text: str,
    world_state: dict,
    llm_client,
    edict_history: list = None,
    use_local_fallback: bool = True,
) -> dict:
    """
    调用 AI 模型解析圣旨（3.0 增强版：预处理+NLP+本地回退）

    Args:
        edict_text: 圣旨文本
        world_state: 世界状态字典
        llm_client: LLM客户端
        edict_history: 历史圣旨记录列表
        use_local_fallback: AI失败时是否使用本地回退解析

    Returns:
        {
            "intent_analysis", "narrative", "resource_assessment",
            "edict_language", "commands", "invalid_commands",
            "risk_warning", "follow_up_suggestion", "summary",
            "ai_generated", "raw_response",
        }
    """
    player_fid = world_state.get("player_faction_id", "")
    player = world_state.get("factions", {}).get(player_fid, {})
    faction_name = player.get("name", "义军")

    # 1. 快速分类（用于日志）
    classification = classify_edict(edict_text)
    logger.info(
        f"圣旨分类: {classification['primary']} "
        f"(置信度{classification['confidence']}) "
        f"原文: {edict_text[:60]}..."
    )

    # 2. 构建完整提示词（含 NLP 预处理）
    world_summary = build_world_summary(world_state)
    system_prompt = build_system_prompt(faction_name, world_summary, edict_history)
    user_prompt = build_user_prompt(edict_text, world_state)

    try:
        # 3. AI 调用
        result = await llm_client.chat_role(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.4,
        )

        if not result or not result.strip():
            logger.warning("AI 返回空文本，尝试本地回退")
            if use_local_fallback:
                return parse_edict_locally(edict_text, world_state)
            return _empty_ai_response(edict_text, "AI未返回有效响应")

        # 4. 多策略 JSON 解析
        parsed = parse_ai_response(result)

        if parsed:
            valid_cmds, invalid_cmds = validate_commands(
                parsed.get("commands", []), world_state
            )

            # 如果 AI 完全没生成指令但圣旨有明确意图，尝试本地补充
            if not valid_cmds and not invalid_cmds:
                local_actions = extract_action_intents(edict_text)
                if local_actions and use_local_fallback:
                    logger.info(f"AI未生成指令，但识别到{len(local_actions)}类操作，使用本地补充")
                    local_result = parse_edict_locally(edict_text, world_state)
                    if local_result.get("commands"):
                        # 合并：使用 AI 的分析文本 + 本地解析的指令
                        return {
                            "intent_analysis": parsed.get("intent_analysis", local_result.get("intent_analysis", "")),
                            "narrative": parsed.get("narrative", local_result.get("narrative", "")),
                            "resource_assessment": parsed.get("resource_assessment", local_result.get("resource_assessment", "")),
                            "edict_language": parsed.get("edict_language", local_result.get("edict_language", "")),
                            "commands": local_result["commands"],
                            "invalid_commands": [],
                            "risk_warning": parsed.get("risk_warning", "（部分指令由本地解析补充）"),
                            "follow_up_suggestion": parsed.get("follow_up_suggestion", ""),
                            "summary": parsed.get("summary", local_result.get("summary", "")),
                            "ai_generated": True,
                            "raw_response": result[:1000] if result else "",
                            "hybrid_mode": True,
                        }

            return {
                "intent_analysis": parsed.get("intent_analysis", ""),
                "narrative": parsed.get("narrative", ""),
                "resource_assessment": parsed.get("resource_assessment", ""),
                "edict_language": parsed.get("edict_language", ""),
                "commands": valid_cmds,
                "invalid_commands": invalid_cmds,
                "risk_warning": parsed.get("risk_warning", ""),
                "follow_up_suggestion": parsed.get("follow_up_suggestion", ""),
                "summary": parsed.get("summary", ""),
                "ai_generated": True,
                "raw_response": result[:1000],
                "classification": classification,
            }
        else:
            # AI 返回了文字但 JSON 解析失败
            logger.warning(f"AI返回可读但JSON解析失败，文本前200: {result[:200]}")
            if use_local_fallback:
                local_result = parse_edict_locally(edict_text, world_state)
                if local_result.get("commands"):
                    local_result["raw_response"] = result[:500]
                    local_result["ai_generated"] = True
                    local_result["hybrid_mode"] = True
                    return local_result
            return _empty_ai_response(edict_text, "AI解析失败，请重新拟旨")

    except Exception as e:
        logger.error(f"AI圣旨解析异常: {e}", exc_info=True)
        if use_local_fallback:
            local_result = parse_edict_locally(edict_text, world_state)
            if local_result.get("commands"):
                local_result["intent_analysis"] += f"（AI服务异常，使用本地解析）"
                return local_result
        return {
            "intent_analysis": f"AI服务异常: {str(e)[:50]}",
            "narrative": "",
            "resource_assessment": "",
            "edict_language": f"奉天承运皇帝，诏曰：{edict_text}钦此。",
            "commands": [],
            "invalid_commands": [],
            "risk_warning": "",
            "follow_up_suggestion": "",
            "summary": "AI服务暂时不可用",
            "ai_generated": False,
            "error": str(e),
        }


def _empty_ai_response(edict_text: str, message: str = "") -> dict:
    """构建空的 AI 响应"""
    return {
        "intent_analysis": message or "AI未能解析圣旨",
        "narrative": "",
        "resource_assessment": "",
        "edict_language": f"奉天承运皇帝，诏曰：{edict_text}钦此。",
        "commands": [],
        "invalid_commands": [],
        "risk_warning": "",
        "follow_up_suggestion": "",
        "summary": message or "圣旨未能正确解析",
        "ai_generated": True,
        "raw_response": "",
    }


def execute_edict_commands(
    commands: list[dict],
    world_state_obj,  # WorldState 实例
    round_engine,     # RoundEngine 实例
) -> dict:
    """
    执行圣旨解析出的指令列表

    圣旨中的多条指令作为一个整体批处理：
    - 先对所有指令做校验
    - 再统一获取操作锁
    - 最后执行（跳过 _acquire_operation_lock 避免同类操作互斥）

    直接修改 world_state_obj 上的数据

    Returns:
        {
            "executed": [{"action": str, "result": dict}, ...],
            "failed": [{"action": str, "reason": str}, ...],
            "total_executed": int,
            "total_failed": int,
        }
    """
    executed = []
    failed = []

    # 第一阶段：收集已用过的锁，避免圣旨内重复指令互相阻止
    used_locks = set()  # {(cat, tile_id)} 或 {(cat, "faction")}

    for cmd in commands:
        action = cmd.get("action", "")
        params = cmd.get("params", {})
        reason = cmd.get("reason", "")

        # 先做资源校验
        check = round_engine._validate_command(action, params)
        if not check["valid"]:
            failed.append({
                "action": action,
                "params": params,
                "reason": check["reason"],
                "ai_reason": reason,
            })
            continue

        # 操作锁去重：同一次圣旨内同类型操作不互相阻止
        # 但需要检查外部是否已有锁（之前回合已执行）
        lock_key = _get_lock_key(action, params)
        if lock_key:
            cat, tile_or_faction = lock_key
            if tile_or_faction == "faction":
                # 势力级别锁：检查是否已被外部锁定
                player = world_state_obj.get_player_faction()
                if player and round_engine._op_lock.check_faction_lock(player.faction_id, cat):
                    failed.append({
                        "action": action,
                        "params": params,
                        "reason": "本回合已执行此类操作",
                        "ai_reason": reason,
                    })
                    continue
            else:
                # 地块级别锁：检查是否已被外部锁定
                if round_engine._op_lock.check_tile_lock(tile_or_faction, cat):
                    failed.append({
                        "action": action,
                        "params": params,
                        "reason": f"地块{tile_or_faction}的本回合已执行此类操作",
                        "ai_reason": reason,
                    })
                    continue

            # 圣旨内部去重
            lock_str = f"{cat.value}:{tile_or_faction}"
            if lock_str in used_locks:
                failed.append({
                    "action": action,
                    "params": params,
                    "reason": "圣旨内重复指令，已自动合并",
                    "ai_reason": reason,
                })
                continue
            used_locks.add(lock_str)

        # 执行指令（跳过 _execute_command 中的锁获取，直接执行核心逻辑）
        try:
            result = _execute_command_direct(action, params, world_state_obj, round_engine)
            if result.get("success"):
                # 执行成功后获取操作锁
                lock_acquired = round_engine._acquire_operation_lock(action, params)
                if not lock_acquired:
                    logger.warning(f"圣旨执行后操作锁获取失败: {action} {params}")
                executed.append({
                    "action": action,
                    "params": params,
                    "result": result,
                    "ai_reason": reason,
                })
            else:
                failed.append({
                    "action": action,
                    "params": params,
                    "reason": result.get("message", "未知错误"),
                    "ai_reason": reason,
                })
        except Exception as e:
            logger.error(f"执行指令异常 [{action}]: {e}", exc_info=True)
            failed.append({
                "action": action,
                "params": params,
                "reason": f"执行异常: {str(e)[:50]}",
                "ai_reason": reason,
            })

    return {
        "executed": executed,
        "failed": failed,
        "total_executed": len(executed),
        "total_failed": len(failed),
    }


def _get_lock_key(action: str, params: dict) -> tuple | None:
    """获取操作的锁标识"""
    from server.core.round_lock import LockCategory

    faction_actions = {
        "tax": LockCategory.TAX,
        "diplomacy": LockCategory.DIPLOMACY,
        "amnesty": LockCategory.LAW,
        "enfeoff": LockCategory.ENFEOFF,
        "buy_horses": LockCategory.BUY_HORSES,
        "cultural_policy": LockCategory.LAW,
        "sea_policy": LockCategory.TAX,
        "move_capital": LockCategory.ENFEOFF,
    }
    if action in faction_actions:
        return (faction_actions[action], "faction")

    tile_actions = {
        "develop": LockCategory.DEVELOP,
        "recruit": LockCategory.RECRUIT,
        "fortify": LockCategory.BUILD,
        "relief": LockCategory.RELIEF,
        "build": LockCategory.BUILD,
        "train_troops": LockCategory.TRAIN_TROOPS,
        "convict_labor": LockCategory.BUILD,
        "medical": LockCategory.DEVELOP,
        "ambush": LockCategory.MARCH,
        "plunder": LockCategory.MARCH,
    }
    if action in tile_actions:
        tile_id = params.get("tile_id", "") or params.get("target_tile", "")
        if tile_id:
            return (tile_actions[action], tile_id)

    # 行军锁
    if action == "march":
        from_tile = params.get("from_tile", "")
        if from_tile:
            return (LockCategory.MARCH, from_tile)

    return None


def _execute_command_direct(action: str, params: dict, world_state_obj, round_engine) -> dict:
    """
    直接执行指令（跳过操作锁检查，因为圣旨引擎已自行管理去重）
    
    复制自 RoundEngine._execute_command 的核心逻辑，但跳过了 _acquire_operation_lock
    """
    round_engine._ensure_engines()
    player = world_state_obj.get_player_faction()
    if not player:
        return {"success": False, "message": "无玩家势力"}

    try:
        if action == "march":
            return round_engine._march_engine.resolve_march(
                from_tile=params.get("from_tile", ""),
                to_tile=params.get("to_tile", ""),
                troops=params.get("troops", 0),
                attacker_faction=player.faction_id,
                grain=params.get("grain", 0),
            )

        elif action == "spy":
            spy_action = params.get("spy_action", "deploy")
            target = params.get("target_faction", "")
            if spy_action == "deploy":
                return round_engine._spy_engine.deploy_spy(player.faction_id, target)
            else:
                return round_engine._spy_engine.spy_action(player.faction_id, target, spy_action)

        elif action == "recruit":
            tile_id = params.get("tile_id", "")
            amount = params.get("amount", 100)
            unit_type = params.get("unit_type", "infantry")  # infantry 或 cavalry
            tile = world_state_obj.get_tile(tile_id)
            if not tile:
                return {"success": False, "message": f"地块{tile_id}不存在"}
            if unit_type == "cavalry":
                # 骑兵征兵：消耗战马
                cost_per = 4  # 骑兵造价更高
                horses_needed = max(1, amount // 5)  # 每5骑兵消耗1战马
                if getattr(player, 'horses', 0) < horses_needed:
                    return {"success": False, "message": f"战马不足（需要{horses_needed}匹，现有{getattr(player, 'horses', 0)}匹）"}
                cost = amount * cost_per
                arms_needed = max(0, amount // 5)
                # Bug #18修复: 征兵前检查资源充足性
                if player.treasury < cost:
                    return {"success": False, "message": f"银两不足（需要{cost}两，现有{player.treasury}两）"}
                if player.arms < arms_needed:
                    return {"success": False, "message": f"军械不足（需要{arms_needed}件，现有{player.arms}件）"}
                player.treasury -= cost
                player.horses -= horses_needed
                # 骑兵也需要军械（长矛、马刀等）
                arms_needed = max(0, amount // 5)
                player.arms -= arms_needed
                tile.troops += amount
                tile.population = max(100, tile.population - amount)
                tile.morale = max(0, tile.morale - 2)
                return {
                    "success": True,
                    "message": f"从{tile.tile_name}招募{amount}骑兵（耗费银{cost}两、战马{horses_needed}匹、军械{arms_needed}件）",
                    "tile": tile_id,
                    "recruited": amount,
                    "unit_type": "cavalry",
                    "cost_silver": cost,
                    "cost_horses": horses_needed,
                    "cost_arms": arms_needed,
                }
            else:
                cost_per = 2
                if tile.tile_type.value in ('city', 'port'):
                    cost_per = 3
                cost = amount * cost_per
                arms_needed = max(0, amount // 3)
                # Bug #18修复: 征兵前检查资源充足性
                if player.treasury < cost:
                    return {"success": False, "message": f"银两不足（需要{cost}两，现有{player.treasury}两）"}
                if player.arms < arms_needed:
                    return {"success": False, "message": f"军械不足（需要{arms_needed}件，现有{player.arms}件）"}
                player.treasury -= cost
                player.arms -= arms_needed
                tile.troops += amount
                tile.population = max(100, tile.population - amount)
                tile.morale = max(0, tile.morale - 3)
                return {
                    "success": True,
                    "message": f"从{tile.tile_name}招募{amount}士兵（耗费银{cost}两、军械{arms_needed}件）",
                    "tile": tile_id,
                    "recruited": amount,
                    "cost_silver": cost,
                    "cost_arms": arms_needed,
                }

        elif action == "buy_horses":
            amount = params.get("amount", 0)
            cost = amount * 5
            # Bug #18修复: 购马前检查资源充足性
            if player.treasury < cost:
                return {"success": False, "message": f"银两不足（需要{cost}两，现有{player.treasury}两）"}
            player.treasury -= cost
            player.horses += amount
            return {
                "success": True,
                "message": f"购买{amount}匹战马（耗费银{cost}两）",
                "purchased": amount,
                "cost_silver": cost,
                "total_horses": player.horses,
            }

        elif action == "train_troops":
            tile_id = params.get("tile_id", "")
            amount = params.get("amount", 0)
            tile = world_state_obj.get_tile(tile_id)
            if not tile:
                return {"success": False, "message": f"地块{tile_id}不存在"}
            # Bug #19修复: 0兵力地块拒绝训练
            if tile.troops <= 0:
                return {"success": False, "message": f"地块{tile.tile_name}无驻军，无法训练"}
            cost = amount * 1
            grain_cost = amount // 2
            # Bug #18修复: 训练前检查资源充足性
            if player.treasury < cost:
                return {"success": False, "message": f"银两不足（需要{cost}两，现有{player.treasury}两）"}
            if player.grain < grain_cost:
                return {"success": False, "message": f"粮草不足（需要{grain_cost}石，现有{player.grain}石）"}
            player.treasury -= cost
            player.grain -= grain_cost
            tile.morale = min(100, tile.morale + 10)
            elite_ratio = getattr(tile, 'elite_ratio', 0.0) or 0.0
            tile.elite_ratio = min(1.0, elite_ratio + amount / tile.troops * 0.1)
            return {
                "success": True,
                "message": f"在{tile.tile_name}训练{amount}士兵（耗费银{cost}两、粮{grain_cost}石）",
                "tile": tile_id,
                "trained": amount,
                "cost_silver": cost,
                "cost_grain": grain_cost,
                "new_morale": tile.morale,
            }

        elif action == "develop":
            tile_id = params.get("tile_id", "")
            dev_type = params.get("type", "farmland")
            tile = world_state_obj.get_tile(tile_id)
            if not tile or tile.faction_id != player.faction_id:
                return {"success": False, "message": f"地块{tile_id}不存在或不属于你方"}
            player.treasury -= 500
            dev_labels = {"water": "水利", "granary": "粮仓", "clinic": "医馆", "farmland": "农田"}
            label = dev_labels.get(dev_type, dev_type)
            if dev_type == "water":
                tile.water_works += 1
            elif dev_type == "granary":
                tile.granary += 1
            elif dev_type == "clinic":
                tile.clinic += 1
            elif dev_type == "farmland":
                # 屯田开垦：增加粮草产出和人口上限
                tile.grain = getattr(tile, 'grain', 0) + 200
                tile.population += int(tile.population * 0.05)
            tile.development_level = getattr(tile, 'development_level', 0) + 1
            return {"success": True, "message": f"「{tile.tile_name or tile_id}」{label}开发完成（耗费500银）", "tile": tile_id}

        elif action == "fortify":
            tile_id = params.get("tile_id", "")
            tile = world_state_obj.get_tile(tile_id)
            if not tile:
                return {"success": False, "message": f"地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"success": False, "message": f"地块{tile_id}不属于你方"}
            cost = 300 * (tile.fortification + 1)
            if player.treasury >= cost:
                player.treasury -= cost
                tile.fortification += 1
                return {"success": True, "message": f"城防提升至{tile.fortification}级", "tile": tile_id}
            return {"success": False, "message": f"银两不足（需要{cost}）"}

        elif action == "relief":
            tile_id = params.get("tile_id", "")
            tile = world_state_obj.get_tile(tile_id)
            if not tile:
                return {"success": False, "message": f"地块{tile_id}不存在"}
            grain_cost = int(tile.population * 0.01)
            if player.grain >= grain_cost:
                player.grain -= grain_cost
                tile.morale = min(100, tile.morale + 10)
                tile.disasters = []
                return {"success": True, "message": "赈灾成功，民心恢复", "tile": tile_id}
            return {"success": False, "message": "粮草不足"}

        elif action == "tax":
            tax_type = params.get("tax_type", "normal")
            if tax_type == "heavy":
                player.realm_stability = max(0, player.realm_stability - 5)
                player.tax_policy = "heavy"  # 标记重税，_calc_tax 中 +30% 税收
                return {"success": True, "message": "重税政策已施行（税收+30%，民心-5）"}
            elif tax_type == "light":
                player.realm_stability = min(100, player.realm_stability + 5)
                player.tax_policy = "light"
                return {"success": True, "message": "减税政策已施行"}
            else:
                player.tax_policy = "normal"
            return {"success": True, "message": "税政如常"}

        elif action == "diplomacy":
            target = params.get("target_faction", "")
            dip_type = params.get("diplomacy_type", "")
            if dip_type == "alliance":
                return round_engine._diplomacy_engine.change_stance(player.faction_id, target, "alliance")
            elif dip_type == "war":
                return round_engine._diplomacy_engine.change_stance(player.faction_id, target, "war")
            elif dip_type == "truce":
                return round_engine._diplomacy_engine.change_stance(player.faction_id, target, "truce")
            elif dip_type == "trade":
                return round_engine._diplomacy_engine.open_trade(player.faction_id, target)
            elif dip_type == "marriage":
                return round_engine._diplomacy_engine.propose_marriage(player.faction_id, target)
            elif dip_type == "tribute":
                player.treasury -= 500
                key = world_state_obj.relation_key(player.faction_id, target)
                rel = world_state_obj.relations.get(key)
                if rel:
                    rel.attitude += 10
                return {"success": True, "message": f"向{target}纳贡500银两"}
            elif dip_type == "vassal":
                return round_engine._diplomacy_engine.change_stance(player.faction_id, target, "vassal")
            return {"success": False, "message": f"未知外交行动: {dip_type}"}

        elif action == "build":
            tile_id = params.get("tile_id", "")
            building = params.get("building", "")
            tile = world_state_obj.get_tile(tile_id)
            if not tile or tile.faction_id != player.faction_id:
                return {"success": False, "message": f"地块{tile_id}不存在或不属于你方"}
            costs = {"granary": 250, "armory": 800, "stable": 600, "port": 400, "clinic": 200,
                     "farmland": 300, "workshop": 500, "barracks": 350, "beacon": 200, "temple": 400,
                     "wall": 600, "dock": 400}
            labels = {"granary": "粮仓", "armory": "军械所", "stable": "马场", "port": "港口", "clinic": "医馆",
                     "farmland": "农田", "workshop": "工坊", "barracks": "征兵营", "beacon": "烽燧", "temple": "寺庙",
                     "wall": "城墙", "dock": "码头"}
            cost = costs.get(building, 500)
            label = labels.get(building, building)
            if player.treasury >= cost:
                player.treasury -= cost
                if building == "granary":
                    tile.granary += 1
                elif building == "armory":
                    tile.armory = getattr(tile, 'armory', 0) + 1
                    tile.elite_ratio = min(1.0, getattr(tile, 'elite_ratio', 0.0) + 0.1)
                elif building == "stable":
                    tile.stable = getattr(tile, 'stable', 0) + 1
                elif building == "clinic":
                    tile.clinic += 1
                elif building == "port":
                    tile.is_port = True
                elif building == "farmland":
                    tile.grain = getattr(tile, 'grain', 0) + 200
                    tile.population += int(tile.population * 0.03)
                elif building == "workshop":
                    tile.development_level = getattr(tile, 'development_level', 0) + 1
                elif building == "barracks":
                    tile.troops += int(tile.population * 0.01)  # 自动募兵1%
                elif building == "beacon":
                    # 烽燧：标记为有瞭望设施（后续可扩展视野效果）
                    tile.development_level = getattr(tile, 'development_level', 0) + 1
                elif building == "temple":
                    tile.morale = min(100, tile.morale + 5)
                elif building == "wall":
                    tile.fortification += 1  # 城墙即加固城防
                elif building == "dock":
                    tile.is_port = True  # 码头即港口
                return {"success": True, "message": f"「{tile.tile_name or tile_id}」{label}建造完成"}
            return {"success": False, "message": f"银两不足（需要{cost}，现有{player.treasury}）"}

        elif action == "enfeoff":
            official_id = params.get("official_id", "")
            if official_id and hasattr(world_state_obj, 'officials'):
                official = world_state_obj.officials.get(official_id)
                if not official:
                    return {"success": False, "message": f"官员{official_id}不存在"}
            if player.treasury < 1000:
                return {"success": False, "message": f"银两不足（需要1000，现有{player.treasury}）"}
            player.treasury -= 1000
            return {"success": True, "message": f"已分封官员"}

        elif action == "amnesty":
            player.reputation += 10
            player.realm_stability = min(100, player.realm_stability + 5)
            # 清空该势力所有俘虏
            freed_count = 0
            prisoner_ids_to_remove = []
            for pid, prisoner in list(world_state_obj.prisoners.items()):
                if prisoner.held_by == player.faction_id:
                    prisoner_ids_to_remove.append(pid)
                    freed_count += 1
            for pid in prisoner_ids_to_remove:
                del world_state_obj.prisoners[pid]
            # 同时清理 FactionState.prisoners 列表
            player.prisoners = [p for p in player.prisoners if p not in prisoner_ids_to_remove]
            return {"success": True, "message": f"大赦天下，民心归附（释放俘虏{freed_count}人）"}

        elif action == "scout":
            target_tile = params.get("target_tile", "")
            tile = world_state_obj.get_tile(target_tile)
            return {
                "success": True,
                "message": "侦查完成",
                "data": tile.model_dump() if tile else {},
            }

        # ===== 新增操作类型 =====

        elif action == "ambush":
            tile_id = params.get("tile_id", "")
            troops = params.get("troops", 0)
            tile = world_state_obj.get_tile(tile_id)
            if not tile:
                return {"success": False, "message": f"地块{tile_id}不存在"}
            if tile.troops < troops:
                return {"success": False, "message": f"兵力不足（需要{troops}，现有{tile.troops}）"}
            grain_cost = troops * 1
            if player.grain < grain_cost:
                return {"success": False, "message": f"粮草不足（需要{grain_cost}石）"}
            player.grain -= grain_cost
            # 伏击持续本回合，标记地块
            tile.ambush_troops = troops
            tile.troops -= troops
            return {
                "success": True,
                "message": f"在{tile.tile_name or tile_id}设伏{troops}人（耗费粮{grain_cost}石）",
                "tile": tile_id,
                "ambush_troops": troops,
                "cost_grain": grain_cost,
            }

        elif action == "plunder":
            target_tile = params.get("target_tile", "")
            troops = params.get("troops", 0)
            tile = world_state_obj.get_tile(target_tile)
            if not tile:
                return {"success": False, "message": f"目标地块{target_tile}不存在"}
            if tile.faction_id == player.faction_id:
                return {"success": False, "message": "不能劫掠己方地块"}
            grain_cost = troops * 1
            if player.grain < grain_cost:
                return {"success": False, "message": "粮草不足"}
            # 劫掠收益 = 目标人口/开发度相关
            loot_silver = min(tile.population * 2, 2000)
            loot_grain = min(tile.population, 1000)
            tile.morale = max(0, tile.morale - 20)
            tile.population = max(100, tile.population - troops // 2)
            tile.development_level = max(0, getattr(tile, 'development_level', 0) - 1)
            player.treasury += loot_silver
            player.grain += loot_grain - grain_cost
            # 外交恶化
            key = world_state_obj.relation_key(player.faction_id, tile.faction_id)
            if key in world_state_obj.relations:
                world_state_obj.relations[key].attitude -= 15
            return {
                "success": True,
                "message": f"劫掠{tile.tile_name or target_tile}，夺取银{loot_silver}两、粮{loot_grain}石",
                "tile": target_tile,
                "loot_silver": loot_silver,
                "loot_grain": loot_grain,
            }

        elif action == "move_capital":
            tile_id = params.get("tile_id", "")
            tile = world_state_obj.get_tile(tile_id)
            if not tile or tile.faction_id != player.faction_id:
                return {"success": False, "message": "目标地块不在己方掌控之内"}
            cost_silver = 3000
            cost_grain = 500
            if player.treasury < cost_silver:
                return {"success": False, "message": f"银两不足（需要{cost_silver}，现有{player.treasury}）"}
            if player.grain < cost_grain:
                return {"success": False, "message": f"粮草不足（需要{cost_grain}石）"}
            player.treasury -= cost_silver
            player.grain -= cost_grain
            # 旧都降级
            for tid, t in world_state_obj.tiles.items():
                if getattr(t, 'is_capital', False) and t.faction_id == player.faction_id:
                    t.is_capital = False
            tile.is_capital = True
            player.realm_stability = max(0, player.realm_stability - 10)
            player.capital_tile_id = tile_id
            return {
                "success": True,
                "message": f"迁都至{tile.tile_name or tile_id}（耗费银{cost_silver}两、粮{cost_grain}石，民心暂时动荡）",
                "new_capital": tile_id,
                "cost_silver": cost_silver,
                "cost_grain": cost_grain,
            }

        elif action == "cultural_policy":
            policy_type = params.get("policy_type", "开科举")
            if player.treasury < 800:
                return {"success": False, "message": "银两不足（需要800）"}
            player.treasury -= 800
            player.reputation += 5
            player.realm_stability = min(100, player.realm_stability + 3)
            return {
                "success": True,
                "message": f"推行{policy_type}政策（耗费800银，声望+5，民心+3）",
                "policy": policy_type,
                "reputation_gain": 5,
            }

        elif action == "sea_policy":
            policy_type = params.get("policy_type", "开海贸")
            if policy_type == "建水师":
                if player.treasury < 1000:
                    return {"success": False, "message": "银两不足（需要1000）"}
                player.treasury -= 1000
                player.navy_power = getattr(player, 'navy_power', 0) + 20
                return {"success": True, "message": "水师已建成（耗费1000银，海军战力+20）"}
            else:
                # 开海贸/禁海
                player.sea_trade_active = (policy_type == "开海贸")
                return {
                    "success": True,
                    "message": f"海策已调整为「{policy_type}」",
                    "policy": policy_type,
                }

        elif action == "medical":
            tile_id = params.get("tile_id", "")
            tile = world_state_obj.get_tile(tile_id)
            if not tile or tile.faction_id != player.faction_id:
                return {"success": False, "message": f"地块{tile_id}不存在或不属于你方"}
            if player.treasury < 400:
                return {"success": False, "message": "银两不足（需要400）"}
            player.treasury -= 400
            tile.clinic += 1
            tile.plague_resistance = min(100, getattr(tile, 'plague_resistance', 0) + 10)
            return {
                "success": True,
                "message": f"「{tile.tile_name or tile_id}」医馆扩张完成（耗费400银，瘟疫抗性+10）",
                "tile": tile_id,
            }

        elif action == "convict_labor":
            tile_id = params.get("tile_id", "")
            project = params.get("project", "筑城")
            tile = world_state_obj.get_tile(tile_id)
            if not tile or tile.faction_id != player.faction_id:
                return {"success": False, "message": f"地块{tile_id}不存在或不属于你方"}
            if tile.population < 200:
                return {"success": False, "message": "人口不足（至少200人才能征发徭役）"}
            tile.morale = max(0, tile.morale - 8)
            tile.population = max(100, tile.population - 100)
            if project in ("筑城", "修路"):
                tile.fortification = min(100, tile.fortification + 2)
                return {"success": True, "message": f"「{tile.tile_name or tile_id}」徭役{project}完成（城防+2，民心-8）"}
            else:
                tile.development_level = getattr(tile, 'development_level', 0) + 3
                return {"success": True, "message": f"「{tile.tile_name or tile_id}」徭役{project}完成（发展度+3，民心-8）"}

        else:
            return {"success": False, "message": f"未知指令类型: {action}"}

    except Exception as e:
        logger.error(f"执行指令失败 [{action}]: {e}", exc_info=True)
        return {"success": False, "message": f"执行异常: {str(e)}"}
