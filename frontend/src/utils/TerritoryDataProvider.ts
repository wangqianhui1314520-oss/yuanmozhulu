/**
 * 疆域基底数据提供器 - 完整元朝全盛疆域数据层
 *
 * 职责：
 * 1. 异步加载全部地图数据 (map_final.json / boundaries.json / admin_hierarchy.json / faction_territories.json)
 * 2. 建立多级索引 (tile → 行政归属 → 势力归属 → 地形)
 * 3. 提供 Vue3 reactive 状态供组件消费
 * 4. 支持增量更新 (势力领地变更、地形变更)
 *
 * 使用方式：
 *   const provider = new TerritoryDataProvider('/data/map')
 *   await provider.initialize()
 *   const tile = provider.getTile('hex_32_6')  // 大都
 *   const province = provider.getProvinceSummary('province_zhongshu')
 */

import { reactive, readonly, computed } from 'vue'

// ============================================================
// 类型定义
// ============================================================

/** 六边形瓦片 (完整字段，与 map_final.json 对齐) */
export interface TerritoryTile {
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
  defense_bonus: number
  is_coastal: boolean
  is_ferry: boolean
  combat_modifiers: { cavalry: number; infantry: number; navy: number }
  supply_yield: number
  province: string
  province_id: string
  circuit_id: string
  prefecture_id: string
  prefecture: string
  faction_id: string
  is_capital: boolean
  is_port: boolean
  is_pass: boolean
  is_strategic: boolean
  strategic_name: string
  strategic_note: string
  water_river: string
  water_lake: string
}

/** 行政边界 */
export interface BoundaryEdge {
  x: number
  y: number
  a: string
  b: string
  tile_a: string
  tile_b: string
}

/** 行政层级节点 */
export interface AdminNode {
  id: string
  name: string
  type: 'root' | 'province' | 'circuit' | 'prefecture'
  meta: Record<string, any>
  tile_count: number
  tile_ids: string[]
  children: AdminNode[]
  _expanded: boolean
  _can_expand: boolean
}

/** 势力领地摘要 */
export interface FactionTerritorySummary {
  faction_id: string
  capital: string
  color: string
  tile_count: number
  tile_ids: string[]
  /** 按行省分组的领地 */
  by_province: Record<string, string[]>
  /** 边界瓦片（与其他势力接壤的 tile 列表） */
  border_tiles: string[]
}

/** 行省摘要 */
export interface ProvinceSummary {
  id: string
  name: string
  meta: Record<string, any>
  tile_count: number
  tile_ids: string[]
  circuit_count: number
}

/** 路摘要 */
export interface CircuitSummary {
  id: string
  name: string
  province_id: string
  province_name: string
  tile_count: number
  tile_ids: string[]
  prefecture_count: number
}

/** 府州摘要 */
export interface PrefectureSummary {
  id: string
  name: string
  circuit_id: string
  circuit_name: string
  province_id: string
  province_name: string
  tile_count: number
  tile_ids: string[]
}

/** 加载状态 */
export interface TerritoryDataState {
  loaded: boolean
  loading: boolean
  error: string | null
  meta: {
    version: string
    total_tiles: number
    grid_rows: number
    grid_max_cols: number
    hex_orientation: string
    hex_size_px: number
  } | null
}

// ============================================================
// 数据提供器
// ============================================================

export class TerritoryDataProvider {
  // ---- 数据源 ----
  private _tiles: Record<string, TerritoryTile> = {}
  private _tilesArray: TerritoryTile[] = []
  private _boundaries: {
    province_boundaries: BoundaryEdge[]
    circuit_boundaries: BoundaryEdge[]
    faction_boundaries?: BoundaryEdge[]
  } = { province_boundaries: [], circuit_boundaries: [] }
  private _hierarchyTree: AdminNode | null = null
  private _factionTerritories: Record<string, FactionTerritorySummary> = {}

