<template>
  <!-- 游戏主界面·舆图沙盘 —— 金戈铁马、运筹帷幄 -->
  <canvas ref="canvas" class="bg-canvas game-sandtable-bg"></canvas>
</template>

<script setup lang="ts">
/**
 * 游戏主界面动态背景：舆图沙盘
 * 
 * 视觉意象：
 * - 底层：大地舆图色块缓慢漂移（秋色/草原/荒漠/水域色带）
 * - 中层：极淡的六边形网格脉动（呼应HexMap的六边形地图）
 * - 上层：行军路线虚线流动（从城池到城池，金色虚线推进）
 * - 天气系统：随机沙尘暴/细雨/雪飘（根据游戏季节）
 * - 边角：营帐篝火微光闪烁
 * - 整体氛围：沙场点兵、运筹千里、天下在握
 */
import { ref, onMounted, onUnmounted } from 'vue'

const canvas = ref<HTMLCanvasElement>()
let animId = 0
let resizeTimer: ReturnType<typeof setTimeout> | null = null

interface TerrainBlob {
  x: number; y: number
  r: number
  vx: number; vy: number
  color: [number, number, number]
  alpha: number
}

interface MarchRoute {
  fromX: number; fromY: number
  toX: number; toY: number
  progress: number
  speed: number
  alpha: number
}

interface CampFire {
  x: number; y: number
  r: number
  flicker: number
  speed: number
  baseAlpha: number
}

interface WeatherParticle {
  x: number; y: number
  vx: number; vy: number
  alpha: number
  size: number
  life: number
  type: number // 0=沙尘, 1=细雨, 2=雪
}

let terrainBlobs: TerrainBlob[] = []
let marchRoutes: MarchRoute[] = []
let campFires: CampFire[] = []
let weatherParticles: WeatherParticle[] = []
let time = 0
let W = 0
let H = 0

// 地形色板
const TERRAIN_COLORS: Array<[number, number, number]> = [
  [90, 110, 65],   // 农田绿
  [110, 90, 55],   // 荒漠褐
  [70, 100, 60],   // 草原绿
  [120, 100, 70],  // 山地黄褐
  [80, 95, 85],    // 水域青
  [100, 80, 50],   // 赤土
]

onMounted(() => {
  initCanvas()
  window.addEventListener('resize', onResize)
  animate()
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', onResize)
  if (resizeTimer) clearTimeout(resizeTimer)
})

function onResize() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => initCanvas(), 200)
}

function initCanvas() {
  const c = canvas.value
  if (!c) return
  c.width = window.innerWidth
  c.height = window.innerHeight
  W = c.width
  H = c.height

  // 大地舆图色块
  terrainBlobs = []
  for (let i = 0; i < 12; i++) {
    terrainBlobs.push({
      x: Math.random() * W,
      y: Math.random() * H,
      r: 150 + Math.random() * 350,
      vx: (Math.random() - 0.5) * 0.15,
      vy: (Math.random() - 0.5) * 0.15,
      color: TERRAIN_COLORS[Math.floor(Math.random() * TERRAIN_COLORS.length)],
      alpha: 0.03 + Math.random() * 0.03,
    })
  }

  // 行军路线
  marchRoutes = []
  for (let i = 0; i < 6; i++) {
    marchRoutes.push({
      fromX: Math.random() * W * 0.8 + W * 0.1,
      fromY: Math.random() * H * 0.8 + H * 0.1,
      toX: Math.random() * W * 0.8 + W * 0.1,
      toY: Math.random() * H * 0.8 + H * 0.1,
      progress: Math.random(),
      speed: 0.0003 + Math.random() * 0.0008,
      alpha: 0.04 + Math.random() * 0.04,
    })
  }

  // 营帐篝火
  campFires = [
    { x: W * 0.05, y: H * 0.15, r: 40, flicker: 0, speed: 0.04, baseAlpha: 0.06 },
    { x: W * 0.95, y: H * 0.1, r: 35, flicker: 1, speed: 0.05, baseAlpha: 0.05 },
    { x: W * 0.08, y: H * 0.85, r: 45, flicker: 2, speed: 0.035, baseAlpha: 0.06 },
    { x: W * 0.92, y: H * 0.88, r: 38, flicker: 3, speed: 0.045, baseAlpha: 0.05 },
  ]

  // 天气粒子
  weatherParticles = []
  const weatherType = Math.floor(Math.abs(Math.sin(Date.now() * 0.0001)) * 3) // 模拟季节变化
  for (let i = 0; i < 40; i++) {
    weatherParticles.push(createWeatherParticle(weatherType))
  }
}

function createWeatherParticle(type?: number): WeatherParticle {
  const t = type ?? Math.floor(Math.random() * 3)
  const isDust = t === 0
  const isRain = t === 1
  return {
    x: Math.random() * W,
    y: isDust ? Math.random() * H : -10 - Math.random() * 50,
    vx: isDust ? 0.4 + Math.random() * 1.2 : (Math.random() - 0.5) * 0.4,
    vy: isDust ? (Math.random() - 0.5) * 0.2 : (isRain ? 1.5 + Math.random() * 2 : 0.3 + Math.random() * 0.6),
    alpha: 0.015 + Math.random() * 0.03,
    size: isDust ? 2 + Math.random() * 3 : (isRain ? 0.5 + Math.random() * 1 : 1.5 + Math.random() * 3),
    life: Math.random(),
    type: t,
  }
}

