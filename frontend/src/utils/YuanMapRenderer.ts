/**
 * 疆域 Canvas 渲染器 - 14 层渲染管线 (Canvas2D)
 *
 * 按沙盘地图系统文档 v3.0 重构，14 层渲染顺序（从底到顶）：
 *   [ 1] 宣纸纹理  — 羊皮纸/宣纸底纹，古风氛围
 *   [ 2] 水域航道  — 海域按深度分色 + 贸易航线
 *   [ 3] 地形底色  — 11 种陆地地形颜色填充
 *   [ 4] 法理宣称  — De Jure 领土边界高亮
 *   [ 5] 势力着色  — 当前控制势力颜色覆盖（半透）
 *   [ 6] 城建建筑  — 城防等级/建筑标记
 *   [ 7] 灾害标记  — 瘟疫/洪水/蝗灾覆盖
 *   [ 8] 迷雾      — 战争迷雾/视野系统
 *   [ 9] 边界线    — 行省界 + 路界 + 势力边界
 *   [10] 战略标记  — 首都★/港口◎/关隘▲/渡口~/据点●
 *   [11] 驻防兵力  — 各城池驻军数量标记
 *   [12] 行军路线  — 军队移动路径可视化
 *   [13] 外交连线  — 同盟/交战/朝贡关系连线
 *   [14] UI 叠加层 — 选中高亮/悬停提示/HUD
 *
 * 使用方式:
 *   const renderer = new YuanMapCanvasRenderer(ctx, provider, factionLayers)
 *   // 每帧渲染:
 *   renderer.renderFrame(viewport, zoomRange, selectedTileId)
 */

import type { TerritoryDataProvider, TerritoryTile, BoundaryEdge } from './TerritoryDataProvider'
import type { FactionLayerManager, FactionColorResult } from './FactionLayerManager'
import type { ViewportState } from './CanvasInteraction'
import type { ZoomRange } from './mapInteractionConfig'
import { ZOOM_RANGES } from './mapInteractionConfig'
import {
  HEX_SIZE, HEX_WIDTH, HEX_HEIGHT,
  offsetToAxial,
  GRID_MAX_COLS,
  TERRAIN_COLORS as hexTerrainColors,
} from './flatTopHexUtils'
import { TERRAIN_COLORS } from './layerUtils'

// ============================================================
// 渲染配置
// ============================================================

export interface RenderConfig {
  /** 视口 padding (像素), 用于裁剪容差 */
  viewportPadding: number
  /** 六边形边框颜色 */
  hexStrokeColor: string
  /** 六边形边框透明度 */
  hexStrokeAlpha: number
  /** 六边形边框宽度 */
  hexStrokeWidth: number
  /** 缩小比例阈值 - 低于此值不绘制六边形边框 */
  hexGridMinScale: number
  /** 边界线宽度 */
  boundaryWidth: Record<string, number>
  /** 边界线颜色 */
  boundaryColor: Record<string, string>
  /** 边界线虚线样式 */
  boundaryDash: Record<string, number[]>
  /** 缩小比例阈值 - 低于此值不绘制边界标签 */
  boundaryLabelMinScale: Record<string, number>
  /** 首都标记半径 */
  capitalRadius: number
  /** 港口标记半径 */
  portRadius: number
  /** 关隘标记尺寸 */
  passSize: number
  /** 选中辉光颜色 */
  selectionGlowColor: string
  /** 选中辉光模糊 */
  selectionGlowBlur: number
  /** 选中边框颜色 */
  selectionStrokeColor: string
  /** 选中边框宽度 */
  selectionStrokeWidth: number
}

export const DEFAULT_RENDER_CONFIG: RenderConfig = {
  viewportPadding: 300,
  hexStrokeColor: '#3a3028',      // 淡墨细笔网格线
  hexStrokeAlpha: 0.25,
  hexStrokeWidth: 0.8,
  hexGridMinScale: 0.5,
  boundaryWidth: {
    province: 3.2,                  // 行省: 浓墨粗笔
    circuit: 2.0,                   // 路: 淡墨中锋
    prefecture: 1.2,
  },
  boundaryColor: {
    province: '#3a2a1a',            // 行省: 浓墨
    circuit: '#5a4a32',             // 路: 淡墨
    prefecture: '#6a5a42',
  },
  boundaryDash: {
    province: [],                   // 行省: 实笔
    circuit: [10, 6],               // 路: 虚笔
    prefecture: [4, 5],
  },
  boundaryLabelMinScale: {
    province: 0.15,
    circuit: 0.5,
    prefecture: 0.9,
  },
  capitalRadius: 6,
  portRadius: 4,
  passSize: 5,
  selectionGlowColor: 'rgba(200, 168, 74, 0.35)',   // 选中: 古金辉光
  selectionGlowBlur: 14,
  selectionStrokeColor: '#c8a84a',                    // 选中: 金描边
  selectionStrokeWidth: 2.5,
}

