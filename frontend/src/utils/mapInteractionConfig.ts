/**
 * CK3 风格地图交互配置 v4.0 - 三级缩放 (行省/路/府州)
 *
 * v4.0 变更：
 * - 缩放层级从四级精简为三级: world → circuit → prefecture
 * - 移除 county 级别
 * - minScale 基于府州级六边形尺寸重新校准
 */

// ---- 缩放区间定义 (三级) ----

export interface ZoomRange {
  key: string
  name: string
  adminLevel: string
  minScale: number
  maxScale: number
  defaultScale: number
  showBoundaries: string[]
  showLabels: string[]
  showHexes: boolean
  showMarkers: string[]
  labelScale: number
}

/** 原始三级缩放区间 (基准值, 由 setDynamicZoomMin 按比率重校准) */
const _BASE_ZOOM_RANGES: ZoomRange[] = [
  {
    key: 'world',
    name: '天下大势',
    adminLevel: 'province',
    minScale: 0.18,
    maxScale: 0.40,
    defaultScale: 0.25,
    showBoundaries: ['province'],
    showLabels: ['province'],
    showHexes: true,
    showMarkers: ['capital'],
    labelScale: 1.0,
  },
  {
    key: 'circuit',
    name: '各路形势',
    adminLevel: 'circuit',
    minScale: 0.38,
    maxScale: 0.70,
    defaultScale: 0.50,
    showBoundaries: ['province', 'circuit'],
    showLabels: ['province', 'circuit'],
    showHexes: true,
    showMarkers: ['capital', 'port', 'pass'],
    labelScale: 1.2,
  },
  {
    key: 'prefecture',
    name: '府州详情',
    adminLevel: 'prefecture',
    minScale: 0.68,
    maxScale: 3.50,
    defaultScale: 0.90,
    showBoundaries: ['province', 'circuit'],
    showLabels: ['province', 'circuit', 'prefecture'],
    showHexes: true,
    showMarkers: ['capital', 'port', 'pass', 'ferry', 'strategic'],
    labelScale: 1.5,
  },
]

/** 当前可变的缩放区间 */
export const ZOOM_RANGES: ZoomRange[] = _BASE_ZOOM_RANGES.map(r => ({ ...r }))

export const ZOOM_MIN = 1.00  // 最小缩放 100%
export const ZOOM_MAX = 3.50
export const ZOOM_WHEEL_FACTOR = 1.08
export const ZOOM_HYSTERESIS = 0.03

// 拖拽配置
export const DRAG_THRESHOLD_PX = 4
export const DRAG_SMOOTH_FACTOR = 0.85

// 动画配置
export const ZOOM_ANIM_DURATION = 300
export const ZOOM_ANIM_EASING = 'easeInOutCubic'
export const INERTIA_ENABLED = true
export const INERTIA_FRICTION = 0.92
export const INERTIA_MIN_VELOCITY = 0.5

// 选中高亮
export const SELECTION_STROKE_COLOR = '#c8a84a'   // 古金描边 (v5.0 水墨渐变)
export const SELECTION_STROKE_WIDTH = 2.5
export const SELECTION_GLOW_COLOR = '#c8a84a'    // 古金辉光
export const SELECTION_GLOW_BLUR = 10

// ============================================================
// 缩放辅助函数
// ============================================================

/** 获取当前 scale 对应的缩放区间 (含滞后) */
export function getZoomRange(scale: number, prevKey?: string): ZoomRange {
  for (let i = ZOOM_RANGES.length - 1; i >= 0; i--) {
    const range = ZOOM_RANGES[i]
    const threshold = range.minScale - (prevKey === range.key ? ZOOM_HYSTERESIS : 0)
    if (scale >= threshold) return range
  }
  return ZOOM_RANGES[0]
}

/** 钳制缩放值（下限由 fitScale 动态决定） */
export function clampZoom(scale: number): number {
  return Math.max(getDynamicZoomMin(), Math.min(ZOOM_MAX, scale))
}

/** 获取当前可见的边界类型 */
export function getVisibleBoundaries(scale: number, prevKey?: string): string[] {
  return getZoomRange(scale, prevKey).showBoundaries
}

/** 获取当前可见的标签类型 */
export function getVisibleLabels(scale: number, prevKey?: string): string[] {
  return getZoomRange(scale, prevKey).showLabels
}

/** 获取当前可见的标记类型 */
export function getVisibleMarkers(scale: number, prevKey?: string): string[] {
  return getZoomRange(scale, prevKey).showMarkers
}

/** 六边形是否可见 */
export function getHexesVisible(scale: number, prevKey?: string): boolean {
  return getZoomRange(scale, prevKey).showHexes
}

// ============================================================
// 远程配置合并
// ============================================================

export function mergeRemoteZoomConfig(remote: any): void {
  if (!remote?.zoom_config) return
  const cfg = remote.zoom_config
  if (Array.isArray(cfg)) {
    for (let i = 0; i < Math.min(cfg.length, ZOOM_RANGES.length); i++) {
      Object.assign(ZOOM_RANGES[i], cfg[i])
      Object.assign(_BASE_ZOOM_RANGES[i], cfg[i])
    }
  }
}

// ============================================================
// 自适应缩放
// ============================================================

export function calculateFitScale(
  territoryPixelW: number,
  territoryPixelH: number,
  viewportW: number,
  viewportH: number,
): number {
  if (territoryPixelW <= 0 || territoryPixelH <= 0 || viewportW <= 0 || viewportH <= 0) {
    return 0.18
  }
  const sw = viewportW / territoryPixelW
  const sh = viewportH / territoryPixelH
  return Math.min(sw, sh)
}

export function calculateFitOffset(
  territoryPixelW: number,
  territoryPixelH: number,
  viewportW: number,
  viewportH: number,
  scale: number,
  territoryOriginX: number = 0,
  territoryOriginY: number = 0,
): { offsetX: number; offsetY: number } {
  const sw = territoryPixelW * scale
  const sh = territoryPixelH * scale
  return {
    offsetX: (viewportW - sw) / 2 - territoryOriginX * scale,
    offsetY: (viewportH - sh) / 2 - territoryOriginY * scale,
  }
}

// ---- 动态缩放下限 + 全区间等比例重校准 ----

let _dynamicZoomMin = _BASE_ZOOM_RANGES[0].minScale
let _baseFitScale = _BASE_ZOOM_RANGES[0].minScale

/** 保存原始值 */
const _ORIGINAL_RANGES = _BASE_ZOOM_RANGES.map(r => ({
  minScale: r.minScale, maxScale: r.maxScale, defaultScale: r.defaultScale,
}))

export function setDynamicZoomMin(scale: number): void {
  _dynamicZoomMin = scale
  // 始终基于原始基准值计算 ratio，防止多次调用累积漂移
  const origBaseMin = _ORIGINAL_RANGES[0].minScale
  const ratio = origBaseMin > 0 ? scale / origBaseMin : 1.0
  _baseFitScale = scale

  for (let i = 0; i < ZOOM_RANGES.length; i++) {
    const orig = _ORIGINAL_RANGES[i]
    ZOOM_RANGES[i].minScale = orig.minScale * ratio
    ZOOM_RANGES[i].maxScale = orig.maxScale * ratio
    ZOOM_RANGES[i].defaultScale = orig.defaultScale * ratio
  }
}

export function getDynamicZoomMin(): number {
  return Math.max(ZOOM_MIN, _dynamicZoomMin)
}
