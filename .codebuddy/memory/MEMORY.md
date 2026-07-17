# 项目记忆 — 元末逐鹿

## 项目概况
- 元末历史大战略游戏，前端 Vue3+TS，后端 Python FastAPI (:8800)
- 八阶段回合引擎 / 六边形沙盘 / 自然语言圣旨 / 十大AI智能体(A1-A10)
- 启动：`$env:PYTHONUTF8="1"` + `python server.py`（uvicorn :8800）
- 编码：PowerShell 启动前必须设置 UTF-8 环境变量，避免 cp950 崩溃

## 核心架构
- `server/api_server.py` — FastAPI，211+ 路由端点
- `server/core/` — 35 个核心模块（回合/战斗/经济/外交/政令/结局等）
- `server/agent/` — 10 大 AI 智能体，含 NPC 记忆情感/关系系统
- `server/infra/llm_client/` — LLM 客户端（混元/DeepSeek），成本追踪，降级兜底
- `frontend/src/` — Vue3 组件 + Pinia stores
- `tests/` — 7 个测试文件，244 个测试，覆盖 hex_grid/combat/economy/fog_of_war/pathfinding/supply

## 已安装 Skill（39个）
**游戏核心**: game-development, autonomous-agent-gaming, llm-npc-dialogue, frontend-design
**画风UI**: game-asset-generation, frontend-design-ui-ux, css-native, image-portrait, pixel-art-sprites
**战略博弈**: coordination-games, wargame, compete, game-strategy-simulator
**经济平衡**: game-economy-designer, game-balance-check
**地图导航**: procedural-gen, navigation, hex
**AI/LLM**: prompt-engineer, senior-prompt-engineer, ai-prompt-engineering, llm-cost-optimizer, prompt-engineering-patterns
**工程部署**: cloudbase, doc-gen, media-asset-management, file-operations, Github, brainstorming
**GameForge**: game-team-orchestrator, game-designer, game-design-review, game-feel, save-systems
**着色器**: shader-dev
**音频**: add-audio, voice-audio-engineer
**浏览器**: browser-use
**代码审查**: review-game, game-qa, improve-game
**其他**: illustrator, arize-ai-provider-integration, ai-product, llm-ops, hackathon-judge（腾讯云黑松客评委，手写创建）

## 已完成的核心系统
- 回合引擎/结算/政令/经济/战斗/战争/外交/补给/城建/国策/武将/NPC/结局
- MCTS博弈/博弈论/战争迷雾/道路驿站/EconomyEngine/FogOfWarEngine
- 自动游玩系统：`python -m server.autoplay.autoplay --faction yuan --max-turns 50 --speed fast`
- 游戏手感V3.1、存档系统、NPC记忆情感/关系网络、Prompt工程
- ElevenLabs TTS + edge-tts 双提供商
- 器物差异化UI全覆盖（V6.0）、地图性能优化（V4.2）、沙盘Bug修复（V4.2.1-4.2.3）
- 多玩家会话隔离（ContextVar per-session）
- 公网部署方案（Docker + Nginx + Let's Encrypt），Ubuntu 22.04 LTS
- 2026-07-16 公网部署安全增强：CORS环境变量化、会话TTL自动清理、Nginx API限流、玩家自带Key模式
- 测试基础设施（244 tests, pytest + conftest.py fixtures）

## 2026-07-16 UI上半部分模块功能审计
- 报告: `UI_UPPER_MODULES_AUDIT.md`（12项诊断）
- 🔴 B1: 面板状态管理四套并行系统（gameStore / uiStore死代码 / 本地ref / store独立ref）
- 🔴 B2: uiStore（248行）完全未被 GamePage 使用
- 🔴 B3: RecruitPanel + EndingPanel 始终挂载（无 v-if/:visible）
- 🟠 B4: 顶部按钮行为不一致 — "战""策""谋""⚙""🛡" 永不关闭，"势" 是 toggle
- 🟠 B5: 3/8 个顶部按钮未设置 panelSide
- 🟠 B6: 工具栏 ID 命名不一致（batch-build vs batch_build）
- 🟡 B7: law-interrogate 面板无公开入口按钮
- 🟡 B8/B9: factions 无工具栏入口 + closeAllPanels 遗漏 eventDetail
- 🔵 B10-B12: 本地ref散落／PanelType旧代码／PanelManager未实现迁移

