/**
 * 地图图层系统完整配置 v1.0
 *
 * 14大独立图层，分5大类：
 * - 基底图层：网格、地形
 * - 势力疆域：势力、边界、迷雾、标记
 * - 军事行动：行军路线、补给线、兵力驻防
 * - 内政建设：城建建筑、灾害动乱
 * - 外交法理：外交附庸、法理宣称、水域航道
 *
 * 所有图层支持：
 * - 独立显隐一键切换
 * - 透明度调节 (0.0 - 1.0)
 * - 层级上下排布渲染
 * - 缩放远近自动精简（zoomMin/zoomMax）
 * - 锁定/淡化
 */

export interface LayerDef {
  id: string
  name: string
  nameShort: string
  category: 'base' | 'territory' | 'military' | 'civil' | 'diplomacy'
  icon: string
  visible: boolean
  opacity: number
  zIndex: number
  locked: boolean
  faded: boolean
  /** 低于此缩放比例自动隐藏 (0 = 永显) */
  zoomMin: number
  /** 高于此缩放比例自动隐藏 (0 = 永显) */
  zoomMax: number
  /** 提示说明 */
  tooltip: string
}

export interface LayerCategoryDef {
  id: string
  name: string
  icon: string
}

export const LAYER_CATEGORIES: LayerCategoryDef[] = [
  { id: 'base', name: '基底图层', icon: '⊞' },
  { id: 'territory', name: '势力疆域', icon: '⚔' },
  { id: 'military', name: '军事行动', icon: '⚡' },
  { id: 'civil', name: '内政建设', icon: '🏛' },
  { id: 'diplomacy', name: '外交法理', icon: '📜' },
]

/** 全部14个图层默认配置 */
export const DEFAULT_LAYERS: LayerDef[] = [
  // ====== 基底图层 ======
  {
    id: 'hex_grid',
    name: '六边形网格',
    nameShort: '网格',
    category: 'base',
    icon: '#',
    visible: true,
    opacity: 1.0,
    zIndex: 0,
    locked: false,
    faded: false,
    zoomMin: 0,
    zoomMax: 0,
    tooltip: '六边形网格线图层，底层基底，可一键隐藏适配CK3不规则多边形地图',
  },
  {
    id: 'terrain',
    name: '地形底色',
    nameShort: '地形',
    category: 'base',
    icon: '🏔',
    visible: true,
    opacity: 1.0,
    zIndex: 1,
    locked: true,  // 地形不建议关闭，关闭后地图仅显示宣纸底色
    faded: false,
    zoomMin: 0,
    zoomMax: 0,
    tooltip: '细分平原/山地/关隘/近海，对应渲染通行损耗标识',
  },

  // ====== 势力疆域 ======
  {
    id: 'faction',
    name: '势力着色',
    nameShort: '势力',
    category: 'territory',
    icon: '⚔',
    visible: true,
    opacity: 0.72,
    zIndex: 10,
    locked: false,
    faded: false,
    zoomMin: 0,
    zoomMax: 0,
    tooltip: '实时跟随AI领土占领动态更新色块与旗帜',
  },
  {
    id: 'boundary',
    name: '边界描边',
    nameShort: '边界',
    category: 'territory',
    icon: '▦',
    visible: true,
    opacity: 1.0,
    zIndex: 15,
    locked: false,
    faded: false,
    zoomMin: 0,
    zoomMax: 0,
    tooltip: '三级描边：本国国境（金边）、同盟边境（绿边）、敌对阵线（红边）',
  },
  {
    id: 'fog',
    name: '战争迷雾',
    nameShort: '迷雾',
    category: 'territory',
    icon: '🌫',
    visible: true,
    opacity: 0.85,
    zIndex: 20,
    locked: false,
    faded: false,
    zoomMin: 0,
    zoomMax: 0,
    tooltip: '绑定谍报探索机制，未探查地块自动遮罩',
  },
  {
    id: 'markers',
    name: '战略标记',
    nameShort: '标记',
    category: 'territory',
    icon: '📍',
    visible: true,
    opacity: 1.0,
    zIndex: 18,
    locked: false,
    faded: false,
    zoomMin: 0,
    zoomMax: 0,
    tooltip: '都城★、港口◎、关隘▲、渡口〰等战略据点标记',
  },

  // ====== 军事行动 ======
  {
    id: 'march_route',
    name: '行军路线',
    nameShort: '行军',
    category: 'military',
    icon: '➤',
    visible: true,
    opacity: 0.85,
    zIndex: 30,
    locked: false,
    faded: false,
    zoomMin: 0.2,
    zoomMax: 0,
    tooltip: '己方与AI军团移动轨迹、行军箭头、路径动画',
  },
  {
    id: 'supply_line',
    name: '补给线',
    nameShort: '补给',
    category: 'military',
    icon: '⛓',
    visible: true,
    opacity: 0.70,
    zIndex: 29,
    locked: false,
    faded: false,
    zoomMin: 0.3,
    zoomMax: 0,
    tooltip: '补给线渲染、断粮路段高亮标记（红色虚线）',
  },
  {
    id: 'garrison',
    name: '兵力驻防',
    nameShort: '驻防',
    category: 'military',
    icon: '🛡',
    visible: true,
    opacity: 0.80,
    zIndex: 32,
    locked: false,
    faded: false,
    zoomMin: 0.35,
    zoomMax: 0,
    tooltip: '直观显示各方守军与远征军团数量（数字标注）',
  },

  // ====== 内政建设 ======
  {
    id: 'building',
    name: '城建建筑',
    nameShort: '城建',
    category: 'civil',
    icon: '🏯',
    visible: true,
    opacity: 0.80,
    zIndex: 25,
    locked: false,
    faded: false,
    zoomMin: 0.4,
    zoomMax: 0,
    tooltip: '工坊🔨、港口⚓、城防🏰等建筑图标',
  },
  {
    id: 'disaster',
    name: '灾害动乱',
    nameShort: '灾害',
    category: 'civil',
    icon: '⚠',
    visible: true,
    opacity: 0.85,
    zIndex: 26,
    locked: false,
    faded: false,
    zoomMin: 0.3,
    zoomMax: 0,
    tooltip: 'AI灾害叛乱智能体生成：流民🚶、灾荒🌾、暴动🔥标记',
  },

  // ====== 外交法理 ======
  {
    id: 'diplomacy_line',
    name: '外交附庸',
    nameShort: '附庸',
    category: 'diplomacy',
    icon: '🔗',
    visible: true,
    opacity: 0.75,
    zIndex: 35,
    locked: false,
    faded: false,
    zoomMin: 0.25,
    zoomMax: 0,
    tooltip: '宗主国与藩属势力从属连线（虚线方向箭头）',
  },
  {
    id: 'claim',
    name: '法理宣称',
    nameShort: '宣称',
    category: 'diplomacy',
    icon: '📜',
    visible: true,
    opacity: 0.65,
    zIndex: 23,
    locked: false,
    faded: false,
    zoomMin: 0.3,
    zoomMax: 0,
    tooltip: '高亮我方可合法宣战的故土地块（半透纹理覆盖）',
  },
  {
    id: 'waterway',
    name: '水域航道',
    nameShort: '航道',
    category: 'diplomacy',
    icon: '⛵',
    visible: true,
    opacity: 0.60,
    zIndex: 8,
    locked: false,
    faded: false,
    zoomMin: 0.2,
    zoomMax: 0,
    tooltip: '标注可通航河道与跨海港口（箭头线标注）',
  },
]

