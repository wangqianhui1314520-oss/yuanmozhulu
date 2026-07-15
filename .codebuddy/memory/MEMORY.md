# 元末逐鹿 3.0 — 项目记忆

## 项目路径与启动
- 根目录: `d:\AI\元末逐鹿3.0原版\元末逐鹿\`
- 后端: `python server.py` → uvicorn :8800（需设置 `$env:PYTHONUTF8="1"` + `$env:PYTHONIOENCODING="utf-8"`）
- 前端: `frontend/`，修改源码后需 `npm run build`
- AI 调用需 `TENCENT_API_KEY` 环境变量

## 架构
- FastAPI 200+端点，前端 HTTP POST 轮询
- AI: CodeBuddy API → DeepSeek-V3，三层模型(advisor/strategy/enemy)
- 8阶段回合制，RoundEngine驱动
- 安全中间件: IP封禁/速率限制/10MB请求限制/审计日志

## 已完成修复汇总 (2026-07-14~15)

### 八大智能体
A1-A8 各修复（献策格式/决策链/事件返回值/皇子成长/案件安全/史书编纂/风险截断）

### 势力ID统一
旧 faction_hansong/chenyouding/liangwang → 新 faction_xushouhui/wangbaobao/mobei

### 安全加固
存档原子写入、深拷贝回滚、events_log上限2000、日志轮转10MB/5、LLM降级10分钟恢复

### AI调用系统
API Key环境变量化、A3 max_tokens→4096

### 历史锚点
4项修复 + 3项补充（锚点②死代码、陈友谅霸业锚点、净损失计算、reactions写入events_log）

### 文档审计
- 核心系统十一大领域: 23处差异全部修复
- 安全体系: 7严重+12中等+5轻微全部修复

### 游玩体验修复 (6+8项)
- Bug #1: agent_guard valid_actions 补充20+合法行动
- Bug #2: 前5回合接壤势力完全可见（修复NPC全部-1）
- Bug #3: advance-turn 返回前30条事件
- Bug #4: AI并发调用超时保护(20-30s)
- Bug #5: player_faction 顶层字段补全
- Bug #6: diplomatic_relations 数组化
- 8项小修复: action别名/ NL命令崩溃/字段补全/事件去重/command_id补齐/phase补齐/存档别名

### security_middleware.py
cleanup_expired() 修复 `self._lock`→`self._ip_locks_lock`

## 2026-07-15 沙盘地图层级修复

- `HexMapView.vue`：`.hex-map-container` 添加 `z-index: 1`
- `GamePage.vue`：已删除 `.map-surface::before`（暖羊皮纸覆盖层）

### 最终层级（.map-surface 内）
```
.map-status-overlay    z-index: 100  (加载/错误覆盖)
.hex-map-container     z-index: 1    (Konva 地图)
.map-surface::after    z-index: 10   (底部40px山脉装饰，不影响地图)
```

## CloudBase 部署信息
- 前端已上线: `https://yuanmozhulu-d7g0odx41c77d74e6-1448258497.tcloudbaseapp.com/`
- 后端未部署: 体验版不支持 CloudRun，需升级套餐
- 部署方式: Dockerfile 多阶段构建 → Cloud Run 容器 + 静态托管

## 已知待修复
- tile_count 初始化用核心地块数，回合结算后修正为实际地块数（非严重）
- 补给断裂逃散日志过多（WARNING刷屏）

## 2026-07-15 游玩界面交互审计 → 已全部修复

### 修复内容
1. **SecurityPanel 致命缺陷**：添加 `showSecurity` ref 声明，🛡 按钮恢复正常
2. **ReplayPanel 死代码复活**：右侧工具栏新增 ⏪ 回放按钮，完整接线到 `showReplay` ref
3. **死代码清理**：删除 GameHeader.vue / IntelligencePanel.vue / HexTooltip.vue / HexDetailPopup.vue 四个永不被导入的残留组件
4. **隐藏面板入口补全**：
   - 左侧工具栏新增：🌲伏击、🏴劫掠、🏛迁都
   - 右侧工具栏新增：🕸️势力图、📊AI推演、🔊音效、⏪回放
   - 律法审讯保持二级面板入口（从律法面板内部触发）
