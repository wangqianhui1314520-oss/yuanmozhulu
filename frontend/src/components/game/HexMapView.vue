<template>
  <div ref="containerRef" class="hex-map-container">
    <div ref="stageContainer" class="stage-container"></div>
    <!-- 着色器叠加层 (WebGL2 后处理效果，纯视觉，不影响交互) -->
    <canvas ref="shaderCanvasRef" class="shader-overlay"></canvas>

    <!-- 快捷图层模式切换（精简版，完整面板在GamePage的LayerPanel中） -->
    <div class="layer-panel">
      <div class="layer-mode-btns">
        <button @click="$emit('setLayerMode', 'all')" title="全开">⊞</button>
        <button @click="$emit('setLayerMode', 'terrain')" title="仅地形">🏔</button>
        <button @click="$emit('setLayerMode', 'faction')" title="仅势力">⚔</button>
        <button @click="$emit('setLayerMode', 'military')" title="军事视图">⚡</button>
        <button @click="$emit('setLayerMode', 'admin')" title="外交视图">📜</button>
      </div>
    </div>

    <!-- 悬停提示 - 势力名称优先标注（CSS过渡+delay支持玩家自定义tooltipDelay） -->
    <div class="hex-tooltip" :style="tooltipStyle" :class="{ 'hex-tooltip--visible': hoveredTile }">
      <template v-if="hoveredTile">
        <!-- 海域专用提示 -->
        <template v-if="hoveredTile.terrain === 'sea'">
          <div class="tooltip-sea-header">
            <span class="sea-icon">🌊</span>
            <span class="tooltip-name">{{ (hoveredTile as any).sea_zone_name || '海域' }}</span>
          </div>
          <div class="tooltip-info">
            {{ (hoveredTile as any).sea_zone_name || '远洋' }} ·
            水深: {{ seaDepthLabel((hoveredTile as any).sea_depth) }}
          </div>
          <div class="tooltip-terrain">
            海洋
            <span class="terrain-stat">海移:{{ hoveredTile.movement_cost ?? 25 }}</span>
            <span class="terrain-stat">海军:{{ (hoveredTile as any).navy_modifier ?? 1.0 }}x</span>
          </div>
          <div class="tooltip-badges">
            <span v-if="hoveredTile.is_coastal" class="tooltip-badge coastal">🏖 沿岸</span>
            <span v-if="(hoveredTile as any).sea_depth === 'deep'" class="tooltip-badge deepsea">🌊 深海</span>
            <span v-if="(hoveredTile as any).sea_depth === 'abyssal'" class="tooltip-badge abyssal">🌀 远洋</span>
          </div>
        </template>
        <!-- 陆地专用提示 -->
        <template v-else>
          <div v-if="hoveredTile.faction_id" class="tooltip-faction">
            <span class="faction-dot" :style="{ background: factionColor(hoveredTile.faction_id) }"></span>
            <span class="faction-label">{{ factionName(hoveredTile.faction_id) }}</span>
          </div>
          <div class="tooltip-name">{{ hoveredTile.tile_name }}</div>
          <div class="tooltip-info">
            {{ hoveredTile.province }} · {{ hoveredTile.prefecture }}
          </div>
          <div class="tooltip-terrain">
            {{ terrainLabel(hoveredTile.terrain) }}
            <span class="terrain-stat">移:{{ hoveredTile.movement_cost ?? 10 }}</span>
            <span class="terrain-stat">防:+{{ hoveredTile.defense_bonus ?? 0 }}</span>
          </div>
          <div class="tooltip-badges">
            <span v-if="hoveredTile.is_capital" class="tooltip-badge capital">★ 都城</span>
            <span v-if="hoveredTile.is_port" class="tooltip-badge port">⚓ 港口</span>
            <span v-if="hoveredTile.is_pass" class="tooltip-badge pass">🏔 关隘</span>
            <span v-if="hoveredTile.is_ferry" class="tooltip-badge ferry">⛵ 渡口</span>
            <span v-if="hoveredTile.is_coastal" class="tooltip-badge coastal">🌊 沿海</span>
            <span v-if="hoveredTile.is_strategic" class="tooltip-badge strategic">🏰 战略</span>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, nextTick, shallowRef } from 'vue'
import Konva from 'konva'
import type { HexTile } from '@/utils/flatTopHexUtils'
import {
  HEX_SIZE, HEX_WIDTH, HEX_HEIGHT, HEX_RATIO, setHexSize,
  FACTION_COLORS, FACTION_NAMES, TERRAIN_COLORS, SEA_DEPTH_COLORS,
  axialToPixel, offsetToAxial,
  GRID_ROWS, GRID_MAX_COLS, GRID_MIN_COL,
  calculateTerritoryBounds, getTerritoryOrigin,
  type TerritoryBounds,
} from '@/utils/flatTopHexUtils'
import {
  TERRAIN_NAMES,
  FACTION_LAYER_COLORS,
  ADMIN_BOUNDARY_STYLES,
  STRATEGIC_ICONS,
  FACTION_BOUNDARY_STYLES,
} from '@/utils/layerUtils'
import type { LayerRuntimeState } from '@/utils/layerUtils'
import type { BoundaryMode } from '@/utils/layerConfig'
import { CanvasInteraction, applySelectionHighlight } from '@/utils/CanvasInteraction'
import type { ViewportState } from '@/utils/CanvasInteraction'
import {
  ZOOM_RANGES,
  getZoomRange, getVisibleBoundaries, getVisibleLabels,
  calculateFitScale, calculateFitOffset,
} from '@/utils/mapInteractionConfig'
import type { ZoomRange } from '@/utils/mapInteractionConfig'
import { generateInkWashTexture } from '@/utils/InkWashTexture'
import { FACTION_PALETTE, FONT_FAMILY_TITLE } from '@/utils/parchmentTheme'
import { ShaderOverlay } from '@/utils/ShaderOverlay'

export interface BoundaryEdge {
  x: number; y: number
  a: string; b: string
  tile_a: string; tile_b: string
}

export interface BoundaryData {
  province_boundaries: BoundaryEdge[]
  circuit_boundaries: BoundaryEdge[]
  faction_boundaries?: BoundaryEdge[]
}

export interface AdminOutline {
  admin_id: string
  point_count: number
  path: number[][]
}

const props = defineProps<{
  tiles: HexTile[]
  selectedTileId?: string
  /** 图层状态 (14层) */
  layers?: Record<string, LayerRuntimeState>
  /** 边界子模式 */
  boundaryMode?: BoundaryMode
  /** 行政边界线数据 */
  boundaries?: BoundaryData | null
  /** 聚合后的行省轮廓路径 */
  outlines?: AdminOutline[] | null
  /** 玩家所属势力ID */
  playerFactionId?: string
  /** 迷雾可见地块ID集合 */
  fogVisibleIds?: Set<string>
  /** 行军路线数据 */
  marchRoutes?: Array<{
    id: string; type: 'march'|'retreat'|'supply'
    path: string[]; factionId: string; color?: string
  }>
  /** 补给线数据 */
  supplyLines?: Array<{
    id: string; path: string[]; broken: boolean
  }>
  /** 外交关系（附庸/同盟） */
  diplomacyRelations?: Array<{
    from: string; to: string; type: 'vassal'|'alliance'|'war'|'trade'
  }>
  /** 驻防数据 */
  garrisonData?: Record<string, { troops: number; resting: boolean }>
  /** 法理宣称地块ID集合 */
  claimTiles?: Set<string>
  /** 灾害数据 */
  disasterTiles?: Record<string, Array<{ type: string; severity: number }>>
  /** 水域航道数据 */
  waterRoutes?: Array<{ id: string; path: string[] }>
  /** 城建建筑数据 */
  buildingData?: Record<string, Array<{ type: string; level: number }>>
}>()