  // ---- 索引 ----
  /** tile_id → TerritoryTile */
  private _tileIndex: Record<string, TerritoryTile> = {}
  /** province_id → tile_id[] */
  private _provinceIndex: Record<string, string[]> = {}
  /** circuit_id → tile_id[] */
  private _circuitIndex: Record<string, string[]> = {}
  /** prefecture_id → tile_id[] */
  private _prefectureIndex: Record<string, string[]> = {}
  /** faction_id → tile_id[] */
  private _factionIndex: Record<string, string[]> = {}
  /** terrain → tile_id[] */
  private _terrainIndex: Record<string, string[]> = {}

  // ---- 摘要信息 ----
  private _provinces: Record<string, ProvinceSummary> = {}
  private _circuits: Record<string, CircuitSummary> = {}
  private _prefectures: Record<string, PrefectureSummary> = {}

  /** 网格尺寸 (不含遮罩的矩形网格) */
  private _gridTotal = 0

  // ---- API 配置 ----
  private _basePath: string

  // ---- 状态 ----
  readonly state = reactive<TerritoryDataState>({
    loaded: false,
    loading: false,
    error: null,
    meta: null,
  })

  constructor(basePath: string = '/api/map') {
    this._basePath = basePath
  }

  // ============================================================
  // 初始化
  // ============================================================

