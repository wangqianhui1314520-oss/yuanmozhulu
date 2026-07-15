/**
 * Inkarnate + AI 分层地图制作完整手册
 * 
 * 本手册涵盖三个核心流程：
 *   1. 将地图书导出的透明地形底图导入 Inkarnate，绘制宣纸纹理+手绘山川
 *   2. 使用 AI 生成两套全景插画（全局沙盘 + 行省特写）
 *   3. 输出分层 PNG 到项目中，前端通过 MapLayerPanel 独立开关
 * 
 * 输出文件清单（共10张PNG）：
 *   public/data/map/
 *   ├── terrain_base.png              ← 地图书导出，透明地形底图
 *   ├── inkarnate_parchment.png       ← Inkarnate：宣纸底纹
 *   ├── inkarnate_mountains.png       ← Inkarnate：手绘山川
 *   ├── inkarnate_decorations.png     ← Inkarnate：装饰贴图
 *   ├── ai_panorama_global.png        ← AI：全局沙盘全景
 *   ├── ai_province_zhongshu.png      ← AI：中书省特写
 *   ├── ai_province_henanjiang.png    ← AI：河南江北特写
 *   ├── ai_province_jiangzhe.png      ← AI：江浙特写
 *   ├── ai_province_huguang.png       ← AI：湖广特写
 *   ├── ai_province_sichuan.png       ← AI：四川特写
 *   └── ai_province_jiangxi.png       ← AI：江西特写
 */

========================================================================
第一部分：Inkarnate 操作流程
========================================================================

1.1 准备工作
-----------
- 订阅 Inkarnate Pro（$14.99/月），支持自定义素材导入 + 8K导出 + 商业使用
- 准备地图书导出的透明 PNG 底图（terrain_base.png，2800x2200）
- 下载元代行省参考图（OSGeo: https://www.osgeo.cn/map/m056c/）

1.2 创建新地图项目
------------------
1. 登录 inkarnate.com → My Maps → New Map
2. 选择 "Fantasy World" 模板 → 4K 分辨率
3. 画布设置：Resize → 自定义 2800 x 2200（匹配 terrain_base.png）
4. 地图类型选 "Parchment World"（羊皮纸世界）

1.3 导入地形底图作为描摹参考
---------------------------
1. Art Manager（素材管理器）→ Assets 折叠区 → 点击 "+"
2. 选择 "Stamp"（图章）类型
3. 上传 terrain_base.png
4. 回到编辑器，在 Object 图层放置此图章，缩放覆盖整个画布
5. 降低该图章透明度至 30%，作为底层描摹参考

1.4 绘制宣纸沙盘纹理（inkarnate_parchment.png）
------------------------------------------------
目标：生成古旧绢本质感的宣纸底纹层

步骤：
a) Background 笔刷层：
   - 使用 Parchment / Aged Paper 纹理笔刷铺满全图
   - 边缘用 Dark Parchment 纹理制造褪色暗角效果
   - 用低透明度（10-15%）的 Brown 纹理在纸张折痕位置轻扫

b) Foreground 笔刷层：
   - 使用 Sand / Light Dirt 纹理在华北平原区域轻涂
   - 使用 Dark Grass 在江南水网区轻涂
   - 使用 Mountain Rock 在西部高原轻涂

c) 遮罩（Mask Tool）：
   - 在海岸线边缘用 Mask Tool 露出 Background 的深色纸边
   - 模拟古地图的海岸线晕染效果

d) 导出：
   - 隐藏所有 Object 图层（印章）
   - 仅保留 Background + Foreground 笔刷层
   - 文件 → Export → PNG，8K 分辨率
   - 保存为 inkarnate_parchment.png

1.5 绘制手绘山川纹理（inkarnate_mountains.png）
------------------------------------------------
目标：Inkarnate 手绘山脉、丘陵、河流、森林等装饰元素

步骤：
a) 新建 Object 图层，命名为 "Mountains & Rivers"

b) 山脉绘制：
   - 使用 Inkarnate Fantasy World 印章集中的 Mountain 印章
   - 沿太行山脉（山西-河北边界）排列 Mountain Range 印章链
   - 秦岭（陕西南部）用 Dark Mountain 印章
   - 南岭（江西-广东边界）用 Hill 印章（较矮）
   - 横断山脉（云南西部）用密集的 High Mountain 印章

c) 河流绘制：
   - 使用 Line Tool → 选 "River" 笔触样式
   - 黄河：从河套 → 潼关 → 开封 → 山东入海，画粗线
   - 长江：从巴蜀 → 三峡 → 武昌 → 应天入海，画粗线
   - 淮河、汉水、湘江、赣江：细线
   - 京杭大运河：虚线样式

d) 森林/植被：
   - 江南丘陵用 Tree Cluster 印章点缀
   - 巴蜀盆地用 Dense Forest 印章
   - 漠北草原用 Grass 印章稀疏点缀