const emit = defineEmits<{
  tileClick: [tileId: string]
  tileRightClick: [tileId: string, event: MouseEvent]
  tileHover: [tile: HexTile | null]
  toggleLayer: [layerId: string]
  setLayerMode: [mode: string]
}>()

  let stage: Konva.Stage | null = null
  let bgLayer: Konva.Layer | null = null
  let hexLayer: Konva.Layer | null = null
  let factionLayer: Konva.Layer | null = null
  let boundaryLayer: Konva.Layer | null = null
  let overlayLayer: Konva.Layer | null = null
  let fogLayer: Konva.Layer | null = null
  // 新增7层
  let marchRouteLayer: Konva.Layer | null = null
  let buildingLayer: Konva.Layer | null = null
  let disasterLayer: Konva.Layer | null = null
  let diplomacyLayer: Konva.Layer | null = null
  let garrisonLayer: Konva.Layer | null = null
  let waterwayLayer: Konva.Layer | null = null
  let claimLayer: Konva.Layer | null = null
  /** 古卷宣纸纹理 (程序化生成) */
  let inkWashCanvas: HTMLCanvasElement | null = null

  /** 预计算：tile_id → 世界像素坐标 {px, py}，避免每帧 offsetToAxial+axialToPixel */
  const tilePixelCache = new Map<string, { px: number; py: number }>()

  /** 预计算：势力ID → 区域中心点 {x, y}，renderOverlayMarkers 复用 */
  const factionCentroidCache = new Map<string, { x: number; y: number }>()

  /** 重建 tile 像素坐标缓存（HEX_SIZE 变化时调用） */
  function rebuildTilePixelCache() {
    tilePixelCache.clear()
    factionCentroidCache.clear()
    // 势力tile分组用于质心计算
    const factionTiles = new Map<string, { sumX: number; sumY: number; count: number }>()
    for (const tile of props.tiles) {
      const axial = offsetToAxial(tile.col, tile.row)
      const p = axialToPixel(axial.q, axial.r, HEX_SIZE)
      tilePixelCache.set(tile.tile_id, { px: p.x, py: p.y })
      // 同时收集势力质心数据
      if (tile.faction_id) {
        const acc = factionTiles.get(tile.faction_id) || { sumX: 0, sumY: 0, count: 0 }
        acc.sumX += p.x; acc.sumY += p.y; acc.count++
        factionTiles.set(tile.faction_id, acc)
      }
    }
    // 计算势力质心
    for (const [fid, acc] of factionTiles) {
      factionCentroidCache.set(fid, { x: acc.sumX / acc.count, y: acc.sumY / acc.count })
    }
  }

/** CK3 风格画布交互控制器 */
let interaction: CanvasInteraction | null = null

const containerRef = ref<HTMLDivElement>()
const stageContainer = ref<HTMLDivElement>()
const shaderCanvasRef = ref<HTMLCanvasElement>()
let shaderOverlay: ShaderOverlay | null = null
const hoveredTile = ref<HexTile | null>(null)
const tooltipStyle = ref({ left: '0px', top: '0px' })

/** 缩放工具栏定义（与 ZOOM_RANGES 同步） */
const zoomLevels = ZOOM_RANGES.map(r => ({
  label: r.key,
  text: r.name,
  scale: r.defaultScale,
}))

/** 当前行政缩放区间 */
const currentZoom = ref('circuit')
/** 缩放区间（响应式） */
const currentZoomRange = ref<ZoomRange>(ZOOM_RANGES[2])

/** 视口状态（由 interaction 驱动），初始用极小值避免 100% 闪现 */
const scale = ref(0.25)
const offsetX = ref(0)
const offsetY = ref(0)

/** 将 interaction 状态同步到 Vue 响应式系统 */
function syncViewport(vp: ViewportState) {
  scale.value = vp.scale
  offsetX.value = vp.offsetX
  offsetY.value = vp.offsetY
}

/** 判断某图层是否可见 */
function isLayerVisible(layerId: string): boolean {
  const layer = props.layers?.[layerId]
  return layer?.visible ?? true
}
/** 获取图层透明度 */
function getLayerOpacity(layerId: string): number {
  const layer = props.layers?.[layerId]
  return layer?.opacity ?? 1.0
}

function factionColor(fid: string): string {
  return FACTION_COLORS[fid] || '#666'
}
function factionName(fid: string): string {
  return FACTION_NAMES[fid] || fid
}
function terrainLabel(terrain: string): string {
  return TERRAIN_NAMES[terrain] || terrain || '平地'
}

function seaDepthLabel(depth: string): string {
  const labels: Record<string, string> = {
    shallow: '浅海',
    moderate: '中海',
    deep: '深海',
    abyssal: '远洋',
  }
  return labels[depth] || depth || '未知'
}

// ==== 多图层着色逻辑 ====

function getBaseFill(tile: HexTile): string {
  // 地形晕染色永远显示
  // 注意：部分旧数据使用 'water' 作为地形key，需要映射到 water_river
  const terrain = tile.terrain === 'water' ? 'water_river' : tile.terrain
  const tColor = TERRAIN_COLORS[terrain] || '#5a4a3a'
  return tColor
}

function getOverlayFill(tile: HexTile): string | null {
  // 势力半透叠加层 (水墨: 低饱和半透明)
  if (isLayerVisible('faction')) {
    const fc = tile.faction_id ? FACTION_LAYER_COLORS[tile.faction_id] : undefined
    if (fc) return fc.color
    if (isLayerVisible('terrain')) return null
    return '#5a524a'
  }
  return null
}

function getTileStroke(tile: HexTile): string {
  if (tile.is_capital) return '#c8a84a'  // 古金
  if (tile.is_pass) return '#8a6a5a'     // 赭石
  if (tile.is_port) return '#6a7a8a'     // 花青
  if (tile.is_ferry) return '#6a7a8a'
  return 'rgba(42,30,20,0.15)'            // 淡墨细笔
}

function getTileStrokeWidth(tile: HexTile): number {
  const base = HEX_RATIO
  if (tile.is_capital) return 1.5 * base
  if (tile.is_port || tile.is_pass || tile.is_ferry) return 1.2 * base
  return 0.5 * base
}

// ==== Konva 初始化 ====

