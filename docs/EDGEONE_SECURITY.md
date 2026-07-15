# EdgeOne 安全加速 Skill 集成方案

> **赛事 AI 创作模块：游戏安全体系** · 元末逐鹿 3.0
> 集成工具：腾讯云 EdgeOne + HaS-Anonymizer · CodeBuddy AI 辅助
> 生成日期：2026-07-14

---

## 一、EdgeOne 安全加速能力覆盖

### 1.1 赛事要求对标

根据黑客松赛题，AI 安全体系需覆盖以下至少一项：

| 要求 | EdgeOne 能力 | 本项目状态 |
|------|-------------|-----------|
| Agent 行为安全 | WAF 自定义规则 + AI Endpoint Protection | ✅ 已集成 |
| 玩家身份鉴权 | Bot 管理 + 速率限制 | ✅ 已集成 |
| 数据交互校验 | 请求体校验 + 注入防护 | ✅ 已集成 |
| 异常行为识别 | 自适应 DDoS 防护 + 行为分析 | ✅ 已集成 |
| 全链路安全防护 | Security Headers + HTTPS + CDN 加速 | ✅ 已配置 |

### 1.2 EdgeOne Skill 使用方式

通过 CodeBuddy 调用 EdgeOne 安全加速 Skill：

```
EdgeOne — ClawHub / SkillHub
- 为游戏上线提供全链路安全保护
- 流畅丝滑的游戏体验
- DDoS 防护、WAF、Bot 管理、CDN 加速一站式配置
```

---

## 二、已集成的安全模块（10 模块体系）

### 2.1 安全响应头配置

已在 `server/security/edgeone_rules.py` 中实现完整的安全头配置：

```python
# 当前已配置的安全头
CSP (Content-Security-Policy): 严格模式
HSTS: max-age=31536000, includeSubdomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera/microphone/geolocation 禁用
Cache-Control: API no-store / 静态资源 86400s
```

### 2.2 WAF 防火墙规则集

已在 `edgeone_rules.py` 中定义 8 条 WAF 规则：

| 规则 ID | 名称 | 防护类型 |
|---------|------|---------|
| waf-001 | SQL Injection Protection | SQL 注入拦截 |
| waf-002 | XSS Protection | 跨站脚本防护 |
| waf-003 | Command Injection Protection | 命令注入防护 |
| waf-004 | Prompt Injection Protection | **LLM 提示注入防护**（独特） |
| waf-005 | Request Size Limit | 请求体大小限制（10MB） |
| waf-006 | Path Traversal Protection | 路径遍历攻击防护 |
| waf-007 | Game API Abuse Protection | 游戏 API 滥用防护（30次/分钟） |
| waf-008 | AI Endpoint Protection | AI 接口特别保护（5次/分钟） |

### 2.3 DDoS 防护

```python
# 已配置的 DDoS 防护阈值
syn_flood: 100,000 pps → JS Challenge
ack_flood: 150,000 pps → JS Challenge
udp_flood: 200,000 pps → Drop
http_flood: 5,000 rps → JS Challenge
connection_flood: 10,000 connections → Drop
```

### 2.4 Bot 管理

- 搜索引擎爬虫：允许
- 社交媒体爬虫：允许
- 未知 Bot：JS Challenge + 行为分析 + 指纹识别
- 自定义规则：游戏状态爬取防护、API 滥用模式检测

### 2.5 IOA 智能风险评估引擎

`server/security/ioa_engine.py` 实现 5 维度 AI 风险评估：

1. **行为风险**：操作频率、异常模式
2. **数据风险**：请求内容、注入检测
3. **AI 风险**：提示注入、模型滥用
4. **网络风险**：IP 信誉、地理异常
5. **综合风险**：加权整合 + 趋势追踪

### 2.6 Agent 行为守卫

`server/security/agent_guard.py`：
- 监控所有 AI 势力的行为边界（通用行为守卫，覆盖 26 种合法行动类型）
- 防止 AI 产出破坏游戏平衡的指令
- AI 输出校验层（`ai_validator.py`）

### 2.7 数据匿名化

`server/security/anonymizer.py` + HaS-Anonymizer：
- 敏感信息脱敏（不对外发布）
- 审计日志脱敏
- 玩家数据保护

---

## 三、接入 EdgeOne 安全检查清单

### 3.1 部署前验证

