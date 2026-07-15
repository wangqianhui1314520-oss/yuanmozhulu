"""
地图模块 v4.1 - 文明6风格X轴奇数交错六边形地图引擎

核心特性:
- Stagger Axis = X, Stagger Index = Odd (奇数行偏移)
- Flat-Top 六边形, hex_size = 72px
- 496 个府州级单格 = 东亚全域 (含朝鲜/日本/琉球台湾/中南半岛北部)
- 三级行政层级: 行省 → 路 → 府州 (可折叠展开)
- 坐标转换 / 六向邻接 / A*寻路 / 补给连通检测
- 九大势力按行省路网划分初始疆域

模块:
- hex_grid.py          : 六边形网格核心 - 32行×42列, 72px
- adjacency.py         : 六向邻接表生成
- admin_hierarchy.py   : 三级行政层级系统
- tile_generator.py    : 标准化地块JSON生成
- faction_territory.py : 势力初始领地 (府州级整块分配)
- boundary_generator.py: 两级行政边界 + 势力边界
- territory_mask.py    : 东亚全域疆域遮罩
- special_markers.py   : 特殊标记 (首都/港口/关隘/渡口)
- pathfinding.py       : A*寻路 + 连通性检测
- layer_config.py      : 三级缩放图层配置
- generate_map.py      : 主入口 - 一键生成全部产物
"""