## 已消除的关键 Bug
- settle_engine 沙盘坐标/阻挡/寻路 Bug（V4.2.1）+ PolicyEngine UnboundLocalError（V4.2.3）
- autoplay 4个严重Bug：RoundEngine.player_faction_id / PayoffMatrix 属性名 / TileType 缺6种地形 / 健康检查 status
- FIX_PLAN 30项全部完成（循环依赖/Pydantic验证/Store架构等）
- **2026-07-16 库银粮草模块4项修复（v4.3.1）**：
  - Bug#1: economy_engine.py `calc_military_upkeep` 军费返回值是兵力总和而非 `troops×0.8` — 修复为正确计算
  - Bug#2: settle_engine.py `phase_settle` 缺失军费/建筑维护费扣除 — 新增实际扣款逻辑（每兵0.8银+BUILDING_CONFIG.upkeep）
  - Bug#3: settle_engine.py `faction.grain` 粮草重复累加（`grain_produced`+`overflow`对同一份粮产计两次）— 移除重复overflow
  - Bug#4: round_engine.py 劫掠虚空产银产粮（加劫掠方但未扣被劫掠方）— 增加目标方字段双双扣除
- **2026-07-16 变法图强板块3项修复（v4.3.2）**：
  - Bug#5: `/api/tech/tree` 数据解析错误 — policies.json 是对象结构但代码按数组遍历（`isinstance(policies_data, list)` 永远 False），导致 categories 永远为空，TechTreePanel 永远空白
  - Bug#6: `/api/tech/research` 同样数据解析错误 — 遍历 dict 的 key 字符串找不到国策定义
  - Bug#7: 字段不一致 — `/api/tech/*` 读写 `faction.policies`（ad-hoc set），其他系统全用 `faction.unlocked_policies`（list），导致 TechTreePanel 解锁的国策其他系统看不到
- **2026-07-16 存档页面黑屏修复（v4.3.3）**：
  - Bug#8: SaveArchiveBg Canvas 层叠上下文遮盖 — Canvas `position: absolute; z-index: 0` 在 `.save-page`（`position: relative`）内遮盖了所有 `position: static` 的内容元素（`.save-header`、`.save-content`）。CSS 规范中定位元素在第 6 层，非定位块级元素在第 3 层。
  - 修复：Canvas `z-index: 0→-1`；`.save-header`、`.save-content` 加 `position: relative; z-index: 1`；`.yuanmo-app` 加 `background: var(--bg-base)` 防止过渡间隙露出空白
- **2026-07-16 API额度耗尽诊断（严重）**：
  - CodeBuddy API返回429（error 14018:"额度已用尽"），所有LLM客户端进入fallback_mode
  - 所有势力返回统一降级文本"时局未明，容臣思之。"，AI功能形同虚设
  - v4.3 LLM深化（+200%调用量，~20→~60次/回合）加速了额度消耗
  - test-llm端点创建独立客户端对象，可能短暂成功但session客户端不同
  - 修复方案：购买加量包 https://www.codebuddy.cn/profile/usage 或更换 API Key（server/config/llm_runtime.json）

## 用户偏好
- 不修改首页背景图（home-bg.jpg、HomePage.vue、ImageDynamicBg.vue）
- 代码审查/审计时只诊断不修改（除非明确要求修复）
- `.codebuddy` 文件夹不可删除

## 2026-07-16 LLM深化优化（v4.3）— 三步完成，AI驱动 ~75%

### 第一步：叙事深化（+15%）
- A8势力专史、A5天下大势、A9战局综述、A2决策反思
- 6个文件，纯叙事增强

### 第二步：结算审阅（+15%）
- 新增 `server/core/llm_review.py`（~500行）— SettlementReview/DiplomacyReview/CombatStanceReview
- 3个hook点（round_engine ×2, settle_engine ×1），有界调整
- 3个文件

### 第三步：世界叙事引擎（+15%）
- 新增 `server/agent/world_narrative.py`（~350行）— CourtDebateEngine/PublicSentimentEngine/GeneralChroniclesEngine
- 9势力×朝堂辩论 + 1次舆情 + 1次将领列传 = 11次chat_fast/回合
- 全部纯叙事，存入events_log，零游戏机制影响
- 修改 `orchestrator.py`（3个新phase方法+组2任务）+ `round_engine.py`（叙事存储）
- 3个文件

### 总计修改（三步累计）
**新增**: world_narrative.py, llm_review.py
**修改**: a8_history.py, a5_event.py, a9_battle_report.py, a2_warlord.py, orchestrator.py, round_engine.py, settle_engine.py
**全部lint通过，0错误**

### LLM调用量变化
- 之前: ~15-20次/回合 → 现在: ~55-60次/回合（+200%）
- AI驱动占比: ~30% → ~75%（达标，超过65%目标）
