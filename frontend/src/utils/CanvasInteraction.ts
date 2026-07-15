/**
 * CK3 风格 Canvas 交互工具类
 *
 * 复刻 CK3 地图交互逻辑：
 * 1. 鼠标左键拖拽平移（带惯性滑动）
 * 2. 鼠标滚轮中心锚点缩放（Stage 中心为缩放锚点）
 * 3. 缩放区间锁定极值
 * 4. 缩放等级绑定行政层级自动折叠/展开
 * 5. 点击地块高亮选中
 *
 * 设计为框架无关的纯 TypeScript 类，通过回调与 Vue3 组件通信。
 *
 * 使用方式：
 *   const interaction = new CanvasInteraction(stage, config)
 *   interaction.onZoomChange = (scale, offset, range) => { ... }
 *   interaction.onDragChange = (offset) => { ... }
 *   interaction.onTileClick = (tileId) => { ... }
 *   interaction.attach()
 */

import {
  ZOOM_MAX,
  ZOOM_WHEEL_FACTOR,
  ZOOM_HYSTERESIS,
  DRAG_THRESHOLD_PX,
  INERTIA_ENABLED,
  INERTIA_FRICTION,
  INERTIA_MIN_VELOCITY,
  ZOOM_ANIM_DURATION,
  ZOOM_RANGES,
  getZoomRange,
  clampZoom,
  getVisibleBoundaries,
  getVisibleLabels,
  getHexesVisible,
  mergeRemoteZoomConfig,
  calculateFitScale,
  calculateFitOffset,
  setDynamicZoomMin,
  getDynamicZoomMin,
  SELECTION_STROKE_COLOR,
  SELECTION_STROKE_WIDTH,
  SELECTION_GLOW_COLOR,
  SELECTION_GLOW_BLUR,
} from './mapInteractionConfig'
import type { ZoomRange } from './mapInteractionConfig'

// ============================================================
// 类型定义
// ============================================================

export interface ViewportState {
  scale: number
  offsetX: number
  offsetY: number
}

export interface InteractionCallbacks {
  /** 缩放变化时触发（含新scale、新offset、当前行政区间） */
  onZoomChange?: (state: ViewportState, zoomRange: ZoomRange) => void
  /** 拖拽变化时触发 */
  onDragChange?: (state: ViewportState) => void
  /** 地块点击时触发 */
  onTileClick?: (tileId: string) => void
  /** 地块悬停时触发 */
  onTileHover?: (tileId: string | null, screenX: number, screenY: number) => void
  /** 视口状态任意变化时触发（用于重新渲染） */
  onViewportChange?: (state: ViewportState) => void
  /** 缩放区间切换时触发 */
  onZoomRangeChange?: (range: ZoomRange, previousRange: ZoomRange | null) => void
}

export interface InteractionConfig {
  /** 初始缩放 */
  initialScale?: number
  /** 初始X偏移 */
  initialOffsetX?: number
  /** 初始Y偏移 */
  initialOffsetY?: number
  /** 地图矩形网格总宽度（像素） */
  mapTotalWidth?: number
  /** 地图矩形网格总高度（像素） */
  mapTotalHeight?: number
  /** 疆域包围盒宽度（像素） */
  territoryWidth?: number
  /** 疆域包围盒高度（像素） */
  territoryHeight?: number
  /** 疆域包围盒在世界坐标中的 X 偏移 */
  territoryOriginX?: number
  /** 疆域包围盒在世界坐标中的 Y 偏移 */
  territoryOriginY?: number
  /** 容器宽度 */
  containerWidth?: number
  /** 容器高度 */
  containerHeight?: number
}

// ============================================================
// 主类
// ============================================================

export class CanvasInteraction {
  // ---- 视口状态 ----
  private _scale: number
  private _offsetX: number
  private _offsetY: number

  // ---- 配置 ----
  private _mapTotalW: number
  private _mapTotalH: number
  private _territoryW: number
  private _territoryH: number
  private _territoryOrgX: number
  private _territoryOrgY: number
  private _containerW: number
  private _containerH: number