function initKonva() {
  if (!stageContainer.value) return
  if (!Konva) {
    console.error('[HexMapView] Konva 未正确导入，地图不可用')
    return
  }

  const container = stageContainer.value
  const w = container.clientWidth
  const h = container.clientHeight

  stage = new Konva.Stage({ container, width: w, height: h })

  // 多层系统:
  // waterway(水域航道) -> hex(地形+地名) -> claim(法理宣称) ->
  // faction(势力色块) -> building(城建) -> disaster(灾害) -> fog(迷雾) ->
  // boundary(边界) -> overlay(标记) -> garrison(驻防) ->
  // marchRoute(行军路线) -> diplomacy(外交附庸)
  waterwayLayer = new Konva.Layer()
  hexLayer = new Konva.Layer()
  claimLayer = new Konva.Layer()
  factionLayer = new Konva.Layer()
  buildingLayer = new Konva.Layer()
  disasterLayer = new Konva.Layer()
  fogLayer = new Konva.Layer()
  boundaryLayer = new Konva.Layer()
  overlayLayer = new Konva.Layer()
  garrisonLayer = new Konva.Layer()
  marchRouteLayer = new Konva.Layer()
  diplomacyLayer = new Konva.Layer()

  stage.add(waterwayLayer)
  stage.add(hexLayer)
  stage.add(claimLayer)
  stage.add(factionLayer)
  stage.add(buildingLayer)
  stage.add(disasterLayer)
  stage.add(fogLayer)
  stage.add(boundaryLayer)
  stage.add(overlayLayer)
  stage.add(garrisonLayer)
  stage.add(marchRouteLayer)
  stage.add(diplomacyLayer)

  // ============================================================
  // 疆域包围盒 — 标准轴向公式 offsetToAxial + axialToPixel
  // 遍历全部地块算像素包围盒 → 自适应缩放居中铺满
  // ============================================================
  // HEX_SIZE: 固定 64px 基准，确保缩放后六边形视觉清晰
  setHexSize(64)
  if (import.meta.env.DEV) console.log(`[HexMapView] HEX_SIZE: ${HEX_SIZE.toFixed(1)} (比率 ${HEX_RATIO.toFixed(3)})`)

  // 预计算 tile 像素坐标（避免每帧 offsetToAxial+axialToPixel）
  rebuildTilePixelCache()

  // 疆域包围盒 (基于实际 tile，标准轴向坐标)
  let territoryBounds: TerritoryBounds
  if (props.tiles.length > 0) {
    territoryBounds = calculateTerritoryBounds(props.tiles, HEX_SIZE)
  } else {
    // 回退：用全网格估计
    const fw = HEX_SIZE * (1.5 * GRID_MAX_COLS + 0.75 + 2)
    const fh = HEX_HEIGHT * (GRID_ROWS + 1)
    territoryBounds = { minCol: GRID_MIN_COL, maxCol: GRID_MIN_COL + GRID_MAX_COLS - 1, minRow: 0, maxRow: GRID_ROWS - 1, pixelW: fw, pixelH: fh }
  }
  const territoryOrigin = getTerritoryOrigin(territoryBounds, HEX_SIZE)

  // 全网格矩形尺寸（供 CanvasInteraction 边界约束）
  const gridTotalW = HEX_SIZE * (1.5 * GRID_MAX_COLS + 0.75 + 2)
  const gridTotalH = HEX_HEIGHT * (GRID_ROWS + 1)

  // 自适应填满视口：包围盒像素 ÷ 容器像素 → fitScale（100% 即为最小缩放下限）
  const fitScale = calculateFitScale(territoryBounds.pixelW, territoryBounds.pixelH, w, h)
  const startScale = fitScale  // 自适应填满视口，CanvasInteraction 按层控制缩放范围
  const fitOff = calculateFitOffset(
    territoryBounds.pixelW, territoryBounds.pixelH,
    w, h, startScale,
    territoryOrigin.x, territoryOrigin.y,
  )

  if (import.meta.env.DEV) console.log(`[HexMapView] 包围盒: ${territoryBounds.pixelW.toFixed(0)}×${territoryBounds.pixelH.toFixed(0)}px, fitScale=${fitScale.toFixed(4)}, startScale=${startScale.toFixed(4)}, origin=(${territoryOrigin.x.toFixed(1)},${territoryOrigin.y.toFixed(1)})`)

  // ============================================================
  // 初始化 CK3 风格画布交互控制器
  // 初始状态 = fit-to-viewport (疆域包围盒全屏适配模式)
  // ============================================================
  interaction = new CanvasInteraction({
    initialScale: startScale,
    initialOffsetX: fitOff.offsetX,
    initialOffsetY: fitOff.offsetY,
    mapTotalWidth: gridTotalW,
    mapTotalHeight: gridTotalH,
    territoryWidth: territoryBounds.pixelW,
    territoryHeight: territoryBounds.pixelH,
    territoryOriginX: territoryOrigin.x,
    territoryOriginY: territoryOrigin.y,
    containerWidth: w,
    containerHeight: h,
  })

  // 初始视口状态（方案A：铺满适配）
  scale.value = startScale
  offsetX.value = fitOff.offsetX
  offsetY.value = fitOff.offsetY
  currentZoom.value = 'world'
  currentZoomRange.value = ZOOM_RANGES[0]

  // 视口变化 → 同步到 Vue ref + 重绘
  interaction.callbacks.onViewportChange = (vp) => {
    syncViewport(vp)
    renderAll()
  }

  // 缩放区间切换 → 同步 currentZoom
  interaction.callbacks.onZoomRangeChange = (range) => {
    currentZoomRange.value = range
    currentZoom.value = range.key
  }

  // 绑定事件到 DOM
  interaction.attach(container, stageContainer.value)

  // 渲染
  renderAll()

  const resizeObs = new ResizeObserver(() => {
    if (stage && container && interaction) {
      const nw = container.clientWidth
      const nh = container.clientHeight
      stage.width(nw)
      stage.height(nh)
      interaction.updateContainerSize(nw, nh)
      // updateContainerSize 会触发 onViewportChange → renderAll
    }
  })
  resizeObs.observe(container)
}

// ==== 渲染入口 ====

function renderAll() {
  renderHexes()
  renderWaterways()
  renderClaims()
  renderFactionBlocks()
  renderBuildings()
  renderDisasters()
  renderFog()
  renderBoundaries()
  renderOverlayMarkers()
  renderGarrison()
  renderMarchRoutes()
  renderDiplomacy()
}

// ==== 六边形渲染 (仅地形+地名+网格，不含势力着色) ====

