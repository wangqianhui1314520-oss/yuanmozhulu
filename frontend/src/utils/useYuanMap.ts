/**
 * useYuanMap - Vue3 全功能疆域地图 Composable v4.0
 *
 * 将 TerritoryDataProvider + CanvasInteraction + FactionLayerManager
 * 整合为单一入口，供 GamePage / HexMapView 消费。
 *
 * 功能覆盖:
 * - ✅ 496 府州级六边形网格底图
 * - ✅ 11 行省 → 42 路 → 496 府州 三级行政边界
 * - ✅ CK3 风格拖拽平移 + 中心锚点滚轮缩放
 * - ✅ 三级行政层级联动折叠 (province → circuit → prefecture)
 * - ✅ 独立势力着色图层 + 透明度/高亮/闪烁/混合模式
 * - ✅ 画布交互 (点击选中/悬停提示/惯性滑动/缩放动画)
 * - ✅ 边界线渲染 (行省界/路界/府州界三级)
 * - ✅ 战争迷雾三级系统 (未探索/已探索/可见)
 *
 * 使用:
 *   const map = useYuanMap()
 *   await map.initialize({ containerRef, canvasRef })
 *   // 组件中直接使用 map.hexTiles / map.viewport / map.zoomRange 等响应式数据
 *
 *   // 渲染六边形:
 *   <div v-for="tile of map.visibleTiles.value" :style="map.getTileStyle(tile.tile_id)" />
 */

import { ref, computed, shallowRef, readonly, onUnmounted, watch } from 'vue'
import type { Ref } from 'vue'

import { TerritoryDataProvider, getTerritoryDataProvider } from './TerritoryDataProvider'
import type {
  TerritoryTile, BoundaryEdge, AdminNode,
  ProvinceSummary, CircuitSummary, PrefectureSummary,
  FactionTerritorySummary,
} from './TerritoryDataProvider'

import { FactionLayerManager, FACTION_COLOR_PRESETS } from './FactionLayerManager'
import type { FactionLayerConfig, FactionColorResult } from './FactionLayerManager'

import { CanvasInteraction } from './CanvasInteraction'
import type { ViewportState, InteractionConfig } from './CanvasInteraction'

import {
  ZOOM_RANGES, ZOOM_MAX,
  getZoomRange, getVisibleBoundaries, getVisibleLabels, getHexesVisible,
  mergeRemoteZoomConfig,
  setDynamicZoomMin, getDynamicZoomMin,
} from './mapInteractionConfig'
import type { ZoomRange } from './mapInteractionConfig'

import {
  HEX_SIZE, HEX_WIDTH, HEX_HEIGHT, HEX_RATIO, setHexSize,
  axialToPixel, offsetToAxial,
  GRID_ROWS, GRID_MAX_COLS, GRID_MIN_COL,
  TERRAIN_COLORS,
  calculateTerritoryBounds, getTerritoryOrigin,
} from './flatTopHexUtils'
import type { HexTile, TerritoryBounds } from './flatTopHexUtils'

import {
  TERRAIN_COLORS as LAYER_TERRAIN_COLORS,
  ADMIN_BOUNDARY_STYLES,
} from './layerUtils'

// ============================================================
// 类型
// ============================================================

export interface YuanMapOptions {
  /** 数据加载方式: 'api' | 'static' */
  dataSource?: 'api' | 'static'
  /** 基础路径 */
  dataBasePath?: string
  /** 初始缩放 */
  initialScale?: number
  /** 势力图层配置 */
  factionLayerConfig?: Partial<FactionLayerConfig>
  /** 是否显示边界线 */
  showBoundaries?: boolean
  /** 是否显示六边形网格线 */
  showHexGrid?: boolean
  /** 是否显示势力标注 */
  showFactionLabels?: boolean
  /** 是否显示地形底色 */
  showTerrain?: boolean
}

export interface YuanMapState {
  /** 地图数据是否就绪 */
  ready: boolean
  /** 加载进度 0-1 */
  loadingProgress: number
  /** 错误信息 */
  error: string | null
  /** 当前显示的缩放区间 */
  zoomRange: ZoomRange
  /** 当前可见的边界层级 */
  visibleBoundaries: string[]
  /** 当前可见的标签层级 */
  visibleLabels: string[]
}

