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

## 已知待修复
- tile_count 初始化用核心地块数，回合结算后修正为实际地块数（非严重）
- 补给断裂逃散日志过多（WARNING刷屏）