  // ---- 自适应缩放 ----
  /** 地图外接矩形自适应填满视口的缩放倍率 (即动态 ZOOM_MIN) */
  private _fitScale: number = 0.30

  // ---- 缩放状态 ----
  private _currentZoomRange: ZoomRange | null = null
  private _prevZoomRangeKey: string | undefined

  // ---- 拖拽状态 ----
  private _isDragging = false
  private _dragMoved = false
  private _dragStartX = 0
  private _dragStartY = 0
  private _dragStartOffX = 0
  private _dragStartOffY = 0

  // ---- 惯性滑动 ----
  private _velocityX = 0
  private _velocityY = 0
  private _lastDragX = 0
  private _lastDragY = 0
  private _lastDragTime = 0
  private _inertiaRaf: number | null = null

  // ---- 缩放动画 ----
  private _zoomAnimRaf: number | null = null

  // ---- 回调 ----
  callbacks: InteractionCallbacks = {}

  // ---- DOM 引用 ----
  private _container: HTMLElement | null = null
  private _canvas: HTMLElement | null = null

  // ---- 绑定的事件处理器（用于移除监听） ----
  private _boundOnWheel: ((e: WheelEvent) => void) | null = null
  private _boundOnMouseDown: ((e: MouseEvent) => void) | null = null
  private _boundOnMouseMove: ((e: MouseEvent) => void) | null = null
  private _boundOnMouseUp: ((e: MouseEvent) => void) | null = null
  private _boundOnContextMenu: ((e: MouseEvent) => void) | null = null
  private _boundOnTouchStart: ((e: TouchEvent) => void) | null = null
  private _boundOnTouchMove: ((e: TouchEvent) => void) | null = null
  private _boundOnTouchEnd: ((e: TouchEvent) => void) | null = null

  // ---- 双指缩放状态 ----
  private _pinchStartDist = 0
  private _pinchStartScale = 0
  private _pinchStartOffX = 0
  private _pinchStartOffY = 0
  private _pinchCenterX = 0
  private _pinchCenterY = 0

  constructor(config: InteractionConfig = {}) {
    this._mapTotalW = config.mapTotalWidth ?? 3000
    this._mapTotalH = config.mapTotalHeight ?? 1600
    // 疆域包围盒 (默认等于矩形网格)
    this._territoryW = config.territoryWidth ?? this._mapTotalW
    this._territoryH = config.territoryHeight ?? this._mapTotalH
    this._territoryOrgX = config.territoryOriginX ?? 0
    this._territoryOrgY = config.territoryOriginY ?? 0
    this._containerW = config.containerWidth ?? 1200
    this._containerH = config.containerHeight ?? 800

    // 计算疆域包围盒自适应填满视口的缩放倍率
    this._fitScale = calculateFitScale(
      this._territoryW, this._territoryH,
      this._containerW, this._containerH,
    )
    // 同步至全局动态缩放下限 + 全区间重校准
    setDynamicZoomMin(this._fitScale)

    // 初始缩放 = fitScale (全屏适配) 或用户指定值 (不小于 100%)
    const initScale = Math.max(1.0, this._fitScale, config.initialScale ?? this._fitScale)
    this._scale = initScale

    // 初始偏移 = 居中疆域包围盒
    const fitOff = calculateFitOffset(
      this._territoryW, this._territoryH,
      this._containerW, this._containerH,
      this._scale,
      this._territoryOrgX, this._territoryOrgY,
    )
    this._offsetX = config.initialOffsetX ?? fitOff.offsetX
    this._offsetY = config.initialOffsetY ?? fitOff.offsetY

    this._currentZoomRange = getZoomRange(this._scale)
  }

  // ============================================================
  // 属性访问器
  // ============================================================

  get scale(): number { return this._scale }
  get offsetX(): number { return this._offsetX }
  get offsetY(): number { return this._offsetY }
  get fitScale(): number { return this._fitScale }
  get viewport(): ViewportState {
    return { scale: this._scale, offsetX: this._offsetX, offsetY: this._offsetY }
  }
  get currentZoomRange(): ZoomRange | null { return this._currentZoomRange }
  get isDragging(): boolean { return this._isDragging }

