/**
 * CK3风格暖羊皮纸地图纹理生成器 v6.0
 *
 * 生成程序化"暖羊皮纸古卷"底板:
 * - 暖黄褐色纸张基调（适配CK3风格）
 * - 密集纤维纹理（模拟羊皮纸肌理）
 * - 不规则做旧水渍（年代感）
 * - 边缘磨损折痕
 * - 势力专属水彩纹理图案（每个势力带独特纹理）
 *
 * 使用 Canvas2D 程序化生成, 零外部依赖。
 */

export interface InkWashConfig {
  /** 纹理宽度 */
  width: number
  /** 纹理高度 */
  height: number
  /** 基底色 (暖羊皮纸) */
  baseColor: string
  /** 纤维密度 (0-1, 默认0.5) */
  fiberDensity: number
  /** 做旧强度 (0-1, 默认0.5) */
  agingIntensity: number
  /** 水渍数量 */
  stainCount: number
  /** 暗角强度 (0-1) */
  vignetteStrength: number
}

export const INK_WASH_DEFAULTS: InkWashConfig = {
  width: 2048,
  height: 1536,
  baseColor: '#c4b898',
  fiberDensity: 0.5,
  agingIntensity: 0.5,
  stainCount: 16,
  vignetteStrength: 0.4,
}

// ===== 势力色水彩纹理生成配置 =====
interface FactionTextureConfig {
  baseColor: string
  accentColor: string
  textureIntensity: number
  grain: number
}

const FACTION_TEXTURES: Record<string, FactionTextureConfig> = {
  faction_yuan:          { baseColor: '#9B4A3A', accentColor: '#B86858', textureIntensity: 0.22, grain: 0.4 },
  faction_xushouhui:     { baseColor: '#C47060', accentColor: '#E09080', textureIntensity: 0.22, grain: 0.4 },
  faction_zhuyuanzhang:  { baseColor: '#B85050', accentColor: '#D47070', textureIntensity: 0.24, grain: 0.4 },
  faction_chenyouliang:  { baseColor: '#4A6A8A', accentColor: '#6A8AAA', textureIntensity: 0.20, grain: 0.4 },
  faction_zhangshicheng: { baseColor: '#B89850', accentColor: '#D4B870', textureIntensity: 0.20, grain: 0.4 },
  faction_fangguozhen:   { baseColor: '#3A7888', accentColor: '#5A98A8', textureIntensity: 0.20, grain: 0.4 },
  faction_wangbaobao:    { baseColor: '#6A5888', accentColor: '#8A78A8', textureIntensity: 0.20, grain: 0.4 },
  faction_mingyuzhen:    { baseColor: '#A88848', accentColor: '#C8A868', textureIntensity: 0.20, grain: 0.4 },
  faction_mobei:         { baseColor: '#6A7A5A', accentColor: '#8A9A7A', textureIntensity: 0.18, grain: 0.4 },
  neutral:               { baseColor: '#9A8A7A', accentColor: '#B0A090', textureIntensity: 0.15, grain: 0.3 },
}

/** 缓存势力纹理图案 */
let _factionPatternCache: Record<string, HTMLCanvasElement> = {}

/**
 * 生成羊皮纸古卷纹理 Canvas
 */
export function generateInkWashTexture(config?: Partial<InkWashConfig>): HTMLCanvasElement {
  const cfg = { ...INK_WASH_DEFAULTS, ...config }
  const canvas = document.createElement('canvas')
  canvas.width = cfg.width
  canvas.height = cfg.height
  const ctx = canvas.getContext('2d')!

  // 1. 暖羊皮纸底色填充
  ctx.fillStyle = cfg.baseColor
  ctx.fillRect(0, 0, cfg.width, cfg.height)

  // 2. 细密纤维纹理（羊皮纸肌理）
  _renderFiberTexture(ctx, cfg)

  // 3. 随机水渍做旧
  _renderStains(ctx, cfg)

  // 4. 边缘磨损折痕
  _renderEdgeWear(ctx, cfg)

  // 5. 暖色暗角（模拟古卷照明效果）
  _renderVignette(ctx, cfg)

  // 6. 细微噪点
  _renderNoise(ctx, cfg)

  return canvas
}

/**
 * 生成势力专属水彩纹理图案（用于六边形填充）
 */