  /**
   * 从后端 API 异步加载全部地图数据
   */
  async initialize(): Promise<void> {
    if (this.state.loaded) return
    this.state.loading = true
    this.state.error = null

    try {
      const base = this._basePath
      const urls = [
        { key: 'tiles', url: `${base}/map-final` },
        { key: 'boundaries', url: `${base}/boundaries` },
        { key: 'hierarchy', url: `${base}/admin-hierarchy` },
        { key: 'factions', url: `${base}/faction-territories` },
      ]

      const results = await Promise.allSettled(
        urls.map(({ url }) =>
          fetch(url).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`)
            return r.json()
          })
        )
      )

      // 处理各数据源
      const data: Record<string, any> = {}
      urls.forEach(({ key }, i) => {
        const result = results[i]
        if (result.status === 'fulfilled') {
          data[key] = (result.value as any).data || result.value
        } else {
          console.warn(`[TerritoryDataProvider] 加载 ${key} 失败:`, result.reason)
        }
      })

      // 按优先级加载
      if (data.tiles) this._loadTiles(data.tiles)
      if (data.boundaries) this._loadBoundaries(data.boundaries)
      if (data.hierarchy) this._loadHierarchy(data.hierarchy)
      if (data.factions) this._loadFactionTerritories(data.factions)

      // 补充内部索引（基于已有数据推断）
      this._buildInternalIndices()

      this.state.loaded = true
      if (import.meta.env.DEV) console.log(
        `[TerritoryDataProvider] 初始化完成: ${this._tilesArray.length} 格, ` +
        `${Object.keys(this._provinces).length} 行省, ` +
        `${Object.keys(this._circuits).length} 路, ` +
        `${Object.keys(this._prefectures).length} 府/州, ` +
        `${Object.keys(this._factionTerritories).length} 势力`
      )
    } catch (err: any) {
      this.state.error = err.message || '初始化失败'
      console.error('[TerritoryDataProvider] 初始化失败:', err)
    } finally {
      this.state.loading = false
    }
  }

  /**
   * 从本地静态 JSON 文件加载 (生产部署模式)
   */
  async initializeFromStatic(basePath: string = '/data/map'): Promise<void> {
    if (this.state.loaded) return
    this.state.loading = true
    this.state.error = null

    const files = [
      { key: 'tiles', file: 'map_final.json' },
      { key: 'boundaries', file: 'boundaries.json' },
      { key: 'hierarchy', file: 'admin_hierarchy.json' },
      { key: 'factions', file: 'faction_territories.json' },
    ]

    try {
      const results = await Promise.allSettled(
        files.map(({ file }) =>
          fetch(`${basePath}/${file}`).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`)
            return r.json()
          })
        )
      )

      const data: Record<string, any> = {}
      files.forEach(({ key }, i) => {
        const result = results[i]
        if (result.status === 'fulfilled') {
          data[key] = result.value
        }
      })

      if (data.tiles) this._loadTiles(data.tiles)
      if (data.boundaries) this._loadBoundaries(data.boundaries)
      if (data.hierarchy) this._loadHierarchy(data.hierarchy)
      if (data.factions) this._loadFactionTerritories(data.factions)

      this._buildInternalIndices()

      this.state.loaded = true
      if (import.meta.env.DEV) console.log(
        `[TerritoryDataProvider] 静态数据初始化完成: ${this._tilesArray.length} 格`
      )
    } catch (err: any) {
      this.state.error = err.message || '加载失败'
    } finally {
      this.state.loading = false
    }
  }

  // ============================================================
  // 数据加载子方法
  // ============================================================

  private _loadTiles(payload: any) {
    const tiles: TerritoryTile[] = payload.tiles || payload

    if (payload.meta) {
      this.state.meta = payload.meta
    }

    for (const tile of tiles) {
      this._tiles[tile.tile_id] = tile
      this._tileIndex[tile.tile_id] = tile
    }

    this._tilesArray = tiles
  }

  private _loadBoundaries(payload: any) {
    const boundaries = payload.boundaries || payload
    this._boundaries = {
      province_boundaries: boundaries.province_boundaries || [],
      circuit_boundaries: boundaries.circuit_boundaries || [],
      faction_boundaries: boundaries.faction_boundaries || [],
    }
  }

  private _loadHierarchy(payload: any) {
    this._hierarchyTree = payload.hierarchy_tree || payload
  }

  private _loadFactionTerritories(payload: any) {
    const factions = payload.factions || payload
    for (const [fid, fdata] of Object.entries(factions) as any) {
      const data = fdata as any
      const tileIds: string[] = data.tiles || []
      const byProvince: Record<string, string[]> = {}

      this._factionIndex[fid] = tileIds

      // 按行省分组
      for (const tid of tileIds) {
        const tile = this._tiles[tid]
        if (tile) {
          if (!byProvince[tile.province_id]) {
            byProvince[tile.province_id] = []
          }
          byProvince[tile.province_id].push(tid)
        }
      }

      // 计算边界瓦片
      const borderTiles = this._computeBorderTiles(tileIds)

      this._factionTerritories[fid] = {
        faction_id: fid,
        capital: data.capital || '',
        color: data.color || '#888888',
        tile_count: tileIds.length,
        tile_ids: tileIds,
        by_province: byProvince,
        border_tiles: borderTiles,
      }
    }
  }

  /**
   * 基于加载的 tiles 推断内部索引 (行政/地形/faction)
   * 当后端返回的 factions 数据不完整时，此方法补充推断
   */
  private _buildInternalIndices() {
    for (const tile of this._tilesArray) {
      const tid = tile.tile_id

      // 行省
      if (tile.province_id) {
        if (!this._provinceIndex[tile.province_id]) {
          this._provinceIndex[tile.province_id] = []
        }
        this._provinceIndex[tile.province_id].push(tid)
      }

      // 路
      if (tile.circuit_id) {
        if (!this._circuitIndex[tile.circuit_id]) {
          this._circuitIndex[tile.circuit_id] = []
        }
        this._circuitIndex[tile.circuit_id].push(tid)
      }

      // 府/州
      if (tile.prefecture_id) {
        if (!this._prefectureIndex[tile.prefecture_id]) {
          this._prefectureIndex[tile.prefecture_id] = []
        }
        this._prefectureIndex[tile.prefecture_id].push(tid)
      }

      // 势力 (仅在 factions 数据未提供时补充)
      if (tile.faction_id && !this._factionIndex[tile.faction_id]) {
        if (!this._factionIndex[tile.faction_id]) {
          this._factionIndex[tile.faction_id] = []
        }
        this._factionIndex[tile.faction_id].push(tid)
      }

      // 地形
      if (tile.terrain) {
        if (!this._terrainIndex[tile.terrain]) {
          this._terrainIndex[tile.terrain] = []
        }
        this._terrainIndex[tile.terrain].push(tid)
      }
    }

    // 构建行省摘要
    for (const [pid, tids] of Object.entries(this._provinceIndex)) {
      const sample = this._tiles[tids[0]]
      this._provinces[pid] = {
        id: pid,
        name: sample?.province || pid,
        meta: {},
        tile_count: tids.length,
        tile_ids: tids,
        circuit_count: 0,
      }
    }

    // 构建路摘要
    for (const [cid, tids] of Object.entries(this._circuitIndex)) {
      const sample = this._tiles[tids[0]]
      this._circuits[cid] = {
        id: cid,
        name: sample?.prefecture || cid, // 府名→路名由 hierarchy 提供
        province_id: sample?.province_id || '',
        province_name: sample?.province || '',
        tile_count: tids.length,
        tile_ids: tids,
        prefecture_count: 0,
      }
    }

    // 构建府/州摘要
    for (const [pfid, tids] of Object.entries(this._prefectureIndex)) {
      const sample = this._tiles[tids[0]]
      this._prefectures[pfid] = {
        id: pfid,
        name: sample?.prefecture || pfid,
        circuit_id: sample?.circuit_id || '',
        circuit_name: '',
        province_id: sample?.province_id || '',
        province_name: sample?.province || '',
        tile_count: tids.length,
        tile_ids: tids,
      }
    }

    // 补充 hierarchy 中的 circuit_count / prefecture_count
    for (const pf of Object.values(this._prefectures)) {
      if (pf.circuit_id && this._circuits[pf.circuit_id]) {
        this._circuits[pf.circuit_id].prefecture_count++
        this._circuits[pf.circuit_id].name = pf.name.includes(pf.circuit_id) ? this._circuits[pf.circuit_id].name : this._circuits[pf.circuit_id].name
      }
    }
    for (const circ of Object.values(this._circuits)) {
      if (circ.province_id && this._provinces[circ.province_id]) {
        this._provinces[circ.province_id].circuit_count++
      }
    }

    this._gridTotal = this._tilesArray.length
  }

  /**
   * 计算势力边界瓦片 (与邻接非己方瓦片相邻者)
   */
  private _computeBorderTiles(tileIds: string[]): string[] {
    const set = new Set(tileIds)
    const border: string[] = []

    for (const tid of tileIds) {
      const tile = this._tiles[tid]
      if (!tile) continue
      for (const nid of tile.neighbors) {
        if (!set.has(nid)) {
          border.push(tid)
          break
        }
      }
    }

    return border
  }

  // ============================================================
  // 查询 API
  // ============================================================

  /** 获取单个瓦片 */
  getTile(tileId: string): TerritoryTile | undefined {
    return this._tileIndex[tileId]
  }

  /** 获取全部瓦片 */
  getAllTiles(): ReadonlyArray<TerritoryTile> {
    return this._tilesArray
  }

  /** 获取全部瓦片 (索引形式) */
  getAllTilesMap(): Readonly<Record<string, TerritoryTile>> {
    return this._tileIndex
  }

  /** 获取网格总数 */
  get gridTotal(): number {
    return this._gridTotal
  }

  /** 获取层级树 (根节点 → 行省 → 路 → 府州) */
  get hierarchyTree(): AdminNode | null {
    return this._hierarchyTree
  }

  /** 获取指定行省的瓦片 */
  getProvinceTiles(provinceId: string): string[] {
    return this._provinceIndex[provinceId] || []
  }

  /** 获取指定路的瓦片 */
  getCircuitTiles(circuitId: string): string[] {
    return this._circuitIndex[circuitId] || []
  }

  /** 获取指定府/州的瓦片 */
  getPrefectureTiles(prefectureId: string): string[] {
    return this._prefectureIndex[prefectureId] || []
  }

  /** 获取指定势力的瓦片 */
  getFactionTiles(factionId: string): string[] {
    return this._factionIndex[factionId] || []
  }

  /** 获取指定地形的瓦片 */
  getTerrainTiles(terrain: string): string[] {
    return this._terrainIndex[terrain] || []
  }

  /** 获取行省摘要 */
  getProvinceSummary(provinceId: string): ProvinceSummary | undefined {
    return this._provinces[provinceId]
  }

  /** 获取所有行省摘要 */
  getAllProvinceSummaries(): ProvinceSummary[] {
    return Object.values(this._provinces)
  }

  /** 获取路摘要 */
  getCircuitSummary(circuitId: string): CircuitSummary | undefined {
    return this._circuits[circuitId]
  }

  /** 获取府州摘要 */
  getPrefectureSummary(prefectureId: string): PrefectureSummary | undefined {
    return this._prefectures[prefectureId]
  }

  /** 获取势力领地摘要 */
  getFactionTerritory(factionId: string): FactionTerritorySummary | undefined {
    return this._factionTerritories[factionId]
  }

  /** 获取所有势力领地摘要 */
  getAllFactionTerritories(): Record<string, FactionTerritorySummary> {
    return this._factionTerritories
  }

  /** 获取边界数据 */
  get boundaries() {
    return this._boundaries
  }

  /**
   * 找出与指定势力相邻的所有其他势力
   * @returns { faction_id: string[] } 相邻势力及其接壤瓦片列表
   */
  getNeighborFactions(factionId: string): Record<string, string[]> {
    const ownTiles = new Set(this._factionIndex[factionId] || [])
    const neighbors: Record<string, string[]> = {}

    for (const tid of this.getFactionBorderTiles(factionId)) {
      const tile = this._tiles[tid]
      if (!tile) continue
      for (const nid of tile.neighbors) {
        const nTile = this._tiles[nid]
        if (nTile && nTile.faction_id && nTile.faction_id !== factionId) {
          if (!neighbors[nTile.faction_id]) {
            neighbors[nTile.faction_id] = []
          }
          if (!neighbors[nTile.faction_id].includes(tid)) {
            neighbors[nTile.faction_id].push(tid)
          }
        }
      }
    }

    return neighbors
  }

  /** 获取势力边界瓦片 */
  getFactionBorderTiles(factionId: string): string[] {
    return this._factionTerritories[factionId]?.border_tiles || []
  }

  /**
   * 按瓦片 ID 批量查询
   */
  getTilesByIds(tileIds: string[]): TerritoryTile[] {
    return tileIds.map(id => this._tiles[id]).filter(Boolean)
  }

  /**
   * 屏幕坐标(像素) → 瓦片 ID (基于六边形网格像素坐标的近似查找)
   */
  findTileAtPixel(px: number, py: number, hexSize: number = 32): string | null {
    // Flat-Top axial → pixel 逆变换
    const q = (2.0 / 3.0 * px) / hexSize
    const r = (-1.0 / 3.0 * px + Math.sqrt(3) / 3.0 * py) / hexSize

    // hex round
    let rq = Math.round(q)
    let rr = Math.round(r)
    const rs = Math.round(-q - r)

    const qDiff = Math.abs(rq - q)
    const rDiff = Math.abs(rr - r)
    const sDiff = Math.abs(rs - (-q - r))

    if (qDiff > rDiff && qDiff > sDiff) {
      rq = -rr - rs
    } else if (rDiff > sDiff) {
      rr = -rq - rs
    }

    // Axial → Offset (Flat-Top, odd-row)
    const row = rr
    const col = rq + (row - (row & 1)) / 2
    const tileId = `hex_${col}_${row}`

    return this._tileIndex[tileId] ? tileId : null
  }

  // ============================================================
  // 更新 API (用于游戏运行时势力领地变更)
  // ============================================================

  /**
   * 更新瓦片势力归属
   */
  updateTileFaction(tileId: string, factionId: string): boolean {
    const tile = this._tileIndex[tileId]
    if (!tile) return false

    const oldFaction = tile.faction_id

    // 更新瓦片
    tile.faction_id = factionId

    // 更新势力索引
    if (oldFaction && this._factionIndex[oldFaction]) {
      const idx = this._factionIndex[oldFaction].indexOf(tileId)
      if (idx >= 0) this._factionIndex[oldFaction].splice(idx, 1)
    }
    if (!this._factionIndex[factionId]) {
      this._factionIndex[factionId] = []
    }
    if (!this._factionIndex[factionId].includes(tileId)) {
      this._factionIndex[factionId].push(tileId)
    }

    // 更新势力摘要
    this._refreshFactionSummary(oldFaction)
    this._refreshFactionSummary(factionId)

    return true
  }

  /**
   * 批量更新瓦片势力归属
   */
  updateTilesFaction(tileIds: string[], factionId: string): number {
    let count = 0
    const affectedFactions = new Set<string>()

    for (const tid of tileIds) {
      const tile = this._tileIndex[tid]
      if (!tile) continue
      if (tile.faction_id) affectedFactions.add(tile.faction_id)
      tile.faction_id = factionId
      count++
    }

    // 重建受影响的势力索引
    affectedFactions.add(factionId)
    for (const fid of affectedFactions) {
      this._factionIndex[fid] = []
    }
    for (const tile of this._tilesArray) {
      if (tile.faction_id && this._factionIndex[tile.faction_id]) {
        this._factionIndex[tile.faction_id].push(tile.tile_id)
      }
    }

    // 刷新摘要
    for (const fid of affectedFactions) {
      this._refreshFactionSummary(fid)
    }

    return count
  }

  private _refreshFactionSummary(factionId: string) {
    if (!factionId) return
    const tids = this._factionIndex[factionId] || []
    const existing = this._factionTerritories[factionId]

    const byProvince: Record<string, string[]> = {}
    for (const tid of tids) {
      const tile = this._tiles[tid]
      if (tile?.province_id) {
        if (!byProvince[tile.province_id]) byProvince[tile.province_id] = []
        byProvince[tile.province_id].push(tid)
      }
    }

    this._factionTerritories[factionId] = {
      faction_id: factionId,
      capital: existing?.capital || '',
      color: existing?.color || '#888',
      tile_count: tids.length,
      tile_ids: tids,
      by_province: byProvince,
      border_tiles: this._computeBorderTiles(tids),
    }
  }

  // ============================================================
  // 统计 / 导出
  // ============================================================

  /** 导出完整统计数据 */
  getStats() {
    return {
      total_tiles: this._tilesArray.length,
      provinces: Object.keys(this._provinces).length,
      circuits: Object.keys(this._circuits).length,
      prefectures: Object.keys(this._prefectures).length,
      factions: Object.keys(this._factionTerritories).length,
      terrain_types: Object.keys(this._terrainIndex).length,
      boundaries: {
        province: this._boundaries.province_boundaries.length,
        circuit: this._boundaries.circuit_boundaries.length,
        faction: this._boundaries.faction_boundaries?.length ?? 0,
      },
    }
  }

  /** 全量导出 (用于调试 / 序列化) */
  exportAll() {
    return {
      tiles: this._tilesArray,
      boundaries: this._boundaries,
      hierarchy_tree: this._hierarchyTree,
      faction_territories: this._factionTerritories,
      indices: {
        provinces: this._provinces,
        circuits: this._circuits,
        prefectures: this._prefectures,
      },
      stats: this.getStats(),
    }
  }
}

// ============================================================
// 单例
// ============================================================

let _instance: TerritoryDataProvider | null = null

/** 获取全局单例 */
export function getTerritoryDataProvider(): TerritoryDataProvider {
  if (!_instance) {
    _instance = new TerritoryDataProvider()
  }
  return _instance
}

/** 重置单例 */
export function resetTerritoryDataProvider(): void {
  _instance = null
}
