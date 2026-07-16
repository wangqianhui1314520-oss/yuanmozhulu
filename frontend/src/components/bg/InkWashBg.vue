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

type InkHue = 'ink' | 'gold' | 'vermillion'

interface InkParticle {
  x: number; y: number
  r: number; maxR: number
  alpha: number
  life: number; maxLife: number
  speed: number
  hue: InkHue
  // V5.0 平滑过渡：旧粒子残留，新粒子渐入
  fadeOut: number
  nextHue: InkHue | null
  nextR: number; nextMaxR: number
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
let dpr = 1

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
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  c.width = window.innerWidth * dpr
  c.height = window.innerHeight * dpr
  c.style.width = window.innerWidth + 'px'
  c.style.height = window.innerHeight + 'px'
  W = c.width
  H = c.height

  const ctx = c.getContext('2d')
  if (ctx) ctx.scale(dpr, dpr)

  // 初始化墨色洇开粒子
  particles = []
  const count = Math.max(8, Math.floor((window.innerWidth * window.innerHeight) / 80000))
  for (let i = 0; i < count; i++) {
    particles.push(createInkParticle())
  }

  // 初始化烛火微光
  candles = [
    { x: window.innerWidth * 0.12, y: window.innerHeight * 0.18, r: 90 + Math.random() * 60, flicker: Math.random() * Math.PI * 2, flickerSpeed: 0.02 + Math.random() * 0.03, baseAlpha: 0.06 },
    { x: window.innerWidth * 0.88, y: window.innerHeight * 0.22, r: 80 + Math.random() * 50, flicker: Math.random() * Math.PI * 2, flickerSpeed: 0.025 + Math.random() * 0.03, baseAlpha: 0.05 },
    { x: window.innerWidth * 0.15, y: window.innerHeight * 0.75, r: 100 + Math.random() * 60, flicker: Math.random() * Math.PI * 2, flickerSpeed: 0.018 + Math.random() * 0.03, baseAlpha: 0.05 },
    { x: window.innerWidth * 0.82, y: window.innerHeight * 0.78, r: 85 + Math.random() * 55, flicker: Math.random() * Math.PI * 2, flickerSpeed: 0.022 + Math.random() * 0.03, baseAlpha: 0.06 },
  ]

  // 初始化朱砂飞点
  dusts = []
  const dustCount = Math.max(5, Math.floor(window.innerWidth / 200))
  for (let i = 0; i < dustCount; i++) {
    dusts.push(createVermilionDust())
  }
}

function createInkParticle(): InkParticle {
  const hues: InkHue[] = ['ink', 'ink', 'ink', 'ink', 'gold', 'vermillion']
  return {
    x: Math.random() * window.innerWidth,
    y: Math.random() * window.innerHeight,
    r: 0,
    maxR: 80 + Math.random() * 200,
    alpha: 0,
    life: 0,
    maxLife: 300 + Math.random() * 500,
    speed: 0.3 + Math.random() * 0.9,
    hue: hues[Math.floor(Math.random() * hues.length)] as InkHue,
    fadeOut: 0,
    nextHue: null,
    nextR: 0,
    nextMaxR: 0,
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
  ctx.save()
  ctx.scale(dpr, dpr)
  const iw = window.innerWidth
  const ih = window.innerHeight
  ctx.clearRect(0, 0, iw, ih)

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

  // 2. 渲染墨色洇开粒子（V5.0 平滑过渡）
  for (const p of particles) {
    p.life += p.speed
    if (p.life > p.maxLife) {
      // 保存旧粒子信息用于平滑过渡
      p.fadeOut = 1.0
      p.nextHue = ['ink', 'ink', 'ink', 'ink', 'gold', 'vermillion'][Math.floor(Math.random() * 6)] as InkHue
      p.nextMaxR = 80 + Math.random() * 200
      p.nextR = 0
      p.r = p.maxR
    }
    // 处理过渡
    if (p.fadeOut > 0) {
      p.fadeOut -= 0.02
      if (p.fadeOut <= 0 && p.nextHue !== null) {
        p.hue = p.nextHue
        p.maxR = p.nextMaxR
        p.r = 0
        p.life = 0
        p.x = Math.random() * iw
        p.y = Math.random() * ih
        p.nextHue = null
        p.fadeOut = 0
      }
    }

    const progress = p.life / p.maxLife
    if (!p.fadeOut) {
      p.r = p.maxR * (1 - Math.pow(1 - progress, 3))
    }
    // 透明度
    if (progress < 0.25) {
      p.alpha = (progress / 0.25) * 0.03
    } else if (progress > 0.75) {
      p.alpha = ((1 - progress) / 0.25) * 0.03
    } else {
      p.alpha = 0.03
    }
    // 过渡时部分淡出
    const blendAlpha = p.alpha * (1 - p.fadeOut * 0.5)

    const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r || 10)
    if (p.hue === 'ink') {
      gradient.addColorStop(0, `rgba(60, 50, 35, ${blendAlpha * 1.3})`)
      gradient.addColorStop(0.5, `rgba(40, 32, 24, ${blendAlpha})`)
      gradient.addColorStop(1, 'rgba(24, 20, 16, 0)')
    } else if (p.hue === 'gold') {
      gradient.addColorStop(0, `rgba(184, 150, 62, ${blendAlpha * 1.5})`)
      gradient.addColorStop(0.5, `rgba(139, 112, 64, ${blendAlpha})`)
      gradient.addColorStop(1, 'rgba(24, 20, 16, 0)')
    } else {
      gradient.addColorStop(0, `rgba(196, 58, 58, ${blendAlpha * 1.2})`)
      gradient.addColorStop(0.5, `rgba(139, 32, 32, ${blendAlpha})`)
      gradient.addColorStop(1, 'rgba(24, 20, 16, 0)')
    }

    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.r || 10, 0, Math.PI * 2)
    ctx.fill()
  }

  // 3. 渲染朱砂飞点
  for (let i = dusts.length - 1; i >= 0; i--) {
    const d = dusts[i]
    d.y += d.vy
    d.x += d.vx + Math.sin(time * 0.02 + i) * 0.3
    d.life += 0.005

    if (d.y > ih + 20 || d.life > 1) {
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
  const vignette = ctx.createRadialGradient(iw / 2, ih / 2, iw * 0.35, iw / 2, ih / 2, iw * 0.75)
  vignette.addColorStop(0, 'rgba(0, 0, 0, 0)')
  vignette.addColorStop(1, 'rgba(0, 0, 0, 0.35)')
  ctx.fillStyle = vignette
  ctx.fillRect(0, 0, iw, ih)

  // 5. 极淡的竖纹竹简肌理（V5.0 离屏预渲染优化）
  const offsetX = Math.sin(time * 0.001) * 0.5
  ctx.strokeStyle = 'rgba(184, 150, 62, 0.008)'
  ctx.lineWidth = 1
  // 大屏下降采样绘制
  const step = iw > 1920 ? 6 : 3
  for (let x = offsetX; x < iw; x += step) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, ih)
    ctx.stroke()
  }

  ctx.restore()
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
