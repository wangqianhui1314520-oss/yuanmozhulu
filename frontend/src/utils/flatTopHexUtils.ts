/**
 * Flat-Top 六边形工具库 v4.1 - 府州级东亚全域
 *
 * v4.1 变更：
 * - 网格: 28×36 → 32×42 (奇数行41列)
 * - 六边形尺寸: 64px → 72px (府州级)
 * - 目标: 496 个有效格子
 * - 地理: 55°E~165°E, 0°N~60°N
 * - 行政层级: 三级 (行省/路/府州)
 */

// ---- 六边形尺寸 ----
export const BASE_HEX_SIZE = 72

/** 预计算常量，避免重复 Math.sqrt(3) 和 Math.PI */
const SQRT3 = Math.sqrt(3)
const DEG60_RAD = Math.PI / 3  // 60° in radians

/** 当前运行时六边形大小 */
export let HEX_SIZE = BASE_HEX_SIZE

/** HEX_SIZE 与基准比率 */
export let HEX_RATIO = 1.0

/** Flat-Top 六边形尺寸 (实时) */
export function getHexWidth(): number { return HEX_SIZE * 2 }
export function getHexHeight(): number { return HEX_SIZE * SQRT3 }
export let HEX_WIDTH = HEX_SIZE * 2
export let HEX_HEIGHT = HEX_SIZE * SQRT3

/** 重设 HEX_SIZE */
export function setHexSize(newSize: number): void {
  HEX_SIZE = newSize
  HEX_RATIO = newSize / BASE_HEX_SIZE
  HEX_WIDTH = newSize * 2
  HEX_HEIGHT = newSize * SQRT3
}

export function resetHexSize(): void { setHexSize(BASE_HEX_SIZE) }

// ---- 网格常量 v4.1 ----
/** 总行数 */
export const GRID_ROWS = 32
/** 偶数行最大列数 */
export const GRID_MAX_COLS = 42
/** 奇数行最大列数 */
export const GRID_ODD_COLS = 41
/** 最左列索引 */
export const GRID_MIN_COL = 0
/** 矩形网格总格数 */
export const TOTAL_TILES_RECT = 1328  // 16×42 + 16×41

// 地理映射
export const GEO_LON_MIN = 55
export const GEO_LON_MAX = 165
export const GEO_LAT_MIN = 0
export const GEO_LAT_MAX = 60

// ---- 类型 ----
export interface HexCoord {
  q: number
  r: number
}

export interface OffsetCoord {
  col: number
  row: number
}

export interface HexTile {
  hex_id: string
  tile_id: string
  tile_name: string
  col: number
  row: number
  q: number
  r: number
  pixel_x: number
  pixel_y: number
  neighbors: string[]
  terrain: string
  movement_cost: number
  move_cost: number
  defense_bonus: number
  attack_modifier: number
  is_coastal: boolean
  is_ferry: boolean
  combat_modifiers: Record<string, any>
  supply_yield: number
  // 三级行政归属
  province: string
  province_id: string
  circuit: string
  circuit_id: string
  prefecture: string
  prefecture_id: string
  // 势力
  faction_id: string | null
  faction_color: string | null
  // 特殊属性
  is_capital: boolean
  is_port: boolean
  is_pass: boolean
  is_strategic: boolean
  strategic_name: string | null
  strategic_note: string | null
  water_river: boolean
  water_lake: boolean
  // 海域属性 (v4.1)
  sea_zone?: string
  sea_depth?: string
  sea_zone_name?: string
  navy_modifier?: number
}

// ---- Flat-Top 六方向 (Axial) ----
export const FLAT_TOP_DIRECTIONS: [number, number][] = [
  [+1, 0],   // 右
  [+1, -1],  // 右上
  [0, -1],   // 左上
  [-1, 0],   // 左
  [-1, +1],  // 左下
  [0, +1],   // 右下
]

// ---- 坐标转换 ----

/** Offset → Axial (Flat-Top, odd-row stagger) */
export function offsetToAxial(col: number, row: number): HexCoord {
  const q = col - (row - (row & 1)) / 2
  return { q, r: row }
}

/** Axial → Offset */
export function axialToOffset(q: number, r: number): OffsetCoord {
  const col = q + (r - (r & 1)) / 2
  return { col, row: r }
}

/** Axial → 像素坐标（保留用于兼容） */
export function axialToPixel(q: number, r: number, size: number = HEX_SIZE): { x: number; y: number } {
  const x = size * (3 / 2 * q)
  const y = size * (SQRT3 / 2 * q + SQRT3 * r)
  return { x, y }
}

