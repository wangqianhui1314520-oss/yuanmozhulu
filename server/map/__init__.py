"""
地图模块 v4.2 - 文明6风格X轴奇数交错六边形地图引擎 (按沙盘地图系统文档 v3.0 重构)

核心特性:
- Stagger Axis = X, Stagger Index = Odd (奇数行偏移)
- Flat-Top 六边形, hex_size = 72px
- 约499 个府州级单格 = 东亚全域 (含朝鲜/日本/琉球台湾/中南半岛北部)
- 三级行政层级: 行省(10+) → 路 → 府州
- 双坐标系: Offset(col,row) 主存储 + Axial(q,r) 内部计算
- 六向邻接 / A*寻路 / BFS补给连通检测
- 九大势力按行省路网 BFS 竞争分配初始疆域
- 14 层渲染管线 (宣纸纹理 → UI叠加层)
- 9 个海域分区支持海军移动/贸易航线/登陆作战

模块:
- hex_grid.py          : 六边形网格核心 - 32行×42列, 72px
- adjacency.py         : 六向邻接表生成
- admin_hierarchy.py   : 三级行政层级 (14省)
- terrain_generator.py : 11种地形 + 9河流 + 10湖泊
- territory_mask.py    : 21顶点疆域遮罩 (Ray-Casting)
- faction_territory.py : 9大势力领地 BFS 竞争分配
- special_markers.py   : 首都/港口/关隘/渡口/战略据点
- boundary_generator.py: 行省界 + 路界 + 势力边界
- tile_generator.py    : 标准化全量地块导出
- sea_generator.py     : 海域分区与水深分级 (9海域)
- layer_config.py      : 14层渲染管线 + 三级缩放配置
- pathfinding.py       : A*寻路 + 补给连通检测
- generate_map.py      : 9步离线生成流水线主控
"""
