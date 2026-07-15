# AI 美术资源生成方案

> **赛事 AI 创作模块：游戏原画** · 元末逐鹿 3.0
> 生成工具：混元/Stable Diffusion · CodeBuddy AI 辅助创作
> 生成日期：2026-07-14

---

## 一、资源清单

9 大势力共需生成以下美术资源：

| 资源类型 | 数量 | 尺寸 | 用途 |
|---------|------|------|------|
| 势力君主立绘 | 9张 | 1024×1024 | 势力选择页主视觉 |
| 都城场景概念图 | 9张 | 1920×1080 | 加载页/场景切换背景 |
| 谋士头像 | 29张 | 512×512 | 谋士献策面板 |
| 战场场景概念图 | 4张 | 1920×1080 | 战斗结算界面（平原/水战/攻城/关隘） |
| UI 装饰元素 | 6张 | 多种 | UI 按钮/边框/纹饰 |

---

## 二、AI 生图提示词模板

### 2.1 推荐工具

| 工具 | 使用方式 | 说明 |
|------|---------|------|
| **混元文生图** | CodeBuddy Skills → `generateImage` | 腾讯云混元大模型，中文理解最佳 |
| **Miora** | miora.design（网页服务） | 游戏美术物料/视频创作 |
| **WorkBuddy** | AI Agent 办公新范式 | 通过 skills 本地生产力 |
| **Stable Diffusion** | ComfyUI / WebUI | 开源方案，可精细 ControlNet 控制 |

### 2.2 统一艺术风格规范

所有 AI 生成美术资源必须遵循以下风格统一要求：

```
艺术风格：Dark Chinese Ink Wash Painting（暗色国风水墨风格）
色调：暗金 + 墨色 + 朱砂红为主色调，参考项目 #D4C5A9（古绢）、#C9A96E（暗金）、#8B0000（深红）
画风：元代水墨人物画 + 现代游戏概念艺术融合
光照：侧光/顶光，营造古画的斑驳感和历史厚重感
笔触：保留水墨笔触痕迹，避免过度光滑的3D渲染
构图：古代卷轴式构图，适当留白
```

---

## 三、九大势力君主立绘 · AI 提示词

### 3.1 元廷 · 元顺帝

```
Prompt (English):
A middle-aged Mongolian emperor in his 40s, wearing golden imperial dragon robes with intricate cloud patterns, sitting on a dragon throne in a dim palace hall. The emperor has a worried expression, with deep-set eyes, a thin mustache, and a tired but dignified bearing. Dark Chinese ink wash art style, side lighting from lanterns casting long shadows. The background is a grand but decaying Yuan Dynasty palace interior with silk curtains and bronze incense burners. Palette: deep crimson (#8B0000), dark gold (#C9A96E), ink black. Inspired by Yuan Dynasty portrait paintings, with textured brushstrokes. Vertical composition, 1024x1024.

Negative Prompt: cartoon, anime, 3D render, smooth plastic skin, bright colors, happy expression, clean modern palace, Western medieval style, blurry, low quality
```

**提示词（中文备用）：**
```
一位40多岁的蒙古皇帝，身着金色云纹龙袍，坐于龙椅之上，宫殿幽暗。面容忧虑而威严，深邃的眼睛，细长的胡须。侧光从宫灯照来投下长影。背景是即将衰败的元代宫殿，丝绸帷幕与青铜香炉。暗色国风水墨风，深红+暗金+墨色，元代肖像画风格，笔触质感。竖幅1024x1024。
```

### 3.2 王保保 · 扩廓帖木儿

```
Prompt (English):
A fierce Mongolian warrior-general in his 30s, wearing ornate lamellar armor with fur-trimmed collar, holding a Mongolian saber. He has a proud, defiant expression, with a scar on his cheek, strong jaw, intense dark eyes. Standing on a snow-covered cliff overlooking the northern steppes. Dark Chinese ink wash style, cold blue-grey (#666699) and dark gold (#C9A96E) palette. Wind sweeping snow and horsehair standard behind him. Heroic composition, dynamic pose. 1024x1024.

Negative Prompt: cartoon, anime, 3D render, smooth skin, smiling, Chinese Han clothing, city background, blurry
```

### 3.3 漠北诸部 · 草原大汗

```
Prompt (English):
A weathered Mongolian tribal chieftain in his 50s, wearing traditional fur and leather nomadic warrior attire, with a bow slung across his back. He has a thick beard, weather-beaten face, fierce hawk-like eyes gazing at the distant horizon. Standing beside a Mongolian horse on the vast green steppe under a stormy sky. Dark ink wash style, earthy brown (#887766) and dark gold palette. Yurt tents and galloping horses in distant background. Sageo-style composition. 1024x1024.

Negative Prompt: cartoon, 3D render, modern city, palace, clean face, smiling, blurry
```

