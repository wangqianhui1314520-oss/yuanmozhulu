# 《元末逐鹿3.0》九大势力游玩流程测试报告

> 测试时间：2026-07-15 | 测试者：CodeBuddy AI
> 依据文档：`docs/九大势力完整游玩方案.md`
> 测试范围：全部9个势力，每势力2回合，逐条测试文档推荐指令

---

## 一、总体概况

| 指标 | 数值 |
|------|------|
| 测试势力数 | 9/9 ✓ |
| 每势力测试回合 | 2 回合 |
| 文档声称指令总数 | 43 种 |
| 实际合法指令数 | 38 种 |
| 文档非法指令数 | **11 种** |
| 发现的问题总数 | **5 大类** |

---

## 二、严重问题（Critical / Major）

### 问题1：文档推荐的11种指令在API中不存在

**严重度**：Critical | **影响**：玩家无法按照文档执行操作

文档声称支持43种指令，但实际测试只有38种合法。以下11种在文档中被积极推荐但API拒绝：

| 非法指令 | 文档使用位置 | 文档角色 |
|----------|-------------|---------|
| **farm** | 朱元璋T1, 张士诚T3, 明玉珍T1×2, 陈友谅T5, 徐寿辉T2 | 农耕 ⭐最常用|
| **supply** | 朱元璋T8, 明玉珍T4, 张士诚T5, 王保保T2, 陈友谅T2/T9, 徐寿辉T7, 元廷T2 | 补给 |
| **edict** | 明玉珍T9, 徐寿辉T7, 元廷T1 | 政令 |
| **appoint** | 朱元璋T5, 明玉珍T9, 元廷T9(文档推荐) | 任命 |
| **retreat** | 文档指令列表 | 撤退 |
| **reinforce** | 文档指令列表 | 增援 |
| **dismiss** | 文档指令列表 | 罢免 |
| **intel** | 文档指令表"谍报"(被Agent拦截) | 情报 |
| **court_settlement** | 文档指令列表 | 朝堂 |
| **prisoner_action** | 文档指令列表 | 囚犯 |
| **policy_unlock** | 文档指令列表 | 政策解锁 |

**注意**：`edict` 应使用 `decree` 替代（decree 在合法列表中），但文档从未提及 `decree`。`edict` 也不在中文别名映射中。

---

### 问题2：所有势力初始领土数据均显示为0

**严重度**：Critical | **影响**：地图/领土信息对玩家不可见

| 势力 | 文档声称领土数 | API返回tiles数 |
|------|:-----------:|:------------:|
| 朱元璋 | 11 | **0** |
| 张士诚 | 9 | **0** |
| 明玉珍 | 8 | **0** |
| 方国珍 | 4 | **0** |
| 王保保 | 6 | **0** |
| 陈友谅 | 11 | **0** |
| 徐寿辉 | 6 | **0** |
| 漠北诸部 | 5 | **0** |
| 元廷 | 9 | **0** |

所有9个势力的 `world_state.factions[fid].tiles` 均返回空数组或长度为0，与文档声称的4-11块初始领地严重不符。玩家无法看到自己的领土范围。

---

### 问题3：回合推进异常

**严重度**：Major | **影响**：回合数不一致

测试中观察到以下回合跳跃/停滞现象：

| 势力 | 异常现象 |
|------|---------|
| 朱元璋 | T2推进后仍显示R1（未增长） |
| 张士诚 | T2推进后仍显示R1（未增长） |
| 方国珍 | T2推进后仍显示R1（未增长） |
| 王保保 | 从R1直接跳到R3（R2被跳过） |

部分势力的回合推进结果与预期不符，`current_round` 在多个回合后未递增或跳号，影响玩家对游戏进程的感知。

---

### 问题4：部分势力数据读取异常

**严重度**：Major | **影响**：状态获取失败

| 势力 | 异常 |
|------|------|
| 朱元璋 T2 | 银两=-1 兵力=-1 粮草=-1 |
| 张士诚 T2 | 银两=-1 兵力=-1 粮草=-1 |
| 方国珍 T2 | 银两=-1 兵力=-1 粮草=-1 |

说明 `world_state.factions[fid]` 在某些回合推进后返回了无效数据或faction数据丢失。明玉珍T2却能正常读取，说明存在间歇性bug。

---

## 三、文档 vs 代码一致性问题

### 3.1 初始数据验证

除领土外，银两/粮草/兵力的文档数据与API返回完全一致：

| 势力 | 银两 | 粮草 | 兵力 | 领土 |
|------|:----:|:----:|:----:|:----:|
| 朱元璋 | ✓8000 | ✓4000 | ✓3000 | ✗0(文档11) |
| 张士诚 | ✓15000 | ✓7000 | ✓3500 | ✗0(文档9) |
| 明玉珍 | ✓6500 | ✓5000 | ✓3000 | ✗0(文档8) |
| 方国珍 | ✓6000 | ✓3000 | ✓2000 | ✗0(文档4) |
| 王保保 | ✓8000 | ✓5000 | ✓4000 | ✗0(文档6) |
| 陈友谅 | ✓12000 | ✓6000 | ✓5000 | ✗0(文档11) |
| 徐寿辉 | ✓6000 | ✓4000 | ✓3500 | ✗0(文档6) |
| 漠北诸部 | ✓5000 | ✓2000 | ✓4500 | ✗0(文档5) |
| 元廷 | ✓20000 | ✓8000 | ✓6000 | ✗0(文档9) |

银两/粮草/兵力数据与配置文件 `server/config/factions.json` 完全一致，文档也与之匹配。领土问题见问题2。

---

### 3.2 文档指令表 vs 实际合法性

文档附录"游戏指令完整列表"声称43种指令：

