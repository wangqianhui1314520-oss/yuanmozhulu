<template>
  <!-- 存档管理页·简牍归档 —— 岁月沉淀、史笔如铁 -->
  <canvas ref="canvas" class="bg-canvas save-archive-bg"></canvas>
</template>

<script setup lang="ts">
/**
 * 存档管理页动态背景：简牍归档
 * 
 * 视觉意象：
 * - 底层：暖黄竹简色底，仿古卷宗库房光线
 * - 中层：竹简编绳横向缓缓飘动（细微起伏）
 * - 上层：墨字碎片缓缓沉降（「史」「录」「存」「档」等篆字）
 * - 角落：烛台光影摇曳，模拟案牍劳形场景
 * - 氛围：静谧、厚重、岁月沉淀
 */
import { ref, onMounted, onUnmounted } from 'vue'

const canvas = ref<HTMLCanvasElement>()
let animId = 0
let resizeTimer: ReturnType<typeof setTimeout> | null = null

interface BambooSlip {
  x: number; y: number
  width: number; height: number
  sway: number
  swaySpeed: number
  alpha: number
}

interface BindingCord {
  y: number
  sway: number
  swaySpeed: number
}

interface InkFragment {
  x: number; y: number
  vy: number; vx: number
  alpha: number
  char: string
  size: number
  life: number; maxLife: number
  rotation: number
  rotSpeed: number
}

interface CandleGlow {
  x: number; y: number
  r: number
  flicker: number
  speed: number
  baseAlpha: number
}

interface DustMote {
  x: number; y: number
  vy: number; vx: number
  alpha: number
  size: number
}

// 篆隶字符库
const ARCHIVE_CHARS = ['史', '录', '存', '档', '卷', '策', '简', '牍', '书', '记', '志', '典', '籍', '簿', '册']

let bambooSlips: BambooSlip[] = []
let bindingCords: BindingCord[] = []
let inkFragments: InkFragment[] = []
let candleGlows: CandleGlow[] = []
let dustMotes: DustMote[] = []
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

  // 竹简条
  bambooSlips = []
  const slipWidth = 5
  for (let x = 0; x < W; x += slipWidth + 1) {
    bambooSlips.push({
      x,
      y: 0,
      width: slipWidth,
      height: H,
      sway: Math.random() * Math.PI * 2,
      swaySpeed: 0.003 + Math.random() * 0.006,
      alpha: 0.03 + Math.random() * 0.04,
    })
  }

  // 编绳
  bindingCords = []
  for (let y = H * 0.2; y < H; y += H * 0.3) {
    bindingCords.push({
      y,
      sway: Math.random() * Math.PI * 2,
      swaySpeed: 0.005 + Math.random() * 0.01,
    })
  }

  // 墨字碎片
  inkFragments = []
  for (let i = 0; i < 10; i++) {
    inkFragments.push(createInkFragment())
  }

  // 烛台
  candleGlows = [
    { x: W * 0.08, y: H * 0.12, r: 60, flicker: 0, speed: 0.03, baseAlpha: 0.08 },
    { x: W * 0.9, y: H * 0.1, r: 55, flicker: 1.5, speed: 0.035, baseAlpha: 0.07 },
    { x: W * 0.07, y: H * 0.88, r: 65, flicker: 3, speed: 0.028, baseAlpha: 0.08 },
  ]

  // 尘埃微粒
  dustMotes = []
  for (let i = 0; i < 25; i++) {
    dustMotes.push(createDustMote())
  }
}

function createInkFragment(): InkFragment {
  return {
    x: Math.random() * W,
    y: -20 - Math.random() * 200,
    vy: 0.2 + Math.random() * 0.5,
    vx: (Math.random() - 0.5) * 0.3,
    alpha: 0.04 + Math.random() * 0.06,
    char: ARCHIVE_CHARS[Math.floor(Math.random() * ARCHIVE_CHARS.length)],
    size: 18 + Math.random() * 28,
    life: 0,
    maxLife: 400 + Math.random() * 600,
    rotation: (Math.random() - 0.5) * 0.3,
    rotSpeed: (Math.random() - 0.5) * 0.003,
  }
}

function createDustMote(): DustMote {
  return {
    x: Math.random() * W,
    y: Math.random() * H,
    vy: -0.1 - Math.random() * 0.3,
    vx: (Math.random() - 0.5) * 0.2,
    alpha: 0.02 + Math.random() * 0.05,
    size: 1 + Math.random() * 2,
  }
}