  // ============================================================
  // 生命周期
  // ============================================================

  /**
   * 附加事件监听到 DOM 元素
   * @param container 外层容器（用于 wheel 和 contextmenu 事件）
   * @param canvas 画布元素（用于 mousedown/touch 事件，通常是 Konva Stage 的容器）
   */
  attach(container: HTMLElement, canvas?: HTMLElement) {
    this.detach()
    this._container = container
    this._canvas = canvas || container

    // 更新容器尺寸
    this._containerW = container.clientWidth
    this._containerH = container.clientHeight

    // 滚轮缩放 → 绑定在容器上
    this._boundOnWheel = this._handleWheel.bind(this)
    container.addEventListener('wheel', this._boundOnWheel, { passive: false })

    // 鼠标拖拽 → 绑定在画布上
    this._boundOnMouseDown = this._handleMouseDown.bind(this)
    this._canvas!.addEventListener('mousedown', this._boundOnMouseDown)

    this._boundOnMouseMove = this._handleMouseMove.bind(this)
    document.addEventListener('mousemove', this._boundOnMouseMove)

    this._boundOnMouseUp = this._handleMouseUp.bind(this)
    document.addEventListener('mouseup', this._boundOnMouseUp)

    // 右键菜单 → 阻止默认行为
    this._boundOnContextMenu = (e: MouseEvent) => e.preventDefault()
    this._canvas!.addEventListener('contextmenu', this._boundOnContextMenu)

    // 触摸事件 → 双指缩放 + 单指拖拽
    this._boundOnTouchStart = this._handleTouchStart.bind(this)
    this._canvas!.addEventListener('touchstart', this._boundOnTouchStart, { passive: false })

    this._boundOnTouchMove = this._handleTouchMove.bind(this)
    this._canvas!.addEventListener('touchmove', this._boundOnTouchMove, { passive: false })

    this._boundOnTouchEnd = this._handleTouchEnd.bind(this)
    this._canvas!.addEventListener('touchend', this._boundOnTouchEnd)
  }

  /** 移除所有事件监听 */
  detach() {
    if (this._container && this._boundOnWheel) {
      this._container.removeEventListener('wheel', this._boundOnWheel)
    }
    if (this._canvas) {
      if (this._boundOnMouseDown) this._canvas.removeEventListener('mousedown', this._boundOnMouseDown)
      if (this._boundOnContextMenu) this._canvas.removeEventListener('contextmenu', this._boundOnContextMenu)
      if (this._boundOnTouchStart) this._canvas.removeEventListener('touchstart', this._boundOnTouchStart)
      if (this._boundOnTouchMove) this._canvas.removeEventListener('touchmove', this._boundOnTouchMove)
      if (this._boundOnTouchEnd) this._canvas.removeEventListener('touchend', this._boundOnTouchEnd)
    }
    if (this._boundOnMouseMove) document.removeEventListener('mousemove', this._boundOnMouseMove)
    if (this._boundOnMouseUp) document.removeEventListener('mouseup', this._boundOnMouseUp)
    this._stopInertia()
    this._stopZoomAnim()
    this._container = null
    this._canvas = null
  }