- [x] Security Headers 配置（CSP/HSTS/XFO/XSS/CORS）
- [x] WAF 规则集（SQL 注入/XSS/命令注入/LLM 提示注入）
- [x] DDoS 防护阈值（SYN/ACK/UDP/HTTP Flood）
- [x] Bot 管理策略（搜索引擎/社交媒体/未知 Bot）
- [x] 速率限制策略（全局 60/min, AI 10/min, 政令 5/min）
- [x] IOA 智能风险评估
- [x] Agent 行为守卫
- [x] 数据校验与匿名化
- [x] 审计日志全量记录
- [x] 前端安全仪表盘可视化

### 3.2 接入步骤

1. **EdgeOne 域名接入**
   - 在腾讯云 EdgeOne 控制台添加游戏域名
   - 配置源站指向前端 Nginx/CloudStudio 地址
   - 开启 HTTPS 加速

2. **安全策略导入**
   - 运行 `python server/security/edgeone_rules.py` 导出完整配置
   - 将 `edgeone_policy.json` 导入 EdgeOne 控制台
   - 验证 WAF 规则有效性

3. **Skill 集成验证**
   - 通过 EdgeOne Skill 测试安全响应头
   - 模拟 SQL 注入/XSS 攻击验证拦截
   - 测试速率限制和 Bot 挑战

4. **监控告警**
   - 接入 SecurityPanel 前端仪表盘
   - 配置异常行为告警
   - 验证审计日志持久化

---

## 四、安全仪表盘（前端可视化）

`frontend/src/components/SecurityPanel.vue` 展示以下实时数据：

```
┌─────────────────────────────────────────────┐
│  安全态势面板              [IOA 风险: 12/100] │
├─────────────────────────────────────────────┤
│  ████████░░ 行为风险    低                   │
│  ████░░░░░░ 数据风险    极低                 │
│  ██████░░░░ 网络风险    中                   │
│  ██████████ AI 风险     高 ← 关注            │
├─────────────────────────────────────────────┤
│  实时威胁: 已拦截 23 次攻击                  │
│  • SQL注入尝试 x12                           │
│  • XSS攻击 x5                                │
│  • 提示注入 x6 ← AI 特有能力                 │
├─────────────────────────────────────────────┤
│  安全评分趋势: ██████░░░░░░░░ (过去 24h)     │
└─────────────────────────────────────────────┘
```

---

## 五、赛事答辩亮点

本项目安全体系的 **差异化优势**：

| 传统游戏安全 | 本项目 AI 安全 |
|-------------|---------------|
| 规则引擎（静态规则匹配） | **AI 驱动的 IOA 智能风险评估** |
| 仅防护网络层攻击 | **覆盖 Agent 层 + 数据层 + 应用层** |
| 无 LLM 攻击防护 | **Prompt Injection 专项防护** |
| 事后审计 | **实时风险可视化仪表盘** |
| 单一防护手段 | **EdgeOne + HaS-Anonymizer 多层纵深** |

以下彩蛋可重点演示：
1. **LLM 提示注入攻击**的实时拦截演示（waf-004 规则在实际对话中识别并拦截恶意 prompt）
2. **AI 智能体的安全边界**：展示 agent_guard 如何防止 AI 谋士输出破坏平衡的指令
3. **EdgeOne DDoS 压力测试**：模拟攻击时的自适应防护响应

---

## 六、集成状态总结

| 模块 | 代码状态 | 部署状态 | 评分贡献 |
|------|---------|---------|---------|
| Security Headers | ✅ 完整 | ⚠️ 需 EdgeOne 配置 | 高 |
| WAF 8 规则 | ✅ 完整 | ⚠️ 需 EdgeOne 配置 | 高 |
| DDoS 防护 | ✅ 配置 | ⚠️ 需 EdgeOne 配置 | 中 |
| Bot 管理 | ✅ 配置 | ⚠️ 需 EdgeOne 配置 | 中 |
| IOA 引擎 | ✅ 完整 | ✅ 运行中 | **极高** |
| Agent 守卫 | ✅ 完整 | ✅ 运行中 | **极高** |
| 数据匿名化 | ✅ 完整 | ✅ 运行中 | 中 |
| 审计日志 | ✅ 完整 | ✅ 运行中 | 中 |
| 前端仪表盘 | ✅ 完整 | ✅ 运行中 | 高 |
| HaS-Anonymizer | ✅ 集成 | ✅ 运行中 | 中 |

**整体 AI 安全完成度：10/10 模块就绪，EdgeOne CDN 配置为部署时最后一步。**

---

**AI 创作声明**：本安全方案由 **CodeBuddy AI 辅助设计**，作为腾讯云黑客松「AI CAN DO IT」赛事 **AI 游戏安全体系** 模块的核心交付物。

集成工具：EdgeOne 安全加速 Skill + HaS-Anonymizer · 生成日期：2026-07-14
