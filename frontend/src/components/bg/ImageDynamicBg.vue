<template>
  <div class="image-dynamic-bg" :class="{ loaded: imageLoaded }">
    <!-- 底图：Ken Burns + 鼠标视差 -->
    <div class="bg-image-wrapper" ref="imageWrapper">
      <img
        ref="bgImage"
        class="bg-image"
        :src="src"
        alt="元末乱世"
        @load="onImageLoad"
        @error="onImageError"
        draggable="false"
      />
    </div>

    <!-- 战火辉光层：边缘脉冲光效 -->
    <div class="bg-war-glow">
      <div class="glow-top-left"></div>
      <div class="glow-top-right"></div>
      <div class="glow-bottom"></div>
    </div>

    <!-- 全局色调与明暗遮罩 -->
    <div class="bg-overlay"></div>
    <div class="bg-vignette"></div>
    <div class="bg-gradient-mask"></div>

    <!-- 粒子画布：火星 / 烟尘 / 硝烟 -->
    <canvas ref="particleCanvas" class="bg-particles"></canvas>

    <!-- 胶片颗粒与扫描线 -->
    <div class="bg-grain" v-if="quality !== 'low'"></div>
    <div class="bg-scanlines" v-if="quality === 'high'"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  src?: string
  parallax?: boolean
  particles?: boolean
  quality?: 'low' | 'medium' | 'high'
}>(), {
  src: '/assets/images/home-bg.jpg',
  parallax: true,
  particles: true,
  quality: 'high',
})

const imageWrapper = ref<HTMLElement>()
const bgImage = ref<HTMLImageElement>()
const particleCanvas = ref<HTMLCanvasElement>()

const imageLoaded = ref(false)
let animId = 0
let resizeTimer: ReturnType<typeof setTimeout> | null = null
let W = 0
let H = 0
let time = 0

// ---- 粒子类型 ----
interface Ember {
  x: number; y: number
  vx: number; vy: number
  size: number
  alpha: number
  life: number; maxLife: number
  hue: number
}

interface Dust {
  x: number; y: number
  vx: number; vy: number
  size: number
  alpha: number
}

interface SmokeWisp {
  x: number; y: number
  vx: number; vy: number
  size: number
  alpha: number
  phase: number
  life: number; maxLife: number
}

let embers: Ember[] = []
let dusts: Dust[] = []
let smokes: SmokeWisp[] = []

// ---- 鼠标视差 ----
let mouseX = 0
let mouseY = 0
let targetPx = 0
let targetPy = 0
let currentPx = 0
let currentPy = 0

function onMouseMove(e: MouseEvent) {
  if (!props.parallax || !imageWrapper.value) return
  const rect = imageWrapper.value.getBoundingClientRect()
  const nx = (e.clientX - rect.left) / rect.width - 0.5
  const ny = (e.clientY - rect.top) / rect.height - 0.5
  mouseX = nx * 2
  mouseY = ny * 2
  targetPx = mouseX * -18
  targetPy = mouseY * -18
}

function onImageLoad() {
  imageLoaded.value = true
}

function onImageError() {
  imageLoaded.value = false
  console.warn('[ImageDynamicBg] 背景图加载失败:', props.src)
}

// ---- 初始化画布 ----
function initCanvas() {
  const c = particleCanvas.value
  if (!c) return
  const dpr = Math.min(window.devicePixelRatio || 1, props.quality === 'high' ? 2 : 1)
  W = window.innerWidth
  H = window.innerHeight
  c.width = Math.floor(W * dpr)
  c.height = Math.floor(H * dpr)
  c.style.width = W + 'px'
  c.style.height = H + 'px'
  const ctx = c.getContext('2d')
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  initParticles()
}

function onResize() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(initCanvas, 200)
}

function initParticles() {
  const emberCount = props.quality === 'low' ? 20 : props.quality === 'medium' ? 45 : 70
  const dustCount = props.quality === 'low' ? 30 : props.quality === 'medium' ? 60 : 100
  const smokeCount = props.quality === 'low' ? 4 : props.quality === 'medium' ? 8 : 14

  embers = []
  for (let i = 0; i < emberCount; i++) embers.push(createEmber(true))

  dusts = []
  for (let i = 0; i < dustCount; i++) dusts.push(createDust(true))

  smokes = []
  for (let i = 0; i < smokeCount; i++) smokes.push(createSmoke(true))
}

function createEmber(randomPos: boolean): Ember {
  return {
    x: randomPos ? Math.random() * W : W * 0.3 + Math.random() * W * 0.4,
    y: randomPos ? Math.random() * H : H + 10,
    vx: (Math.random() - 0.5) * 1.2,
    vy: -0.8 - Math.random() * 2.0,
    size: 1.5 + Math.random() * 3.5,
    alpha: 0,
    life: 0,
    maxLife: 140 + Math.random() * 280,
    hue: 8 + Math.random() * 55, // 橙红到金黄
  }
}