  /** 更新容器尺寸 (窗口 resize 时调用，重算 fitScale 并锁定下限) */
  updateContainerSize(w: number, h: number) {
    this._containerW = w
    this._containerH = h

    // 重新计算疆域包围盒自适应填满视口的缩放倍率
    this._fitScale = calculateFitScale(
      this._territoryW, this._territoryH,
      this._containerW, this._containerH,
    )
    setDynamicZoomMin(this._fitScale)

    // 如果当前缩放小于新的有效下限（fitScale 与 100% 取大值），拉回并居中
    const effectiveMin = Math.max(1.0, this._fitScale)
    if (this._scale < effectiveMin) {
      this._scale = effectiveMin
      const fitOff = calculateFitOffset(
        this._territoryW, this._territoryH,
        this._containerW, this._containerH,
        effectiveMin,
        this._territoryOrgX, this._territoryOrgY,
      )
      this._offsetX = fitOff.offsetX
      this._offsetY = fitOff.offsetY
    } else if (this._scale <= effectiveMin * 1.05) {
      // 接近下限时，重新居中以避免黑边
      const fitOff = calculateFitOffset(
        this._territoryW, this._territoryH,
        this._containerW, this._containerH,
        this._scale,
        this._territoryOrgX, this._territoryOrgY,
      )
      this._offsetX = fitOff.offsetX
      this._offsetY = fitOff.offsetY
    }

    this._currentZoomRange = getZoomRange(this._scale, this._prevZoomRangeKey)
    this._notifyViewportChange()
    this._notifyZoomChange()
  }

  /** 更新地图尺寸与疆域包围盒 */
  updateMapSize(totalW: number, totalH: number, territoryW?: number, territoryH?: number, orgX?: number, orgY?: number) {
    this._mapTotalW = totalW
    this._mapTotalH = totalH
    if (territoryW !== undefined) this._territoryW = territoryW
    if (territoryH !== undefined) this._territoryH = territoryH
    if (orgX !== undefined) this._territoryOrgX = orgX
    if (orgY !== undefined) this._territoryOrgY = orgY
  }

  // ============================================================
  // 公开 API
  // ============================================================

  /**
   * 重置视图到全屏适配模式 (疆域包围盒 fit-to-viewport)
   */
  resetView(defaultScale?: number) {
    const targetScale = defaultScale ?? this._fitScale
    const clamped = clampZoom(targetScale)
    const fitOff = calculateFitOffset(
      this._territoryW, this._territoryH,
      this._containerW, this._containerH,
      clamped,
      this._territoryOrgX, this._territoryOrgY,
    )
    this._offsetX = fitOff.offsetX
    this._offsetY = fitOff.offsetY
    this._scale = clamped
    this._currentZoomRange = getZoomRange(this._scale)
    this._notifyViewportChange()
    this._notifyZoomChange()
  }

  /**
   * 跳转到指定缩放级别（带动画）
   */
  zoomTo(targetScale: number, animate: boolean = true) {
    const clamped = clampZoom(targetScale)
    if (animate && Math.abs(clamped - this._scale) > 0.01) {
      this._animateZoom(this._scale, clamped)
    } else {
      this._applyZoom(clamped, this._containerW / 2, this._containerH / 2)
    }
  }

  /**
   * 以指定屏幕坐标为中心缩放（CK3 风格：Stage 中心锚点）
   */
  zoomAt(centerX: number, centerY: number, delta: number) {
    const factor = delta > 0 ? 1.0 / ZOOM_WHEEL_FACTOR : ZOOM_WHEEL_FACTOR
    const newScale = clampZoom(this._scale * factor)
    this._applyZoom(newScale, centerX, centerY)
  }

  /** 以画布中心放大一级 */
  zoomIn() {
    this.zoomAt(this._containerW / 2, this._containerH / 2, 1)
  }

  /** 以画布中心缩小一级 */
  zoomOut() {
    this.zoomAt(this._containerW / 2, this._containerH / 2, -1)
  }

  /**
   * 跳转到指定缩放级别（对应按钮点击）
   */
  setZoomLevel(levelKey: string) {
    const range = ZOOM_RANGES.find(r => r.key === levelKey)
    if (!range) return

    const centerX = this._containerW / 2
    const centerY = this._containerH / 2
    this._animateZoom(this._scale, range.defaultScale, centerX, centerY)
  }

  /**
   * 平移视图
   */
  panBy(dx: number, dy: number) {
    this._offsetX += dx
    this._offsetY += dy
    this._clampOffset()
    this._notifyViewportChange()
  }

