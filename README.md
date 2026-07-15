# 元末逐鹿 3.0 · 完整游戏设计方案

## 一、游戏总览

| 项目 | 内容 |
|------|------|
| **类型** | 回合制国风策略推演 · CloudAgent 多智能体全涌现式 |
| **背景** | 至正十一年(1351)，红巾起义，群雄逐鹿 |
| **势力** | 9大势力(元廷/徐寿辉/朱元璋/陈友谅/张士诚/明玉珍/方国珍/王保保/漠北诸部) |
| **回合** | 月令制，12回合/年，上限240回合(20年) |
| **地图** | 32×42 Flat-Top六边形网格，1328个地块 |
| **模式** | player_turn(玩家决策) / ai_watch(AI旁观)双模式 |

## 二、技术架构

### 后端 (Python/FastAPI)
```
server/
├── api_server.py          # FastAPI 主应用，200+ API端点
├── models/                # Pydantic 数据模型
│   ├── world_state.py     # WorldState 类型化核心（替代单一大dict）
│   ├── requests.py        # API请求模型
│   └── events.py          # 游戏事件模型
├── core/                  # 核心引擎
│   └── round_engine.py    # 回合生命周期管理器（8阶段）
└── config/                # 配置
    ├── factions.json      # 九大势力配置
    └── game_const.yaml    # 11领域游戏常量
```

### 前端 (Vue 3 + TypeScript + Pinia)
```
frontend/
├── src/
│   ├── pages/             # 页面组件
│   │   ├── HomePage.vue       # 首页（古绢卷轴风格）
│   │   ├── FactionSelectPage.vue  # 势力选择
│   │   ├── GamePage.vue        # 游戏主界面
│   │   └── SaveManagerPage.vue # 存档管理
│   ├── stores/
│   │   └── gameStore.ts        # Pinia 全局状态管理
│   ├── services/
│   │   └── api.ts              # API 客户端
│   ├── types/
│   │   └── index.ts            # TypeScript 类型定义
│   ├── styles/
│   │   └── main.css            # 全局样式（古绢国风）
│   ├── router/index.ts
│   ├── App.vue
│   └── main.ts
└── package.json
```

## 三、启动方式

### 后端
```bash
pip install -r server/requirements.txt
python server.py
# API 服务启动于 http://127.0.0.1:8800
# API 文档 http://127.0.0.1:8800/docs
```

### 前端
```bash
cd frontend
npm install
npm run dev
# 开发服务器启动于 http://localhost:3000
```

## 四、3.0 重构要点

| 层级 | 当前状态 | 3.0实现 |
|------|---------|---------|
| 数据层 | `global_world_state` 单一大dict | ✅ 类型化 WorldState Pydantic模型 |
| 业务层 | 84个散落工具函数 | ✅ 14个领域服务模块 |
| API层 | 66+端点散落 | ✅ 统一Router + Pydantic校验（200+端点） |
| 前端 | Vanilla JS + Vue3混合 | ✅ Vue3 + TypeScript + Pinia |
| 回合引擎 | 混杂在api_server | ✅ RoundEngine 8阶段生命周期 |

## 五、开发计划

- [x] 项目骨架搭建（配置、模型、引擎）
- [x] 前端Vue3完整组件树
- [x] 14领域服务模块实现
- [x] 84个游戏工具实现
- [x] AI Agent系统接入（8大智能体全部完成）
- [x] 六边形地图Canvas渲染 (Konva多层系统)
- [x] 存档系统（API端点已修复闭环）
- [x] 结局判定系统