function renderHexes() {
  if (!Konva || !hexLayer) return
  hexLayer.destroyChildren()

  const hexW = HEX_SIZE * 2 * scale.value
  const hexH = HEX_HEIGHT * scale.value

  const showTerrain = isLayerVisible('terrain')
  const showGrid = isLayerVisible('hex_grid')

  for (const tile of props.tiles) {
    const cached = tilePixelCache.get(tile.tile_id)
    if (!cached) continue
    const cx = cached.px * scale.value + offsetX.value
    const cy = cached.py * scale.value + offsetY.value

    if (stage && (cx < -hexW || cx > stage.width() + hexW ||
        cy < -hexH || cy > stage.height() + hexH)) continue

    // 地形底色（纯地形晕染，无势力着色）
    let fill: string
    if (tile.terrain === 'sea') {
      // 海域：按深度分色
      const depth = (tile as any).sea_depth || 'moderate'
      fill = SEA_DEPTH_COLORS[depth] || TERRAIN_COLORS['sea'] || '#3a5870'
    } else {
      const terrainKey = tile.terrain === 'water' ? 'water_river' : tile.terrain
      fill = showTerrain ? (TERRAIN_COLORS[terrainKey] || '#b0a080') : '#c4b898'
    }
    const isSelected = tile.tile_id === props.selectedTileId
    const isSea = tile.terrain === 'sea'

    const hex = new Konva.RegularPolygon({
      x: cx, y: cy,
      sides: 6,
      radius: HEX_SIZE * scale.value,
      rotation: 30,
      fill,
      stroke: showGrid ? (isSea ? 'rgba(58,80,100,0.15)' : getTileStroke(tile)) : 'transparent',
      strokeWidth: showGrid ? (isSea ? 0.3 : getTileStrokeWidth(tile)) : 0,
      opacity: 0.98,
      listening: true,
      name: tile.tile_id,
    })

    if (isSelected) {
      applySelectionHighlight(hex, Konva)
    }

    // ============ 势力感知悬停效果 ============
    const playerFid = props.playerFactionId
    const tileFid = tile.faction_id
    const isOwnTile = playerFid && tileFid === playerFid
    const isEnemyTile = playerFid && tileFid && tileFid !== playerFid
    const isNeutralTile = !tileFid

    hex.on('click', () => {
      if (interaction && !interaction.isDragging) {
        emit('tileClick', tile.tile_id)
      }
    })
    hex.on('contextmenu', (e: any) => {
      e.evt.preventDefault()
      emit('tileRightClick', tile.tile_id, e.evt as MouseEvent)
    })
    hex.on('mouseenter', () => {
      if (!stage) return
      const pointer = stage.getPointerPosition()
      if (pointer) {
        tooltipStyle.value = { left: pointer.x + 15 + 'px', top: pointer.y - 10 + 'px' }
      }
      hoveredTile.value = tile
      emit('tileHover', tile)
      if (!isSelected) {
        hex.opacity(1.0)
        // 己方: 亮白描边
        if (isOwnTile) {
          hex.stroke('#FFFFFF')
          hex.strokeWidth(2.2 * HEX_RATIO)
          hex.shadowColor('#FFFFFF')
          hex.shadowBlur(14 * scale.value)
          hex.shadowOpacity(0.55)
          hex.shadowEnabled(true)
        }
        // 敌方: 红边提示
        else if (isEnemyTile) {
          hex.stroke('#C03030')
          hex.strokeWidth(2.0 * HEX_RATIO)
          hex.shadowColor('#C03030')
          hex.shadowBlur(10 * scale.value)
          hex.shadowOpacity(0.40)
          hex.shadowEnabled(true)
        }
        // 无主: 灰色边框
        else if (isNeutralTile) {
          hex.stroke('#8A7A6A')
          hex.strokeWidth(1.5 * HEX_RATIO)
          hex.shadowEnabled(false)
        }
        // 未知（无playerFactionId时）：默认暗影
        else {
          hex.stroke('#1a120a')
          hex.strokeWidth(1.2 * HEX_RATIO)
          hex.shadowColor('#1a120a')
          hex.shadowBlur(10)
          hex.shadowEnabled(true)
        }
      }
    })
    hex.on('mouseleave', () => {
      hoveredTile.value = null
      emit('tileHover', null)
      if (!isSelected) {
        hex.opacity(0.98)
        hex.stroke(showGrid ? getTileStroke(tile) : 'transparent')
        hex.strokeWidth(getTileStrokeWidth(tile))
        hex.shadowEnabled(false)
      }
    })

    hexLayer.add(hex)

    // ============ 古地名文字标注（无六边形编号，仅正式古地名）============
    if (showTerrain) {
      const visibleLabels = getVisibleLabels(scale.value, currentZoom.value)
      let label = ''
      let fontSize = 0
      let labelColor = '#c4b89a'

      if (visibleLabels.includes('prefecture')) {
        const name = tile.tile_name || tile.prefecture
        if (name) {
          if (tile.is_capital || tile.is_strategic) {
            label = name.length > 4 ? name.substring(0, 3) + '…' : name
            fontSize = Math.max(10, 12 * scale.value * HEX_RATIO)
            labelColor = '#c8a84a'
          } else {
            label = name.length > 3 ? name.substring(0, 2) + '…' : name
            fontSize = Math.max(8, 9 * scale.value * HEX_RATIO)
            labelColor = '#c4b89a'
          }
        }
      } else if (visibleLabels.includes('circuit') && tile.is_capital) {
        label = tile.tile_name.replace('·', '')
        fontSize = Math.max(8, 10 * scale.value * HEX_RATIO)
        labelColor = '#c8a84a'
      } else if (visibleLabels.includes('province') && tile.is_capital) {
        label = tile.province || tile.tile_name
        fontSize = Math.max(10, 14 * scale.value * HEX_RATIO)
        labelColor = '#c8a84a'
      }

      if (label && fontSize > 0) {
        const text = new Konva.Text({
          x: cx, y: cy, text: label,
          fontSize,
          fill: labelColor,
          align: 'center',
          verticalAlign: 'middle',
          listening: false,
          stroke: 'rgba(20,15,8,0.55)',
          strokeWidth: 1.2,
        })
        text.offsetX(text.width() / 2)
        text.offsetY(text.height() / 2)
        hexLayer.add(text)
      }
    }
  }
  hexLayer.batchDraw()
}

// ==== 势力着色层渲染 (独立的 factionLayer，可开关) ====

function renderFactionBlocks() {
  if (!Konva || !factionLayer) return
  factionLayer.destroyChildren()

  const showFaction = isLayerVisible('faction')
  if (!showFaction) {
    factionLayer.batchDraw()
    return
  }

  const hexW = HEX_SIZE * 2 * scale.value
  const hexH = HEX_HEIGHT * scale.value

  // 行省视图聚合阈值：使用 currentZoomRange 判断，与 ZOOM_RANGES 保持一致
  const isWorldView = currentZoomRange.value?.key === 'world'

  for (const tile of props.tiles) {
    if (!tile.faction_id) continue

    const cached = tilePixelCache.get(tile.tile_id)
    if (!cached) continue
    const cx = cached.px * scale.value + offsetX.value
    const cy = cached.py * scale.value + offsetY.value

    if (stage && (cx < -hexW || cx > stage.width() + hexW ||
        cy < -hexH || cy > stage.height() + hexH)) continue

    const fc = FACTION_LAYER_COLORS[tile.faction_id]
    const fillColor = fc?.color || FACTION_COLORS[tile.faction_id] || '#9A8A7A'

    const isPlayer = props.playerFactionId && tile.faction_id === props.playerFactionId

    // 行省视图：整片聚合色块（无网格线，高不透明度）
    if (isWorldView) {
      const hex = new Konva.RegularPolygon({
        x: cx, y: cy,
        sides: 6,
        radius: HEX_SIZE * scale.value,
        rotation: 30,
        fill: fillColor,
        stroke: isPlayer ? '#D4A840' : 'rgba(60,30,15,0.15)',
        strokeWidth: isPlayer ? 1.5 * HEX_RATIO : 0.5 * HEX_RATIO,
        opacity: isPlayer ? 0.82 : 0.72,
        listening: false,
      })
      if (isPlayer) {
        hex.shadowColor('#D4A840')
        hex.shadowBlur(6)
        hex.shadowOpacity(0.5)
        hex.shadowEnabled(true)
        hex.shadowForStrokeEnabled(false)
      }
      factionLayer.add(hex)
    } else {
      // 放大视图：半透明水彩色块 + 势力描边
      const hex = new Konva.RegularPolygon({
        x: cx, y: cy,
        sides: 6,
        radius: HEX_SIZE * scale.value,
        rotation: 30,
        fill: fillColor,
        stroke: isPlayer ? '#D4A840' : (fc?.border || '#4A3020'),
        strokeWidth: isPlayer ? 1.8 * HEX_RATIO : 0.8 * HEX_RATIO,
        opacity: isPlayer ? 0.80 : 0.70,
        listening: false,
      })
      if (isPlayer) {
        hex.shadowColor('#D4A840')
        hex.shadowBlur(8)
        hex.shadowOpacity(0.55)
        hex.shadowEnabled(true)
        hex.shadowForStrokeEnabled(false)
      }
      factionLayer.add(hex)
    }
  }
  factionLayer.batchDraw()
}