// ============================================================
// 预计算常量
// ============================================================

const HEX_COS_SIN = [0, 1, 2, 3, 4, 5].map(i => {
  const angle = (60 * i) * Math.PI / 180
  return { cos: Math.cos(angle), sin: Math.sin(angle) }
})

// ============================================================
// 主类
// ============================================================

export class YuanMapCanvasRenderer {
  private _ctx: CanvasRenderingContext2D
  private _provider: TerritoryDataProvider
  private _factionLayers: FactionLayerManager
  private _config: RenderConfig
  private _canvasW = 0
  private _canvasH = 0

  /** 预计算六边形顶点 (按 tile_id 缓存) */
  private _hexVertexCache: Map<string, { x: number; y: number }[]> = new Map()

  /** 上次渲染的 scale (用于判断是否需要重建缓存) */
  private _lastRenderScale = 0

  constructor(
    ctx: CanvasRenderingContext2D,
    provider: TerritoryDataProvider,
    factionLayers: FactionLayerManager,
    config?: Partial<RenderConfig>,
  ) {
    this._ctx = ctx
    this._provider = provider
    this._factionLayers = factionLayers
    this._config = { ...DEFAULT_RENDER_CONFIG, ...config }
  }

  // ============================================================
  // 尺寸管理
  // ============================================================

  /** 更新画布尺寸 */
  setCanvasSize(w: number, h: number) {
    this._canvasW = w
    this._canvasH = h
  }

  /** 更新配置 */
  updateConfig(config: Partial<RenderConfig>) {
    Object.assign(this._config, config)
  }

  // ============================================================
  // 帧渲染
  // ============================================================

  /**
   * 渲染完整一帧 (14 层管线)
   */
  renderFrame(
    viewport: ViewportState,
    zoomRange: ZoomRange,
    selectedTileId?: string | null,
  ) {
    const ctx = this._ctx
    const { scale, offsetX, offsetY } = viewport
    const { viewportPadding } = this._config

    // 清空画布
    ctx.clearRect(0, 0, this._canvasW, this._canvasH)
    ctx.save()

    // 应用视口变换
    ctx.translate(offsetX, offsetY)
    ctx.scale(scale, scale)

    // 视口裁剪范围 (世界坐标)
    const clipLeft = -offsetX / scale - viewportPadding
    const clipTop = -offsetY / scale - viewportPadding
    const clipRight = (-offsetX + this._canvasW) / scale + viewportPadding
    const clipBottom = (-offsetY + this._canvasH) / scale + viewportPadding

    // [ 1] 宣纸纹理 — 古朴羊皮纸底纹
    this._renderParchmentLayer()

    // [ 2] 水域航道 — 海域深度分色
    this._renderWaterwaysLayer(clipLeft, clipTop, clipRight, clipBottom)

    // [ 3] 地形底色 — 11 种陆地地形填充
    this._renderTerrainLayer(clipLeft, clipTop, clipRight, clipBottom)

    // [ 4] 法理宣称 — De Jure 边界高亮 (低透明度)
    this._renderDeJureLayer(clipLeft, clipTop, clipRight, clipBottom)

    // [ 5] 势力着色 — 当前势力颜色覆盖
    this._renderFactionLayer(clipLeft, clipTop, clipRight, clipBottom)

    // [ 6] 城建建筑 — 城防/建筑标记
    this._renderCityBuildingsLayer(clipLeft, clipTop, clipRight, clipBottom)

    // [ 7] 灾害标记 — 瘟疫/洪水/蝗灾覆盖
    this._renderDisastersLayer(clipLeft, clipTop, clipRight, clipBottom)

    // [ 8] 迷雾 — 战争迷雾（暂用 overlay 方式）
    this._renderFogLayer(clipLeft, clipTop, clipRight, clipBottom)

    // [ 9] 边界线 — 行省界 + 路界 + 势力边界
    this._renderBoundaries(zoomRange.showBoundaries, scale)

    // [10] 六边形网格线
    if (scale >= this._config.hexGridMinScale) {
      this._renderHexGrid(clipLeft, clipTop, clipRight, clipBottom)
    }

    // [10] 战略标记 — 首都/港口/关隘/渡口/据点
    if (zoomRange.showMarkers) {
      this._renderMarkers(clipLeft, clipTop, clipRight, clipBottom)
    }

    // [11] 驻防兵力 — 各城池驻军标记
    this._renderGarrisonsLayer(clipLeft, clipTop, clipRight, clipBottom)

    // [12] 行军路线 — 军队移动路径
    this._renderMarchRoutesLayer()

    // [13] 外交连线 — 同盟/交战/朝贡关系线
    this._renderDiplomaticLinksLayer()

    // [14] UI 叠加层 — 选中高亮
    if (selectedTileId) {
      this._renderSelection(selectedTileId)
    }

    ctx.restore()
  }