  /**
   * 滚动到指定世界坐标（使该坐标位于屏幕中心）
   */
  panToWorld(worldX: number, worldY: number, animate: boolean = false) {
    const targetOffX = this._containerW / 2 - worldX * this._scale
    const targetOffY = this._containerH / 2 - worldY * this._scale

    if (animate) {
      this._animatePan(targetOffX, targetOffY)
    } else {
      this._offsetX = targetOffX
      this._offsetY = targetOffY
      this._clampOffset()
      this._notifyViewportChange()
    }
  }

  /**
   * 屏幕坐标 → 世界坐标
   */
  screenToWorld(screenX: number, screenY: number): { x: number; y: number } {
    return {
      x: (screenX - this._offsetX) / this._scale,
      y: (screenY - this._offsetY) / this._scale,
    }
  }

  /**
   * 世界坐标 → 屏幕坐标
   */
  worldToScreen(worldX: number, worldY: number): { x: number; y: number } {
    return {
      x: worldX * this._scale + this._offsetX,
      y: worldY * this._scale + this._offsetY,
    }
  }

  /**
   * 获取当前可见的边界层级列表
   */
  getVisibleBoundaries(): string[] {
    return getVisibleBoundaries(this._scale, this._prevZoomRangeKey)
  }

  /**
   * 获取当前可见的标签层级列表
   */
  getVisibleLabels(): string[] {
    return getVisibleLabels(this._scale, this._prevZoomRangeKey)
  }

  /**
   * 获取当前六边形是否应显示
   */
  getHexesVisible(): boolean {
    return getHexesVisible(this._scale, this._prevZoomRangeKey)
  }

  /**
   * 销毁实例
   */
  destroy() {
    this.detach()
    this.callbacks = {}
  }

  // ============================================================
  // 私有：事件处理
  // ============================================================

  private _handleWheel(e: WheelEvent) {
    e.preventDefault()

    // CK3 风格：缩放锚点 = Stage/容器中心（而非鼠标指针位置）
    // 这确保了缩放时地图保持居中感，行政层级展开/折叠视觉稳定
    const centerX = this._containerW / 2
    const centerY = this._containerH / 2

    const factor = e.deltaY > 0 ? 1.0 / ZOOM_WHEEL_FACTOR : ZOOM_WHEEL_FACTOR
    const newScale = clampZoom(this._scale * factor)

    if (newScale !== this._scale) {
      this._applyZoom(newScale, centerX, centerY)
    }
  }

  private _handleMouseDown(e: MouseEvent) {
    // 仅左键拖拽
    if (e.button !== 0) return

    // 检查点击目标：如果点击在 Konva 形状上（非空白区域），
    // 则不启动拖拽，让 Konva 的 click 事件处理
    const target = e.target as HTMLElement
    if (target.tagName === 'CANVAS') {
      this._startDrag(e.clientX, e.clientY)
    }
  }

  private _handleMouseMove(e: MouseEvent) {
    if (!this._isDragging) return

    const dx = e.clientX - this._dragStartX
    const dy = e.clientY - this._dragStartY

    // 判断是否超过拖拽阈值
    if (!this._dragMoved) {
      if (Math.abs(dx) < DRAG_THRESHOLD_PX && Math.abs(dy) < DRAG_THRESHOLD_PX) return
      this._dragMoved = true
    }

    // 更新偏移
    this._offsetX = this._dragStartOffX + dx
    this._offsetY = this._dragStartOffY + dy
    this._clampOffset()

    // 计算速度（用于惯性）
    const now = performance.now()
    const dt = now - this._lastDragTime
    if (dt > 0) {
      this._velocityX = (e.clientX - this._lastDragX) / dt * 16 // 归一化到 ~60fps
      this._velocityY = (e.clientY - this._lastDragY) / dt * 16
    }
    this._lastDragX = e.clientX
    this._lastDragY = e.clientY
    this._lastDragTime = now

    this._notifyViewportChange()
  }