e) 沙漠/戈壁：
   - 塔克拉玛干（西域）用 Sand Dune 印章
   - 蒙古戈壁用 Rocky Desert 印章

f) 导出：
   - 仅显示 "Mountains & Rivers" 图层
   - 隐藏笔刷层和底图参考
   - 文件 → Export → PNG（透明背景）
   - 保存为 inkarnate_mountains.png

1.6 绘制装饰贴图（inkarnate_decorations.png）
----------------------------------------------
目标：城池图标、军旗、龙纹、卷轴边框等装饰性元素

步骤：
a) 新建 Object 图层 "Decorations"

b) 城池标记：
   - 使用 Inkarnate 的 City / Castle / Tower 印章
   - 大都（北京）放最大最华丽的 Castle 印章
   - 各路治所放中型 City 印章
   - 关隘（潼关、居庸关、山海关）放 Fortress 印章

c) 装饰元素：
   - 四角放置卷轴边框装饰（需先导入自定义边框 PNG 素材）
   - 上方中央放置"元末逐鹿"龙纹匾额（自定义素材）
   - 地图左下角放置指北针+比例尺（Inkarnate内置印章）

d) 导出：
   - 仅显示 "Decorations" 图层
   - 导出为透明 PNG
   - 保存为 inkarnate_decorations.png

1.7 关键技巧
-----------
- 分层导出：每个图层单独导出透明PNG，不要合并
- 笔刷层扁平化：导出前将不编辑的印章 Flatten 到笔刷层（提高性能+避免印章丢失）
- 透明度控制：导出的PNG自带透明度，前端可叠加 opacity CSS 控制
- 混合模式：前端用 CSS mix-blend-mode 控制叠加效果


========================================================================
第二部分：AI 全景插画生成流程
========================================================================

2.1 工具选择
-----------
推荐方案（按优先级）：

方案A：ComfyUI + LayerDiffuse（本地/云端GPU）
  - 优点：分层生成、精细控制、可批量
  - 节点：ComfyUI-layerdiffuse（透明背景输出）
  - 模型：国风水墨 LoRA + ControlNet（Canny/Depth）

方案B：Midjourney + 后期分层
  - 优点：出图质量极高、古风理解好
  - 缺点：不支持直接分层输出，需后期抠图

方案C：Stable Diffusion WebUI + ControlNet
  - 优点：免费、可控
  - 模型推荐：GuoFeng3 / 墨心 / 三馅馄饨国风水墨

2.2 全局沙盘全景（ai_panorama_global.png）
-------------------------------------------
目标：一张古风水墨风格的元末势力分布全景俯视图

Prompt 模板（中文）：
"""
俯视视角，古风水墨风格，元代至正年间中国疆域全景地图。
宣纸底色，水墨晕染，淡彩。
标注元顺帝（大都）、朱元璋（应天）、陈友谅（武昌）、
张士诚（苏州）、王保保（汴梁）、明玉珍（重庆）六大势力范围。
北方蒙古高原用枯笔皴擦，中原用淡墨晕染，江南用水墨点染。
黄河长江蜿蜒贯穿，太行秦岭横亘。
无文字标注，纯绘画风格，绢本质感，轻微旧化做旧。
画幅比例 4:3，全景俯视。
"""

ComfyUI 工作流要点：
1. Load Checkpoint: GuoFeng3 或 墨心模型
2. Load LoRA: 国风水墨 LoRA（权重0.7-0.8）
3. CLIP Text Encode (正向): 上述 prompt
4. CLIP Text Encode (负向): "现代建筑, 文字, 标签, 照片, 3D渲染, 西方风格"
5. Empty Latent: 1400x1050（或 2800x2100 高分辨率）
6. KSampler: steps 30, CFG 7, sampler DPM++ 2M
7. LayerDiffuse Decode: 输出带透明通道的 RGBA PNG
8. 导出为 ai_panorama_global.png（2800x2100）

ControlNet 增强（可选）：
- 将 inkarnate_mountains.png 转灰度后作为 Canny 输入
- ControlNet Weight: 0.4-0.5（不要过强，保留AI创作空间）

2.3 行省特写图（ai_province_*.png）
-------------------------------------
目标：六张行省级别的特写插画，每张聚焦一个行省的地理特征

通用 Prompt 模板：
"""
俯视视角，古风水墨风格，[行省名]地理特写。
[地理特征描述]。淡墨晕染，局部浓墨点缀。
绢本质感，轻微旧化，无文字标注。
画幅 3:2，区域特写。
"""

各行省 Prompt：

【中书省 - ai_province_zhongshu.png】
"""
俯视视角，古风水墨风格，元大都及中书省腹地特写。
华北平原广袤，太行山脉西侧屏障，燕山北面拱卫。
大都城（北京）居画面中央偏上，永定河环绕。
黄土色调，枯笔皴擦表现平原，浓墨点染太行。
"""

