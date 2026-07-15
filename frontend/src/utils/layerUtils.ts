/**
 * 地图图层系统工具 v2.0 - 14大图层完整管理
 *
 * 重构为基于 layerConfig.ts 的通用图层管理，
 * 支持显隐/透明度/zIndex/锁定/缩放自适应/预设切换
 */

import { ref, computed, reactive, watch } from 'vue'
import {
  DEFAULT_LAYERS,
  LAYER_CATEGORIES,
  LAYER_PRESETS,
  type LayerDef,
  type LayerPreset,
  type BoundaryMode,
} from './layerConfig'

// ===== API 加载图层配置 =====

export interface RemoteLayerConfig {
  layers: Record<string, any>
  faction_colors: Record<string, any>
  admin_zoom_levels: Record<string, any>
  fog_of_war: Record<string, any>
}

let _remoteConfig: RemoteLayerConfig | null = null

export async function loadLayerConfig(apiBase: string = '/api'): Promise<RemoteLayerConfig> {
  const res = await fetch(`${apiBase}/map/layer-config`)
  if (!res.ok) throw new Error(`加载图层配置失败: ${res.status}`)
  const data = await res.json()
  const payload = data.data || data
  _remoteConfig = payload
  return payload
}

export function getRemoteConfig(): RemoteLayerConfig | null {
  return _remoteConfig
}

export function getColorSource(): 'remote' | 'local' {
  return _remoteConfig ? 'remote' : 'local'
}

// ===== 地形颜色映射 =====

export const TERRAIN_COLORS: Record<string, string> = {
  flatland: '#a09070',
  mountain: '#6b727a',
  water: '#5a788a',
  forest: '#3a4a3a',
  hill: '#8a7a62',
  wetland: '#5a6a5a',
  desert: '#9a8a72',
  coastal: '#7a8a82',
  steppe: '#8a9272',
  taiga: '#4a5242',
  oasis: '#6a8a62',
  water_river: '#5a788a',
  water_lake: '#4a6880',
  sea: '#3a5870',
  unknown: '#6a625a',
}

export const TERRAIN_NAMES: Record<string, string> = {
  flatland: '平地', mountain: '山地', water: '水域', forest: '林地',
  hill: '丘陵', wetland: '湿地', desert: '荒漠', coastal: '沿海',
  steppe: '草原', taiga: '冻土林', oasis: '绿洲',
}

// ===== 势力颜色映射 =====

export const FACTION_LAYER_COLORS: Record<string, { color: string; border: string; name: string }> = {
  faction_yuan:          { color: '#9B4A3A', border: '#6A3020', name: '元廷' },
  faction_xushouhui:     { color: '#C47060', border: '#8A4840', name: '徐寿辉' },
  faction_zhuyuanzhang:  { color: '#B85050', border: '#803038', name: '朱元璋' },
  faction_chenyouliang:  { color: '#4A6A8A', border: '#2A4A6A', name: '陈友谅' },
  faction_zhangshicheng: { color: '#B89850', border: '#806830', name: '张士诚' },
  faction_mingyuzhen:    { color: '#A88848', border: '#786028', name: '明玉珍' },
  faction_fangguozhen:   { color: '#3A7888', border: '#1A5060', name: '方国珍' },
  faction_wangbaobao:    { color: '#6A5888', border: '#4A3868', name: '王保保' },
  faction_mobei:         { color: '#6A7A5A', border: '#4A5A3A', name: '漠北诸部' },
  neutral:               { color: '#9A8A7A', border: '#6A5A4A', name: '中立' },
}

// ===== 边界样式 =====

export const ADMIN_BOUNDARY_STYLES: Record<string, { color: string; lineWidth: number; dash: number[]; opacity: number }> = {
  province:   { color: '#3A2210', lineWidth: 4.5, dash: [],          opacity: 0.85 },
  circuit:    { color: '#5A3A1A', lineWidth: 2.8, dash: [12, 7],     opacity: 0.70 },
  prefecture: { color: '#4A3020', lineWidth: 1.2, dash: [4, 3],      opacity: 0.40 },
}