export function getFactionTextureCanvas(factionId: string, size: number = 64): HTMLCanvasElement | null {
  const cfg = FACTION_TEXTURES[factionId]
  if (!cfg) return null
  const cacheKey = `${factionId}_${size}`
  if (_factionPatternCache[cacheKey]) return _factionPatternCache[cacheKey]

  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!

  // 底色（势力色但稍暗，用于做底色）
  ctx.fillStyle = cfg.baseColor
  ctx.fillRect(0, 0, size, size)

  // 水彩晕染：随机色块叠加
  const accentCount = Math.floor(6 + Math.random() * 6)
  for (let i = 0; i < accentCount; i++) {
    const cx = Math.random() * size
    const cy = Math.random() * size
    const r = size * (0.2 + Math.random() * 0.5)
    const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, r)
    const alpha = cfg.textureIntensity * (0.3 + Math.random() * 0.4)
    gradient.addColorStop(0, _hexToRgba(cfg.accentColor, alpha))
    gradient.addColorStop(0.6, _hexToRgba(cfg.baseColor, alpha * 0.5))
    gradient.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.fill()
  }

  // 细微纹理噪点（增加纸质肌理）
  const imageData = ctx.getImageData(0, 0, size, size)
  const data = imageData.data
  for (let i = 0; i < data.length; i += 4) {
    const grain = (Math.random() - 0.5) * 18 * cfg.grain
    data[i] = Math.max(0, Math.min(255, data[i] + grain))
    data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + grain))
    data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + grain))
  }
  ctx.putImageData(imageData, 0, 0)

  // 绘制不规则边缘（模拟水彩边缘晕染）
  ctx.strokeStyle = _hexToRgba(cfg.baseColor, 0.15)
  ctx.lineWidth = 1
  for (let i = 0; i < 4; i++) {
    ctx.beginPath()
    const sx = Math.random() * size
    const sy = Math.random() * size
    ctx.moveTo(sx, sy)
    ctx.lineTo(sx + (Math.random() - 0.5) * size * 0.6, sy + (Math.random() - 0.5) * size * 0.6)
    ctx.stroke()
  }

  _factionPatternCache[cacheKey] = canvas
  return canvas
}

/** 清除势力纹理缓存 */
export function clearFactionTextureCache() {
  _factionPatternCache = {}
}

/**
 * 将纹理设为容器背景 (返回 CSS backgroundImage 值)
 */
export function getInkWashBackground(texture?: HTMLCanvasElement): string {
  if (!texture) return '#c4b898'
  try {
    const dataUrl = texture.toDataURL('image/jpeg', 0.85)
    return `url(${dataUrl})`
  } catch {
    return '#c4b898'
  }
}

/**
 * 生成适合全屏平铺的小尺寸纹理
 */
export function generateTileableTexture(tileSize: number = 512): HTMLCanvasElement {
  return generateInkWashTexture({
    width: tileSize,
    height: tileSize,
    fiberDensity: 0.3,
    agingIntensity: 0.3,
    stainCount: 3,
    vignetteStrength: 0,
  })
}

// ============================================================
// 内部渲染函数
// ============================================================

/** 纤维纹理 - 羊皮纸植物纤维网格 */
function _renderFiberTexture(ctx: CanvasRenderingContext2D, cfg: InkWashConfig) {
  const { width, height, fiberDensity } = cfg
  const imageData = ctx.getImageData(0, 0, width, height)
  const data = imageData.data

  // 水平纤维线（密集横向肌理）
  const hLines = Math.floor(height * fiberDensity * 0.8)
  for (let i = 0; i < hLines; i++) {
    const y = Math.floor(Math.random() * height)
    const opacity = 0.01 + Math.random() * 0.03
    const len = width * (0.4 + Math.random() * 0.6)
    const startX = Math.floor(Math.random() * (width - len))
    for (let x = startX; x < startX + len; x++) {
      if (x < 0 || x >= width || y < 0 || y >= height) continue
      const idx = (y * width + x) * 4
      const bump = Math.floor(opacity * 255)
      // 暖色调微调（更偏黄褐）
      data[idx] = Math.min(255, data[idx] + bump + 2)
      data[idx + 1] = Math.min(255, data[idx + 1] + bump)
      data[idx + 2] = Math.max(0, data[idx + 2] - bump)
    }
  }

  // 垂直纤维线（稀疏纵向肌理）
  const vLines = Math.floor(width * fiberDensity * 0.3)
  for (let i = 0; i < vLines; i++) {
    const x = Math.floor(Math.random() * width)
    const opacity = 0.01 + Math.random() * 0.02
    const len = height * (0.2 + Math.random() * 0.5)
    const startY = Math.floor(Math.random() * (height - len))
    for (let y = startY; y < startY + len; y++) {
      if (x < 0 || x >= width || y < 0 || y >= height) continue
      const idx = (y * width + x) * 4
      const bump = Math.floor(opacity * 255)
      data[idx] = Math.min(255, data[idx] + bump + 2)
      data[idx + 1] = Math.min(255, data[idx + 1] + bump)
      data[idx + 2] = Math.max(0, data[idx + 2] - bump)
    }
  }

  // 纤维团簇（不规则斑点，模拟羊皮纸纤维团）
  const clusters = Math.floor(width * height * fiberDensity * 0.00003)
  for (let i = 0; i < clusters; i++) {
    const cx = Math.random() * width
    const cy = Math.random() * height
    const r = 2 + Math.random() * 10
    const opacity = 0.01 + Math.random() * 0.02
    for (let dy = -r; dy < r; dy++) {
      for (let dx = -r; dx < r; dx++) {
        if (dx * dx + dy * dy > r * r) continue
        const x = Math.floor(cx + dx)
        const y = Math.floor(cy + dy)
        if (x < 0 || x >= width || y < 0 || y >= height) continue
        const dist = Math.sqrt(dx * dx + dy * dy) / r
        const idx = (y * width + x) * 4
        const bump = Math.floor(opacity * (1 - dist) * 255)
        data[idx] = Math.min(255, data[idx] + bump + 1)
        data[idx + 1] = Math.min(255, data[idx + 1] + bump)
        data[idx + 2] = Math.max(0, data[idx + 2] - bump)
      }
    }
  }

  ctx.putImageData(imageData, 0, 0)
}