【河南江北 - ai_province_henanjiang.png】
"""
俯视视角，古风水墨风格，河南江北行省中原腹地特写。
黄河蜿蜒横贯，开封（汴梁）居中，洛阳在西。
黄淮平原广阔，大别山南缘。
黄土色主调，黄河用淡赭石晕染。
"""

【江浙 - ai_province_jiangzhe.png】
"""
俯视视角，古风水墨风格，江浙行省江南水乡特写。
太湖居中，杭州（临安）在画面下方，应天（南京）在左上方。
水网密布，长江下游横贯，江南丘陵起伏。
青绿淡彩，水墨淋漓，湿润感。
"""

【湖广 - ai_province_huguang.png】
"""
俯视视角，古风水墨风格，湖广行省荆楚大地特写。
长江中游横贯，武昌（武汉）居中，洞庭湖在左。
江汉平原广袤，幕阜山南缘，武陵山西侧。
水墨晕染，江湖水汽蒸腾感。
"""

【四川 - ai_province_sichuan.png】
"""
俯视视角，古风水墨风格，四川行省巴蜀盆地特写。
成都平原居中，重庆（夔州）在右下，长江三峡贯穿。
四面环山（秦岭、大巴山、横断山），盆地内沃野千里。
淡墨晕染盆地，浓墨皴擦四围山脉。
"""

【江西 - ai_province_jiangxi.png】
"""
俯视视角，古风水墨风格，江西行省鄱阳湖区特写。
鄱阳湖居中偏上，南昌（龙兴）在湖西南。
赣江纵贯南北，武夷山东缘，南岭南下。
青绿淡彩，湖光山色，水汽氤氲。
"""

2.4 分层输出要求
----------------
每张AI生成的插画必须满足：
- 输出格式：PNG（RGBA，含透明通道）
- 分辨率：2800x2200（全局），2000x1500（特写）
- 透明区域：行省特写图中，非目标行省区域保持透明
- 风格统一：所有插画使用相同的模型+LoRA组合
- 色彩调性：与 inkarnate_parchment.png 的暖黄宣纸色协调

推荐使用 ComfyUI LayerDiffuse 的 Foreground Only 模式：
- 只生成前景内容
- 背景自动透明
- 前端叠加时自然融入宣纸底色


========================================================================
第三部分：前端分层渲染系统
========================================================================

3.1 架构概览
-----------
layers_config.json          ← 图层配置（可见性/透明度/z序/混合模式）
     ↓
mapLayerManager.ts          ← 图层管理单例（加载/切换/订阅）
     ↓
RegionMap.vue               ← SVG渲染（分层PNG + 矢量边界 + 交互）
     ↓
MapLayerPanel.vue           ← UI控制面板（右侧浮动面板，开关各层）

3.2 图层渲染顺序（zIndex 从低到高）
----------------------------------
z=0  terrain_base.png           地形底图（地图书导出）
z=1  inkarnate_parchment.png    宣纸沙盘纹理（multiply混合）
z=2  inkarnate_mountains.png    手绘山川装饰
z=3  ai_panorama_global.png     AI全局沙盘全景（overlay混合）
z=4  ai_province_*.png          AI行省特写（overlay混合，默认隐藏）
z=5  inkarnate_decorations.png  装饰贴图层
     ↓ 以上为PNG层，以下为SVG矢量层 ↓
     行省底色（SVG polygon）   势力着色
     路底色                    二级区域着色
     行省边界（SVG path）      粗线
     路边界                    细线
     势力边界                  彩色粗线
     单元格交互区              点击热区
     标签文字                  地名标注

3.3 图层控制面板操作
-------------------
- 点击右上角 "舆图层" 面板 → 勾选/取消各层
- 拖动透明度滑块 → 实时调整每层叠加强度
- 组开关：地形/Inkarnate/AI全景/AI特写 四组独立控制
- 默认状态：AI特写组关闭，其余开启

3.4 文件部署
-----------
将所有PNG放入 frontend/public/data/map/ 目录：
- 文件名必须与 layers_config.json 中的 file 字段一致
- PNG 建议用 TinyPNG 压缩（保持透明通道）
- 总大小预计：10张PNG × ~300KB = ~3MB（可接受）


========================================================================
附录：快速检查清单
========================================================================

□ 地图书导出 terrain_base.png（2800x2200, 透明）
□ Inkarnate 订阅 Pro 版
□ Inkarnate 完成 4 层绘制并分别导出
□ ComfyUI 安装 layerdiffuse 插件 + 国风 LoRA
□ AI 生成 1 张全局全景 + 6 张行省特写
□ 所有 PNG 放入 public/data/map/
□ 确认文件名与 layers_config.json 一致
□ 前端构建成功，无 linter 错误
□ 打开游戏，图层面板可正常切换
□ 各层独立开关 + 透明度调节正常工作