  // ============================================================
  // 14 层渲染子方法
  // ============================================================

  /**
   * [ 1] 宣纸纹理 — 古朴羊皮纸/宣纸底纹，营造古风氛围
   */
  private _renderParchmentLayer() {
    const ctx = this._ctx
    // 暖色调底色，模拟宣纸/羊皮纸质感
    ctx.fillStyle = 'rgba(228, 215, 185, 0.12)'
    ctx.fillRect(-5000, -5000, 10000, 10000)
  }

  /**
   * [ 2] 水域航道 — 海域按深度分色 + 贸易航线
   */
  private _renderWaterwaysLayer(
    clipL: number, clipT: number, clipR: number, clipB: number,
  ) {
    const ctx = this._ctx
    const tiles = this._provider.getAllTiles()

    for (const tile of tiles) {
      if (!this._isTileVisible(tile, clipL, clipT, clipR, clipB)) continue
      if (tile.terrain !== 'sea') continue

      const cx = tile.pixel_x
      const cy = tile.pixel_y
      const seaTile = tile as any

      // 水深分色 (4级: 浅海/中海/深海/远洋)
      const depthColors: Record<string, string> = {
        shallow: '#5a8090',
        moderate: '#4a6a80',
        deep: '#3a5a70',
        abyssal: '#1a3040',
      }
      const color = depthColors[seaTile.sea_depth] || '#3a5a70'
      this._drawHex(cx, cy, color, 0.8)
    }
  }

  /**
   * [ 3] 地形底色 — 11 种地形颜色填充
   */
  private _renderTerrainLayer(
    clipL: number, clipT: number, clipR: number, clipB: number,
  ) {
    const ctx = this._ctx
    const tiles = this._provider.getAllTiles()

    for (const tile of tiles) {
      if (!this._isTileVisible(tile, clipL, clipT, clipR, clipB)) continue
      const cx = tile.pixel_x
      const cy = tile.pixel_y
      const color = TERRAIN_COLORS[tile.terrain] || hexTerrainColors[tile.terrain] || '#5a4a3a'

      this._drawHex(cx, cy, color, 1)
    }
  }

  /**
   * 势力着色层
   */
  private _renderFactionLayer(
    clipL: number, clipT: number, clipR: number, clipB: number,
  ) {
    const ctx = this._ctx

    // 按势力分组批量绘制
    const factions = this._factionLayers.getRegisteredFactions()
    for (const fid of factions) {
      const layer = this._factionLayers.getLayer(fid)
      if (!layer || !layer.visible) continue

      for (const tid of layer.tileIds) {
        const tile = this._provider.getTile(tid)
        if (!tile || !this._isTileVisible(tile, clipL, clipT, clipR, clipB)) continue

        const cx = tile.pixel_x
        const cy = tile.pixel_y
        const colorResult = this._factionLayers.getTileColor(tid)

        // 墨韵叠加: 地形晕染 65% 底色 + 势力半透 35%
        const terrainColor = TERRAIN_COLORS[tile.terrain] || hexTerrainColors[tile.terrain] || '#5a4a3a'
        this._drawHex(cx, cy, terrainColor, 0.65)
        // _drawHex 内部会设置 globalAlpha，使用传入的 alpha 值，
        // 外层不再叠加 globalAlpha 避免双重乘法
        this._drawHex(cx, cy, colorResult.color, colorResult.opacity * 0.45)

        // 高亮辉光 (古金色)
        if (colorResult.glowIntensity > 0) {
          this._drawHexGlow(cx, cy, colorResult.glowColor, colorResult.glowIntensity)
        }

        ctx.globalAlpha = 1
      }
    }
  }