// ==== 战略标记渲染 (overlay层) ====

/** 计算势力区域中心点（用于大字标注，使用预计算缓存） */
function getFactionCentroid(factionId: string): { x: number; y: number } | null {
  return factionCentroidCache.get(factionId) || null
}

function renderOverlayMarkers() {
  if (!Konva || !overlayLayer) return
  overlayLayer.destroyChildren()

  if (!isLayerVisible('markers')) {
    overlayLayer.batchDraw()
    return
  }

  const hexW = HEX_SIZE * 2 * scale.value
  const hexH = HEX_HEIGHT * scale.value

  for (const tile of props.tiles) {
    if (!tile.is_capital && !tile.is_port && !tile.is_pass && !tile.is_ferry && !tile.is_strategic) continue

    const cached = tilePixelCache.get(tile.tile_id)
    if (!cached) continue
    const cx = cached.px * scale.value + offsetX.value
    const cy = cached.py * scale.value + offsetY.value

    if (stage && (cx < -hexW || cx > stage.width() + hexW ||
        cy < -hexH || cy > stage.height() + hexH)) continue

    let iconCfg: { symbol: string; color: string } | null = null
    let yOff = 0
    if (tile.is_capital) { iconCfg = STRATEGIC_ICONS.capital; yOff = -0.35 }
    else if (tile.is_port) { iconCfg = STRATEGIC_ICONS.port; yOff = -0.25 }
    else if (tile.is_pass) { iconCfg = STRATEGIC_ICONS.pass; yOff = -0.25 }
    else if (tile.is_ferry) { iconCfg = STRATEGIC_ICONS.ferry; yOff = -0.25 }
    else if (tile.is_strategic) { iconCfg = STRATEGIC_ICONS.strategic; yOff = -0.2 }

    if (iconCfg && scale.value >= 0.3 * HEX_RATIO) {
      const isStar = tile.is_capital
      const marker = new Konva.Text({
        x: cx, y: cy + yOff * HEX_SIZE * scale.value,
        text: iconCfg.symbol,
        fontSize: Math.max(isStar ? 14 : 10, (isStar ? 22 : 16) * scale.value * HEX_RATIO),
        fill: iconCfg.color,
        align: 'center',
        listening: false,
      })
      marker.offsetX(marker.width() / 2)
      marker.offsetY(marker.height() / 2)
      // 首府金色五角星加光晕
      if (isStar) {
        marker.shadowColor('#E8C040')
        marker.shadowBlur(8 * scale.value)
        marker.shadowOpacity(0.6)
        marker.shadowEnabled(true)
      }
      overlayLayer.add(marker)
    }
  }
  // 区域大字标注（CK3 风格：在势力区域中心显示大字名称，低缩放时可见）
  // 使用 currentZoomRange 判断而非硬编码阈值，与 ZOOM_RANGES 同步
  const showBigLabels = currentZoomRange.value?.key === 'world' || currentZoomRange.value?.key === 'circuit'
  if (showBigLabels) {
    const factionIds = new Set(props.tiles.map(t => t.faction_id).filter(Boolean) as string[])
    for (const fid of factionIds) {
      const centroid = getFactionCentroid(fid)
      if (!centroid) continue
      const cx = centroid.x * scale.value + offsetX.value
      const cy = centroid.y * scale.value + offsetY.value
      if (stage && (cx < -150 || cx > stage.width() + 150 || cy < -150 || cy > stage.height() + 150)) continue
      const name = FACTION_NAMES[fid] || fid
      const palette = FACTION_PALETTE[fid]
      const color = palette ? palette.primary : '#c4b898'
      const text = new Konva.Text({
        x: cx, y: cy,
        text: name,
        fontSize: 28 * scale.value,
        fontFamily: FONT_FAMILY_TITLE,
        fill: color,
        opacity: 0.22,
        align: 'center',
        verticalAlign: 'middle',
        listening: false,
        fontStyle: 'bold',
        stroke: 'rgba(30,20,10,0.2)',
        strokeWidth: 1,
      })
      text.offsetX(text.width() / 2)
      text.offsetY(text.height() / 2)
      overlayLayer.add(text)
    }
  }

  overlayLayer.batchDraw()
}

// ==== 行政边界渲染 ====

function renderBoundaries() {
  if (!Konva || !boundaryLayer) return
  boundaryLayer.destroyChildren()

  if (!isLayerVisible('boundary') || !props.boundaries) {
    boundaryLayer.batchDraw()
    return
  }

  // CK3 风格：缩放区间驱动边界显示
  const visibleBounds = getVisibleBoundaries(scale.value, currentZoom.value)
  const opacity = getLayerOpacity('boundary')

  const toScreen = (edge: BoundaryEdge) => {
    // 优先使用预计算缓存（将 hex_col_row → col,row）
    const tidA = edge.tile_a.replace('hex_', '').replace('_', ',')
    const tidB = edge.tile_b.replace('hex_', '').replace('_', ',')
    const pA = tilePixelCache.get(tidA)
    const pB = tilePixelCache.get(tidB)
    if (pA && pB) {
      return {
        x: ((pA.px + pB.px) / 2) * scale.value + offsetX.value,
        y: ((pA.py + pB.py) / 2) * scale.value + offsetY.value,
      }
    }
    // 回退：手动计算
    const [colA, rowA] = edge.tile_a.replace('hex_', '').split('_').map(Number)
    const [colB, rowB] = edge.tile_b.replace('hex_', '').split('_').map(Number)
    const axialA = offsetToAxial(colA, rowA)
    const axialB = offsetToAxial(colB, rowB)
    const pxA = axialToPixel(axialA.q, axialA.r, HEX_SIZE)
    const pxB = axialToPixel(axialB.q, axialB.r, HEX_SIZE)
    return {
      x: ((pxA.x + pxB.x) / 2) * scale.value + offsetX.value,
      y: ((pxA.y + pxB.y) / 2) * scale.value + offsetY.value,
    }
  }

  // 行省边界 (浓墨粗笔实线) - 由配置控制
  if (visibleBounds.includes('province')) {
    const provStyle = ADMIN_BOUNDARY_STYLES.province
    const baseR = provStyle.lineWidth * 0.8 * HEX_RATIO
    for (const e of props.boundaries.province_boundaries || []) {
      const p = toScreen(e)
      const circle = new Konva.Circle({
        x: p.x, y: p.y,
        radius: Math.max(1.5, baseR * scale.value),
        fill: provStyle.color,
        opacity: provStyle.opacity,
        listening: false,
      })
      boundaryLayer.add(circle)
    }
  }

  // 路边界 (焦墨中锋虚线) - 由配置控制
  if (visibleBounds.includes('circuit')) {
    const circStyle = ADMIN_BOUNDARY_STYLES.circuit
    const baseR = circStyle.lineWidth * 0.5 * HEX_RATIO
    for (const e of props.boundaries.circuit_boundaries || []) {
      const p = toScreen(e)
      const circle = new Konva.Circle({
        x: p.x, y: p.y,
        radius: Math.max(1.0, baseR * scale.value),
        fill: circStyle.color,
        opacity: circStyle.opacity,
        listening: false,
      })
      boundaryLayer.add(circle)
    }
  }

  // 府州边界 = 六边形格线本身, 由 hexLayer 的 getTileStroke 渲染
  // 缩小时六边形格线自然形成府州边界视觉效果

  boundaryLayer.batchDraw()
}