function animate() {
  const c = canvas.value
  if (!c) return
  const ctx = c.getContext('2d')
  if (!ctx) return

  time += 1
  ctx.clearRect(0, 0, W, H)

  // 1. 大地舆图色块漂移
  for (const blob of terrainBlobs) {
    blob.x += blob.vx
    blob.y += blob.vy
    if (blob.x < -blob.r) blob.x = W + blob.r
    if (blob.x > W + blob.r) blob.x = -blob.r
    if (blob.y < -blob.r) blob.y = H + blob.r
    if (blob.y > H + blob.r) blob.y = -blob.r

    const [r, g, b] = blob.color
    const grad = ctx.createRadialGradient(blob.x, blob.y, 0, blob.x, blob.y, blob.r)
    grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${blob.alpha})`)
    grad.addColorStop(1, 'rgba(24, 20, 16, 0)')
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.arc(blob.x, blob.y, blob.r, 0, Math.PI * 2)
    ctx.fill()
  }

  // 2. 六边形网格脉动（呼应HexMap）
  const hexSize = 35
  const hexW = hexSize * 1.5
  const hexH = hexSize * Math.sqrt(3)
  ctx.strokeStyle = 'rgba(184, 150, 62, 0.025)'
  ctx.lineWidth = 0.5
  for (let row = -2; row < H / hexH + 3; row++) {
    const offsetX = (row % 2 === 0) ? 0 : hexW / 2
    for (let col = -2; col < W / hexW + 3; col++) {
      const cx = col * hexW + offsetX
      const cy = row * hexH * 0.5
      const pulse = 1 + Math.sin(time * 0.008 + cx * 0.01 + cy * 0.01) * 0.4
      ctx.globalAlpha = 0.5 + pulse * 0.5
      ctx.beginPath()
      for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 6
        const x = cx + hexSize * Math.cos(angle)
        const y = cy + hexSize * Math.sin(angle)
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.stroke()
    }
  }
  ctx.globalAlpha = 1

  // 3. 行军路线虚线流动
  for (const route of marchRoutes) {
    route.progress += route.speed
    if (route.progress > 1) route.progress -= 1

    const dx = route.toX - route.fromX
    const dy = route.toY - route.fromY
    const len = Math.sqrt(dx * dx + dy * dy)
    const ux = dx / len
    const uy = dy / len

    // 虚线：绘制4段，根据progress偏移
    const dashLen = len * 0.12
    const gapLen = len * 0.08
    const totalUnit = dashLen + gapLen

    ctx.strokeStyle = `rgba(184, 150, 62, ${route.alpha})`
    ctx.lineWidth = 1
    ctx.lineCap = 'round'
    ctx.setLineDash([dashLen, gapLen])
    ctx.lineDashOffset = -route.progress * totalUnit
    ctx.beginPath()
    ctx.moveTo(route.fromX, route.fromY)
    ctx.lineTo(route.toX, route.toY)
    ctx.stroke()
    ctx.setLineDash([])

    // 行进中的光点
    const dotX = route.fromX + dx * route.progress
    const dotY = route.fromY + dy * route.progress
    const dotGlow = ctx.createRadialGradient(dotX, dotY, 0, dotX, dotY, 8)
    dotGlow.addColorStop(0, `rgba(184, 150, 62, ${route.alpha * 2})`)
    dotGlow.addColorStop(1, 'rgba(24, 20, 16, 0)')
    ctx.fillStyle = dotGlow
    ctx.beginPath()
    ctx.arc(dotX, dotY, 8, 0, Math.PI * 2)
    ctx.fill()
  }

  // 4. 营帐篝火
  for (const fire of campFires) {
    fire.flicker += fire.speed
    const flickAlpha = fire.baseAlpha * (0.6 + 0.4 * Math.abs(Math.sin(fire.flicker)))
    const grad = ctx.createRadialGradient(fire.x, fire.y, 0, fire.x, fire.y, fire.r)
    grad.addColorStop(0, `rgba(220, 160, 60, ${flickAlpha * 1.3})`)
    grad.addColorStop(0.5, `rgba(184, 130, 50, ${flickAlpha * 0.6})`)
    grad.addColorStop(1, 'rgba(24, 20, 16, 0)')
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.arc(fire.x, fire.y, fire.r, 0, Math.PI * 2)
    ctx.fill()
  }

  // 5. 天气粒子
  for (let i = weatherParticles.length - 1; i >= 0; i--) {
    const p = weatherParticles[i]
    p.x += p.vx
    p.y += p.vy
    p.life += 0.002

    if (p.y > H + 20 || p.x < -20 || p.x > W + 20 || p.life > 1) {
      weatherParticles[i] = createWeatherParticle(p.type)
      continue
    }

    if (p.type === 0) {
      // 沙尘
      ctx.fillStyle = `rgba(160, 130, 80, ${p.alpha * (1 - p.life)})`
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
      ctx.fill()
    } else if (p.type === 1) {
      // 细雨
      ctx.strokeStyle = `rgba(180, 190, 200, ${p.alpha * (1 - p.life)})`
      ctx.lineWidth = 0.5
      ctx.beginPath()
      ctx.moveTo(p.x, p.y)
      ctx.lineTo(p.x - p.vx * 2, p.y - p.vy * 0.5)
      ctx.stroke()
    } else {
      // 雪
      ctx.fillStyle = `rgba(220, 215, 200, ${p.alpha * (1 - p.life)})`
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // 6. 墨晕暗角
  const vignette = ctx.createRadialGradient(W / 2, H / 2, W * 0.25, W / 2, H / 2, W * 0.8)
  vignette.addColorStop(0, 'rgba(0, 0, 0, 0)')
  vignette.addColorStop(1, 'rgba(0, 0, 0, 0.4)')
  ctx.fillStyle = vignette
  ctx.fillRect(0, 0, W, H)

  animId = requestAnimationFrame(animate)
}
</script>

<style scoped>
.bg-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background: #181410;
}
</style>