// ============================================================
// Composable
// ============================================================

export function useYuanMap(options: YuanMapOptions = {}) {
  // ---- 依赖 ----
  const provider = getTerritoryDataProvider()
  const factionLayers = new FactionLayerManager(options.factionLayerConfig)
  let interaction: CanvasInteraction | null = null

  // ---- 响应式状态 ----
  const ready = ref(false)
  const loadingProgress = ref(0)
  const error = ref<string | null>(null)
  const hexTiles = shallowRef<ReadonlyArray<TerritoryTile>>([])
  const viewport = ref<ViewportState>({ scale: options.initialScale ?? 1.0, offsetX: 0, offsetY: 0 })
  const zoomRange = ref<ZoomRange>(ZOOM_RANGES[2]) // 默认路级
  const isDragging = ref(false)
  const selectedTileId = ref<string | null>(null)
  const hoveredTileId = ref<string | null>(null)
  const hoveredScreenPos = ref({ x: 0, y: 0 })

  // 图层显隐
  const showBoundaries = ref(options.showBoundaries ?? true)
  const showHexGrid = ref(options.showHexGrid ?? true)
  const showFactionLabels = ref(options.showFactionLabels ?? true)
  const showTerrain = ref(options.showTerrain ?? true)

  // ---- 计算属性 ----
  const visibleBoundaries = computed(() => getVisibleBoundaries(viewport.value.scale))
  const visibleLabels = computed(() => getVisibleLabels(viewport.value.scale))
  const hexesVisible = computed(() => getHexesVisible(viewport.value.scale))

  /** 当前视口内可见的瓦片 */
  const visibleTiles = computed(() => {
    if (!viewport.value || hexTiles.value.length === 0) return []
    const { scale, offsetX, offsetY } = viewport.value
    // tile 的 pixel_x/pixel_y 在 BASE_HEX_SIZE=32 系统，需转换为动态 HEX_SIZE
    const pxScale = HEX_SIZE / 32
    return hexTiles.value.filter(tile => {
      const sx = tile.pixel_x * pxScale * scale + offsetX
      const sy = tile.pixel_y * pxScale * scale + offsetY
      return sx > -HEX_WIDTH * scale * 2 &&
             sy > -HEX_HEIGHT * scale * 2 &&
             sx < window.innerWidth + HEX_WIDTH * scale * 2 &&
             sy < window.innerHeight + HEX_HEIGHT * scale * 2
    })
  })

  /** 按行省分组的瓦片 */
  const tilesByProvince = computed(() => {
    const groups: Record<string, TerritoryTile[]> = {}
    for (const tile of hexTiles.value) {
      if (tile.province_id) {
        if (!groups[tile.province_id]) groups[tile.province_id] = []
        groups[tile.province_id].push(tile)
      }
    }
    return groups
  })

  /** 按势力分组的瓦片 */
  const tilesByFaction = computed(() => {
    const groups: Record<string, TerritoryTile[]> = {}
    for (const tile of hexTiles.value) {
      if (tile.faction_id) {
        if (!groups[tile.faction_id]) groups[tile.faction_id] = []
        groups[tile.faction_id].push(tile)
      }
    }
    return groups
  })

  // ---- 初始化 ----

  async function initialize(domOptions: {
    containerRef: Ref<HTMLElement | undefined>
    canvasRef?: Ref<HTMLElement | undefined>
  }) {
    try {
      loadingProgress.value = 0.1

      // 1. 加载数据
      const dataSource = options.dataSource || 'static'
      if (dataSource === 'api') {
        await provider.initialize()
      } else {
        await provider.initializeFromStatic(options.dataBasePath || '/data/map')
      }

      loadingProgress.value = 0.4

      // 2. 初始化势力图层
      factionLayers.initializeFromProvider(provider.getAllFactionTerritories())

      loadingProgress.value = 0.6

      // 3. 更新瓦片数据
      hexTiles.value = provider.getAllTiles()

      loadingProgress.value = 0.8

      // 4. 初始化画布交互 (fit-to-viewport 自动计算起始缩放)
      // 矩形网格物理尺寸
      const gridTotalW = HEX_SIZE * 1.5 * GRID_MAX_COLS + HEX_SIZE * 2
      const gridTotalH = HEX_SIZE * Math.sqrt(3) * GRID_ROWS + HEX_SIZE * 2

      // 动态 HEX_SIZE 适配视口
      const baseHexSize = 32
      const rawHexW = baseHexSize * 1.5 * GRID_MAX_COLS + baseHexSize * 2
      const rawHexH = baseHexSize * Math.sqrt(3) * GRID_ROWS + baseHexSize * 2
      const dynamicHexSize = Math.min(
        (window.innerWidth) / (rawHexW / baseHexSize),
        (window.innerHeight) / (rawHexH / baseHexSize),
      )
      setHexSize(dynamicHexSize)

      // 疆域包围盒
      const rawTiles = hexTiles.value.map(t => ({ col: t.col, row: t.row }))
      const territoryBounds = rawTiles.length > 0
        ? calculateTerritoryBounds(rawTiles)
        : { minCol: GRID_MIN_COL, maxCol: GRID_MIN_COL + GRID_MAX_COLS - 1, minRow: 0, maxRow: GRID_ROWS - 1, pixelW: gridTotalW, pixelH: gridTotalH }
      const territoryOrigin = getTerritoryOrigin(territoryBounds)

      interaction = new CanvasInteraction({
        mapTotalWidth: gridTotalW,
        mapTotalHeight: gridTotalH,
        territoryWidth: territoryBounds.pixelW,
        territoryHeight: territoryBounds.pixelH,
        territoryOriginX: territoryOrigin.x,
        territoryOriginY: territoryOrigin.y,
      })

      // 绑定交互回调
      interaction.callbacks = {
        onViewportChange: (vp) => {
          viewport.value = { ...vp }
          isDragging.value = interaction?.isDragging ?? false
        },
        onZoomRangeChange: (range) => {
          zoomRange.value = range
        },
        onTileClick: (tileId) => {
          selectedTileId.value = tileId
          // 点击时高亮对应势力
          const tile = provider.getTile(tileId)
          if (tile?.faction_id) {
            factionLayers.unhighlightAll()
            factionLayers.highlight(tile.faction_id)
          }
        },
        onTileHover: (tileId, sx, sy) => {
          hoveredTileId.value = tileId
          hoveredScreenPos.value = { x: sx, y: sy }
        },
      }

      // 5. 挂载 DOM 事件
      if (domOptions.containerRef.value) {
        interaction.attach(
          domOptions.containerRef.value,
          domOptions.canvasRef?.value
        )
      }

      // 6. 启动动画
      factionLayers.startAnimation()

      loadingProgress.value = 1.0
      ready.value = true

      if (import.meta.env.DEV) console.log(`[useYuanMap] 初始化完成: ${hexTiles.value.length} 格, 已就绪`)
    } catch (err: any) {
      error.value = err.message || '地图初始化失败'
      console.error('[useYuanMap] 初始化失败:', err)
    }
  }

  // ============================================================
  // 查询 API
  // ============================================================

  /** 获取瓦片信息 */
  function getTile(tileId: string): TerritoryTile | undefined {
    return provider.getTile(tileId)
  }

  /** 获取瓦片的势力渲染颜色 */
  function getTileFactionColor(tileId: string): FactionColorResult {
    return factionLayers.getTileColor(tileId)
  }

  /** 获取瓦片的地形颜色 */
  function getTileTerrainColor(tileId: string): string {
    const tile = provider.getTile(tileId)
    if (!tile) return '#888'
    return LAYER_TERRAIN_COLORS[tile.terrain] || TERRAIN_COLORS[tile.terrain] || '#8B9A6B'
  }

  /** 获取行省摘要 */
  function getProvince(provinceId: string): ProvinceSummary | undefined {
    return provider.getProvinceSummary(provinceId)
  }

  /** 获取所有行省 */
  function getProvinces(): ProvinceSummary[] {
    return provider.getAllProvinceSummaries()
  }

  /** 获取势力领地摘要 */
  function getFactionTerritory(factionId: string): FactionTerritorySummary | undefined {
    return provider.getFactionTerritory(factionId)
  }

  /** 获取行省内的势力分布 */
  function getProvinceFactions(provinceId: string): Record<string, number> {
    const tiles = provider.getProvinceTiles(provinceId)
    const factionCounts: Record<string, number> = {}
    for (const tid of tiles) {
      const tile = provider.getTile(tid)
      if (tile?.faction_id) {
        factionCounts[tile.faction_id] = (factionCounts[tile.faction_id] || 0) + 1
      }
    }
    return factionCounts
  }

  /** 获取边界线数据 (按层级) */
  function getBoundaries(level: 'province' | 'circuit' | 'prefecture'): BoundaryEdge[] {
    const b = provider.boundaries
    switch (level) {
      case 'province': return b.province_boundaries
      case 'circuit': return b.circuit_boundaries
      default: return []
    }
  }

  /** 获取层级树 */
  function getHierarchyTree(): AdminNode | null {
    return provider.hierarchyTree
  }

  // ============================================================
  // 交互 API
  // ============================================================

  /** 缩放至指定级别 */
  function zoomToLevel(levelKey: string) {
    interaction?.setZoomLevel(levelKey)
  }

  /** 缩放到指定 scale */
  function zoomTo(targetScale: number, animate = true) {
    interaction?.zoomTo(targetScale, animate)
  }

  /** 重置视图 */
  function resetView() {
    interaction?.resetView()
  }

  /** 平移至世界坐标 */
  function panToWorld(worldX: number, worldY: number, animate = false) {
    interaction?.panToWorld(worldX, worldY, animate)
  }

  /** 平移至指定瓦片 */
  function panToTile(tileId: string, animate = true) {
    const tile = provider.getTile(tileId)
    if (tile) {
      interaction?.panToWorld(tile.pixel_x, tile.pixel_y, animate)
    }
  }

  /** 屏幕坐标 → 瓦片 ID (适配动态 HEX_SIZE) */
  function screenToTile(screenX: number, screenY: number): string | null {
    if (!interaction) return null
    const world = interaction.screenToWorld(screenX, screenY)
    // world 坐标在动态 HEX_SIZE 系统中，findTileAtPixel 在 BASE_HEX_SIZE=32 系统中
    // 需要缩放到 32px 基准
    const scale32 = 32 / HEX_SIZE
    return provider.findTileAtPixel(world.x * scale32, world.y * scale32, 32)
  }

  /** 选中瓦片 */
  function selectTile(tileId: string | null) {
    selectedTileId.value = tileId
    if (tileId) {
      const tile = provider.getTile(tileId)
      if (tile?.faction_id) {
        factionLayers.unhighlightAll()
        factionLayers.highlight(tile.faction_id)
      }
    } else {
      factionLayers.unhighlightAll()
    }
  }

  /** 获取选中瓦片 */
  function getSelectedTile(): TerritoryTile | undefined {
    if (!selectedTileId.value) return undefined
    return provider.getTile(selectedTileId.value)
  }

  // ============================================================
  // 势力图层 API
  // ============================================================

  /** 高亮势力 */
  function highlightFaction(factionId: string, color?: string) {
    factionLayers.unhighlightAll()
    factionLayers.highlight(factionId, color)
  }

  /** 取消所有势力高亮 */
  function clearHighlight() {
    factionLayers.unhighlightAll()
  }

  /** 闪烁势力 (警告/通知) */
  function pulseFaction(factionId: string) {
    factionLayers.startPulse(factionId)
  }

  /** 停止闪烁 */
  function stopPulse(factionId: string) {
    factionLayers.stopPulse(factionId)
  }

  /** 设置势力图层混合模式 */
  function setBlendMode(mode: FactionLayerConfig['blendMode']) {
    factionLayers.setBlendMode(mode)
  }

  /** 设置全局势力透明度 */
  function setFactionOpacity(opacity: number) {
    factionLayers.setGlobalOpacity(opacity)
  }

  /** 获取势力颜色 */
  function getFactionColor(factionId: string): string {
    return FACTION_COLOR_PRESETS[factionId]?.color || '#888'
  }

  /** 获取势力名称 */
  function getFactionName(factionId: string): string {
    return FACTION_COLOR_PRESETS[factionId]?.name || factionId
  }

  // ============================================================
  // 图层开关
  // ============================================================

  function toggleBoundaries() { showBoundaries.value = !showBoundaries.value }
  function toggleHexGrid() { showHexGrid.value = !showHexGrid.value }
  function toggleFactionLabels() { showFactionLabels.value = !showFactionLabels.value }
  function toggleTerrain() { showTerrain.value = !showTerrain.value }

  // ============================================================
  // 统计
  // ============================================================

  /** 获取地图统计数据 */
  function getStats() {
    return {
      tiles: hexTiles.value.length,
      provinces: provider.getAllProvinceSummaries().length,
      factions: factionLayers.getRegisteredFactions().length,
      selectedTile: selectedTileId.value,
      viewport: viewport.value,
      dataProvider: provider.getStats(),
      boundaries: {
        province: provider.boundaries.province_boundaries.length,
        circuit: provider.boundaries.circuit_boundaries.length,
        faction: (provider.boundaries as any).faction_boundaries?.length ?? 0,
      },
    }
  }

  /** 导出全量数据 */
  function exportAll() {
    return {
      data: provider.exportAll(),
      factionLayers: factionLayers.getRegisteredFactions().map(fid => ({
        id: fid,
        layer: factionLayers.getLayer(fid),
        territory: provider.getFactionTerritory(fid),
      })),
    }
  }

  // ============================================================
  // 生命周期
  // ============================================================

  /** 更新容器尺寸 */
  function updateContainerSize(w: number, h: number) {
    interaction?.updateContainerSize(w, h)
  }

  function destroy() {
    interaction?.destroy()
    interaction = null
    factionLayers.destroy()
    ready.value = false
  }

  // 组件卸载时自动清理
  onUnmounted(destroy)

  // ============================================================
  // 返回
  // ============================================================

  return {
    // -- 状态 --
    ready: readonly(ready),
    loadingProgress: readonly(loadingProgress),
    error: readonly(error),
    hexTiles: readonly(hexTiles),
    viewport,
    zoomRange,
    isDragging: readonly(isDragging),
    selectedTileId: readonly(selectedTileId),
    hoveredTileId: readonly(hoveredTileId),
    hoveredScreenPos: readonly(hoveredScreenPos),

    // -- 图层开关 --
    showBoundaries,
    showHexGrid,
    showFactionLabels,
    showTerrain,

    // -- 计算属性 --
    visibleBoundaries,
    visibleLabels,
    hexesVisible,
    visibleTiles,
    tilesByProvince,
    tilesByFaction,

    // -- 初始化 --
    initialize,

    // -- 查询 --
    getTile,
    getTileFactionColor,
    getTileTerrainColor,
    getProvince,
    getProvinces,
    getFactionTerritory,
    getProvinceFactions,
    getBoundaries,
    getHierarchyTree,

    // -- 交互 --
    zoomToLevel,
    zoomTo,
    resetView,
    panToWorld,
    panToTile,
    screenToTile,
    selectTile,
    getSelectedTile,

    // -- 势力图层 --
    highlightFaction,
    clearHighlight,
    pulseFaction,
    stopPulse,
    setBlendMode,
    setFactionOpacity,
    getFactionColor,
    getFactionName,

    // -- 图层开关方法 --
    toggleBoundaries,
    toggleHexGrid,
    toggleFactionLabels,
    toggleTerrain,

    // -- 统计 --
    getStats,
    exportAll,

    // -- 生命周期 --
    updateContainerSize,
    destroy,

    // -- 底层实例 (高级用法) --
    provider,
    factionLayers,
  }
}