function createDust(randomPos: boolean): Dust {
  return {
    x: randomPos ? Math.random() * W : -20,
    y: randomPos ? Math.random() * H : H * 0.65 + Math.random() * H * 0.35,
    vx: 0.5 + Math.random() * 1.5,
    vy: (Math.random() - 0.5) * 0.5,
    size: 1.5 + Math.random() * 4,
    alpha: 0.12 + Math.random() * 0.28,
  }
}

function createSmoke(randomPos: boolean): SmokeWisp {
  return {
    x: randomPos ? Math.random() * W : W * 0.15 + Math.random() * W * 0.7,
    y: randomPos ? Math.random() * H * 0.8 : H + 40,
    vx: (Math.random() - 0.5) * 0.4,
    vy: -0.3 - Math.random() * 0.6,
    size: 40 + Math.random() * 100,
    alpha: 0,
    phase: Math.random() * Math.PI * 2,
    life: 0,
    maxLife: 400 + Math.random() * 600,
  }
}

// ---- 动画循环 ----
function animate() {
  if (!props.particles) {
    animId = requestAnimationFrame(animate)
    return
  }

  const c = particleCanvas.value
  if (!c) return
  const ctx = c.getContext('2d')
  if (!ctx) return

  time += 1
  ctx.clearRect(0, 0, W, H)

  // 平滑视差插值
  currentPx += (targetPx - currentPx) * 0.06
  currentPy += (targetPy - currentPy) * 0.06
  if (imageWrapper.value) {
    imageWrapper.value.style.setProperty('--px', currentPx.toFixed(2) + 'px')
    imageWrapper.value.style.setProperty('--py', currentPy.toFixed(2) + 'px')
  }

  drawEmbers(ctx)
  drawDust(ctx)
  drawSmoke(ctx)

  animId = requestAnimationFrame(animate)
}

function drawEmbers(ctx: CanvasRenderingContext2D) {
  for (let i = embers.length - 1; i >= 0; i--) {
    const p = embers[i]
    p.x += p.vx + Math.sin(time * 0.02 + p.life * 0.05) * 0.3
    p.y += p.vy
    p.life += 1

    const progress = p.life / p.maxLife
    if (progress < 0.15) p.alpha = (progress / 0.15) * 0.8
    else if (progress > 0.75) p.alpha = ((1 - progress) / 0.25) * 0.8
    else p.alpha = 0.8

    if (p.y < -10 || p.life > p.maxLife) {
      embers[i] = createEmber(false)
      continue
    }

    const flicker = 0.7 + 0.3 * Math.sin(time * 0.15 + i)
    const a = p.alpha * flicker
    const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 2)
    grad.addColorStop(0, `hsla(${p.hue}, 90%, 65%, ${a})`)
    grad.addColorStop(0.5, `hsla(${p.hue - 10}, 80%, 45%, ${a * 0.5})`)
    grad.addColorStop(1, `hsla(${p.hue}, 70%, 20%, 0)`)
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size * 2, 0, Math.PI * 2)
    ctx.fill()
  }
}

function drawDust(ctx: CanvasRenderingContext2D) {
  for (let i = dusts.length - 1; i >= 0; i--) {
    const p = dusts[i]
    p.x += p.vx + Math.sin(time * 0.01 + i) * 0.2
    p.y += p.vy
    if (p.x > W + 20) {
      p.x = -20
      p.y = H * 0.65 + Math.random() * H * 0.35
    }

    ctx.fillStyle = `rgba(140, 120, 90, ${p.alpha * (0.6 + 0.4 * Math.sin(time * 0.02 + i))})`
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
    ctx.fill()
  }
}

function drawSmoke(ctx: CanvasRenderingContext2D) {
  for (let i = smokes.length - 1; i >= 0; i--) {
    const s = smokes[i]
    s.phase += 0.01
    s.x += s.vx + Math.sin(s.phase) * 0.5
    s.y += s.vy
    s.life += 1
    s.size += 0.15

    const progress = s.life / s.maxLife
    if (progress < 0.2) s.alpha = (progress / 0.2) * 0.12
    else if (progress > 0.7) s.alpha = ((1 - progress) / 0.3) * 0.12
    else s.alpha = 0.12

    if (s.y < -s.size || s.life > s.maxLife) {
      smokes[i] = createSmoke(false)
      continue
    }

    const grad = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, s.size)
    grad.addColorStop(0, `rgba(60, 50, 40, ${s.alpha})`)
    grad.addColorStop(0.5, `rgba(45, 38, 30, ${s.alpha * 0.6})`)
    grad.addColorStop(1, 'rgba(30, 25, 20, 0)')
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2)
    ctx.fill()
  }
}

onMounted(() => {
  initCanvas()
  window.addEventListener('resize', onResize)
  if (props.parallax) window.addEventListener('mousemove', onMouseMove, { passive: true })
  animate()
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('mousemove', onMouseMove)
  if (resizeTimer) clearTimeout(resizeTimer)
})
</script>