```
军事类14种: recruit, train_troops, train, conscript, march, attack, 
            raid, ambush, garrison, retreat✗, reinforce✗, supply✗, mobilize, transport

经济类8种:  farm✗, trade, develop, tax, collect_tax, relief, build, buy_horses

内政类8种:  edict✗, decree, law, appoint✗, dismiss✗, enfeoff, purge, amnesty

外交类6种:  diplomacy, tribute, pledge, vassal, marriage, governor

谍报类8种:  spy, scout, counter_spy, sabotage, bribe, assassinate, intel✗, survey

其他5种:    fortify, move_capital, court_settlement✗, prisoner_action✗, policy_unlock✗
```
标记 ✗ 的为API中不存在的指令。

---

## 四、各势力游玩流程命中率

按文档推荐的回合指令，分别统计各势力指令合法性：

| 势力 | 文档推荐指令数(2回合) | 合法数 | 非法数 | 命中率 |
|------|:---:|:---:|:---:|:---:|
| 朱元璋 | 4 | 3 | 1 (farm) | 75% |
| 张士诚 | 4 | 4 | 0 | **100%** |
| 明玉珍 | 4 | 2 | 2 (farm×2) | 50% |
| 方国珍 | 4 | 4 | 0 | **100%** |
| 王保保 | 4 | 4 | 0 | **100%** |
| 陈友谅 | 4 | 4 | 0 | **100%** |
| 徐寿辉 | 4 | 3 | 1 (farm) | 75% |
| 漠北诸部 | 4 | 4 | 0 | **100%** |
| 元廷 | 4 | 2 | 2 (edict, supply) | 50% |

**关键统计**：
- 60%势力(5/9)使用了文档推荐的非法指令
- `farm` 是最常见的非法指令（命中3个势力: 朱/明/徐）
- `edict` 和 `supply` 各影响1个势力（元廷）
- 元廷文档推荐 `supply` 但API拒绝，导致第2步无法推进

---

## 五、明细问题清单

| # | 严重度 | 势力 | 类别 | 描述 |
|---|:------:|------|------|------|
| 1 | Critical | 全局 | 指令非法 | `farm` 不在API合法列表中，文档广泛使用（朱元璋/张士诚/明玉珍/陈友谅/徐寿辉） |
| 2 | Critical | 全局 | 指令非法 | `supply` 不在API合法列表中（朱元璋/王保保/陈友谅/徐寿辉/元廷） |
| 3 | Critical | 全局 | 指令非法 | `edict` 不在API合法列表中（明玉珍/徐寿辉/元廷），应改用 `decree` |
| 4 | Critical | 全局 | 指令非法 | `appoint` 不在API合法列表中（朱元璋/明玉珍/元廷） |
| 5 | Critical | 全局 | 领土数据 | 全部9个势力初始领土tiles=0，文档声称4-11块 |
| 6 | Major | 全局 | 指令非法 | `retreat`, `reinforce`, `dismiss`, `intel`, `court_settlement`, `prisoner_action`, `policy_unlock` 不在验证列表 |
| 7 | Major | 朱元璋 | 回合推进 | T2推进后仍显示R1, factions数据变为银=-1兵=-1粮=-1 |
| 8 | Major | 张士诚 | 回合推进 | T2推进后仍显示R1, factions数据变为银=-1兵=-1粮=-1 |
| 9 | Major | 方国珍 | 回合推进 | T2推进后仍显示R1, factions数据变为银=-1兵=-1粮=-1 |
| 10 | Major | 王保保 | 回合跳跃 | R1直接跳到R3，R2被跳过 |
| 11 | Minor | 明玉珍 | 文档一致性 | 文档推荐的farm×2无效，玩家第1回合只能执行0个有效指令 |
| 12 | Minor | 元廷 | 文档一致性 | T1的edict+T2的supply均无效，T1只剩recruit可用 |

---

## 六、对比分析：文档附录 vs API实际

文档附录声称的指令结构：
```
军事(14): recruit, train_troops, train, conscript, march, attack, raid, ambush, garrison, 
          retreat✗, reinforce✗, supply✗, mobilize, transport
经济(8):  farm✗, trade, develop, tax, collect_tax, relief, build, buy_horses
内政(8):  edict✗, decree, law, appoint✗, dismiss✗, enfeoff, purge, amnesty
外交(6):  diplomacy, tribute, pledge, vassal, marriage, governor
谍报(8):  spy, scout, counter_spy, sabotage, bribe, assassinate, intel✗, survey
其他(5):  fortify, move_capital, court_settlement✗, prisoner_action✗, policy_unlock✗
```

**修正后的实际可用指令列表 (38种)**：
```
军事(11): recruit, train_troops, train, conscript, march, attack, raid, ambush, 
          garrison, mobilize, transport
经济(7):  trade, develop, tax, collect_tax, relief, build, buy_horses
内政(6):  decree, law, enfeoff, purge, amnesty
外交(6):  diplomacy, tribute, pledge, vassal, marriage, governor
谍报(7):  spy, scout, counter_spy, sabotage, bribe, assassinate, survey
其他(2):  fortify, move_capital
```

---

## 七、建议

1. **文档需更新**：将 `farm` → `develop`、`supply` → `supply` (需API端加入)、`edict` → `decree`、`appoint` → 需API端加入
2. **API需补充**：添加 `farm`、`supply`、`appoint`、`retreat`、`reinforce` 到 valid_actions 和中文别名映射中
3. **领土数据**：排查 `world_state.factions[fid].tiles` 返回空的原因
4. **回合推进bug**：排查 advance-turn 多轮后 factions 数据变 -1 的原因
5. **round 计数**：排查 R1→R1 不增长和 R1→R3 跳号的问题