/** 势力边界三级描边 */
export const FACTION_BOUNDARY_STYLES: Record<string, { color: string; lineWidth: number; dash: number[] }> = {
  own:      { color: '#D4A840', lineWidth: 3.5, dash: [] },            // 本国国境——金边
  ally:     { color: '#5A9A5A', lineWidth: 2.5, dash: [10, 5] },      // 同盟边境——绿边
  enemy:    { color: '#C03030', lineWidth: 3.0, dash: [8, 3] },       // 敌对阵线——红边
  neutral:  { color: '#8A7A6A', lineWidth: 1.5, dash: [4, 6] },       // 中立——灰边
}

// ===== 战略图标 =====

export const STRATEGIC_ICONS: Record<string, { symbol: string; color: string }> = {
  capital:   { symbol: '★', color: '#E8C040' },
  port:      { symbol: '◎', color: '#7a8a92' },
  pass:      { symbol: '▲', color: '#8a6a5a' },
  ferry:     { symbol: '〰', color: '#6a7a8a' },
  strategic: { symbol: '▣', color: '#7a6a52' },
}

// ===== 缩放级别定义 =====

export interface AdminZoomLevel {
  key: string; name: string; level: string
  zoomScale: number; showBoundaries: string[]; showLabels: string[]; description: string
}

export const ADMIN_ZOOM_LEVELS: AdminZoomLevel[] = [
  { key: 'world', name: '天下大势', level: 'province', zoomScale: 0.25,
    showBoundaries: ['province'], showLabels: ['province'],
    description: '显示所有行省轮廓和行省名称标签' },
  { key: 'circuit', name: '各路形势', level: 'circuit', zoomScale: 0.50,
    showBoundaries: ['province', 'circuit'], showLabels: ['province', 'circuit'],
    description: '显示各路边界和标签' },
  { key: 'prefecture', name: '府州详情', level: 'prefecture', zoomScale: 0.90,
    showBoundaries: ['province', 'circuit'], showLabels: ['province', 'circuit', 'prefecture'],
    description: '显示各府州标签与详情' },
]

// ===== 辅助函数 =====

export function getFactionColor(factionId: string): string | null {
  if (!factionId) return null
  if (_remoteConfig?.faction_colors) {
    const cfg = _remoteConfig.faction_colors[factionId]
    if (cfg) return cfg.color || cfg.fill || cfg
  }
  return FACTION_LAYER_COLORS[factionId]?.color ?? null
}

export function getFactionBorder(factionId: string): string | null {
  if (!factionId) return null
  if (_remoteConfig?.faction_colors) {
    const cfg = _remoteConfig.faction_colors[factionId]
    if (cfg) return cfg.border || cfg
  }
  return FACTION_LAYER_COLORS[factionId]?.border ?? null
}

export function getTerrainDisplayColor(terrain: string): string {
  if (_remoteConfig?.layers?.terrain?.colors) {
    const c = _remoteConfig.layers.terrain.colors[terrain]
    if (c) return c
  }
  return TERRAIN_COLORS[terrain] || '#8B9A6B'
}

// ====================================================================
// 核心：useMapLayers composable (14层版本)
// ====================================================================

export interface LayerRuntimeState {
  id: string
  name: string
  nameShort: string
  category: string
  icon: string
  visible: boolean
  opacity: number
  zIndex: number
  locked: boolean
  faded: boolean
  zoomMin: number
  zoomMax: number
  tooltip: string
}

