/**
 * 势力着色图层管理器 - 独立势力着色层
 *
 * 职责：
 * 1. 管理每个势力的独立着色图层 (颜色/透明度/高亮/动画过渡)
 * 2. 支持多图层混合模式 (叠加/替换/仅边界)
 * 3. 提供势力切换、高亮、闪烁效果
 * 4. 支持战争迷雾叠加 (可见/探索/未探索)
 *
 * 设计为框架无关的纯 TypeScript 类，通过回调与渲染引擎通信。
 *
 * 使用方式：
 *   const layerMgr = new FactionLayerManager()
 *   layerMgr.registerFaction('faction_yuan', { color: '#8B0000', name: '元廷' })
 *   layerMgr.setActiveLayer('faction_yuan')
 *   // 在渲染循环中:
 *   const color = layerMgr.getTileColor(tileId, baseColor)
 */

// ============================================================
// 类型定义
// ============================================================

export interface FactionLayerEntry {
  factionId: string
  name: string
  color: string
  /** 图层透明度 0-1 */
  opacity: number
  /** 是否可见 */
  visible: boolean
  /** 是否高亮 */
  highlighted: boolean
  /** 高亮强度 0-1 */
  highlightIntensity: number
  /** 高亮颜色覆盖 */
  highlightColor: string
  /** 是否闪烁中 */
  pulsing: boolean
  /** 闪烁阶段 0-1 */
  pulsePhase: number
  /** 领地瓦片 ID 集合 */
  tileIds: Set<string>
}

export interface FactionColorResult {
  /** 最终颜色 (hex) */
  color: string
  /** 最终透明度 0-1 */
  opacity: number
  /** 是否处于高亮状态 */
  highlighted: boolean
  /** 高亮叠加色 (用于 CSS/shader 叠加) */
  glowColor: string
  /** 高亮强度 0-1 */
  glowIntensity: number
  /** 是否为边界瓦片 */
  isBorder: boolean
  /** 闪烁动画相位 0-1 (仅在 pulsing=true 时 >0) */
  pulsePhase: number
}

export interface FactionLayerConfig {
  /** 默认图层透明度 */
  defaultOpacity: number
  /** 高亮默认颜色 */
  highlightDefaultColor: string
  /** 高亮默认强度 */
  highlightDefaultIntensity: number
  /** 闪烁速度 (秒/周期) */
  pulseSpeed: number
  /** 启用动画循环 */
  animationEnabled: boolean
  /** 图层混合模式 */
  blendMode: 'normal' | 'multiply' | 'overlay' | 'screen'
  /** 未分配瓦片的默认颜色 */
  neutralColor: string
  /** 未分配瓦片的透明度 */
  neutralOpacity: number
}

// ============================================================
// 势力颜色预设 v5.0 - 古卷水墨国风
// ============================================================

export const FACTION_COLOR_PRESETS: Record<string, { color: string; name: string }> = {
  faction_yuan:          { color: '#9B4A3A', name: '元廷' },     // 暗赭红
  faction_xushouhui:     { color: '#C47060', name: '徐寿辉' },  // 淡朱砂
  faction_zhuyuanzhang:  { color: '#B85050', name: '朱元璋' },  // 墨朱
  faction_chenyouliang:  { color: '#4A6A8A', name: '陈友谅' },  // 靛青
  faction_zhangshicheng: { color: '#B89850', name: '张士诚' },  // 暗琥珀
  faction_mingyuzhen:    { color: '#A88848', name: '明玉珍' },  // 暗巴蜀金
  faction_fangguozhen:   { color: '#3A7888', name: '方国珍' },  // 海青灰
  faction_wangbaobao:    { color: '#6A5888', name: '王保保' },  // 淡紫檀
  faction_mobei:         { color: '#6A7A5A', name: '漠北诸部' }, // 草灰绿
}

// ============================================================
// 主类
// ============================================================

export class FactionLayerManager {
  // ---- 势力图层 ----
  private _layers: Map<string, FactionLayerEntry> = new Map()

  // ---- 瓦片→势力映射 (用于快速查找) ----
  private _tileFactionMap: Record<string, string> = {}

  // ---- 边界瓦片缓存 ----
  private _borderCache: Map<string, Set<string>> = new Map()

  // ---- 配置 ----
  private _config: FactionLayerConfig