/** Offset(col,row) → 标准正向平铺像素坐标（无倾斜，Flat-Top 奇行右移半格） */
export function offsetToPixel(col: number, row: number, size: number = HEX_SIZE): { x: number; y: number } {
  const x = size * (1.5 * col + (row & 1) * 0.75)
  const y = size * SQRT3 * row
  return { x, y }
}

/** 像素 → Axial */
export function pixelToAxial(px: number, py: number, size: number = HEX_SIZE): HexCoord {
  const q = (2 / 3 * px) / size
  const r = (-1 / 3 * px + SQRT3 / 3 * py) / size
  return hexRound({ q, r })
}

/** 像素 → Offset（近邻搜索，匹配 offsetToPixel 逆向） */
export function pixelToOffset(px: number, py: number, size: number = HEX_SIZE): OffsetCoord {
  const rowApprox = Math.max(0, Math.round(py / (size * SQRT3)))
  let bestCol = 0, bestRow = 0, bestDist = Infinity
  for (let dr = -2; dr <= 2; dr++) {
    const r = rowApprox + dr
    if (r < 0) continue
    const colApprox = Math.round((px - (r & 1) * size * 0.75) / (size * 1.5))
    for (let dc = -2; dc <= 2; dc++) {
      const c = colApprox + dc
      if (c < 0) continue
      const center = offsetToPixel(c, r, size)
      const dist = (px - center.x) ** 2 + (py - center.y) ** 2
      if (dist < bestDist) { bestDist = dist; bestCol = c; bestRow = r }
    }
  }
  return { col: bestCol, row: bestRow }
}

/** 六边形取整 */
export function hexRound(h: HexCoord): HexCoord {
  let q = Math.round(h.q)
  let r = Math.round(h.r)
  const s = -q - r
  const sq = Math.round(s)

  const qDiff = Math.abs(q - h.q)
  const rDiff = Math.abs(r - h.r)
  const sDiff = Math.abs(sq - s)

  if (qDiff > rDiff && qDiff > sDiff) {
    q = -r - sq
  } else if (rDiff > sDiff) {
    r = -q - sq
  }
  return { q, r }
}

/** Flat-Top 六边形6个顶点（使用预计算角度，避免重复 trig） */
const HEX_ANGLES = [0, 1, 2, 3, 4, 5].map(i => DEG60_RAD * i)
const HEX_COS = HEX_ANGLES.map(Math.cos)
const HEX_SIN = HEX_ANGLES.map(Math.sin)

export function hexCornersFlat(cx: number, cy: number, size: number = HEX_SIZE): { x: number; y: number }[] {
  const corners: { x: number; y: number }[] = []
  for (let i = 0; i < 6; i++) {
    corners.push({
      x: cx + size * HEX_COS[i],
      y: cy + size * HEX_SIN[i],
    })
  }
  return corners
}

/** 六边形曼哈顿距离 */
export function hexDistance(a: HexCoord, b: HexCoord): number {
  return (Math.abs(a.q - b.q) + Math.abs(a.r - b.r) +
          Math.abs(a.q + a.r - b.q - b.r)) / 2
}

/** 邻居计算 */
export function hexNeighbors(q: number, r: number): HexCoord[] {
  return FLAT_TOP_DIRECTIONS.map(([dq, dr]) => ({ q: q + dq, r: r + dr }))
}

/** 解析 tile_id "col,row" */
export function parseTileId(id: string): OffsetCoord {
  const [col, row] = id.split(',').map(Number)
  return { col, row }
}

export function makeTileId(col: number, row: number): string {
  return `${col},${row}`
}

// ---- 颜色映射 ----

// ---- 古卷水墨国风配色 v5.0 ----
// 传统中国画颜料色系: 低饱和、暗调、半透明叠加

/**
 * 九大势力低饱和水墨色 v8.0 — 国画晕染效果
 * 按元末历史实情：元廷衰败暗红、红巾军淡朱砂、朱元璋墨朱、陈友谅靛青、
 * 张士诚暗琥珀、方国珍海青灰、王保保淡紫檀、明玉珍暗巴蜀金、漠北草灰绿
 */
export const FACTION_COLORS: Record<string, string> = {
  faction_yuan:          '#9B4A3A',  // 暗赭红 — 衰败的蒙古帝国
  faction_xushouhui:     '#C47060',  // 淡朱砂 — 红巾军标志（天完政权）
  faction_zhuyuanzhang:  '#B85050',  // 墨朱 — 朱元璋，"朱"即红
  faction_chenyouliang:  '#4A6A8A',  // 靛青 — 鄱阳湖水战，大汉政权
  faction_zhangshicheng: '#B89850',  // 暗琥珀 — 盐商起家的大周
  faction_fangguozhen:   '#3A7888',  // 海青灰 — 海上枭雄，浙东割据
  faction_wangbaobao:    '#6A5888',  // 淡紫檀 — 蒙古贵胄，元末最后名将
  faction_mingyuzhen:    '#A88848',  // 暗巴蜀金 — 四川大夏政权
  faction_mobei:         '#6A7A5A',  // 草灰绿 — 草原游牧诸部
}