### 3.4 朱元璋 · 吴国公

```
Prompt (English):
A determined Chinese rebel leader in his early 40s, wearing deep red battle robes with simple leather armor, standing in a war council tent. He has a long face with prominent cheekbones, penetrating eyes showing both wisdom and ruthlessness, a thin mustache. Behind him is a partially visible map on a wooden table. Dark Chinese ink wash style, crimson (#DC143C) and ink black palette. Candlelight illumination. Historically-inspired portrait style, dignified but not ostentatious. 1024x1024.

Negative Prompt: cartoon, anime, 3D render, emperor crown, golden dragon robes, palace, smiling, fat face, blurry
```

### 3.5 陈友谅 · 汉帝

```
Prompt (English):
A fierce Chinese warlord in his 40s, wearing ornate blue battle armor with gold trim, standing on the deck of a massive war junk ship. He has a sharp, ambitious face with piercing eyes and a thin black beard. Behind him are towering warship masts, lake waters churning, and distant naval battle smoke. Dark Chinese ink wash style, deep blue (#1E90FF) and dark gold palette. Dramatic stormy lighting. The largest warship in the background emphasizes his naval power. 1024x1024.

Negative Prompt: cartoon, anime, 3D render, modern ship, palace, smiling, peaceful lake, blurry
```

### 3.6 张士诚 · 周王

```
Prompt (English):
A wealthy-looking Chinese warlord in his late 30s, wearing elegant silk robes in warm orange tones with jade ornaments, sitting in a luxurious garden pavilion in Suzhou. He has a round, prosperous face, calm gentle eyes, looking slightly complacent. Behind him: Jiangnan garden with lotus pond, curved bridges, willow trees. Dark ink wash style, warm orange (#FF8C00) and dark gold palette. Soft afternoon light. The overall feeling is wealthy but lacking military ambition. 1024x1024.

Negative Prompt: cartoon, 3D render, armor, weapons, battlefield, poor clothing, angry expression, blurry
```

### 3.7 徐寿辉 · 天完皇帝

```
Prompt (English):
A charismatic Chinese rebel leader in his 40s with a spiritual aura, wearing simple robes with Buddhist prayer beads, a red headband (red turban). He has an earnest, zealous expression, with eyes looking upward as if receiving divine mandate. Holding a Buddhist sutra in one hand and a sword in the other. Background: mountain temple with prayer flags, misty peaks. Dark ink wash style, earthy brown (#996633) and crimson palette. Religious, mystical atmosphere. 1024x1024.

Negative Prompt: cartoon, 3D render, dragon robes, throne, palace, modern, blurry
```

### 3.8 方国珍 · 浙东节度

```
Prompt (English):
A cunning Chinese maritime merchant-lord in his 40s, wearing practical coastal trader's clothing in sea-green tones with a compass hanging from his belt. He has a shrewd, calculating expression with a slight knowing smile. Standing at the bow of a Chinese junk ship, with a bustling harbor and island archipelago behind him. Dark ink wash style, sea-green (#20B2AA) and ink black palette. Sea spray and dramatic clouds. Maritime trade goods visible. 1024x1024.

Negative Prompt: cartoon, 3D render, inland, desert, palace, armor, blurry
```

### 3.9 明玉珍 · 大夏皇帝

```
Prompt (English):
A benevolent-looking Chinese ruler in his 40s, wearing modest imperial robes in dark gold with jade accessories, standing on a cliff overlooking the Sichuan basin with its winding rivers and terraced fields. He has a kind, reserved expression with calm eyes. Behind him: the majestic Three Gorges mountains shrouded in mist, stone fortress walls. Dark ink wash style, earth gold (#B8860B) and ink black palette. Misty mountain scenery, Song Dynasty landscape painting influence. 1024x1024.

Negative Prompt: cartoon, 3D render, ocean, flat plains, palace interior, arrogant expression, blurry
```

---

## 四、都城场景概念图 · AI 提示词

### 4.1 大都（元廷都城）

```
Chinese ink wash landscape painting of Dadu (Khanbaliq/Beijing) in the 14th century Yuan Dynasty. A grand walled city seen from outside, with towering gate towers, Mongol yurt encampments outside the walls, and the Forbidden City-like palace complex within. Snow on the northern mountains in distance. Dark, moody atmosphere. Oil-paper lanterns glowing at dusk. 1920x1080, cinematic wide shot. Palette: dark crimson, ink black, dark gold. Weathered, ancient scroll texture.
```