5. **军团系统**：前端无对应组件，需从零构建，留待后续

### 修改文件
- `frontend/src/pages/GamePage.vue`：添加 showSecurity ref + showSecurity/showReplay 完整接线 + 左右工具栏各新增 3/4 个按钮
- 删除 `frontend/src/components/GameHeader.vue`
- 删除 `frontend/src/components/IntelligencePanel.vue`
- 删除 `frontend/src/components/HexTooltip.vue`
- 删除 `frontend/src/components/HexDetailPopup.vue`

## 2026-07-15 人物图片统一 → 已全部完成

用户桌面的 9 张人物图片（yuan/zhuyuanzhang/chenyouliang/zhangshicheng/fangguozhen/mingyuzhen/wangbaobao/mobei/xushouhui.jpg）已作为全游戏统一人物立绘。

### 统一路径
所有人物图片统一为 `frontend/public/assets/factions/ruler_*.jpg`：
| 势力 | 图片文件 |
|------|---------|
| faction_yuan | ruler_yuan.jpg |
| faction_zhuyuanzhang | ruler_zhuyuan.jpg |
| faction_chenyouliang | ruler_chen.jpg |
| faction_zhangshicheng | ruler_zhang.jpg |
| faction_fangguozhen | ruler_fang.jpg |
| faction_mingyuzhen | ruler_ming.jpg |
| faction_wangbaobao | ruler_wang.jpg |
| faction_mobei | ruler_tatar.jpg |
| faction_xushouhui | ruler_xushou.jpg |

### 修改内容
1. `server/config/factions.json`：9个 faction 的 `image` 字段从 hash 命名改为 `ruler_*.jpg`
2. `frontend/src/pages/SandboxIntroPage.vue`：BUILTIN 数据 image 从 `ai_portrait_*.png` / hash 命名改为 `ruler_*.jpg`
3. `frontend/src/components/CharacterPortrait.vue`：新增 `imageUrl` prop 和 `RULER_IMAGE_MAP` 导出；有 `imageUrl` 时用 `<img>` 替代 Canvas 绘制
4. `frontend/src/components/AdvisorPanel.vue`：`getNPCPortraitData()` 对 ruler 角色自动传入 faction 对应图片
5. `frontend/src/components/GeneralChatPanel.vue`：`getPortraitData()` 对 ruler 角色自动传入 faction 对应图片
6. `FactionSelectPage.vue` 和 `GamePage.vue` 本身已使用 `ruler_*.jpg`，无需修改

## 2026-07-15 沙盘地图系统重构（按文档 `地图与地形系统总结.md` 对齐）

### 修改文件
1. **`server/map/generate_map.py`** (v4.2→v4.3)：
   - 文档更新：12种地形、90个地理区域、8个海域分区
   - 新增 `build_full_map(tiles)` 函数，在流水线[9]步之后自动合并陆地+海域生成 `map_full.json`
   - 新增 `import json` 依赖
   - 保留 `generate_full_map()` 旧接口兼容

2. **`server/map/sea_generator.py`** (v1.0→v2.0)：
   - 移除 `northern_sea`（北洋）海域分区，对齐文档的8海域
   - 更新 `priority_zones` 列表（7项+deep_ocean兜底=8分区）
   - 移除 `SEA_ZONES["northern_sea"]` 定义
   - 文档注释更新

3. **`server/map/terrain_generator.py`**：
   - GEO_REGIONS 注释：89→90个地理区域
   - 新增第90个区域："粤东沿海丘陵" (潮汕沿海丘陵)
   - 第1遍扫描注释更新

### 已验证一致（无需修改）
- `layer_config.py`：势力ID已统一为 `faction_` 前缀 ✅
- `special_markers.py`：势力ID已统一 ✅
- `faction_territory.py`：势力ID统一、配额499格、首都坐标正确 ✅
- `admin_hierarchy.py`：14行省定义与文档完全匹配 ✅
- `generate_map.py`：第4步已调用 `generate_terrain_map()` ✅
- `terrain_generator.py`：12种地形类型与文档完全一致 ✅