  private _handleMouseUp(e: MouseEvent) {
    if (!this._isDragging) return

    this._isDragging = false

    // 如果没有移动（未超过阈值），视为点击
    if (!this._dragMoved) {
      // 点击事件由 Konva 直接处理，此处不重复触发
    }

    // 启动惯性滑动
    if (INERTIA_ENABLED && this._dragMoved &&
        (Math.abs(this._velocityX) > INERTIA_MIN_VELOCITY ||
         Math.abs(this._velocityY) > INERTIA_MIN_VELOCITY)) {
      this._startInertia()
    }

    this._dragMoved = false
    this._velocityX = 0
    this._velocityY = 0
  }

  // ============================================================
  // 私有：触摸事件（移动端双指缩放）
  // ============================================================

  private _handleTouchStart(e: TouchEvent) {
    if (e.touches.length === 2) {
      // 双指：开始缩放
      e.preventDefault()
      const t1 = e.touches[0]
      const t2 = e.touches[1]
      this._pinchStartDist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY)
      this._pinchStartScale = this._scale
      this._pinchStartOffX = this._offsetX
      this._pinchStartOffY = this._offsetY
      this._pinchCenterX = (t1.clientX + t2.clientX) / 2
      this._pinchCenterY = (t1.clientY + t2.clientY) / 2
    } else if (e.touches.length === 1) {
      // 单指：开始拖拽
      const t = e.touches[0]
      this._startDrag(t.clientX, t.clientY)
    }
  }

  private _handleTouchMove(e: TouchEvent) {
    if (e.touches.length === 2 && this._pinchStartDist > 0) {
      e.preventDefault()
      const t1 = e.touches[0]
      const t2 = e.touches[1]
      const dist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY)
      const newScale = clampZoom(this._pinchStartScale * (dist / this._pinchStartDist))
      this._applyZoom(newScale, this._pinchCenterX, this._pinchCenterY)
    } else if (e.touches.length === 1 && this._isDragging) {
      const t = e.touches[0]
      this._handleMouseMove({ clientX: t.clientX, clientY: t.clientY } as MouseEvent)
    }
  }

  private _handleTouchEnd(e: TouchEvent) {
    if (e.touches.length === 0) {
      this._pinchStartDist = 0
      this._handleMouseUp(e as unknown as MouseEvent)
    }
  }

  // ============================================================
  // 私有：核心逻辑
  // ============================================================

  private _startDrag(clientX: number, clientY: number) {
    this._isDragging = true
    this._dragMoved = false
    this._dragStartX = clientX
    this._dragStartY = clientY
    this._dragStartOffX = this._offsetX
    this._dragStartOffY = this._offsetY
    this._lastDragX = clientX
    this._lastDragY = clientY
    this._lastDragTime = performance.now()
    this._velocityX = 0
    this._velocityY = 0
    this._stopInertia()
  }

  /**
   * CK3 风格：以指定屏幕锚点为中心缩放
   *
   * 核心公式：
   *   newOffset = anchorPoint - (anchorPoint - oldOffset) * (newScale / oldScale)
   *
   * 这确保了缩放时锚点位置的世界坐标保持不变。
   */
  private _applyZoom(newScale: number, anchorX: number, anchorY: number) {
    if (newScale === this._scale) return

    const ratio = newScale / this._scale
    const newOffX = anchorX - (anchorX - this._offsetX) * ratio
    const newOffY = anchorY - (anchorY - this._offsetY) * ratio

    this._scale = newScale
    this._offsetX = newOffX
    this._offsetY = newOffY
    this._clampOffset()

    // 检测缩放区间切换
    const newRange = getZoomRange(this._scale, this._prevZoomRangeKey)
    if (this._currentZoomRange?.key !== newRange.key) {
      const prev = this._currentZoomRange
      this._prevZoomRangeKey = prev?.key
      this._currentZoomRange = newRange
      if (this.callbacks.onZoomRangeChange) {
        this.callbacks.onZoomRangeChange(newRange, prev)
      }
    }

    this._notifyViewportChange()
    this._notifyZoomChange()
  }

  /**
   * 夹紧偏移量
   *
   * 缩放下限锁定策略：
   * - 处于 fitScale (±5%) 时：偏移锁定为疆域包围盒居中，地图精确填满视口，不留黑边
   * - 放大后：允许自由拖拽平移，但防止地图完全飘出视口
   */
  private _clampOffset() {
    const scaledW = this._territoryW * this._scale
    const scaledH = this._territoryH * this._scale

    // 处于缩放下限附近 (±5%)：锁定居中，疆域包围盒自适应填满视口
    if (this._scale <= Math.max(1.0, this._fitScale) * 1.05) {
      this._offsetX = (this._containerW - scaledW) / 2 - this._territoryOrgX * this._scale
      this._offsetY = (this._containerH - scaledH) / 2 - this._territoryOrgY * this._scale
      return
    }

    // 放大后：允许拖拽平移，边界留 margin 防止完全飘出
    const margin = 100
    this._offsetX = Math.max(-this._mapTotalW * this._scale + margin, Math.min(this._containerW - margin, this._offsetX))
    this._offsetY = Math.max(-this._mapTotalH * this._scale + margin, Math.min(this._containerH - margin, this._offsetY))
  }

  // ============================================================
  // 私有：惯性滑动
  // ============================================================

  private _startInertia() {
    this._stopInertia()

    // 捕获当前速度快照，防止 _handleMouseUp 后续清零影响惯性动画
    let vx = this._velocityX
    let vy = this._velocityY

    const animate = () => {
      vx *= INERTIA_FRICTION
      vy *= INERTIA_FRICTION

      if (Math.abs(vx) < INERTIA_MIN_VELOCITY &&
          Math.abs(vy) < INERTIA_MIN_VELOCITY) {
        this._stopInertia()
        return
      }

      this._offsetX += vx
      this._offsetY += vy
      this._clampOffset()
      this._notifyViewportChange()

      this._inertiaRaf = requestAnimationFrame(animate)
    }

    this._inertiaRaf = requestAnimationFrame(animate)
  }

  private _stopInertia() {
    if (this._inertiaRaf !== null) {
      cancelAnimationFrame(this._inertiaRaf)
      this._inertiaRaf = null
    }
  }

  // ============================================================
  // 私有：缩放动画（easeInOutCubic）
  // ============================================================

  private _animateZoom(fromScale: number, toScale: number, anchorX?: number, anchorY?: number) {
    this._stopZoomAnim()

    const ax = anchorX ?? this._containerW / 2
    const ay = anchorY ?? this._containerH / 2
    const startTime = performance.now()
    const startScale = fromScale
    const startOffX = this._offsetX
    const startOffY = this._offsetY

    const animate = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(1, elapsed / ZOOM_ANIM_DURATION)

      // easeInOutCubic
      const eased = progress < 0.5
        ? 4 * progress * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 3) / 2

      const currentScale = startScale + (toScale - startScale) * eased
      const ratio = currentScale / startScale
      const currentOffX = ax - (ax - startOffX) * ratio
      const currentOffY = ay - (ay - startOffY) * ratio

      this._scale = currentScale
      this._offsetX = currentOffX
      this._offsetY = currentOffY
      this._clampOffset()

      // 检测区间切换
      const newRange = getZoomRange(this._scale, this._prevZoomRangeKey)
      if (this._currentZoomRange?.key !== newRange.key) {
        const prev = this._currentZoomRange
        this._prevZoomRangeKey = prev?.key
        this._currentZoomRange = newRange
        if (this.callbacks.onZoomRangeChange) {
          this.callbacks.onZoomRangeChange(newRange, prev)
        }
      }

      this._notifyViewportChange()
      this._notifyZoomChange()

      if (progress < 1) {
        this._zoomAnimRaf = requestAnimationFrame(animate)
      } else {
        this._zoomAnimRaf = null
      }
    }

    this._zoomAnimRaf = requestAnimationFrame(animate)
  }

  private _animatePan(targetOffX: number, targetOffY: number) {
    const startTime = performance.now()
    const startOffX = this._offsetX
    const startOffY = this._offsetY
    const duration = ZOOM_ANIM_DURATION

    const animate = (now: number) => {
      const progress = Math.min(1, (now - startTime) / duration)
      const eased = progress < 0.5
        ? 4 * progress * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 3) / 2

      this._offsetX = startOffX + (targetOffX - startOffX) * eased
      this._offsetY = startOffY + (targetOffY - startOffY) * eased
      this._notifyViewportChange()

      if (progress < 1) {
        requestAnimationFrame(animate)
      }
    }

    requestAnimationFrame(animate)
  }

  private _stopZoomAnim() {
    if (this._zoomAnimRaf !== null) {
      cancelAnimationFrame(this._zoomAnimRaf)
      this._zoomAnimRaf = null
    }
  }

  // ============================================================
  // 私有：通知回调
  // ============================================================

  private _notifyViewportChange() {
    if (this.callbacks.onViewportChange) {
      this.callbacks.onViewportChange(this.viewport)
    }
    if (this.callbacks.onDragChange) {
      this.callbacks.onDragChange(this.viewport)
    }
  }

  private _notifyZoomChange() {
    if (this.callbacks.onZoomChange && this._currentZoomRange) {
      this.callbacks.onZoomChange(this.viewport, this._currentZoomRange)
    }
  }
}