/** 随机水渍 - 模拟古卷年代痕迹 */
function _renderStains(ctx: CanvasRenderingContext2D, cfg: InkWashConfig) {
  const { width, height, stainCount, agingIntensity } = cfg

  for (let i = 0; i < stainCount; i++) {
    const cx = width * 0.05 + Math.random() * width * 0.9
    const cy = height * 0.05 + Math.random() * height * 0.9
    const maxR = 20 + Math.random() * 100

    const parts = 3 + Math.floor(Math.random() * 4)
    for (let j = 0; j < parts; j++) {
      const ox = (Math.random() - 0.5) * maxR * 0.8
      const oy = (Math.random() - 0.5) * maxR * 0.8
      const r = maxR * (0.3 + Math.random() * 0.7)
      const alpha = (0.02 + Math.random() * 0.06) * agingIntensity

      const gradient = ctx.createRadialGradient(cx + ox, cy + oy, r * 0.1, cx + ox, cy + oy, r)
      const darken = 20 + Math.floor(Math.random() * 20)
      // 暖色调水渍（偏黄褐）
      gradient.addColorStop(0, `rgba(${darken+8},${darken+3},${darken-5},${alpha})`)
      gradient.addColorStop(0.5, `rgba(${darken+5},${darken},${darken-8},${alpha * 0.5})`)
      gradient.addColorStop(1, 'rgba(0,0,0,0)')

      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(cx + ox, cy + oy, r, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // 边缘水渍痕迹
  for (let edge = 0; edge < 4; edge++) {
    const count = Math.floor(2 + Math.random() * 3)
    for (let i = 0; i < count; i++) {
      let cx: number, cy: number
      const dist = 5 + Math.random() * 35
      switch (edge) {
        case 0: cx = Math.random() * width; cy = dist; break
        case 1: cx = Math.random() * width; cy = height - dist; break
        case 2: cx = dist; cy = Math.random() * height; break
        default: cx = width - dist; cy = Math.random() * height; break
      }
      const r = 20 + Math.random() * 50
      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, r)
      gradient.addColorStop(0, `rgba(40,32,18,0.12)`)
      gradient.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.fill()
    }
  }
}

/** 边缘磨损折痕 */
function _renderEdgeWear(ctx: CanvasRenderingContext2D, cfg: InkWashConfig) {
  const { width, height } = cfg
  ctx.save()
  ctx.strokeStyle = 'rgba(60,50,30,0.08)'
  ctx.lineWidth = 1
  // 不规则折痕线
  for (let i = 0; i < 6; i++) {
    ctx.beginPath()
    let x = Math.random() * width
    let y = Math.random() * height
    ctx.moveTo(x, y)
    for (let s = 0; s < 4; s++) {
      x += (Math.random() - 0.5) * width * 0.4
      y += (Math.random() - 0.5) * height * 0.4
      ctx.lineTo(x, y)
    }
    ctx.stroke()
  }
  ctx.restore()
}

/** 暖色暗角（模拟古卷照明） */
function _renderVignette(ctx: CanvasRenderingContext2D, cfg: InkWashConfig) {
  const { width, height, vignetteStrength } = cfg
  const cx = width / 2
  const cy = height / 2
  const maxR = Math.sqrt(cx * cx + cy * cy)

  const gradient = ctx.createRadialGradient(cx, cy, maxR * 0.3, cx, cy, maxR)
  gradient.addColorStop(0, 'rgba(60,50,30,0)')
  gradient.addColorStop(0.6, 'rgba(60,50,30,0)')
  gradient.addColorStop(0.85, `rgba(50,40,20,${vignetteStrength * 0.4})`)
  gradient.addColorStop(1, `rgba(40,30,15,${vignetteStrength * 0.7})`)

  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, width, height)
}

/** 细微噪点 */
function _renderNoise(ctx: CanvasRenderingContext2D, cfg: InkWashConfig) {
  const { width, height } = cfg
  const imageData = ctx.getImageData(0, 0, width, height)
  const data = imageData.data

  for (let i = 0; i < data.length; i += 16) {
    const noise = (Math.random() - 0.5) * 10
    data[i] = Math.max(0, Math.min(255, data[i] + noise))
    data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + noise))
    data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + noise))
  }

  ctx.putImageData(imageData, 0, 0)
}

/** 将 hex 颜色转换为 rgba 字符串 */
function _hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}