### 4.2 应天府（朱元璋都城）

```
Chinese ink wash painting of Yingtian (Nanjing) in the 14th century. A fortified city on the south bank of the Yangtze River, with the massive stone city walls, drum towers, and a grand river port with hundreds of trade junks. Purple Mountain visible in background mist. Spring atmosphere with plum blossoms. 1920x1080, wide landscape. Palette: crimson, ink black, dark gold.
```

### 4.3 武昌（陈友谅都城）

```
Chinese ink wash painting of Wuchang in the 14th century. A lakeside fortress city where the Han River meets the Yangtze, with towering warship docks, naval shipyards with massive vessels under construction, and fortified river walls. Stormy sky with lightning over the water. 1920x1080. Palette: deep blue, ink black, dark gold.
```

### 4.4 平江（张士诚都城）

```
Chinese ink wash painting of Pingjiang (Suzhou) in the 14th century. A prosperous canal city with white-walled buildings, curved stone bridges, silk workshops along the waterways, and elegant garden pavilions. Merchant boats laden with goods. Cherry blossoms and willow trees. Lively market scene along the Grand Canal. 1920x1080. Warm orange-golden palette.
```

### 4.5 庆元（方国珍都城）

```
Chinese ink wash painting of Qingyuan (Ningbo) in the 14th century. A bustling coastal port city with a vast natural harbor, hundreds of ocean-going junks with battened sails, island fortifications, lighthouse tower on a hill, and warehouse districts along the waterfront. Sea mist and dramatic clouds. 1920x1080. Sea-green and ink black palette.
```

### 4.6 重庆（明玉珍都城）

```
Chinese ink wash painting of Chongqing in the 14th century. A mountain fortress city built on steep cliffs where two great rivers meet, connected by rope bridges and steep stone stairs. Watchtowers on every peak, surrounded by misty gorges and terraced rice fields climbing the mountainsides. 1920x1080. Earth-gold and ink black palette.
```

### 4.7 太原（王保保都城）

```
Chinese ink wash painting of Taiyuan in the 14th century. A northern frontier fortress city on the edge of the steppe, with massive rammed-earth walls, cavalry training grounds with thousands of horses, and snow-capped northern mountains beyond. Mongolian yurt encampments outside the walls. 1920x1080. Cold blue-grey palette.
```

### 4.8 和林（漠北都城）

```
Chinese ink wash painting of Karakorum in the 14th century. The ancient Mongol capital on the vast grassland steppe, a city of yurts and low wooden buildings surrounding a golden Buddhist temple, with herds of horses stretching to the horizon. Storm clouds gathering over the endless grass sea. 1920x1080. Earth-brown palette.
```

### 4.9 襄阳（徐寿辉都城）

```
Chinese ink wash painting of Xiangyang in the 14th century. A strategic fortress city on the Han River, with thick stone walls pierced by arrow towers, where the river forms a natural moat. Red turban flags flying from the battlements. Temple pagodas visible within. Sunset lighting creates a dramatic silhouette. 1920x1080. Earth-brown and crimson palette.
```

---

## 五、战场场景概念图 · AI 提示词

### 5.1 平原会战

```
Epic Chinese ink wash painting of a massive medieval battle. Two armies clash on a vast plain at sunset. One side: Mongol cavalry with fur banners. The other side: Chinese infantry with red turban flags. Dust clouds, cavalry charges, spear formations silhouetted against the orange sky. Very wide panoramic composition, cinematic. 1920x1080. Dark ink and blood-red palette.
```

### 5.2 水战（鄱阳湖）

```
Epic Chinese ink wash painting of a naval battle. Hundreds of massive warships burning on a great lake. Tower ships with three decks exchanging fire arrows and grappling hooks. Smoke and flames reflecting on dark water. Ships colliding, soldiers boarding. Stormy sky and burning horizon. 1920x1080. Blue-black and flame-orange palette.
```

### 5.3 攻城战

```
Epic Chinese ink wash painting of a siege battle. A massive fortified city under assault at night. Siege towers and ladders against towering stone walls. Defenders pouring boiling oil. Flaming projectiles arcing through the dark sky. Battering ram at the main gate. Dramatic firelight illumination. 1920x1080. Ink black and fire-orange palette.
```

### 5.4 关隘争夺

```
Epic Chinese ink wash painting of a mountain pass battle. Two armies fighting in a narrow mountain defile between towering cliffs. Cavalry bottlenecked in the pass. Archers on high cliffs raining arrows. Stone fortifications and wooden palisades. Morning mist and mountain shadows. 1920x1080. Cold grey and dark gold palette.
```