function animate() {
  const c = canvas.value
  if (!c) return
  const ctx = c.getContext('2d')
  if (!ctx) return

  time += 1
  ctx.clearRect(0, 0, W, H)

  // 1. 竹简底色暖黄渐变
  const baseGrad = ctx.createLinearGradient(0, 0, 0, H)
  baseGrad.addColorStop(0, '#221d16')
  baseGrad.addColorStop(0.3, '#27221a')
  baseGrad.addColorStop(0.5, '#2a241c')
  baseGrad.addColorStop(0.7, '#27221a')
  baseGrad.addColorStop(1, '#1c1812')
  ctx.fillStyle = baseGrad
  ctx.fillRect(0, 0, W, H)

  // 2. 竹简条（竖纹肌理）
  for (const slip of bambooSlips) {
    slip.sway += slip.swaySpeed
    const offsetX = Math.sin(slip.sway) * 0.3

    const grad = ctx.createLinearGradient(slip.x + offsetX, 0, slip.x + slip.width + offsetX, 0)
    grad.addColorStop(0, `rgba(184, 150, 62, ${slip.alpha * 0.5})`)
    grad.addColorStop(0.5, `rgba(184, 150, 62, ${slip.alpha})`)
    grad.addColorStop(1, `rgba(184, 150, 62, ${slip.alpha * 0.5})`)
    ctx.fillStyle = grad
    ctx.fillRect(slip.x + offsetX, 0, slip.width, H)
  }

  // 3. 编绳（横向暗线微动）
  for (const cord of bindingCords) {
    cord.sway += cord.swaySpeed
    const swayY = cord.y + Math.sin(cord.sway) * 2

    ctx.strokeStyle = 'rgba(139, 100, 50, 0.08)'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.moveTo(0, swayY)
    // 编绳略微波动
    for (let x = 0; x <= W; x += 20) {
      const wy = swayY + Math.sin(x * 0.02 + cord.sway) * 1.5
      ctx.lineTo(x, wy)
    }
    ctx.stroke()
  }

  // 4. 墨字碎片沉降
  for (let i = inkFragments.length - 1; i >= 0; i--) {
    const frag = inkFragments[i]
    frag.y += frag.vy
    frag.x += frag.vx + Math.sin(time * 0.005 + i) * 0.2
    frag.life += 1
    frag.rotation += frag.rotSpeed

    if (frag.y > H + 40 || frag.life > frag.maxLife) {
      inkFragments[i] = createInkFragment()
      continue
    }

    const lifeProgress = frag.life / frag.maxLife
    let fadeAlpha = frag.alpha
    if (lifeProgress > 0.7) fadeAlpha = frag.alpha * ((1 - lifeProgress) / 0.3)

    ctx.save()
    ctx.translate(frag.x, frag.y)
    ctx.rotate(frag.rotation)
    ctx.font = `${frag.size}px "STKaiti", "KaiTi", "FZShuTi", serif`
    ctx.fillStyle = `rgba(60, 50, 35, ${fadeAlpha})`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(frag.char, 0, 0)
    ctx.restore()
  }

  // 5. 烛台光影
  for (const candle of candleGlows) {
    candle.flicker += candle.speed
    const flickAlpha = candle.baseAlpha * (0.65 + 0.35 * Math.sin(candle.flicker))
    const grad = ctx.createRadialGradient(candle.x, candle.y, 0, candle.x, candle.y, candle.r)
    grad.addColorStop(0, `rgba(200, 160, 80, ${flickAlpha * 1.2})`)
    grad.addColorStop(0.6, `rgba(160, 120, 60, ${flickAlpha * 0.3})`)
    grad.addColorStop(1, 'rgba(34, 29, 22, 0)')
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.arc(candle.x, candle.y, candle.r, 0, Math.PI * 2)
    ctx.fill()
  }

  // 6. 浮尘微粒
  for (let i = dustMotes.length - 1; i >= 0; i--) {
    const d = dustMotes[i]
    d.y += d.vy
    d.x += d.vx + Math.sin(time * 0.01 + i) * 0.15
    if (d.y < -10 || d.y > H + 10 || d.x < -10 || d.x > W + 10) {
      dustMotes[i] = createDustMote()
      continue
    }
    ctx.fillStyle = `rgba(200, 180, 140, ${d.alpha})`
    ctx.beginPath()
    ctx.arc(d.x, d.y, d.size, 0, Math.PI * 2)
    ctx.fill()
  }

  // 7. 整体暗角
  const vignette = ctx.createRadialGradient(W / 2, H / 2, W * 0.35, W / 2, H / 2, W * 0.8)
  vignette.addColorStop(0, 'rgba(0, 0, 0, 0)')
  vignette.addColorStop(1, 'rgba(0, 0, 0, 0.35)')
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
  background: #221d16;
}
</style>