  /**
   * 六边形网格线
   */
  private _renderHexGrid(
    clipL: number, clipT: number, clipR: number, clipB: number,
  ) {
    const ctx = this._ctx
    const { hexStrokeColor, hexStrokeAlpha, hexStrokeWidth } = this._config

    ctx.strokeStyle = hexStrokeColor
    ctx.globalAlpha = hexStrokeAlpha
    ctx.lineWidth = hexStrokeWidth

    const tiles = this._provider.getAllTiles()
    for (const tile of tiles) {
      if (!this._isTileVisible(tile, clipL, clipT, clipR, clipB)) continue
      this._strokeHex(tile.pixel_x, tile.pixel_y)
    }

    ctx.globalAlpha = 1
  }

  /**
   * 行政边界线
   * BoundaryEdge 包含 tile_a/tile_b 的 tile_id，通过 tile 的 pixel 坐标
   * 计算相邻六边形共享边的中点来绘制真正的边界线
   */
  private _renderBoundaries(levels: string[], scale: number) {
    const ctx = this._ctx

    for (const level of levels) {
      const edges = this._getBoundaryEdges(level)
      if (!edges.length) continue

      const bw = this._config.boundaryWidth[level] || 1.5
      const color = this._config.boundaryColor[level] || '#999'
      const dash = this._config.boundaryDash[level] || []

      ctx.strokeStyle = color
      ctx.lineWidth = bw
      ctx.setLineDash(dash)
      ctx.beginPath()

      for (const edge of edges) {
        // 优先用 tile_a/tile_b 的像素坐标计算共享边中点
        const tileA = this._provider.getTile(edge.tile_a)
        const tileB = this._provider.getTile(edge.tile_b)

        if (tileA && tileB) {
          // 两个相邻瓦片中心的中点 = 共享边的中点
          const mx = (tileA.pixel_x + tileB.pixel_x) / 2
          const my = (tileA.pixel_y + tileB.pixel_y) / 2
          ctx.moveTo(mx, my - 0.5)
          ctx.lineTo(mx, my + 0.5)
        } else {
          // 回退：使用 BoundaryEdge 自身的 x/y
          ctx.moveTo(edge.x, edge.y - 0.5)
          ctx.lineTo(edge.x, edge.y + 0.5)
        }
      }

      ctx.stroke()
      ctx.setLineDash([])
    }
  }

  /**
   * 特殊标记
   */
  private _renderMarkers(
    clipL: number, clipT: number, clipR: number, clipB: number,
  ) {
    const ctx = this._ctx
    const tiles = this._provider.getAllTiles()

    for (const tile of tiles) {
      if (!this._isTileVisible(tile, clipL, clipT, clipR, clipB)) continue
      const cx = tile.pixel_x
      const cy = tile.pixel_y

      // 首都
      if (tile.is_capital) {
        this._drawCapitalMarker(cx, cy, '#FFD700')
      }

      // 港口
      if (tile.is_port) {
        this._drawPortMarker(cx, cy)
      }

      // 关隘
      if (tile.is_pass) {
        this._drawPassMarker(cx, cy)
      }

      // 渡口
      if (tile.is_ferry) {
        this._drawFerryMarker(cx, cy)
      }

      // 战略据点
      if (tile.is_strategic) {
        this._drawStrategicMarker(cx, cy)
      }
    }
  }

  /**
   * [ 4] 法理宣称 — De Jure 领土边界高亮 (低透明度)
   */
  private _renderDeJureLayer(
    _clipL: number, _clipT: number, _clipR: number, _clipB: number,
  ) {
    // 预留：法理宣称边界渲染
    // 在当前实现中，通过 faction_territory 的初始分配间接体现
  }

  /**
   * [ 6] 城建建筑 — 城防等级/建筑标记
   */
  private _renderCityBuildingsLayer(
    _clipL: number, _clipT: number, _clipR: number, _clipB: number,
  ) {
    // 预留：城建建筑等级标记
    // 待城市系统数据接入后激活
  }