  // ---- 动画 ----
  private _animRaf: number | null = null
  private _lastAnimTime = 0

  // ---- 回调 ----
  onLayerChanged?: (factionId: string) => void
  onConfigChanged?: () => void

  constructor(config?: Partial<FactionLayerConfig>) {
    this._config = {
      defaultOpacity: 0.55,           // 势力层半透明, 透出宣纸底色
      highlightDefaultColor: '#c8a84a', // 高亮: 古金色
      highlightDefaultIntensity: 0.35,
      pulseSpeed: 1.5,
      animationEnabled: true,
      blendMode: 'normal',
      neutralColor: '#4a423a',        // 未分配: 淡墨色
      neutralOpacity: 0.25,
      ...config,
    }
  }

  // ============================================================
  // 势力注册
  // ============================================================

  /**
   * 注册一个势力到图层系统
   */
  registerFaction(
    factionId: string,
    options: { color?: string; name?: string; tileIds?: string[] }
  ): FactionLayerEntry {
    const preset = FACTION_COLOR_PRESETS[factionId]

    const entry: FactionLayerEntry = {
      factionId,
      name: options.name || preset?.name || factionId,
      color: options.color || preset?.color || '#888888',
      opacity: this._config.defaultOpacity,
      visible: true,
      highlighted: false,
      highlightIntensity: this._config.highlightDefaultIntensity,
      highlightColor: this._config.highlightDefaultColor,
      pulsing: false,
      pulsePhase: 0,
      tileIds: new Set(options.tileIds || []),
    }

    this._layers.set(factionId, entry)

    // 更新瓦片映射
    if (options.tileIds) {
      for (const tid of options.tileIds) {
        this._tileFactionMap[tid] = factionId
      }
    }

    return entry
  }

  /**
   * 从 TerritoryDataProvider 批量初始化所有势力
   */
  initializeFromProvider(
    factionTerritories: Record<string, {
      faction_id: string
      color: string
      tile_ids: string[]
      border_tiles: string[]
    }>
  ) {
    for (const [fid, data] of Object.entries(factionTerritories)) {
      const name = FACTION_COLOR_PRESETS[fid]?.name || fid
      this.registerFaction(fid, {
        color: data.color,
        name,
        tileIds: data.tile_ids,
      })
      // 预缓存边界
      if (data.border_tiles?.length) {
        this._borderCache.set(fid, new Set(data.border_tiles))
      }
    }
  }

  /**
   * 注销势力
   */
  unregisterFaction(factionId: string) {
    const entry = this._layers.get(factionId)
    if (entry) {
      // 清除瓦片映射
      for (const tid of entry.tileIds) {
        if (this._tileFactionMap[tid] === factionId) {
          delete this._tileFactionMap[tid]
        }
      }
      this._layers.delete(factionId)
      this._borderCache.delete(factionId)
    }
  }

  // ============================================================
  // 瓦片归属管理
  // ============================================================

  /**
   * 设置瓦片的势力归属
   */
  setTileFaction(tileId: string, factionId: string) {
    const oldFaction = this._tileFactionMap[tileId]

    // 移除旧归属
    if (oldFaction && this._layers.has(oldFaction)) {
      this._layers.get(oldFaction)!.tileIds.delete(tileId)
    }

    // 设置新归属
    if (factionId && this._layers.has(factionId)) {
      this._layers.get(factionId)!.tileIds.add(tileId)
      this._tileFactionMap[tileId] = factionId
    } else {
      delete this._tileFactionMap[tileId]
    }

    // 失效边界缓存
    if (oldFaction) this._borderCache.delete(oldFaction)
    if (factionId) this._borderCache.delete(factionId)
  }

  /**
   * 批量设置瓦片势力归属
   */
  setTilesFaction(tileIds: string[], factionId: string) {
    for (const tid of tileIds) {
      this.setTileFaction(tid, factionId)
    }
  }

  /**
   * 获取瓦片所属势力 ID
   */
  getTileFaction(tileId: string): string | undefined {
    return this._tileFactionMap[tileId]
  }

