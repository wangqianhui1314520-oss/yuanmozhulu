/**
 * 六边形网格工具函数
 * 采用 Pointy-Top 尖顶六边形 Axial 轴向坐标体系
 * 与后端寻路算法坐标完全对齐
 *
 * 后端使用 Axial 坐标系 (q=col, r=row)
 * 六方向: [(+1,0), (+1,-1), (0,-1), (-1,0), (-1,+1), (0,+1)]
 */

export interface HexCoord {
  q: number
  r: number
}

export interface HexTile {
  tile_id: string
  tile_name: string
  tile_type: string
  region: string
  faction_id: string
  population: number
  troops: number
  grain: number
  morale: number
  treasury: number
  refugee_ratio: number
  water_works: number
  granary: number
  clinic: number
  fortification: number
  siege_state: string | null
  garrison_resting: boolean
  elite_ratio: number
  stable: number
  armory: number
  disasters: string[]
  is_capital: boolean
  is_port: boolean
  special_effect: string | null
  q: number
  r: number
}

/**
 * Pointy-Top 六边形的6个邻居方向（Axial坐标系）
 * 与后端 settle_engine.py _HEX_DIRECTIONS 完全一致
 */
export const HEX_DIRECTIONS: HexCoord[] = [
  { q: +1, r: 0 },  // 右
  { q: +1, r: -1 }, // 右上
  { q: 0, r: -1 },  // 左上
  { q: -1, r: 0 },  // 左
  { q: -1, r: +1 }, // 左下
  { q: 0, r: +1 },  // 右下
]

/** 六边形外接圆半径 */
export const HEX_SIZE = 20

/** 六边形宽度（水平方向，Pointy-Top 为 sqrt(3)*size） */
export const HEX_WIDTH = HEX_SIZE * Math.sqrt(3)

/** 六边形高度（垂直方向，Pointy-Top 为 2*size） */
export const HEX_HEIGHT = HEX_SIZE * 2

/**
 * Axial 坐标 → 像素坐标（Pointy-Top 标准公式）
 * x = size * (sqrt(3)*q + sqrt(3)/2*r)
 * y = size * (3/2 * r)
 */
export function hexToPixel(q: number, r: number): { x: number; y: number } {
  const x = HEX_SIZE * (Math.sqrt(3) * q + (Math.sqrt(3) / 2) * r)
  const y = HEX_SIZE * (3 / 2) * r
  return { x, y }
}

/**
 * 像素坐标 → Axial 坐标（Pointy-Top 逆变换）
 */
export function pixelToHex(px: number, py: number): HexCoord {
  const q = (Math.sqrt(3) / 3 * px - 1 / 3 * py) / HEX_SIZE
  const r = (2 / 3 * py) / HEX_SIZE
  return hexRound(q, r)
}

/** Axial 坐标圆整 */
export function hexRound(q: number, r: number): HexCoord {
  const s = -q - r
  let rq = Math.round(q)
  let rr = Math.round(r)
  let rs = Math.round(s)

  const dq = Math.abs(rq - q)
  const dr = Math.abs(rr - r)
  const ds = Math.abs(rs - s)

  if (dq > dr && dq > ds) {
    rq = -rr - rs
  } else if (dr > ds) {
    rr = -rq - rs
  }
  return { q: rq, r: rr }
}

/**
 * 计算 Pointy-Top 六边形6个顶点像素坐标
 * 从正右方开始（角度0），逆时针
 */
export function hexCorners(cx: number, cy: number, size: number = HEX_SIZE): { x: number; y: number }[] {
  const corners: { x: number; y: number }[] = []
  for (let i = 0; i < 6; i++) {
    const angleDeg = 60 * i - 30 // Pointy-Top: 顶点从30度偏移开始
    const angleRad = (Math.PI / 180) * angleDeg
    corners.push({
      x: cx + size * Math.cos(angleRad),
      y: cy + size * Math.sin(angleRad),
    })
  }
  return corners
}

/** 获取六边形邻居坐标 */
export function hexNeighbors(q: number, r: number): HexCoord[] {
  return HEX_DIRECTIONS.map(d => ({ q: q + d.q, r: r + d.r }))
}