  /**
   * [ 7] 灾害标记 — 瘟疫/洪水/蝗灾覆盖
   */
  private _renderDisastersLayer(
    _clipL: number, _clipT: number, _clipR: number, _clipB: number,
  ) {
    // 预留：灾害覆盖渲染
    // 待灾害系统数据接入后激活
  }

  /**
   * [ 8] 迷雾 — 战争迷雾/视野系统
   */
  private _renderFogLayer(
    _clipL: number, _clipT: number, _clipR: number, _clipB: number,
  ) {
    // 预留：战争迷雾渲染
    // 当前由 fogOfWar.ts / layer_config.py 的 fog 图层处理
  }

  /**
   * [11] 驻防兵力 — 各城池驻军数量标记
   */
  private _renderGarrisonsLayer(
    _clipL: number, _clipT: number, _clipR: number, _clipB: number,
  ) {
    // 预留：驻防兵力标记
    // 待军团系统数据接入后激活
  }

  /**
   * [12] 行军路线 — 军队移动路径可视化
   */
  private _renderMarchRoutesLayer() {
    // 预留：行军路线渲染
    // 待行军系统数据接入后激活
  }

  /**
   * [13] 外交连线 — 同盟/交战/朝贡关系连线
   */
  private _renderDiplomaticLinksLayer() {
    // 预留：外交关系连线渲染
    // 待外交系统数据接入后激活
  }

  /**
   * [14] 选中高亮
   */
  private _renderSelection(tileId: string) {
    const tile = this._provider.getTile(tileId)
    if (!tile) return

    const ctx = this._ctx
    const { cx, cy } = { cx: tile.pixel_x, cy: tile.pixel_y }

    // 辉光
    ctx.shadowColor = this._config.selectionGlowColor
    ctx.shadowBlur = this._config.selectionGlowBlur
    ctx.strokeStyle = this._config.selectionStrokeColor
    ctx.lineWidth = this._config.selectionStrokeWidth
    this._strokeHex(cx, cy)
    ctx.shadowColor = 'transparent'
    ctx.shadowBlur = 0
  }

  // ============================================================
  // 绘制原语
  // ============================================================

  /** 填充六边形 */
  private _drawHex(cx: number, cy: number, fillColor: string, alpha: number) {
    const ctx = this._ctx
    const corners = this._getHexCorners(cx, cy)

    ctx.globalAlpha = alpha
    ctx.fillStyle = fillColor
    ctx.beginPath()
    ctx.moveTo(corners[0].x, corners[0].y)
    for (let i = 1; i < 6; i++) {
      ctx.lineTo(corners[i].x, corners[i].y)
    }
    ctx.closePath()
    ctx.fill()
  }

  /** 描边六边形 */
  private _strokeHex(cx: number, cy: number) {
    const ctx = this._ctx
    const corners = this._getHexCorners(cx, cy)

    ctx.beginPath()
    ctx.moveTo(corners[0].x, corners[0].y)
    for (let i = 1; i < 6; i++) {
      ctx.lineTo(corners[i].x, corners[i].y)
    }
    ctx.closePath()
    ctx.stroke()
  }

  /** 六边形辉光 */
  private _drawHexGlow(cx: number, cy: number, color: string, intensity: number) {
    const ctx = this._ctx
    ctx.shadowColor = color
    ctx.shadowBlur = 8 + intensity * 16
    ctx.strokeStyle = color
    ctx.lineWidth = 1 + intensity * 2
    ctx.globalAlpha = intensity * 0.6
    this._strokeHex(cx, cy)
    ctx.shadowColor = 'transparent'
    ctx.shadowBlur = 0
    ctx.globalAlpha = 1
  }

  /** 首都标记 ◆ - 白描金印 */
  private _drawCapitalMarker(cx: number, cy: number, color: string) {
    const ctx = this._ctx
    const r = this._config.capitalRadius

    ctx.fillStyle = color       // #c8a84a 古金色
    ctx.strokeStyle = '#2a1a0a' // 浓墨勾边
    ctx.lineWidth = 1.2

    // 菱形 (代表印玺)
    ctx.beginPath()
    ctx.moveTo(cx, cy - r)
    ctx.lineTo(cx + r * 0.7, cy)
    ctx.lineTo(cx, cy + r)
    ctx.lineTo(cx - r * 0.7, cy)
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
  }