// ============================================================
// Vue3 Composable 封装
// ============================================================

import { ref, shallowRef, onMounted, onUnmounted, type Ref } from 'vue'

export interface UseCanvasInteractionOptions {
  containerRef: Ref<HTMLElement | undefined>
  canvasRef?: Ref<HTMLElement | undefined>
  initialScale?: number
  mapTotalWidth?: number
  mapTotalHeight?: number
}

export function useCanvasInteraction(options: UseCanvasInteractionOptions) {
  const interaction = shallowRef<CanvasInteraction | null>(null)
  const viewport = ref<ViewportState>({
    scale: options.initialScale ?? 1.0,
    offsetX: 0,
    offsetY: 0,
  })
  const zoomRange = ref<ZoomRange>(ZOOM_RANGES[2]) // 默认 circuit 级别
  const isDragging = ref(false)

  function init() {
    if (!options.containerRef.value) return

    const inst = new CanvasInteraction({
      initialScale: options.initialScale,
      mapTotalWidth: options.mapTotalWidth,
      mapTotalHeight: options.mapTotalHeight,
      containerWidth: options.containerRef.value.clientWidth,
      containerHeight: options.containerRef.value.clientHeight,
    })

    // 同步状态到 Vue ref
    inst.callbacks.onViewportChange = (vp) => {
      viewport.value = { ...vp }
      isDragging.value = inst.isDragging
    }
    inst.callbacks.onZoomRangeChange = (range) => {
      zoomRange.value = range
    }

    inst.attach(options.containerRef.value, options.canvasRef?.value)
    interaction.value = inst
  }

  function cleanup() {
    interaction.value?.destroy()
    interaction.value = null
  }

  return {
    interaction,
    viewport,
    zoomRange,
    isDragging,
    init,
    cleanup,
  }
}

// ============================================================
// 选中高亮工具
// ============================================================

/**
 * 为 Konva Shape 应用选中高亮效果
 */
export function applySelectionHighlight(shape: any, Konva: any) {
  if (!shape) return

  shape.stroke(SELECTION_STROKE_COLOR)
  shape.strokeWidth(SELECTION_STROKE_WIDTH)
  shape.shadowColor(SELECTION_GLOW_COLOR)
  shape.shadowBlur(SELECTION_GLOW_BLUR)
  shape.shadowEnabled(true)
  shape.shadowOffset({ x: 0, y: 0 })
}

/**
 * 移除 Konva Shape 的选中高亮效果
 */
export function removeSelectionHighlight(shape: any, originalStroke: string, originalStrokeWidth: number) {
  if (!shape) return

  shape.stroke(originalStroke)
  shape.strokeWidth(originalStrokeWidth)
  shape.shadowEnabled(false)
}