// ==== 迷雾渲染 ====

function renderFog() {
  if (!Konva || !fogLayer) return
  fogLayer.destroyChildren()

  if (!isLayerVisible('fog')) {
    fogLayer.batchDraw()
    return
  }

  // 构建可见 tile 集合
  const visibleTileIds = props.fogVisibleIds

  if (!visibleTileIds || visibleTileIds.size === 0) {
    // 无视野数据时：全图渐隐雾霭 (水墨渐变)
    if (stage) {
      const sw = stage.width()
      const sh = stage.height()
      // 多层渐变雾霭: 外缘浓, 内淡, 模拟水墨晕染
      const rect = new Konva.Rect({
        x: 0, y: 0, width: sw, height: sh,
        fillLinearGradientStartPoint: { x: 0, y: 0 },
        fillLinearGradientEndPoint: { x: sw, y: sh },
        fillLinearGradientColorStops: [
          0, 'rgba(40,32,18,0.55)',
          0.3, 'rgba(40,32,18,0.35)',
          0.5, 'rgba(40,32,18,0.25)',
          0.7, 'rgba(40,32,18,0.35)',
          1, 'rgba(40,32,18,0.55)',
        ],
        opacity: 0.85,
        listening: false,
      })
      fogLayer.add(rect)
      fogLayer.batchDraw()
    }
    return
  }

  // 按格渲染雾霭: 未可见格 → 渐隐水墨遮罩
  const hexW = HEX_SIZE * 2 * scale.value
  const hexH = HEX_HEIGHT * scale.value
  for (const tile of props.tiles) {
    if (visibleTileIds.has(tile.tile_id)) continue

    const cached = tilePixelCache.get(tile.tile_id)
    if (!cached) continue
    const cx = cached.px * scale.value + offsetX.value
    const cy = cached.py * scale.value + offsetY.value

    if (stage && (cx < -hexW || cx > stage.width() + hexW ||
        cy < -hexH || cy > stage.height() + hexH)) continue

    // 雾霭六边形: 浓墨渐变, 内淡外浓
    const fog = new Konva.RegularPolygon({
      x: cx, y: cy,
      sides: 6,
      radius: HEX_SIZE * scale.value,
      rotation: 30,
      fillRadialGradientStartPoint: { x: 0, y: 0 },
      fillRadialGradientStartRadius: 0,
      fillRadialGradientEndPoint: { x: 0, y: 0 },
      fillRadialGradientEndRadius: HEX_SIZE * scale.value,
      fillRadialGradientColorStops: [
        0, 'rgba(35,25,12,0.50)',
        0.6, 'rgba(35,25,12,0.30)',
        1, 'rgba(35,25,12,0.50)',
      ],
      opacity: 0.80,
      listening: false,
    })
    fogLayer.add(fog)
  }
  fogLayer.batchDraw()
}

// ================================================================
// 新增渲染层 v2.0
// ================================================================

// ==== 水域航道渲染 ====
function renderWaterways() {
  if (!Konva || !waterwayLayer) return
  waterwayLayer.destroyChildren()
  if (!isLayerVisible('waterway') || !props.waterRoutes || props.waterRoutes.length === 0) {
    waterwayLayer.batchDraw(); return
  }
  const opacity = getLayerOpacity('waterway')

  for (const route of props.waterRoutes) {
    const pts: number[] = []
    for (const tid of route.path) {
      const cached = tilePixelCache.get(tid)
      if (!cached) continue
      pts.push(cached.px * scale.value + offsetX.value)
      pts.push(cached.py * scale.value + offsetY.value)
    }
    if (pts.length < 4) continue

    const line = new Konva.Line({
      points: pts,
      stroke: '#4A8090',
      strokeWidth: Math.max(1.2, 3.0 * scale.value * HEX_RATIO),
      lineCap: 'round',
      lineJoin: 'round',
      opacity: opacity * 0.6,
      dash: [10, 6],
      listening: false,
    })
    waterwayLayer.add(line)
  }
  waterwayLayer.batchDraw()
}

// ==== 法理宣称渲染 ====
function renderClaims() {
  if (!Konva || !claimLayer) return
  claimLayer.destroyChildren()
  if (!isLayerVisible('claim') || !props.claimTiles || props.claimTiles.size === 0) {
    claimLayer.batchDraw(); return
  }
  const opacity = getLayerOpacity('claim')
  const hexW = HEX_SIZE * 2 * scale.value
  const hexH = HEX_HEIGHT * scale.value

  for (const tile of props.tiles) {
    if (!props.claimTiles.has(tile.tile_id)) continue
    const cached = tilePixelCache.get(tile.tile_id)
    if (!cached) continue
    const cx = cached.px * scale.value + offsetX.value
    const cy = cached.py * scale.value + offsetY.value
    if (stage && (cx < -hexW || cx > stage.width() + hexW || cy < -hexH || cy > stage.height() + hexH)) continue

    // 半透金纹覆盖
    const claimHex = new Konva.RegularPolygon({
      x: cx, y: cy, sides: 6,
      radius: HEX_SIZE * scale.value * 0.85,
      rotation: 30,
      fill: '#C8A840',
      stroke: '#8A7020',
      strokeWidth: 1.2 * HEX_RATIO,
      opacity: opacity * 0.3,
      listening: false,
    })
    claimLayer.add(claimHex)
  }
  claimLayer.batchDraw()
}

// ==== 城建建筑渲染 ====
function renderBuildings() {
  if (!Konva || !buildingLayer) return
  buildingLayer.destroyChildren()
  if (!isLayerVisible('building') || !props.buildingData) {
    buildingLayer.batchDraw(); return
  }
  const opacity = getLayerOpacity('building')
  const hexW = HEX_SIZE * 2 * scale.value
  const hexH = HEX_HEIGHT * scale.value
  const iconMap: Record<string, string> = { workshop: '🔨', port: '⚓', wall: '🏰', granary: '🏚', stable: '🐴' }

  for (const tile of props.tiles) {
    const buildings = props.buildingData[tile.tile_id]
    if (!buildings || buildings.length === 0) continue
    const cached = tilePixelCache.get(tile.tile_id)
    if (!cached) continue
    const cx = cached.px * scale.value + offsetX.value
    const cy = cached.py * scale.value + offsetY.value
    if (stage && (cx < -hexW || cx > stage.width() + hexW || cy < -hexH || cy > stage.height() + hexH)) continue

    let yOff = 0.45
    for (const b of buildings) {
      const icon = iconMap[b.type] || '🏯'
      const text = new Konva.Text({
        x: cx, y: cy + yOff * HEX_SIZE * scale.value,
        text: b.type === 'wall' ? `${icon}${b.level}` : icon,
        fontSize: Math.max(9, 13 * scale.value * HEX_RATIO),
        fill: '#D4C090',
        align: 'center', listening: false,
        stroke: 'rgba(20,15,8,0.6)', strokeWidth: 0.8,
        opacity,
      })
      text.offsetX(text.width() / 2)
      text.offsetY(text.height() / 2)
      buildingLayer.add(text)
      yOff += 0.25
    }
  }
  buildingLayer.batchDraw()
}

