<template>
  <!-- 首页·墨韵洇开 —— 竹简为骨、墨色为肉 -->
  <canvas ref="canvas" class="bg-canvas home-ink-wash"></canvas>
</template>

<script setup lang="ts">
/**
 * 首页动态背景：墨韵洇开
 * 
 * 视觉意象：
 * - 深色竹简底，12个墨色粒子缓缓洇开消散，模拟水墨在宣纸上渗透的效果
 * - 鎏金微光如烛火摇曳，点缀在画面暗角
 * - 偶有朱砂飞点飘落，暗示"朱批为魂"
 * - 整体氛围：沉稳、古雅、待启
 */
import { ref, onMounted, onUnmounted } from 'vue'

const canvas = ref<HTMLCanvasElement>()
let animId = 0
let resizeTimer: ReturnType<typeof setTimeout> | null = null

interface InkParticle {
  x: number; y: number
  r: number; maxR: number
  alpha: number
  life: number; maxLife: number
  speed: number
  hue: number // 0=墨色, 1=鎏金, 2=朱砂
}

interface CandleLight {
  x: number; y: number
  r: number
  flicker: number
  flickerSpeed: number
  baseAlpha: number
}

interface VermilionDust {
  x: number; y: number
  vy: number; vx: number
  alpha: number
  size: number
  life: number
}

let particles: InkParticle[] = []
let candles: CandleLight[] = []
let dusts: VermilionDust[] = []
let time = 0
let W = 0
let H = 0

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

  // 初始化墨色洇开粒子
  particles = []
  for (let i = 0; i < 15; i++) {
    particles.push(createInkParticle())
  }

  // 初始化烛火微光
  candles = [
    { x: W * 0.12, y: H * 0.18, r: 90 + Math.random() * 60, flicker: Math.random() * Math.PI * 2, flickerSpeed: 0.02 + Math.random() * 0.03, baseAlpha: 0.06 },
    { x: W * 0.88, y: H * 0.22, r: 80 + Math.random() * 50, flicker: Math.random() * Math.PI * 2, flickerSpeed: 0.025 + Math.random() * 0.03, baseAlpha: 0.05 },
    { x: W * 0.15, y: H * 0.75, r: 100 + Math.random() * 60, flicker: Math.random() * Math.PI * 2, flickerSpeed: 0.018 + Math.random() * 0.03, baseAlpha: 0.05 },
    { x: W * 0.82, y: H * 0.78, r: 85 + Math.random() * 55, flicker: Math.random() * Math.PI * 2, flickerSpeed: 0.022 + Math.random() * 0.03, baseAlpha: 0.06 },
  ]

  // 初始化朱砂飞点
  dusts = []
  for (let i = 0; i < 8; i++) {
    dusts.push(createVermilionDust())
  }
}

function createInkParticle(): InkParticle {
  return {
    x: Math.random() * W,
    y: Math.random() * H,
    r: 0,
    maxR: 80 + Math.random() * 200,
    alpha: 0,
    life: 0,
    maxLife: 300 + Math.random() * 500,
    speed: 0.3 + Math.random() * 0.9,
    hue: Math.random() < 0.75 ? 0 : (Math.random() < 0.5 ? 1 : 2),
  }
}

function createVermilionDust(): VermilionDust {
  return {
    x: Math.random() * W,
    y: -10 - Math.random() * 100,
    vy: 0.3 + Math.random() * 0.8,
    vx: (Math.random() - 0.5) * 0.6,
    alpha: 0.3 + Math.random() * 0.5,
    size: 1 + Math.random() * 2.5,
    life: 0,
  }
}