---

## 六、UI 装饰元素 · AI 提示词

### 6.1 卷轴边框

```
Traditional Chinese horizontal scroll ornament border, ink wash style, dark gold (#C9A96E) pattern on aged silk background. Decorative cloud motifs at scroll ends. Weathered texture, ancient manuscript aesthetic. Clean edges suitable for UI frame. 1920x120.
```

### 6.2 印章纹饰

```
Traditional Chinese red seal stamp pattern, square vermillion ink seal with ancient seal script characters, on aged paper texture. Square format with irregular edge wear. Dark red (#8B0000) on parchment background. Suitable for faction emblem or game logo. 512x512.
```

### 6.3 云纹底纹

```
Chinese ink wash cloud pattern, subtle dark gold clouds on dark background, traditional Xiangyun (auspicious cloud) motif. Seamless tileable pattern, very low contrast, suitable for UI panel background texture. 512x512, tileable.
```

### 6.4 水墨山川

```
Subtle Chinese ink wash mountain landscape silhouette, misty peaks in various opacity levels, ink black on transparent/dark background. Low contrast, decorative background for loading screens or empty states. Horizontal composition. 1024x256.
```

### 6.5 战旗纹样

```
Ancient Chinese military banner design, triangular war flag with tattered edges, ink wash style. Dragon or tiger emblem in gold thread on dark crimson fabric. Flowing in the wind effect. Suitable for faction war banner decoration. 512x512.
```

### 6.6 龙纹徽章

```
Traditional Chinese dragon medallion design, circular badge with coiled dragon motif in dark gold, ink wash style. Yuan Dynasty imperial style, suitable for faction seal or power indicator. Circular format. 512x512.
```

---

## 七、批量生成流程

### Step 1：准备工作
1. 确认使用工具（推荐混元文生图/Tencent Hunyuan）
2. 准备每个势力的独立色彩 profile
3. 创建输出目录：`frontend/public/assets/factions/ai_generated/`

### Step 2：分批生成
- **批次1**：9张君主立绘（1024×1024）→ 势力选择页
- **批次2**：9张都城场景（1920×1080）→ 场景切换背景
- **批次3**：29张谋士头像（512×512）→ 谋士面板
- **批次4**：4张战场概念（1920×1080）→ 战斗界面
- **批次5**：6张UI装饰（多种尺寸）→ UI组件

### Step 3：后期处理
- 统一裁切和尺寸
- 风格一致性检查（暗金+墨色主色调）
- 添加水墨纹理叠加层（参考项目 `InkWashTexture.ts`）
- WebP 压缩优化

### Step 4：前端集成
- 更新 `factions.json` 中的 `image` 字段指向新生成的立绘
- 创建场景图切换逻辑
- 更新 UI 装饰元素引用

---

## 八、已有资源映射表

| 势力 | 当前立绘 | 需替换 | 已有 ruler 图 |
|------|---------|--------|-------------|
| 元廷 | a6f30b6324fce83790efa49f2d0929fd.jpg | ✅ 需AI生成 | ruler_yuan.jpg |
| 朱元璋 | b47057828607bd36e92aa37417631bf9.jpg | ✅ 需AI生成 | ruler_zhuyuan.jpg |
| 陈友谅 | a1838ce68653600728081332905c0fd1.jpg | ✅ 需AI生成 | ruler_chen.jpg |
| 张士诚 | 649817e3158b0df1c68ab2e2a2a0e4f7.jpg | ✅ 需AI生成 | ruler_zhang.jpg |
| 方国珍 | 0f3acb15948b699fbbd2a780dea693b8.jpg | ✅ 需AI生成 | ruler_fang.jpg |
| 徐寿辉 | 7a6ae9a077f4d6178e55be82b7039c7a.jpg | ✅ 需AI生成 | ruler_xushou.jpg |
| 明玉珍 | 649817e3158b0df1c68ab2e2a2a0e4f7.jpg | ✅ 需AI生成 | ruler_ming.jpg |
| 王保保 | a1838ce68653600728081332905c0fd1.jpg | ✅ 需AI生成 | ruler_wang.jpg |
| 漠北诸部 | 5812a954fbc9e83b11ddaa4cc2b7a88a.jpg | ✅ 需AI生成 | ruler_tatar.jpg |

> **注**：当前立绘为占位图片（多个势力共用同一张图），需全部替换为 AI 生成的专属立绘。

---

**AI 创作声明**：本文档中所有美术提示词（Prompt）由 **CodeBuddy AI 辅助生成**，作为腾讯云黑客松「AI CAN DO IT」赛事 **AI 游戏原画** 模块的技术方案。