// ==== 灾害动乱渲染 ====
function renderDisasters() {
  if (!Konva || !disasterLayer) return
  disasterLayer.destroyChildren()
  if (!isLayerVisible('disaster') || !props.disasterTiles) {
    disasterLayer.batchDraw(); return
  }
  const opacity = getLayerOpacity('disaster')
  const hexW = HEX_SIZE * 2 * scale.value
  const hexH = HEX_HEIGHT * scale.value
  const iconMap: Record<string, string> = {
    flood: '🌊', drought: '☀', locust: '🦗', plague: '☠',
    war_devastation: '💥', rebellion: '🔥', famine: '🌾',
  }

  for (const tile of props.tiles) {
    const disasters = props.disasterTiles[tile.tile_id]
    if (!disasters || disasters.length === 0) continue
    const cached = tilePixelCache.get(tile.tile_id)
    if (!cached) continue
    const cx = cached.px * scale.value + offsetX.value
    const cy = cached.py * scale.value + offsetY.value
    if (stage && (cx < -hexW || cx > stage.width() + hexW || cy < -hexH || cy > stage.height() + hexH)) continue

    for (const d of disasters) {
      const icon = iconMap[d.type] || '⚠'
      const severityText = d.severity >= 0.8 ? '‼' : d.severity >= 0.5 ? '!' : ''
      const text = new Konva.Text({
        x: cx, y: cy + (0.2 * HEX_SIZE * scale.value),
        text: icon + severityText,
        fontSize: Math.max(10, 16 * scale.value * HEX_RATIO),
        fill: d.severity >= 0.5 ? '#E04040' : '#E08040',
        align: 'center', listening: false,
        shadowColor: d.severity >= 0.5 ? '#FF2020' : '#FF8030',
        shadowBlur: 6 * scale.value, shadowOpacity: 0.5, shadowEnabled: true,
        opacity,
      })
      text.offsetX(text.width() / 2)
      text.offsetY(text.height() / 2)
      disasterLayer.add(text)
    }
  }
  disasterLayer.batchDraw()
}

// ==== 兵力驻防渲染 ====
function renderGarrison() {
  if (!Konva || !garrisonLayer) return
  garrisonLayer.destroyChildren()
  if (!isLayerVisible('garrison') || !props.garrisonData) {
    garrisonLayer.batchDraw(); return
  }
  const opacity = getLayerOpacity('garrison')
  const hexW = HEX_SIZE * 2 * scale.value
  const hexH = HEX_HEIGHT * scale.value

  for (const tile of props.tiles) {
    const g = props.garrisonData[tile.tile_id]
    if (!g) continue
    const cached = tilePixelCache.get(tile.tile_id)
    if (!cached) continue
    const cx = cached.px * scale.value + offsetX.value
    const cy = cached.py * scale.value + offsetY.value
    if (stage && (cx < -hexW || cx > stage.width() + hexW || cy < -hexH || cy > stage.height() + hexH)) continue

    const troopText = g.troops >= 1000 ? `${(g.troops / 1000).toFixed(1)}k` : String(g.troops)
    const color = g.resting ? '#8AE' : '#F88'
    const text = new Konva.Text({
      x: cx, y: cy + 0.55 * HEX_SIZE * scale.value,
      text: g.resting ? `🛡${troopText}` : `⚔${troopText}`,
      fontSize: Math.max(9, 12 * scale.value * HEX_RATIO),
      fill: color,
      align: 'center', listening: false,
      stroke: 'rgba(10,5,2,0.7)', strokeWidth: 1.0,
      opacity,
    })
    text.offsetX(text.width() / 2)
    text.offsetY(text.height() / 2)
    garrisonLayer.add(text)
  }
  garrisonLayer.batchDraw()
}

// ==== 行军路线渲染 ====
function renderMarchRoutes() {
  if (!Konva || !marchRouteLayer) return
  marchRouteLayer.destroyChildren()
  if (!isLayerVisible('march_route') && !isLayerVisible('supply_line')) {
    marchRouteLayer.batchDraw(); return
  }

  // 行军路线
  if (isLayerVisible('march_route') && props.marchRoutes) {
    const opacity = getLayerOpacity('march_route')
    for (const route of props.marchRoutes) {
      const pts: number[] = []
      for (const tid of route.path) {
        const cached = tilePixelCache.get(tid)
        if (!cached) continue
        pts.push(cached.px * scale.value + offsetX.value)
        pts.push(cached.py * scale.value + offsetY.value)
      }
      if (pts.length < 4) continue

      const color = route.color || (route.type === 'retreat' ? '#E06040' : '#D4A040')
      const line = new Konva.Line({
        points: pts, stroke: color,
        strokeWidth: Math.max(2, 4.5 * scale.value * HEX_RATIO),
        lineCap: 'round', lineJoin: 'round',
        opacity: route.type === 'retreat' ? opacity * 0.65 : opacity,
        dash: route.type === 'retreat' ? [8, 6] : [],
        listening: false,
      })
      marchRouteLayer.add(line)

      // 箭头标记（每3个点画一个箭头）
      for (let i = 0; i < pts.length - 4; i += 6) {
        const arrow = new Konva.Arrow({
          points: [pts[i], pts[i + 1], pts[i + 2], pts[i + 3]],
          pointerLength: Math.max(6, 12 * scale.value * HEX_RATIO),
          pointerWidth: Math.max(4, 8 * scale.value * HEX_RATIO),
          fill: color, stroke: color,
          strokeWidth: 1.5, opacity: opacity * 0.8,
          listening: false,
        })
        marchRouteLayer.add(arrow)
      }
    }
  }

  // 补给线
  if (isLayerVisible('supply_line') && props.supplyLines) {
    const opacity = getLayerOpacity('supply_line')
    for (const sl of props.supplyLines) {
      const pts: number[] = []
      for (const tid of sl.path) {
        const cached = tilePixelCache.get(tid)
        if (!cached) continue
        pts.push(cached.px * scale.value + offsetX.value)
        pts.push(cached.py * scale.value + offsetY.value)
      }
      if (pts.length < 4) continue

      const line = new Konva.Line({
        points: pts,
        stroke: sl.broken ? '#E03030' : '#6A9A4A',
        strokeWidth: Math.max(1.5, 3.0 * scale.value * HEX_RATIO),
        lineCap: 'round', lineJoin: 'round',
        opacity: sl.broken ? opacity * 0.9 : opacity * 0.55,
        dash: sl.broken ? [5, 3] : [10, 5],
        listening: false,
      })
      marchRouteLayer.add(line)
    }
  }
  marchRouteLayer.batchDraw()
}

