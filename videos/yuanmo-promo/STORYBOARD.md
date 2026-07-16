---
format: 1920x1080
message: "在元末乱世中，书写属于你的帝王史诗"
arc: Future Pacing — 乱世降临 → 群雄逐鹿 → 游戏登场 → 沙盘博弈 → 圣旨号令 → 深度系统 → AI博弈 → 天命终局 → 号召
audience: 策略游戏玩家、历史爱好者、国风文化受众
mode: autonomous
---

## Video direction

**色调**: dark-panel (#0D0D0D) 为主基调，red-panel (#8B0000) 为情绪高潮面，bg (#E8D5B7) 古卷色为系统展示面。金色 (#DAA520) 为唯一强调色。

**镜头节奏**: 前3帧建立紧迫感（暗→快→密），Frame 4-8 展示系统（交替面板色），Frame 9-10 情绪高潮（红色全屏），Frame 11-12 收束（从红回到暗金锁定）。

**动作语言**: 全程平稳推力镜头 + 逐词弹出（kinetic-type-beats 为主力），Frame 5/7/8 用 geometric 展开（六边形/卡片/节点），Frame 10 用 stat-big 大字倾斜冲击。

**BGM**: 史诗战鼓+弦乐，渐强式，Frame 10 达到高潮后渐弱收尾。
**SFX**: 金印落下(impact-heavy) / 火焰燃烧(whoosh) / 文字砸落(impact-soft) / 节点连接(blip) / 终场鼓点(big-impact)

---

## Frame 1 — 天下大乱

- scene: 暗红渐变背景，大字逐词弹出"天下大乱"，最后一个字猛然放大倾斜
- voiceover: "公元一三五一年，红巾军起义，天下大乱。"
- duration: 6s
- transition_in: cut
- status: outline
- src: compositions/frames/01-chaos.html
- type: hook
- persuasion: Pain validation
- beat: tension + urgency
- blueprint: kinetic-type-beats (Reproduce)
- focal: typography — "天下大乱" 四字
- roles: text-hero = hero · progress-bar = chrome
- sfx: whoosh, impact-heavy

Reproduce the full kinetic-type-beats shape: words enter one-at-a-time on hard-cut, last word slams in at 3x scale.
Scene 1 (0.0–1.5s): dark-panel (#0D0D0D) full-bleed; red progress bar bottom, length ~10%. 汉字"天" dead-center in gold (#DAA520), hero-title scale — flash in with scale burst + quick settle.
Scene 2 (1.5–3.0s): "下" hard-cut replaces at center, same scale, slight jitter settle. Progress bar ticks to ~25%.
Scene 3 (3.0–4.5s): "大" hard-cut replaces center. Transition: scale-bounce settle, progress bar ~45%.
Scene 4 (4.5–6.0s): "乱" slams in at hero-title-red scale (rotated −4°, gold), stacked-text-shadow fires. Camera push-in micro-drift underneath. Progress bar fills to 100%. Hold for read.

narrativeRole: 开场即把观众扔进元末乱世的紧迫感中 — 时代背景一笔带过，情绪先行。
keyMessage: 天下已乱，英雄当出。

## Frame 2 — 元室将倾

- scene: 金色数字倒计时/统计（红巾军规模、起义省份数），镜头推过数字最终停留在"元"字崩塌
- voiceover: "蒙古铁骑的余威散尽，帝国的版图燃烧殆尽。十八路反王，六方割据，逐鹿中原。"
- duration: 7s
- transition_in: zoom-through
- status: outline
- src: compositions/frames/02-collapse.html
- type: pain_point
- persuasion: Statistical proof + Negative contrast
- beat: anxiety + overwhelm
- blueprint: dataviz-countup (Adapt)
- focal: typography — 数字 + "元" 字崩坏
- roles: stat-number = hero · "元" glyph = payoff · progress-bar = chrome
- sfx: riser, impact-heavy, crash

Adapt: keep count-up signature but simplified — single hero number that counts up, then the "元" glyph cracks and dissolves. No chart.
Scene 1 (0.0–2.0s): dark-panel. Gold number "1351" dead-center at stat-big scale (−6° tilt) — value-scaled counter climbs 1300→1351. Camera slow push-in.
Scene 2 (2.0–4.5s): number fades, "十八路" and "六方" appear diagonally — staggered, scale-swap handoff. Gold label chips below.
Scene 3 (4.5–7.0s): the character "元" materializes center at hero-title-red scale, tilted −5°. On the VO's "燃尽" beat, the glyph cracks (SVG split), shards fall. Dark panel holds on empty center for final 0.5s.

narrativeRole: 用数据制造压迫感，让观众感受到元朝的崩溃已是定局。
keyMessage: 旧秩序崩塌，新王当立。

## Frame 3 — 群雄逐鹿

- scene: 六大势力名（朱元璋/陈友谅/张士诚/方国珍/王保保/李思齐）呈星环排列，中心一个"鹿"字金光闪耀
- voiceover: "朱元璋、陈友谅、张士诚……六方诸侯，各怀天命。而你，将是其中之一。"
- duration: 7s
- transition_in: crossfade
- status: outline
- src: compositions/frames/03-warlords.html
- type: pain_point
- persuasion: Future pacing — 让观众代入"你即将成为其中一人"
- beat: intrigue + aspiration
- blueprint: constellation-hub (Adapt)
- focal: typography — "鹿" 字 + 六势力名
- roles: center-glyph = hero · orbiting-names = supporting · progress-bar = chrome
- sfx: whoosh, blip ×6, impact-soft

Adapt: logo/avatar ring becomes faction name ring. Nodes are Chinese characters, not icons. Keep signature move: nodes spring into ring, camera push-IN.
Scene 1 (0.0–3.0s): dark-panel. Center "鹿" in gold (#DAA520), section-header scale. Six faction names orbit into ring around it — each enters with a scaled spring-pop (cluster→outward expansion), staggered 0.3s apart in sequence: 朱元璋 → 陈友谅 → 张士诚 → 方国珍 → 王保保 → 李思齐.
Scene 2 (3.0–7.0s): camera push-IN — the ring tightens as center "鹿" grows to hero-title scale, gold glow bloom. On "而你" beat, all six names flash and dim to 40% opacity, leaving only center "鹿" fully lit. Hold.

narrativeRole: 把叙事从"观看历史"转为"参与历史"—— 你，将扮演一方诸侯。
keyMessage: 天下英雄，唯你一人。

## Frame 4 — 元末逐鹿

- scene: 游戏标题"元末逐鹿"四字剧烈组装，帝金描边，墨夜为底，下方副标题逐字打出
- voiceover: "元末逐鹿 —— 一款元末历史大战略游戏。"
- duration: 5s
- transition_in: zoom-through
- status: outline
- src: compositions/frames/04-title.html
- type: product_intro
- persuasion: Authority by association — 以宏大历史为背书
- beat: curiosity + awe
- blueprint: logo-assemble-lockup (Adapt)
- focal: typography — "元末逐鹿" 四字 LOGO
- roles: title-characters = hero · subtitle = supporting · progress-bar = chrome
- sfx: impact-heavy ×4, whoosh

Adapt: wordless premium sting → Chinese title assembly. Four characters fly in from four corners, assemble at center as a lockup. Keep signature move: elements assemble around a fixed mark.
Scene 1 (0.0–2.0s): dark-panel. Four gold characters ("元""末""逐""鹿") start at four corners, 50% opacity, small scale. Multi-phase camera: slow pull-back into center.
Scene 2 (2.0–4.0s): characters converge to center in staggered sequence — "元" (top-left) → "末" (top-right) → "逐" (bottom-left) → "鹿" (bottom-right) — each landing with a scale bounce + flash. Lockup holds centered at hero-title scale, gold.
Scene 3 (4.0–5.0s): subtitle "元末历史大战略游戏" typewriter-reveals below the lockup, gold body scale. Hold for read.

narrativeRole: 产品首次登场，用游戏名的视觉冲击锚定观众记忆。
keyMessage: 这就是元末逐鹿。

## Frame 5 — 六边形沙盘

- scene: 抽象六边形网格从中心向外扩散，网格上浮现"行省"名称和边界，代表战略沙盘地图
- voiceover: "六边形战略沙盘，纵横千里江山。十四行省，四百九十六座城池 —— 每一步，都牵动天下。"
- duration: 7s
- transition_in: crossfade
- status: outline
- src: compositions/frames/05-sandbox.html
- type: feature_showcase
- persuasion: Show-don't-tell proof — 六边形网格本身就是游戏核心玩法的视觉证明
- beat: awe + control
- blueprint: grid-card-assemble (Adapt)
- focal: geometric — 六边形网格
- roles: hex-grid = hero · province-labels = supporting · progress-bar = chrome
- sfx: blip ×14, riser, impact-soft

Adapt: card grid → hexagon grid. Hexagons self-assemble in staggered cascade, province names pop in. Keep signature: staggered cascade assembly across the grid.
Scene 1 (0.0–2.5s): dark-panel. Single gold hexagon at dead center, small scale. Camera slow push-IN.
Scene 2 (2.5–5.0s): hex grid expands outward in staggered cascade — first ring (6 hex) → second ring (12) → third ring (18). Gold 1px stroke, 20% fill. Camera pulls back to reveal full grid.
Scene 3 (5.0–7.0s): province name labels pop in on key hex cells — "江浙" "湖广" "河南" "陕西" "四川" — each springing in on its VO cue. "496" stat-big number slam at top-right, tilted −6°, gold. Hold for read.

narrativeRole: 展示游戏最核心的视觉符号 — 六边形沙盘地图。
keyMessage: 一棋一子，皆是江山。

## Frame 6 — 圣旨号令

- scene: 古卷展开，圣旨文字逐行书写出现，金印落下，文字扩散为金色光芒
- voiceover: "以帝王口吻发号施令 —— 自然语言圣旨系统。你的每一道圣旨，都将化为千军万马。"
- duration: 7s
- transition_in: push-slide UP
- status: outline
- src: compositions/frames/06-edict.html
- type: feature_showcase
- persuasion: Feature-to-benefit translation — 圣旨输入→ 即刻生效
- beat: power + excitement
- blueprint: typewriter-reveal (Adapt)
- focal: typography — 圣旨文字 + 金印
- roles: edict-text = hero · gold-seal = payoff · progress-bar = chrome
- sfx: whoosh (parchment), typewriter-click, impact-heavy (seal)

Adapt: modern typewriter → ancient edict scroll. Text types vertically (Chinese edict style) on a parchment ground. Keep signature: live typing caret, then seal stamp as payoff.
Scene 1 (0.0–2.0s): bg-panel (#E8D5B7 parchment). A scroll unfurls from top-center (SVG path-draw of scroll edges). Vertical text area center ~40%.
Scene 2 (2.0–5.0s): edict characters type on character-by-character, vertical orientation, in dark ink on parchment — "朕命北伐" four characters appear with typewriter caret. Camera slow push-in.
Scene 3 (5.0–7.0s): gold imperial seal slams down at bottom-right of scroll (impact-heavy SFX, scale boom + settle). On seal impact, text glows gold briefly, then the scroll fades. BG transitions to a faint dark-panel with "千军万马" in gold hero-title scale, then settles.

narrativeRole: 展示游戏最独特的创新 — 自然语言圣旨系统。
keyMessage: 一言既出，万军齐发。

## Frame 7 — 深度系统

- scene: 卡片网格 — 经济/军事/外交/朝堂/城建/国策 六张卡片同时弹出，每张带简短描述
- voiceover: "经济、军事、外交、朝堂、城建、国策 —— 六大维度，环环相扣，牵一发而动全身。"
- duration: 8s
- transition_in: crossfade
- status: outline
- src: compositions/frames/07-systems.html
- type: benefit_highlight
- persuasion: Value stacking — 一口气列出六大系统形成压倒性的丰富感
- beat: confidence + excitement
- blueprint: grid-card-assemble (Reproduce)
- focal: typography — 六大系统卡片
- roles: system-cards = hero · labels = supporting · progress-bar = chrome
- sfx: blip ×6, riser

Reproduce: 6 cards assemble in staggered 2×3 grid, labels pop in per card, very dense.
Scene 1 (0.0–1.0s): bg-panel (#E8D5B7). Empty canvas, center.
Scene 2 (1.0–4.0s): Six cards self-assemble in staggered cascade — 2×3 grid. Each card: dark border (fin-grid style: 3px outer + 1.5px inner), gold section-header label on top, body text subtitle below. Cards enter in reading order: 经济 (top-left) → 军事 → 外交 → 朝堂 → 城建 → 国策 (bottom-right). Each springs in with a 0.2s stagger.
Scene 3 (4.0–8.0s): All six cards co-resident. "牵一发而动全身" appears as gold hero-title across top of grid. Subtle jitter on the full grid. Hold for read — dense frame.

narrativeRole: 展示游戏深度，给硬核策略玩家一个"这款游戏够我玩很久"的承诺。
keyMessage: 治国如烹小鲜，运筹于千里之外。

## Frame 8 — AI博弈

- scene: 中心"AI"发光，十个节点从四周汇聚成神经网络般的连接图，每个节点标注势力名
- voiceover: "十大AI智能体，各怀谋略。MCTS博弈树推演，兰彻斯特战斗方程 —— 你的对手，绝非等闲。"
- duration: 7s
- transition_in: push-slide LEFT
- status: outline
- src: compositions/frames/08-ai.html
- type: benefit_highlight
- persuasion: Authority — 以技术名词（MCTS/兰彻斯特）建立硬核可信度
- beat: curiosity + respect
- blueprint: constellation-hub (Adapt)
- focal: typography — "AI" + 节点 + 势力名
- roles: center-ai-marker = hero · orbiting-nodes = supporting · connection-lines = decoration · progress-bar = chrome
- sfx: blip ×10, riser, whoosh (lines draw)

Adapt: logo ring → AI node network. Ten nodes spring into a ring around center "AI" glyph, SVG connection lines draw between them. Keep signature: nodes enter + connectors + camera push-IN.
Scene 1 (0.0–2.0s): dark-panel. Center "AI" in gold, hero-title scale, glow bloom. Subtle breathing pulse.
Scene 2 (2.0–5.0s): Ten nodes spring into elliptical ring around center — staggered entry 0.15s apart. Each node: faction name label in gold body scale. SVG connection lines self-draw between nodes (svg-path-draw, gold 40% opacity).
Scene 3 (5.0–7.0s): "MCTS" and "兰彻斯特" technical text appear above and below ring, gold section-header → settle to body scale. Camera slow push-in tightens ring. On "绝非等闲", all nodes flash bright gold simultaneously. Hold.

narrativeRole: 证明AI对手不是简单脚本，而是真正有谋略的敌人。
keyMessage: 与人斗，其乐无穷。与AI斗，步步惊心。

## Frame 9 — 战争迷雾

- scene: 大地图被暗影笼罩，视野如烛光般逐格点亮，补给线以金线延伸
- voiceover: "战争迷雾遮天蔽日，补给线千里绵延。你不只要打赢一场仗 —— 你要打赢整场战争。"
- duration: 7s
- transition_in: blur-crossfade
- status: outline
- src: compositions/frames/09-fog.html
- type: feature_showcase
- persuasion: Friction reduction through understanding — 展示了战争不仅是战斗，而是全局博弈
- beat: tension + relief
- blueprint: compose (custom fog-of-war reveal)
- focal: geometric — 迷雾 + 补给线 + 视野圈
- roles: fog-layer = background · vision-circle = hero · supply-lines = supporting · progress-bar = chrome
- sfx: riser, whoosh (fog), blip (nodes light up)

Compose freely: fog-of-war reveal built from CSS opacity + golden supply lines.
Scene 1 (0.0–2.0s): dark-panel. Entire frame covered in dark fog layer (dark #0D0D0D at 85% opacity over a dim hex-grid background). Center small circle of visibility at ~15% frame diameter, barely lit.
Scene 2 (2.0–5.0s): visibility circle expands in pulses — each VO cue triggers a circle expansion (3 stages: hex grid partial → province borders → key city nodes). Golden supply lines draw from bottom-left toward center (svg-path-draw, staggered).
Scene 3 (5.0–7.0s): On "整场战争", the fog layer drops to 40% opacity revealing full map. Gold supply lines complete. "整场战争" four characters slam center at hero-title-red scale, tilted −5°. Hold for read — the stillness after reveal is the point.

narrativeRole: 展示战争迷雾和补给线系统，突出策略深度。
keyMessage: 真正的战争，始于粮草，成于谋略。

## Frame 10 — 天命

- scene: 全红色面板，一个巨大的"命"字倾斜占据画面，金光从字后迸射
- voiceover: "每一个决策，都将改变历史。北伐中原，一统天下 —— 还是偏安一隅，苟且偷生？"
- duration: 6s
- transition_in: zoom-through
- status: outline
- src: compositions/frames/10-destiny.html
- type: branding
- persuasion: Emotional stakes — 把选择权交到观众手中
- beat: awe + urgency-to-act
- blueprint: kinetic-type-beats (Adapt)
- focal: typography — "命" 字大字
- roles: destiny-glyph = hero · choice-text = supporting · progress-bar = chrome
- sfx: riser, impact-heavy ×2, big-impact

Adapt: use red-panel + stacked-text-shadow for maximum impact. Single giant glyph.
Scene 1 (0.0–2.0s): full red-panel (#8B0000). "天" in gold at close-big scale, dead center, stacked-text-shadow active. Camera slow push-in.
Scene 2 (2.0–4.0s): "天" scales down slightly and drifts upward, revealing "命" at stat-big scale (gold, rotated −6°, stacked-text-shadow). Gold glow bloom behind it. The crescendo.
Scene 3 (4.0–6.0s): "北伐中原" and "偏安一隅" appear as two lines left and right of "命" in gold body scale — a choice pair. "命" holds center at stat-big, breathing pulse. The stillness is the emotion. Hold.

narrativeRole: 情绪高潮 — 把游戏玩法升华为"你的选择决定历史"。
keyMessage: 天命，由你书写。

## Frame 11 — 元末逐鹿 锁定

- scene: 标题"元末逐鹿"四字从碎片重新聚合，帝金光芒收敛，定格为最终LOGO，墨夜背景
- voiceover: "元末逐鹿。"
- duration: 5s
- transition_in: crossfade
- status: outline
- src: compositions/frames/11-lockup.html
- type: branding
- persuasion: Brand imprint — 最后的品牌记忆点
- beat: confidence + peace of mind
- blueprint: logo-assemble-lockup (Reproduce)
- focal: typography — 最终 LOGO
- roles: brand-lockup = hero · progress-bar = chrome
- sfx: whoosh, impact-soft

Reproduce: full lockup assembly — elements fly in from edges, converge to form the logo.
Scene 1 (0.0–2.0s): dark-panel. Four gold character fragments at four corners, small scale, pulsing.
Scene 2 (2.0–4.5s): fragments converge center, assembling into "元末逐鹿" lockup at hero-title scale. Gold glow bloom builds, then settles. Subtitle fades in below.
Scene 3 (4.5–5.0s): lockup holds dead center, still. Progress bar fills complete. The pause before the final ask.

narrativeRole: 品牌锁定 — 在情绪高潮后给观众一个沉静的品牌锚点。
keyMessage: 这就是元末逐鹿。

## Frame 12 — 天命由你书写

- scene: 品牌标记凝结为一句"天命由你书写"，光标划过，下方浮现行动号召
- voiceover: "天命，由你书写。元末逐鹿 —— 即刻开启你的帝王史诗。"
- duration: 5s
- transition_in: push-slide UP
- status: outline
- src: compositions/frames/12-cta.html
- type: cta
- persuasion: Urgency + Personal agency
- beat: motivation + excitement
- blueprint: cta-morph-press (Adapt)
- focal: typography — CTA 文字
- roles: cta-line = hero · brand-name = supporting · cursor-click = payoff · progress-bar = chrome
- sfx: whoosh, impact-soft, click

Adapt: brand lockup morphs into CTA line. Keep signature: center morph → cursor arrives → click.
Scene 1 (0.0–1.5s): dark-panel. "天命由你书写" appears at center, hero-title scale, gold — kinetic type, staggered word reveal: "天" → "命" → "由你" → "书写".
Scene 2 (1.5–3.5s): text settles to section-header scale. Below it, "元末逐鹿" appears in gold body. Cursor icon slides in from right, pauses over the text, clicks (cursor-click-ripple).
Scene 3 (3.5–5.0s): On click, "即刻开启你的帝王史诗" types on below in gold body scale. Full lockup holds center. Progress bar fills and flashes gold at 100%. End frame.

narrativeRole: 收束全片，将史诗感转化为行动力。
keyMessage: 现在，轮到你了。
