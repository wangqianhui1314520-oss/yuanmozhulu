/**
 * 元末逐鹿3.0 - 疆域地图工具层统一导出 v5.0 古卷水墨国风
 *
 * 完整地图系统包含:
 * - TerritoryDataProvider: 疆域基底数据加载/索引/查询
 * - FactionLayerManager:   独立势力着色图层管理
 * - CanvasInteraction:     CK3 风格拖拽平移+滚轮缩放
 * - YuanMapRenderer:       Canvas 批量渲染引擎
 * - useYuanMap:            Vue3 全功能 Composable
 * - flatTopHexUtils:       平顶六边形几何计算
 * - mapInteractionConfig:  三级行政缩放区间配置
 * - layerUtils:            图层显隐/颜色系统
 * - InkWashTexture:        古卷宣纸纹理生成器
 */

// ---- 核心数据层 ----
export {
  TerritoryDataProvider,
  getTerritoryDataProvider,
  resetTerritoryDataProvider,
} from './TerritoryDataProvider'
export type {
  TerritoryTile,
  BoundaryEdge,
  AdminNode,
  ProvinceSummary,
  CircuitSummary,
  PrefectureSummary,
  FactionTerritorySummary,
  TerritoryDataState,
} from './TerritoryDataProvider'

// ---- 势力图层 ----
export {
  FactionLayerManager,
  FACTION_COLOR_PRESETS,
} from './FactionLayerManager'
export type {
  FactionLayerEntry,
  FactionColorResult,
  FactionLayerConfig,
} from './FactionLayerManager'

// ---- 画布交互 ----
export {
  CanvasInteraction,
  useCanvasInteraction,
  applySelectionHighlight,
  removeSelectionHighlight,
} from './CanvasInteraction'
export type {
  ViewportState,
  InteractionCallbacks,
  InteractionConfig,
} from './CanvasInteraction'

// ---- 渲染器 ----
export {
  YuanMapCanvasRenderer,
  DEFAULT_RENDER_CONFIG,
} from './YuanMapRenderer'
export type { RenderConfig } from './YuanMapRenderer'

// ---- Vue3 Composable ----
export { useYuanMap } from './useYuanMap'
export type { YuanMapOptions, YuanMapState } from './useYuanMap'

// ---- 六边形几何 ----
export {
  offsetToAxial,
  axialToOffset,
  axialToPixel,
  hexCornersFlat,
  hexDistance,
  hexNeighbors,
  pixelToAxial,
  hexRound,
  parseTileId,
  makeTileId,
  HEX_SIZE,
  HEX_WIDTH,
  HEX_HEIGHT,
  GRID_ROWS,
  GRID_MAX_COLS,
  GRID_ODD_COLS,
  TERRAIN_COLORS as HEX_TERRAIN_COLORS,
  FACTION_COLORS,
  FACTION_NAMES,
} from './flatTopHexUtils'
export type { HexCoord, OffsetCoord, HexTile } from './flatTopHexUtils'

// ---- 缩放配置 ----
export {
  ZOOM_RANGES,
  ZOOM_MAX,
  ZOOM_WHEEL_FACTOR,
  ZOOM_HYSTERESIS,
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
} from './mapInteractionConfig'
export type { ZoomRange } from './mapInteractionConfig'

// ---- 疆域包围盒 ----
export {
  calculateTerritoryBounds,
  getTerritoryOrigin,
  setHexSize,
  resetHexSize,
  HEX_RATIO,
} from './flatTopHexUtils'
export type { TerritoryBounds } from './flatTopHexUtils'

// ---- 图层工具 ----
export {
  TERRAIN_COLORS,
  FACTION_LAYER_COLORS,
  ADMIN_BOUNDARY_STYLES,
  FACTION_BOUNDARY_STYLES,
  STRATEGIC_ICONS,
  loadLayerConfig,
  getRemoteConfig,
  getColorSource,
  TERRAIN_NAMES,
} from './layerUtils'
export type {
  LayerState,
  LayerConfig,
  RemoteLayerConfig,
  BoundaryMode,
  MarkersFogMode,
} from './layerUtils'

// ---- 古卷宣纸纹理生成器 ----
export {
  generateInkWashTexture,
  generateTileableTexture,
  getInkWashBackground,
  INK_WASH_DEFAULTS,
} from './InkWashTexture'
export type { InkWashConfig } from './InkWashTexture'

// ---- UI 音效合成器 ----
export {
  playUiSfx,
  initUiSfx,
  destroyUiSfx,
  setUiSfxOptions,
  uiClick,
  uiPanel,
  uiNotify,
  uiAction,
  uiHex,
  uiTurn,
  getAudioContextState,
} from './uiSfx'
export type { SfxCategory, UiSfxOptions } from './uiSfx'

// ---- Vue3 UI 音频插件与 Composable ----
export { UiAudioPlugin, useUiAudio } from './uiAudioPlugin'
export type { UseUiAudioReturn } from './uiAudioPlugin'