  /**
   * 判断瓦片是否为势力边界
   */
  isBorderTile(tileId: string, factionId: string, neighborProvider: (tileId: string) => string[]): boolean {
    if (this._borderCache.has(factionId)) {
      return this._borderCache.get(factionId)!.has(tileId)
    }

    // 计算边界缓存
    const borderSet = new Set<string>()
    const factionTiles = this._layers.get(factionId)?.tileIds
    if (factionTiles) {
      for (const tid of factionTiles) {
        const neighbors = neighborProvider(tid)
        for (const nid of neighbors) {
          if (this._tileFactionMap[nid] !== factionId) {
            borderSet.add(tid)
            break
          }
        }
      }
    }
    this._borderCache.set(factionId, borderSet)
    return borderSet.has(tileId)
  }

  // ============================================================
  // 颜色/渲染查询
  // ============================================================

  /**
   * 获取瓦片的最终渲染颜色
   * @param tileId 瓦片 ID
   * @param baseColor 基础地形色 (用于叠加模式)
   * @returns 最终颜色结果
   */
  getTileColor(tileId: string, baseColor?: string): FactionColorResult {
    const factionId = this._tileFactionMap[tileId]

    if (!factionId) {
      // 中立瓦片
      return {
        color: this._config.neutralColor,
        opacity: this._config.neutralOpacity,
        highlighted: false,
        glowColor: 'transparent',
        glowIntensity: 0,
        isBorder: false,
        pulsePhase: 0,
      }
    }

    const layer = this._layers.get(factionId)
    if (!layer || !layer.visible) {
      return {
        color: this._config.neutralColor,
        opacity: this._config.neutralOpacity,
        highlighted: false,
        glowColor: 'transparent',
        glowIntensity: 0,
        isBorder: false,
        pulsePhase: 0,
      }
    }

    // 计算透明度 (考虑闪烁)
    let opacity = layer.opacity
    let glowIntensity = 0
    let glowColor = 'transparent'

    if (layer.highlighted) {
      glowIntensity = layer.highlightIntensity
      glowColor = layer.highlightColor
      opacity = Math.min(1, opacity + 0.15)
    }

    if (layer.pulsing) {
      const pulseBoost = Math.abs(Math.sin(layer.pulsePhase * Math.PI * 2)) * 0.2
      opacity = Math.min(1, opacity + pulseBoost)
      if (layer.highlighted) {
        glowIntensity = Math.min(1, glowIntensity + pulseBoost * 1.5)
      }
    }

    // 叠加模式
    let finalColor = layer.color
    if (this._config.blendMode === 'overlay' && baseColor) {
      finalColor = this._blendOverlay(baseColor, finalColor)
    }

    return {
      color: finalColor,
      opacity: Math.max(0, Math.min(1, opacity)),
      highlighted: layer.highlighted,
      glowColor,
      glowIntensity: Math.max(0, Math.min(1, glowIntensity)),
      isBorder: false, // 由外部 neighborProvider 判断
      pulsePhase: layer.pulsing ? layer.pulsePhase : 0,
    }
  }

  /**
   * 按势力批量获取瓦片颜色 (用于 Canvas 批量绘制优化)
   */
  getFactionTileColors(factionId: string): Map<string, FactionColorResult> {
    const layer = this._layers.get(factionId)
    const results = new Map<string, FactionColorResult>()

    if (!layer || !layer.visible) return results

    for (const tid of layer.tileIds) {
      results.set(tid, this.getTileColor(tid))
    }

    return results
  }