  /** 港口标记 ◎ - 白描双环 */
  private _drawPortMarker(cx: number, cy: number) {
    const ctx = this._ctx
    const r = this._config.portRadius

    ctx.strokeStyle = '#7a8a92'
    ctx.lineWidth = 1.2
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(cx, cy, r * 0.45, 0, Math.PI * 2)
    ctx.stroke()

    // 小锚点
    ctx.fillStyle = '#7a8a92'
    ctx.beginPath()
    ctx.arc(cx, cy, 1.2, 0, Math.PI * 2)
    ctx.fill()
  }

  /** 关隘标记 ▲ - 白描山形 */
  private _drawPassMarker(cx: number, cy: number) {
    const ctx = this._ctx
    const s = this._config.passSize

    ctx.fillStyle = '#8a6a5a'
    ctx.strokeStyle = '#3a2a1a'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(cx, cy - s)
    ctx.lineTo(cx + s, cy + s * 0.7)
    ctx.lineTo(cx + s * 0.3, cy + s * 0.3)
    ctx.lineTo(cx - s * 0.3, cy + s * 0.3)
    ctx.lineTo(cx - s, cy + s * 0.7)
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
  }

  /** 渡口标记 - 白描水纹 */
  private _drawFerryMarker(cx: number, cy: number) {
    const ctx = this._ctx
    ctx.strokeStyle = '#6a7a8a'
    ctx.lineWidth = 1.2
    // 三波浪线
    for (let i = -1; i <= 1; i++) {
      ctx.beginPath()
      ctx.moveTo(cx - 4, cy + i * 2.5)
      ctx.quadraticCurveTo(cx - 1.5, cy + i * 2.5 - 1.5, cx + 1.5, cy + i * 2.5)
      ctx.quadraticCurveTo(cx + 4.5, cy + i * 2.5 + 1.5, cx + 5, cy + i * 2.5)
      ctx.stroke()
    }
  }

  /** 战略据点标记 □ - 白描方框 */
  private _drawStrategicMarker(cx: number, cy: number) {
    const ctx = this._ctx
    ctx.strokeStyle = '#7a6a52'
    ctx.lineWidth = 1.5
    // 方框 (城墙/要塞)
    const s = 4
    ctx.beginPath()
    ctx.moveTo(cx - s, cy - s)
    ctx.lineTo(cx + s, cy - s)
    ctx.lineTo(cx + s, cy + s)
    ctx.lineTo(cx - s, cy + s)
    ctx.closePath()
    ctx.stroke()
    // 内部交叉线
    ctx.lineWidth = 0.8
    ctx.beginPath()
    ctx.moveTo(cx, cy - s * 0.7)
    ctx.lineTo(cx, cy + s * 0.7)
    ctx.moveTo(cx - s * 0.7, cy)
    ctx.lineTo(cx + s * 0.7, cy)
    ctx.stroke()
  }

  // ============================================================
  // 辅助
  // ============================================================

  /** 获取六边形六个顶点（使用预计算 cos/sin） */
  private _getHexCorners(cx: number, cy: number): { x: number; y: number }[] {
    const key = `${cx},${cy}`
    if (!this._hexVertexCache.has(key)) {
      const corners: { x: number; y: number }[] = []
      for (let i = 0; i < 6; i++) {
        corners.push({
          x: cx + HEX_SIZE * HEX_COS_SIN[i].cos,
          y: cy + HEX_SIZE * HEX_COS_SIN[i].sin,
        })
      }
      this._hexVertexCache.set(key, corners)
    }
    return this._hexVertexCache.get(key)!
  }

  /** 判断瓦片是否在视口内 */
  private _isTileVisible(
    tile: TerritoryTile,
    clipL: number, clipT: number, clipR: number, clipB: number,
  ): boolean {
    return tile.pixel_x + HEX_SIZE > clipL &&
           tile.pixel_x - HEX_SIZE < clipR &&
           tile.pixel_y + HEX_SIZE * 0.866 > clipT &&
           tile.pixel_y - HEX_SIZE * 0.866 < clipB
  }

  /** 获取边界线 */
  private _getBoundaryEdges(level: string): BoundaryEdge[] {
    const b = this._provider.boundaries
    switch (level) {
      case 'province': return b.province_boundaries
      case 'circuit': return b.circuit_boundaries
      default: return []
    }
  }

  /** 清除顶点缓存 */
  clearCache() {
    this._hexVertexCache.clear()
    this._lastRenderScale = 0
  }

  /** 销毁 */
  destroy() {
    this.clearCache()
  }
}