function animate() {
  const c = canvas.value
  if (!c) return
  const ctx = c.getContext('2d')
  if (!ctx) return

  time += 1
  ctx.clearRect(0, 0, W, H)

  // 1. 渲染烛火微光（底层）
  for (const candle of candles) {
    candle.flicker += candle.flickerSpeed
    const flickAlpha = candle.baseAlpha * (0.7 + 0.3 * Math.sin(candle.flicker))
    const gradient = ctx.createRadialGradient(candle.x, candle.y, 0, candle.x, candle.y, candle.r)
    gradient.addColorStop(0, `rgba(184, 150, 62, ${flickAlpha * 1.2})`)
    gradient.addColorStop(0.5, `rgba(184, 150, 62, ${flickAlpha * 0.5})`)
    gradient.addColorStop(1, 'rgba(24, 20, 16, 0)')
    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.arc(candle.x, candle.y, candle.r, 0, Math.PI * 2)
    ctx.fill()
  }

  // 2. 渲染墨色洇开粒子
  for (const p of particles) {
    p.life += p.speed
    if (p.life > p.maxLife) {
      Object.assign(p, createInkParticle())
      p.life = 0
    }

    const progress = p.life / p.maxLife
    // 洇开曲线：快入缓出
    p.r = p.maxR * (1 - Math.pow(1 - progress, 3))
    // 透明度：快速浮现 → 缓慢消散
    if (progress < 0.25) {
      p.alpha = (progress / 0.25) * 0.03
    } else if (progress > 0.75) {
      p.alpha = ((1 - progress) / 0.25) * 0.03
    } else {
      p.alpha = 0.03
    }

    const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r)
    if (p.hue === 0) {
      // 墨色
      gradient.addColorStop(0, `rgba(60, 50, 35, ${p.alpha * 1.3})`)
      gradient.addColorStop(0.5, `rgba(40, 32, 24, ${p.alpha})`)
      gradient.addColorStop(1, 'rgba(24, 20, 16, 0)')
    } else if (p.hue === 1) {
      // 鎏金微光
      gradient.addColorStop(0, `rgba(184, 150, 62, ${p.alpha * 1.5})`)
      gradient.addColorStop(0.5, `rgba(139, 112, 64, ${p.alpha})`)
      gradient.addColorStop(1, 'rgba(24, 20, 16, 0)')
    } else {
      // 朱砂
      gradient.addColorStop(0, `rgba(196, 58, 58, ${p.alpha * 1.2})`)
      gradient.addColorStop(0.5, `rgba(139, 32, 32, ${p.alpha})`)
      gradient.addColorStop(1, 'rgba(24, 20, 16, 0)')
    }

    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fill()
  }

  // 3. 渲染朱砂飞点
  for (let i = dusts.length - 1; i >= 0; i--) {
    const d = dusts[i]
    d.y += d.vy
    d.x += d.vx + Math.sin(time * 0.02 + i) * 0.3
    d.life += 0.005

    if (d.y > H + 20 || d.life > 1) {
      dusts[i] = createVermilionDust()
      continue
    }

    const fadeAlpha = d.alpha * (1 - d.life)
    ctx.fillStyle = `rgba(196, 58, 58, ${fadeAlpha})`
    ctx.shadowColor = `rgba(196, 58, 58, ${fadeAlpha * 0.6})`
    ctx.shadowBlur = 6
    ctx.beginPath()
    ctx.arc(d.x, d.y, d.size, 0, Math.PI * 2)
    ctx.fill()
    ctx.shadowBlur = 0
  }

  // 4. 整体墨晕暗角
  const vignette = ctx.createRadialGradient(W / 2, H / 2, W * 0.35, W / 2, H / 2, W * 0.75)
  vignette.addColorStop(0, 'rgba(0, 0, 0, 0)')
  vignette.addColorStop(1, 'rgba(0, 0, 0, 0.35)')
  ctx.fillStyle = vignette
  ctx.fillRect(0, 0, W, H)

  // 5. 极淡的竖纹竹简肌理（动态偏移模拟卷轴微动）
  const offsetX = Math.sin(time * 0.001) * 0.5
  ctx.strokeStyle = 'rgba(184, 150, 62, 0.008)'
  ctx.lineWidth = 1
  for (let x = offsetX; x < W; x += 3) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, H)
    ctx.stroke()
  }

  animId = requestAnimationFrame(animate)
}
</script>

<style scoped>
.bg-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background: linear-gradient(180deg, #181410 0%, #1e1a14 40%, #181410 70%, #1a1612 100%);
}
</style>