  private _blendOverlay(base: string, overlay: string): string {
    // 简单的线性插值叠加 (50%)
    try {
      const b = this._hexToRgb(base)
      const o = this._hexToRgb(overlay)
      const r = Math.round(b.r * 0.5 + o.r * 0.5)
      const g = Math.round(b.g * 0.5 + o.g * 0.5)
      const bb = Math.round(b.b * 0.5 + o.b * 0.5)
      return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${bb.toString(16).padStart(2, '0')}`
    } catch {
      return overlay
    }
  }

  private _hexToRgb(hex: string): { r: number; g: number; b: number } {
    const h = hex.replace('#', '')
    if (h.length === 3) {
      return {
        r: parseInt(h[0] + h[0], 16),
        g: parseInt(h[1] + h[1], 16),
        b: parseInt(h[2] + h[2], 16),
      }
    }
    return {
      r: parseInt(h.substring(0, 2), 16),
      g: parseInt(h.substring(2, 4), 16),
      b: parseInt(h.substring(4, 6), 16),
    }
  }

  // ============================================================
  // 图层控制
  // ============================================================

  /** 设置势力图层可见性 */
  setVisible(factionId: string, visible: boolean) {
    const layer = this._layers.get(factionId)
    if (layer) {
      layer.visible = visible
      this.onLayerChanged?.(factionId)
    }
  }

  /** 设置势力图层透明度 */
  setOpacity(factionId: string, opacity: number) {
    const layer = this._layers.get(factionId)
    if (layer) {
      layer.opacity = Math.max(0, Math.min(1, opacity))
      this.onLayerChanged?.(factionId)
    }
  }

  /** 设置全局透明度 */
  setGlobalOpacity(opacity: number) {
    const clamped = Math.max(0, Math.min(1, opacity))
    for (const layer of this._layers.values()) {
      layer.opacity = clamped
    }
    this.onConfigChanged?.()
  }

  /** 高亮指定势力 */
  highlight(factionId: string, color?: string, intensity?: number) {
    const layer = this._layers.get(factionId)
    if (layer) {
      layer.highlighted = true
      layer.highlightColor = color || this._config.highlightDefaultColor
      layer.highlightIntensity = intensity ?? this._config.highlightDefaultIntensity
      this.onLayerChanged?.(factionId)
    }
  }

  /** 取消高亮 */
  unhighlight(factionId: string) {
    const layer = this._layers.get(factionId)
    if (layer) {
      layer.highlighted = false
      layer.highlightIntensity = 0
      this.onLayerChanged?.(factionId)
    }
  }

  /** 取消所有高亮 */
  unhighlightAll() {
    for (const layer of this._layers.values()) {
      layer.highlighted = false
      layer.highlightIntensity = 0
    }
    this.onConfigChanged?.()
  }

  /** 闪烁指定势力 (用于警告/通知) */
  startPulse(factionId: string) {
    const layer = this._layers.get(factionId)
    if (layer) {
      layer.pulsing = true
      layer.pulsePhase = 0
    }
  }

  /** 停止闪烁 */
  stopPulse(factionId: string) {
    const layer = this._layers.get(factionId)
    if (layer) {
      layer.pulsing = false
      layer.pulsePhase = 0
    }
  }

  /** 停止所有闪烁 */
  stopAllPulse() {
    for (const layer of this._layers.values()) {
      layer.pulsing = false
      layer.pulsePhase = 0
    }
  }

  /** 设置图层混合模式 */
  setBlendMode(mode: FactionLayerConfig['blendMode']) {
    this._config.blendMode = mode
    this.onConfigChanged?.()
  }

  /** 更新配置 */
  updateConfig(config: Partial<FactionLayerConfig>) {
    Object.assign(this._config, config)
    this.onConfigChanged?.()
  }

  get config(): Readonly<FactionLayerConfig> {
    return this._config
  }

  /**
   * 获取所有已注册势力 ID 列表
   */
  getRegisteredFactions(): string[] {
    return Array.from(this._layers.keys())
  }

  /**
   * 获取势力图层信息
   */
  getLayer(factionId: string): Readonly<FactionLayerEntry> | undefined {
    return this._layers.get(factionId)
  }

  // ============================================================
  // 动画循环
  // ============================================================

  /**
   * 启动动画循环
   */
  startAnimation() {
    if (!this._config.animationEnabled) return
    if (this._animRaf !== null) return

    this._lastAnimTime = performance.now()

    const tick = (now: number) => {
      const dt = (now - this._lastAnimTime) / 1000
      this._lastAnimTime = now

      let hasPulsing = false
      for (const layer of this._layers.values()) {
        if (layer.pulsing) {
          layer.pulsePhase = (layer.pulsePhase + dt / this._config.pulseSpeed) % 1
          hasPulsing = true
        }
      }

      this._animRaf = hasPulsing ? requestAnimationFrame(tick) : null
    }

    this._animRaf = requestAnimationFrame(tick)
  }

  /**
   * 停止动画循环
   */
  stopAnimation() {
    if (this._animRaf !== null) {
      cancelAnimationFrame(this._animRaf)
      this._animRaf = null
    }
  }

  // ============================================================
  // 清理
  // ============================================================

  destroy() {
    this.stopAnimation()
    this._layers.clear()
    this._tileFactionMap = {}
    this._borderCache.clear()
    this.onLayerChanged = undefined
    this.onConfigChanged = undefined
  }
}