<style scoped>
.image-dynamic-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  background: linear-gradient(180deg, #14100c 0%, #1e1a14 50%, #181410 100%);
}

/* 底图容器：Ken Burns + 鼠标视差 */
.bg-image-wrapper {
  position: absolute;
  inset: -4%;
  width: 108%;
  height: 108%;
  opacity: 0;
  transition: opacity 1.2s ease-out;
  transform: translate(var(--px, 0), var(--py, 0)) scale(1.05);
  will-change: transform;
}

.image-dynamic-bg.loaded .bg-image-wrapper {
  opacity: 1;
  animation: kenBurns 30s ease-in-out infinite alternate;
}

.bg-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 60%;
  filter: sepia(0.15) contrast(1.08) saturate(0.92) brightness(0.85);
}

@keyframes kenBurns {
  0% { transform: translate(var(--px, 0), var(--py, 0)) scale(1.05) translate(-0.5%, -0.3%); }
  25% { transform: translate(var(--px, 0), var(--py, 0)) scale(1.14) translate(-1.8%, -1.2%); }
  50% { transform: translate(var(--px, 0), var(--py, 0)) scale(1.10) translate(0.5%, 0.8%); }
  75% { transform: translate(var(--px, 0), var(--py, 0)) scale(1.15) translate(1.2%, -0.5%); }
  100% { transform: translate(var(--px, 0), var(--py, 0)) scale(1.05) translate(-0.5%, -0.3%); }
}

/* ===== 战火辉光层 ===== */
.bg-war-glow {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
}

.glow-top-left {
  position: absolute;
  top: -10%;
  left: -5%;
  width: 50%;
  height: 45%;
  background: radial-gradient(ellipse at 30% 40%, rgba(200, 80, 30, 0.08), rgba(180, 60, 20, 0.03) 40%, transparent 70%);
  animation: glowPulse1 6s ease-in-out infinite alternate;
}

.glow-top-right {
  position: absolute;
  top: -8%;
  right: -5%;
  width: 45%;
  height: 40%;
  background: radial-gradient(ellipse at 60% 35%, rgba(220, 140, 40, 0.06), rgba(180, 100, 30, 0.02) 45%, transparent 70%);
  animation: glowPulse2 8s ease-in-out infinite alternate;
}

.glow-bottom {
  position: absolute;
  bottom: -15%;
  left: 10%;
  width: 80%;
  height: 50%;
  background: radial-gradient(ellipse at 50% 30%, rgba(200, 70, 25, 0.12), rgba(150, 50, 15, 0.05) 35%, transparent 65%);
  animation: glowPulse3 7s ease-in-out infinite alternate;
}

@keyframes glowPulse1 {
  0% { opacity: 0.4; transform: scale(1.0); }
  100% { opacity: 1.0; transform: scale(1.08); }
}

@keyframes glowPulse2 {
  0% { opacity: 0.6; transform: scale(1.05); }
  100% { opacity: 1.0; transform: scale(0.95); }
}

@keyframes glowPulse3 {
  0% { opacity: 0.3; transform: scale(1.0) translateY(0); }
  100% { opacity: 1.0; transform: scale(1.06) translateY(-2%); }
}

/* 全局暖褐色调遮罩 */
.bg-overlay {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 50% 40%, transparent 0%, rgba(20, 16, 12, 0.4) 60%, rgba(12, 10, 8, 0.75) 100%),
    linear-gradient(180deg, rgba(60, 40, 25, 0.25) 0%, rgba(40, 28, 18, 0.35) 50%, rgba(20, 14, 10, 0.55) 100%);
  pointer-events: none;
  z-index: 1;
}

/* 暗角 */
.bg-vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 40%, rgba(0, 0, 0, 0.55) 100%);
  pointer-events: none;
  z-index: 2;
}

/* 上下 readability 渐变 */
.bg-gradient-mask {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(10, 8, 6, 0.55) 0%, transparent 25%, transparent 70%, rgba(10, 8, 6, 0.7) 100%);
  pointer-events: none;
  z-index: 3;
}

/* 粒子画布 */
.bg-particles {
  position: absolute;
  inset: 0;
  z-index: 4;
  pointer-events: none;
}

/* 胶片颗粒 */
.bg-grain {
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
  opacity: 0.07;
  mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  animation: grainShift 0.5s steps(10) infinite;
}

@keyframes grainShift {
  0%, 100% { transform: translate(0, 0); }
  20% { transform: translate(-1%, -1%); }
  40% { transform: translate(1%, 0.5%); }
  60% { transform: translate(-0.5%, 1%); }
  80% { transform: translate(0.5%, -0.5%); }
}

/* 扫描线 */
.bg-scanlines {
  position: absolute;
  inset: 0;
  z-index: 6;
  pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 3px,
    rgba(0, 0, 0, 0.03) 3px,
    rgba(0, 0, 0, 0.03) 6px
  );
  opacity: 0.5;
}
</style>