export function useMapLayers() {
  // 初始化14个图层
  const layers = reactive<Record<string, LayerRuntimeState>>(
    Object.fromEntries(
      DEFAULT_LAYERS.map(d => [d.id, { ...d }])
    )
  )

  // 边界子模式
  const boundaryMode = ref<BoundaryMode>('faction')
  // 当前行政缩放级别
  const currentZoomLevel = ref<AdminZoomLevel>(ADMIN_ZOOM_LEVELS[1])
  const selectedAdminId = ref<string | null>(null)
  // 当前视口缩放值（外部注入）
  const currentScale = ref(1.0)

  // 按zIndex排序的可见图层列表
  const visibleLayers = computed(() => {
    return Object.values(layers)
      .filter(l => l.visible)
      .sort((a, b) => a.zIndex - b.zIndex)
      .map(l => l.id)
  })

  // 按分类分组
  const layersByCategory = computed(() => {
    const groups: Record<string, LayerRuntimeState[]> = {}
    for (const cat of LAYER_CATEGORIES) {
      groups[cat.id] = Object.values(layers).filter(l => l.category === cat.id)
    }
    return groups
  })

  /** 获取图层完整状态 */
  function getLayer(id: string): LayerRuntimeState | undefined {
    return layers[id]
  }

  /** 切换图层显隐 */
  function toggleLayer(layerId: string) {
    const layer = layers[layerId]
    if (layer && !layer.locked) {
      layer.visible = !layer.visible
    }
  }

  /** 设置图层透明度 */
  function setLayerOpacity(layerId: string, opacity: number) {
    const layer = layers[layerId]
    if (layer) {
      layer.opacity = Math.max(0, Math.min(1, opacity))
    }
  }

  /** 锁定/解锁图层 */
  function toggleLayerLock(layerId: string) {
    const layer = layers[layerId]
    if (layer) layer.locked = !layer.locked
  }

  /** 淡化/正常图层 */
  function toggleLayerFade(layerId: string) {
    const layer = layers[layerId]
    if (layer) layer.faded = !layer.faded
  }

  /** 设置图层Z序 */
  function setLayerZIndex(layerId: string, zIndex: number) {
    const layer = layers[layerId]
    if (layer) layer.zIndex = zIndex
  }

  /** 上移图层 */
  function moveLayerUp(layerId: string) {
    const layer = layers[layerId]
    if (!layer) return
    const maxZ = Math.max(...Object.values(layers).map(l => l.zIndex))
    layer.zIndex = Math.min(maxZ + 1, 99)
  }

  /** 下移图层 */
  function moveLayerDown(layerId: string) {
    const layer = layers[layerId]
    if (!layer) return
    const minZ = Math.min(...Object.values(layers).map(l => l.zIndex))
    layer.zIndex = Math.max(minZ - 1, 0)
  }

  /** 复位所有图层到默认状态 */
  function resetAllLayers() {
    for (const def of DEFAULT_LAYERS) {
      layers[def.id].visible = def.visible
      layers[def.id].opacity = def.opacity
      layers[def.id].zIndex = def.zIndex
      layers[def.id].locked = def.locked
      layers[def.id].faded = false
    }
  }

  /** 应用预设 */
  function applyPreset(presetId: string) {
    const preset = LAYER_PRESETS.find(p => p.id === presetId)
    if (!preset) return
    for (const [layerId, visible] of Object.entries(preset.layerVisibility)) {
      const layer = layers[layerId]
      if (layer && !layer.locked) {
        layer.visible = visible
      }
    }
  }

  /** 快捷模式切换（兼容旧API） */
  function setLayerMode(mode: string) {
    const presetMap: Record<string, string> = {
      terrain: 'terrain_only',
      faction: 'clean',
      combined: 'all',
      admin: 'diplomacy_view',
      borders: 'military',
      all: 'all',
      military: 'military',
      civil: 'civil',
    }
    const preset = presetMap[mode] || mode
    applyPreset(preset)
  }

  /** 根据当前缩放比例自动调整图层显隐 */
  function updateZoomAdaptive(scale: number) {
    currentScale.value = scale
    for (const layer of Object.values(layers)) {
      if (layer.locked) continue
      if (layer.zoomMin > 0 && scale < layer.zoomMin) {
        // 缩放过小，该图层细节无意义，自动隐藏
        if (layer.visible && !layer._zoomHidden) {
          (layer as any)._zoomHidden = true
          (layer as any)._prevVisible = true
        }
      } else if ((layer as any)._zoomHidden && layer.zoomMin > 0 && scale >= layer.zoomMin) {
        delete (layer as any)._zoomHidden
        if ((layer as any)._prevVisible) {
          layer.visible = true
          delete (layer as any)._prevVisible
        }
      }
    }
  }

  return {
    layers,
    boundaryMode,
    currentZoomLevel,
    selectedAdminId,
    visibleLayers,
    layersByCategory,
    currentScale,
    getLayer,
    toggleLayer,
    setLayerOpacity,
    toggleLayerLock,
    toggleLayerFade,
    setLayerZIndex,
    moveLayerUp,
    moveLayerDown,
    resetAllLayers,
    applyPreset,
    setLayerMode,
    updateZoomAdaptive,
  }
}