export const FACTION_NAMES: Record<string, string> = {
  faction_yuan:          '元廷',
  faction_xushouhui:     '徐寿辉',
  faction_zhuyuanzhang:  '朱元璋',
  faction_chenyouliang:  '陈友谅',
  faction_zhangshicheng: '张士诚',
  faction_fangguozhen:   '方国珍',
  faction_wangbaobao:    '王保保',
  faction_mingyuzhen:    '明玉珍',
  faction_mobei:         '漠北诸部',
}

// ---- 国画晕染地貌配色 ----
// 以传统山水画颜料为基调: 赭石、花青、藤黄、墨色
// 全部压低饱和度, 融入宣纸暗调基底

export const TERRAIN_COLORS: Record<string, string> = {
  flatland: '#a09070',    // 淡赭 (浅赭石染, 平原沃土)
  mountain: '#6b727a',    // 墨青 (远山淡墨, 山峦叠嶂)
  hill: '#8a7a62',        // 赭褐 (丘陵坡地, 赭石皴染)
  forest: '#3a4a3a',      // 墨绿 (松林积墨, 暗绿晕染)
  wetland: '#5a6a5a',     // 青灰 (湿地沼泽, 花青淡染)
  desert: '#9a8a72',      // 土黄 (荒漠戈壁, 赭黄铺陈)
  coastal: '#7a8a82',     // 淡青灰 (海岸滩涂, 水墨浅绛)
  steppe: '#8a9272',      // 草黄 (草原牧场, 藤黄淡染)
  taiga: '#4a5242',       // 深墨绿 (冻土针林, 浓墨重染)
  oasis: '#6a8a62',       // 青绿 (绿洲水源, 石绿点染)
  water_river: '#5a788a', // 花青 (江河, 花青渲染)
  water_lake: '#4a6880',  // 深花青 (湖泊, 浓花青)
  sea: '#3a5870',         // 深海蓝灰 (海洋, 水墨晕染)
  unknown: '#6a625a',     // 淡墨 (未知, 水墨底色)
}

// 海域按深度分色
export const SEA_DEPTH_COLORS: Record<string, string> = {
  shallow: '#4a6878',
  moderate: '#3a5870',
  deep: '#325268',
  abyssal: '#1a3040',
}

// ---- 疆域包围盒 ----

export interface TerritoryBounds {
  minCol: number; maxCol: number
  minRow: number; maxRow: number
  pixelW: number; pixelH: number
}

/** 遍历全部地块，用标准轴向公式 (offsetToAxial + axialToPixel) 算出精确像素包围盒 */
export function calculateTerritoryBounds(
  tiles: Array<{ col: number; row: number }>,
  hexSize: number = HEX_SIZE,
): TerritoryBounds {
  let minCol = Infinity, maxCol = -Infinity
  let minRow = Infinity, maxRow = -Infinity
  let minX = Infinity, maxX = -Infinity
  let minY = Infinity, maxY = -Infinity

  for (const t of tiles) {
    if (t.col < minCol) minCol = t.col
    if (t.col > maxCol) maxCol = t.col
    if (t.row < minRow) minRow = t.row
    if (t.row > maxRow) maxRow = t.row
    const axial = offsetToAxial(t.col, t.row)
    const p = axialToPixel(axial.q, axial.r, hexSize)
    if (p.x < minX) minX = p.x
    if (p.x > maxX) maxX = p.x
    if (p.y < minY) minY = p.y
    if (p.y > maxY) maxY = p.y
  }

  const pixelW = maxX - minX + hexSize * 2
  const pixelH = maxY - minY + hexSize * SQRT3

  return { minCol, maxCol, minRow, maxRow, pixelW, pixelH }
}

/** 包围盒像素原点（用轴向公式取 minCol/minRow 的中心再偏移） */
export function getTerritoryOrigin(bounds: TerritoryBounds, hexSize: number = HEX_SIZE): { x: number; y: number } {
  const axial = offsetToAxial(bounds.minCol, bounds.minRow)
  const center = axialToPixel(axial.q, axial.r, hexSize)
  return {
    x: center.x - hexSize * 0.75,
    y: center.y - hexSize * SQRT3 / 2,
  }
}