/** 快速预设定义 */
export interface LayerPreset {
  id: string
  name: string
  icon: string
  description: string
  layerVisibility: Record<string, boolean>
}

export const LAYER_PRESETS: LayerPreset[] = [
  {
    id: 'all',
    name: '全开',
    icon: '⊞',
    description: '所有图层全部显示',
    layerVisibility: Object.fromEntries(DEFAULT_LAYERS.map(l => [l.id, true])),
  },
  {
    id: 'terrain_only',
    name: '地形',
    icon: '🏔',
    description: '仅地形+网格，适合观察地理',
    layerVisibility: {
      hex_grid: true, terrain: true,
      faction: false, boundary: false, fog: false, markers: false,
      march_route: false, supply_line: false, garrison: false,
      building: false, disaster: false,
      diplomacy_line: false, claim: false, waterway: false,
    },
  },
  {
    id: 'military',
    name: '军事',
    icon: '⚡',
    description: '地形+势力+行军+驻防+补给线',
    layerVisibility: {
      hex_grid: true, terrain: true, faction: true, boundary: true,
      fog: false, markers: true,
      march_route: true, supply_line: true, garrison: true,
      building: false, disaster: false,
      diplomacy_line: false, claim: false, waterway: false,
    },
  },
  {
    id: 'diplomacy_view',
    name: '外交',
    icon: '📜',
    description: '势力+边界+外交附庸+法理宣称',
    layerVisibility: {
      hex_grid: false, terrain: true, faction: true, boundary: true,
      fog: false, markers: false,
      march_route: false, supply_line: false, garrison: false,
      building: false, disaster: false,
      diplomacy_line: true, claim: true, waterway: false,
    },
  },
  {
    id: 'civil',
    name: '内政',
    icon: '🏛',
    description: '城建+灾害+兵力驻防全开',
    layerVisibility: {
      hex_grid: false, terrain: true, faction: true, boundary: false,
      fog: false, markers: true,
      march_route: false, supply_line: false, garrison: true,
      building: true, disaster: true,
      diplomacy_line: false, claim: false, waterway: false,
    },
  },
  {
    id: 'clean',
    name: '纯净',
    icon: '◯',
    description: '最小化显示，仅地形+势力',
    layerVisibility: {
      hex_grid: false, terrain: true, faction: true,
      boundary: false, fog: false, markers: false,
      march_route: false, supply_line: false, garrison: false,
      building: false, disaster: false,
      diplomacy_line: false, claim: false, waterway: false,
    },
  },
]

/** 边界子模式 */
export type BoundaryMode = 'admin' | 'faction' | 'both'