/** 六边形距离（Axial） */
export function hexDistance(a: HexCoord, b: HexCoord): number {
  const dq = a.q - b.q
  const dr = a.r - b.r
  const ds = -dq - dr
  return (Math.abs(dq) + Math.abs(dr) + Math.abs(ds)) / 2
}

/** 获取环形范围内的六边形 */
export function hexRing(center: HexCoord, radius: number): HexCoord[] {
  const results: HexCoord[] = []
  if (radius === 0) return [{ q: center.q, r: center.r }]
  let hex = {
    q: center.q + HEX_DIRECTIONS[4].q * radius,
    r: center.r + HEX_DIRECTIONS[4].r * radius,
  }
  for (let i = 0; i < 6; i++) {
    for (let j = 0; j < radius; j++) {
      results.push({ ...hex })
      hex = { q: hex.q + HEX_DIRECTIONS[i].q, r: hex.r + HEX_DIRECTIONS[i].r }
    }
  }
  return results
}

/** 获取圆形范围内的所有六边形 */
export function hexSpiral(center: HexCoord, radius: number): HexCoord[] {
  const results: HexCoord[] = []
  for (let k = 0; k <= radius; k++) {
    results.push(...hexRing(center, k))
  }
  return results
}

/** A* 寻路（六边形网格，与后端 _a_star_pathfind 对齐） */
export function hexPathfind(
  start: HexCoord,
  end: HexCoord,
  blocked: Set<string>,
  maxSteps: number = 100,
): HexCoord[] {
  const key = (h: HexCoord) => `${h.q},${h.r}`

  interface PQItem { k: string; f: number }
  const openSet: PQItem[] = [{ k: key(start), f: hexDistance(start, end) }]
  const cameFrom = new Map<string, string>()
  const gScore = new Map<string, number>()
  gScore.set(key(start), 0)

  while (openSet.length > 0) {
    openSet.sort((a, b) => a.f - b.f)
    const current = openSet.shift()!
    const [cq, cr] = current.k.split(',').map(Number)

    if (cq === end.q && cr === end.r) {
      const path: HexCoord[] = [{ q: cq, r: cr }]
      let k = current.k
      while (cameFrom.has(k)) {
        const prev = cameFrom.get(k)!
        const [pq, pr] = prev.split(',').map(Number)
        path.unshift({ q: pq, r: pr })
        k = prev
      }
      return path
    }

    const g = gScore.get(current.k) ?? Infinity
    if (g > maxSteps) continue

    for (const n of hexNeighbors(cq, cr)) {
      const nk = key(n)
      if (blocked.has(nk)) continue
      const tentativeG = g + 1
      if (tentativeG < (gScore.get(nk) ?? Infinity)) {
        cameFrom.set(nk, current.k)
        gScore.set(nk, tentativeG)
        const f = tentativeG + hexDistance(n, end)
        const existingIdx = openSet.findIndex(item => item.k === nk)
        if (existingIdx >= 0) {
          openSet[existingIdx].f = f
        } else {
          openSet.push({ k: nk, f })
        }
      }
    }
  }
  return []
}

/** 地块类型名称映射 */
export const TILE_TYPE_NAMES: Record<string, string> = {
  farmland: '农田',
  mountain: '山地',
  water: '水域',
  coast: '海岸',
  city: '城池',
  pass: '关隘',
  port: '港口',
  desert: '漠地',
  grassland: '草原',
}

/** 地块类型对应颜色（旧版兼容） */
export const TILE_TYPE_COLORS: Record<string, string> = {
  farmland: '#a8c8a0',
  mountain: '#9e8b72',
  water: '#3a6d99',
  coast: '#4a8ab5',
  city: '#c9ad7a',
  pass: '#8c7a6a',
  port: '#3478a0',
  desert: '#dcc898',
  grassland: '#8da85a',
}

/** 获取势力色 */
export function getFactionColor(factionId: string, factions: Record<string, { color: string }>): string {
  return factions[factionId]?.color || '#8b7355'
}