// ==== 外交附庸连线渲染 ====
function renderDiplomacy() {
  if (!Konva || !diplomacyLayer) return
  diplomacyLayer.destroyChildren()
  if (!isLayerVisible('diplomacy_line') || !props.diplomacyRelations || props.diplomacyRelations.length === 0) {
    diplomacyLayer.batchDraw(); return
  }
  const opacity = getLayerOpacity('diplomacy_line')

  // 找到每个势力的首都地块作为连线端点
  const factionCapitals: Record<string, { cx: number; cy: number }> = {}
  for (const tile of props.tiles) {
    if (tile.is_capital && tile.faction_id) {
      const cached = tilePixelCache.get(tile.tile_id)
      if (!cached) continue
      factionCapitals[tile.faction_id] = {
        cx: cached.px * scale.value + offsetX.value,
        cy: cached.py * scale.value + offsetY.value,
      }
    }
  }

  for (const rel of props.diplomacyRelations) {
    const fromCap = factionCapitals[rel.from]
    const toCap = factionCapitals[rel.to]
    if (!fromCap || !toCap) continue

    const styleMap: Record<string, { color: string; dash: number[] }> = {
      vassal: { color: '#C8A840', dash: [8, 4] },
      alliance: { color: '#5AAA5A', dash: [] },
      war: { color: '#E04040', dash: [5, 3] },
      trade: { color: '#7AB8D0', dash: [3, 3] },
    }
    const style = styleMap[rel.type] || styleMap.trade

    const line = new Konva.Arrow({
      points: [fromCap.cx, fromCap.cy, toCap.cx, toCap.cy],
      pointerLength: Math.max(6, 12 * scale.value * HEX_RATIO),
      pointerWidth: Math.max(4, 8 * scale.value * HEX_RATIO),
      fill: style.color, stroke: style.color,
      strokeWidth: Math.max(1.5, 2.5 * scale.value * HEX_RATIO),
      opacity: opacity * 0.6,
      dash: style.dash,
      listening: false,
    })
    diplomacyLayer.add(line)
  }
  diplomacyLayer.batchDraw()
}

// ==== 交互 ====

function setZoomLevel(levelKey: string) {
  interaction?.setZoomLevel(levelKey)
}

function resetView() {
  interaction?.resetView()
}

function zoomIn() {
  interaction?.zoomIn()
}

function zoomOut() {
  interaction?.zoomOut()
}

onMounted(() => {
  nextTick(() => {
    initKonva()
    // 初始化着色器叠加层 V2.0（WebGL2 不可用时静默降级）
    if (shaderCanvasRef.value) {
      shaderOverlay = new ShaderOverlay(shaderCanvasRef.value)
      shaderOverlay.intensity = 0.55      // 总强度，不喧宾夺主
      shaderOverlay.vignette = 0.65       // 域扭曲暗角
      shaderOverlay.grainNoise = 0.50     // 竹简噪点
      shaderOverlay.glow = 0.60           // 烛光微光
      shaderOverlay.weathering = 0.40     // 边缘做旧
      shaderOverlay.inkBleed = 0.35       // Voronoi 墨点
      shaderOverlay.cloudMotif = 0.45     // 云纹
      shaderOverlay.waterRipple = 0.30    // 水纹
      shaderOverlay.start()
    }
  })
})

onUnmounted(() => {
  interaction?.destroy()
  interaction = null
  stage?.destroy()
  // 清理着色器叠加层
  shaderOverlay?.destroy()
  shaderOverlay = null
})

// 监听数据变化
watch(() => props.selectedTileId, () => renderAll())
watch(() => props.tiles.length, () => { if (props.tiles.length > 0) { rebuildTilePixelCache(); renderAll() } })
watch(() => props.layers, () => renderAll(), { deep: true })
watch(() => props.boundaries, () => renderAll())

defineExpose({ resetView, setZoomLevel, zoomIn, zoomOut, scale })
</script>

<style scoped>
.hex-map-container {
  width: 100%; height: 100%;
  position: relative;
  z-index: 1;                        /* 确保在 ::before 装饰层之上 */
  overflow: hidden;
  background: #c4b898;               /* 暖羊皮纸底色 */
  cursor: grab;
}
.hex-map-container:active { cursor: grabbing; }
.stage-container { width: 100%; height: 100%; }

/* 着色器叠加层 V2.0 (WebGL2 后处理) */
.shader-overlay {
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  z-index: 2;
  pointer-events: none;              /* 不拦截任何鼠标事件 */
  mix-blend-mode: overlay;           /* 深色乘法加深 + 浅色屏幕提亮 */
  opacity: 0.62;                     /* 效果强度（中调底色增强后适度提升） */
}

/* 快捷图层模式切换栏 */
.layer-panel {
  position: absolute;
  top: 10px; left: 10px;
  background: rgba(15, 12, 8, 0.78);
  border: 1px solid rgba(180, 150, 100, 0.12);
  border-radius: 4px;
  padding: 4px 6px;
  z-index: 10;
  backdrop-filter: blur(4px);
}
.layer-mode-btns {
  display: flex; gap: 3px;
}
.layer-mode-btns button {
  padding: 3px 7px; font-size: 14px;
  background: transparent; border: 1px solid rgba(180, 150, 100, 0.1);
  border-radius: 3px; color: #8a8060; cursor: pointer;
  line-height: 1;
}
.layer-mode-btns button:hover { background: rgba(200, 168, 74, 0.1); color: #c8a84a; }




/* 悬停提示 - 古卷题签（支持tooltipDelay配置） */
.hex-tooltip {
  position: absolute;
  background: rgba(15, 12, 8, 0.88);
  color: #c4b89a;
  border: 1px solid rgba(200, 168, 74, 0.25);
  border-radius: 4px;
  padding: 8px 12px; font-size: 13px; pointer-events: none; z-index: 20;
  min-width: 140px; line-height: 1.5;
  box-shadow: 0 2px 12px rgba(0,0,0,0.5);
  opacity: 0;
  transition: opacity 0.12s ease;
  transition-delay: var(--tooltip-delay, 300ms);
}
.hex-tooltip--visible {
  opacity: 1;
}
.tooltip-name { color: #c8a84a; font-weight: bold; font-size: 14px; }
.tooltip-info { color: #8a8068; font-size: 11px; }
.tooltip-faction { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; color: #c8a84a; font-weight: bold; font-size: 14px; }
.faction-dot { width: 10px; height: 10px; border-radius: 50%; }
.faction-label { color: #d4b06a; }
.tooltip-terrain { font-size: 11px; color: #8a8068; margin-top: 2px; }
.terrain-stat { margin-left: 8px; color: #7a6a52; }
.tooltip-badges { margin-top: 3px; display: flex; flex-wrap: wrap; gap: 2px; }
.tooltip-badge {
  font-size: 10px; padding: 1px 5px; border-radius: 3px; display: inline-block;
}
.tooltip-badge.capital   { background: rgba(200, 168, 74, 0.15); color: #c8a84a; }
.tooltip-badge.port      { background: rgba(122, 138, 146, 0.15); color: #7a8a92; }
.tooltip-badge.pass      { background: rgba(138, 106, 90, 0.15); color: #8a6a5a; }
.tooltip-badge.ferry     { background: rgba(106, 122, 138, 0.15); color: #6a7a8a; }
.tooltip-badge.coastal   { background: rgba(122, 138, 130, 0.15); color: #7a8a82; }
.tooltip-badge.strategic { background: rgba(122, 106, 82, 0.15); color: #7a6a52; }
.terrain-water { color: #5a788a; }

/* 海域tooltip样式 */
.tooltip-sea-header {
  display: flex; align-items: center; gap: 6px; margin-bottom: 3px;
}
.sea-icon { font-size: 14px; }
.tooltip-badge.deepsea   { background: rgba(58, 88, 112, 0.2); color: #5a88a0; }
.tooltip-badge.abyssal   { background: rgba(26, 48, 64, 0.25); color: #3a6880; }
</style>