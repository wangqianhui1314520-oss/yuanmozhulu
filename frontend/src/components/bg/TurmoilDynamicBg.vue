<template>
  <!-- 元末乱世·山河破碎 —— 10层递进动态背景 -->
  <canvas ref="canvas" class="bg-canvas turmoil-bg"></canvas>
</template>

<script setup lang="ts">
/**
 * 元末乱世·山河破碎 动态背景
 * 
 * 10层递进（由远及近）：
 * L01: 暗色苍穹 — 深棕黑渐变
 * L02: 远山雾气 — 5团径向渐变雾气缓慢飘移
 * L03: 远山残垣 — 6+座山体剪影，顶部烽火台垛口破损
 * L04: 黄河决堤 — 8+条正弦波浪在画面下部翻涌
 * L05: 烽火狼烟 — 6股黑烟从各方升起，3层叠加烟雾
 * L06: 铁骑烟尘 — 8队骑兵剪影从右向左横向掠过
 * L07: 红巾飘飞 — 12片红色不规则布片碎片飘散
 * L08: 陨星划落 — 偶尔出现（2%概率/帧），带长拖尾光晕
 * L09: 竹简竖纹 — 3px间隔金色极淡竖线，微动偏移
 * L10: 墨晕暗角 — 聚焦中央，径向渐变+上下遮幅渐暗
 */
import { ref, onMounted, onUnmounted } from 'vue'

const canvas = ref<HTMLCanvasElement>()
let animId = 0
let resizeTimer: ReturnType<typeof setTimeout> | null = null
let time = 0
let W = 0
let H = 0

// ─── L02: 远山雾气 ───
interface Mist {
  x: number; y: number
  baseX: number; baseY: number
  rx: number; ry: number
  alpha: number
  phase: number
  speed: number
  driftAmp: number
}
let mists: Mist[] = []

// ─── L03: 远山残垣 ───
interface Mountain {
  points: { x: number; y: number }[]
  basePoints: { x: number; y: number }[]
  damage: number // 0.3~0.7 破损程度
  battlementPositions: { x: number; y: number; broken: boolean }[]
  color: string
  // V5.0 预计算山脊线数据（避免每帧随机抖动）
  ridgeLines: { sx: number; sy: number; ex: number; ey: number }[]
}
let mountains: Mountain[] = []

// ─── L04: 黄河决堤 ───
interface Wave {
  phase: number
  speed: number
  amplitude: number
  baseY: number
  segments: number
  foamParticles: { x: number; y: number; life: number; maxLife: number; vx: number; vy: number }[]
}
let riverWaves: Wave[] = []

// ─── L05: 烽火狼烟 ───
interface BeaconFire {
  baseX: number; baseY: number
  x: number; y: number
  smokeLayers: {
    offsetY: number
    width: number; height: number
    alpha: number
    phase: number
    swayAmp: number
    riseSpeed: number
  }[]
  fireGlow: { radius: number; alpha: number; phase: number }
  sparkParticles: { x: number; y: number; vx: number; vy: number; life: number; maxLife: number; alpha: number }[]
}
let beaconFires: BeaconFire[] = []

// ─── L06: 铁骑烟尘 ───
interface Cavalry {
  x: number; y: number
  baseY: number
  speed: number
  trailFrames: { x: number; y: number; alpha: number }[]
  riderHeight: number
  horseWidth: number
  hasSpear: boolean
}
let cavalries: Cavalry[] = []

// ─── L07: 红巾飘飞 ───
interface RedScarf {
  x: number; y: number
  vx: number; vy: number
  rotation: number; rotSpeed: number
  scale: number
  alpha: number
  life: number; maxLife: number
  // 破边控制点偏移
  edgeRoughness: number[]
  foldPhase: number
}
let redScarves: RedScarf[] = []

// ─── L08: 陨星划落 ───
interface Meteor {
  x: number; y: number
  vx: number; vy: number
  alpha: number
  life: number; maxLife: number
  trailLength: number
  size: number
}
let meteors: Meteor[] = []

// ─── L09: 竹简竖纹 ───
let bambooOffset = 0
const BAMBOO_SPACING = 3 // px

// 势力色
const FACTION_COLORS = [
  '#c43a3a', '#4a8ac0', '#b88a2a',
  '#c89830', '#3a9080', '#8a60b0',
  '#a08030', '#788898', '#a04030',
]

// ─── 初始化 ───
function initLayers() {
  // L02: 远山雾气 — 5团
  mists = []
  for (let i = 0; i < 5; i++) {
    mists.push({
      x: W * (0.1 + i * 0.2),
      y: H * 0.25 + Math.random() * H * 0.08,
      baseX: W * (0.1 + i * 0.2),
      baseY: H * 0.25 + Math.random() * H * 0.08,
      rx: W * 0.12 + Math.random() * W * 0.15,
      ry: H * 0.06 + Math.random() * H * 0.06,
      alpha: 0.03 + Math.random() * 0.04,
      phase: Math.random() * Math.PI * 2,
      speed: 0.003 + Math.random() * 0.005,
      driftAmp: 20 + Math.random() * 40,
    })
  }

  // L03: 远山残垣 — 6+座
  mountains = []
  const mountainCount = 7
  for (let i = 0; i < mountainCount; i++) {
    const cx = W * (i / (mountainCount - 1))
    const peakH = H * 0.22 + Math.random() * H * 0.18
    const baseY = H * 0.55 + Math.random() * H * 0.05
    const halfW = W * 0.06 + Math.random() * W * 0.1
    const damage = 0.3 + Math.random() * 0.4

    // 山体剪影控制点
    const points: { x: number; y: number }[] = []
    const basePoints: { x: number; y: number }[] = []
    const steps = 20
    for (let s = 0; s <= steps; s++) {
      const t = s / steps
      const px = cx - halfW + t * halfW * 2
      // 山体轮廓（不规则锯齿）
      const heightFactor = 1 - Math.abs(t - 0.5) * 2 // 三角形包络
      const roughness = (Math.sin(t * 7 + i * 1.7) * 0.12 + Math.sin(t * 13 + i * 3.1) * 0.06)
      const py = baseY - peakH * heightFactor * (0.85 + roughness)
      const bpy = baseY - peakH * heightFactor * 0.85
      points.push({ x: px, y: py })
      basePoints.push({ x: px, y: bpy })
    }

    // 烽火台垛口
    const battlements: { x: number; y: number; broken: boolean }[] = []
    const bmCount = 3 + Math.floor(Math.random() * 4)
    for (let b = 0; b < bmCount; b++) {
      const bt = 0.35 + b * (0.3 / bmCount) + Math.random() * 0.05
      const bx = cx - halfW + bt * halfW * 2
      const heightFactor = 1 - Math.abs(bt - 0.5) * 2
      const by = baseY - peakH * heightFactor * 0.85 - 4 - Math.random() * 6
      battlements.push({
        x: bx,
        y: by,
        broken: Math.random() < damage,
      })
    }

    // V5.0 预计算山脊线（避免每帧随机抖动）
    const ridgeLines = []
    for (let ri = 0; ri < points.length; ri += 3) {
      if (Math.random() < damage * 0.3) continue
      ridgeLines.push({
        sx: points[ri].x,
        sy: points[ri].y,
        ex: points[ri].x + (Math.random() - 0.5) * 4,
        ey: points[ri].y + 2 + Math.random() * 8,
      })
    }

    mountains.push({
      points,
      basePoints,
      damage,
      battlementPositions: battlements,
      color: `hsl(${25 + Math.random() * 10}, ${8 + Math.random() * 5}%, ${10 + Math.random() * 8}%)`,
      ridgeLines,
    })
  }
  // 按远近排序（低山在后）
  mountains.sort((a, b) => a.points.reduce((s, p) => s + p.y, 0) / a.points.length - b.points.reduce((s, p) => s + p.y, 0) / b.points.length)

  // L04: 黄河决堤 — 8+条波浪
  riverWaves = []
  const waveCount = 10
  for (let i = 0; i < waveCount; i++) {
    riverWaves.push({
      phase: Math.random() * Math.PI * 2,
      speed: 0.015 + Math.random() * 0.03,
      amplitude: 8 + Math.random() * 20,
      baseY: H * 0.68 + i * (H * 0.28 / waveCount),
      segments: 60 + Math.floor(Math.random() * 20),
      foamParticles: [],
    })
  }

  // L05: 烽火狼烟 — 6股
  beaconFires = []
  const firePositions = [
    { x: 0.15, y: 0.42 }, { x: 0.3, y: 0.35 },
    { x: 0.5, y: 0.38 }, { x: 0.68, y: 0.4 },
    { x: 0.82, y: 0.36 }, { x: 0.92, y: 0.44 },
  ]
  for (let i = 0; i < 6; i++) {
    const baseX = W * firePositions[i].x
    const baseY = H * firePositions[i].y
    beaconFires.push({
      baseX, baseY, x: baseX, y: baseY,
      smokeLayers: [
        { offsetY: 0, width: 30 + Math.random() * 20, height: 60 + Math.random() * 40, alpha: 0.08, phase: Math.random() * Math.PI * 2, swayAmp: 8 + Math.random() * 12, riseSpeed: 0.2 + Math.random() * 0.3 },
        { offsetY: -20, width: 40 + Math.random() * 25, height: 80 + Math.random() * 50, alpha: 0.05, phase: Math.random() * Math.PI * 2, swayAmp: 15 + Math.random() * 20, riseSpeed: 0.15 + Math.random() * 0.25 },
        { offsetY: -40, width: 50 + Math.random() * 30, height: 100 + Math.random() * 60, alpha: 0.03, phase: Math.random() * Math.PI * 2, swayAmp: 25 + Math.random() * 30, riseSpeed: 0.1 + Math.random() * 0.2 },
      ],
      fireGlow: { radius: 15 + Math.random() * 10, alpha: 0.06 + Math.random() * 0.04, phase: Math.random() * Math.PI * 2 },
      sparkParticles: [],
    })
  }

  // L06: 铁骑烟尘 — 8队
  cavalries = []
  for (let i = 0; i < 8; i++) {
    cavalries.push(createCavalry())
  }

  // L07: 红巾飘飞 — 12片
  redScarves = []
  for (let i = 0; i < 12; i++) {
    redScarves.push(createRedScarf(true))
  }

  // L08: 陨星
  meteors = []
}

function createCavalry(): Cavalry {
  const y = H * 0.5 + Math.random() * H * 0.4
  return {
    x: W + Math.random() * 300,
    y,
    baseY: y,
    speed: 0.6 + Math.random() * 2.0,
    trailFrames: [],
    riderHeight: 20 + Math.random() * 10,
    horseWidth: 18 + Math.random() * 10,
    hasSpear: Math.random() > 0.4,
  }
}

function createRedScarf(randomPos: boolean): RedScarf {
  const roughness: number[] = []
  for (let i = 0; i < 6; i++) roughness.push(Math.random() * 0.3)
  return {
    x: randomPos ? Math.random() * W : -40,
    y: randomPos ? Math.random() * H : H * 0.15 + Math.random() * H * 0.6,
    vx: -0.6 + Math.random() * 0.8,
    vy: -0.2 + Math.random() * 0.5,
    rotation: Math.random() * Math.PI * 2,
    rotSpeed: (Math.random() - 0.5) * 0.02,
    scale: 0.6 + Math.random() * 1.2,
    alpha: 0.06 + Math.random() * 0.08,
    life: 0,
    maxLife: 300 + Math.random() * 500,
    edgeRoughness: roughness,
    foldPhase: Math.random() * Math.PI * 2,
  }
}

// ─── Canvas 尺寸适配 ───
function initCanvas() {
  const c = canvas.value
  if (!c) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2) // 限制像素比以保证性能
  c.width = window.innerWidth * dpr
  c.height = window.innerHeight * dpr
  W = window.innerWidth
  H = window.innerHeight
  const ctx = c.getContext('2d')
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  initLayers()
}

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
  resizeTimer = setTimeout(() => initCanvas(), 300)
}

// ─── 绘制函数 ───
function drawSky(ctx: CanvasRenderingContext2D) {
  // L01: 暗色苍穹 — 深棕黑渐变 #14100c → #1e1a14
  const grad = ctx.createLinearGradient(0, 0, 0, H)
  grad.addColorStop(0, '#14100c')
  grad.addColorStop(0.5, '#181410')
  grad.addColorStop(1, '#1e1a14')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, W, H)
}

function drawMists(ctx: CanvasRenderingContext2D) {
  // L02: 远山雾气 — 5团径向渐变雾气缓慢飘移
  for (const m of mists) {
    m.phase += m.speed
    m.x = m.baseX + Math.sin(m.phase) * m.driftAmp
    m.y = m.baseY + Math.cos(m.phase * 0.7) * m.driftAmp * 0.5

    const grad = ctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, m.rx)
    grad.addColorStop(0, `rgba(180, 160, 130, ${m.alpha * 1.5})`)
    grad.addColorStop(0.4, `rgba(160, 140, 110, ${m.alpha})`)
    grad.addColorStop(1, 'rgba(20, 16, 12, 0)')
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.ellipse(m.x, m.y, m.rx, m.ry, 0, 0, Math.PI * 2)
    ctx.fill()
  }
}

function drawMountains(ctx: CanvasRenderingContext2D) {
  // L03: 远山残垣 — 山体剪影 + 烽火台破损垛口
  for (const mt of mountains) {
    // 山体剪影
    ctx.fillStyle = mt.color
    ctx.beginPath()
    ctx.moveTo(mt.points[0].x, H)
    for (const p of mt.points) ctx.lineTo(p.x, p.y)
    ctx.lineTo(mt.points[mt.points.length - 1].x, H)
    ctx.closePath()
    ctx.fill()

    // 山脊纹理（破损线条）
    ctx.strokeStyle = `rgba(40, 30, 20, 0.5)`
    ctx.lineWidth = 0.5
    // V5.0 使用预计算山脊线（避免每帧随机抖动）
    for (const ridge of mt.ridgeLines) {
      ctx.beginPath()
      ctx.moveTo(ridge.sx, ridge.sy)
      ctx.lineTo(ridge.ex, ridge.ey)
      ctx.stroke()
    }

    // 烽火台垛口
    for (const bm of mt.battlementPositions) {
      const bw = 3 + Math.random() * 2
      const bh = 5 + Math.random() * 3
      ctx.fillStyle = mt.color
      ctx.fillRect(bm.x - bw / 2, bm.y - bh, bw, bh)

      if (bm.broken) {
        // 破损垛口 — 不规则缺角
        ctx.fillStyle = '#1e1a14' // 背景色"穿透"
        ctx.beginPath()
        ctx.moveTo(bm.x - bw / 2 + 1, bm.y - bh + 1)
        ctx.lineTo(bm.x + bw / 2 - 1, bm.y - bh + 1)
        ctx.lineTo(bm.x + bw / 2 - 1 - Math.random() * 2, bm.y - bh + 3 + Math.random() * 2)
        ctx.lineTo(bm.x - bw / 2 + 1 + Math.random() * 2, bm.y - bh + 2 + Math.random() * 2)
        ctx.closePath()
        ctx.fill()

        // 裂缝
        ctx.strokeStyle = 'rgba(20, 16, 12, 0.6)'
        ctx.lineWidth = 0.5
        ctx.beginPath()
        ctx.moveTo(bm.x - 1, bm.y - bh + 2)
        ctx.lineTo(bm.x + 1, bm.y)
        ctx.stroke()
      }
    }
  }
}

function drawRiver(ctx: CanvasRenderingContext2D) {
  // L04: 黄河决堤 — 浑浊泥黄色正弦波浪翻涌
  for (const wave of riverWaves) {
    wave.phase += wave.speed

    // 主波浪
    ctx.beginPath()
    const segWidth = W / wave.segments
    for (let s = 0; s <= wave.segments; s++) {
      const x = s * segWidth
      const turbulence = Math.sin(s * 0.3 + wave.phase) * wave.amplitude * 0.4
      const y = wave.baseY + Math.sin(s * 0.08 + wave.phase * 1.3) * wave.amplitude + turbulence
      if (s === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    // 完成波浪形状 — 填充下方
    ctx.lineTo(W, H)
    ctx.lineTo(0, H)
    ctx.closePath()

    const waveGrad = ctx.createLinearGradient(0, wave.baseY - wave.amplitude * 2, 0, H)
    waveGrad.addColorStop(0, 'rgba(160, 130, 60, 0.12)')
    waveGrad.addColorStop(0.3, 'rgba(140, 110, 50, 0.18)')
    waveGrad.addColorStop(0.6, 'rgba(120, 90, 40, 0.22)')
    waveGrad.addColorStop(1, 'rgba(80, 60, 30, 0.08)')
    ctx.fillStyle = waveGrad
    ctx.fill()

    // 浪花泡沫（白色细线点缀）
    ctx.strokeStyle = 'rgba(200, 180, 140, 0.08)'
    ctx.lineWidth = 0.8
    ctx.beginPath()
    for (let s = 0; s <= wave.segments; s += 2) {
      const x = s * segWidth
      const y = wave.baseY + Math.sin(s * 0.08 + wave.phase * 1.3) * wave.amplitude
      if (s === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.stroke()

    // 更新泡沫粒子
    for (let f = wave.foamParticles.length - 1; f >= 0; f--) {
      const p = wave.foamParticles[f]
      p.x += p.vx
      p.y += p.vy
      p.life++
      if (p.life > p.maxLife) {
        wave.foamParticles.splice(f, 1)
      }
    }

    // 生成新泡沫
    if (Math.random() < 0.1 && wave.foamParticles.length < 15) {
      wave.foamParticles.push({
        x: Math.random() * W,
        y: wave.baseY + Math.sin(Math.random() * 10 + wave.phase) * wave.amplitude,
        life: 0, maxLife: 30 + Math.random() * 40,
        vx: (Math.random() - 0.5) * 0.5,
        vy: -0.2 - Math.random() * 0.5,
      })
    }

    // 绘制泡沫
    for (const p of wave.foamParticles) {
      const alpha = p.life < 5 ? p.life / 5 * 0.06 : (1 - p.life / p.maxLife) * 0.06
      ctx.fillStyle = `rgba(220, 200, 160, ${alpha})`
      ctx.beginPath()
      ctx.arc(p.x, p.y, 1.5, 0, Math.PI * 2)
      ctx.fill()
    }
  }
}

function drawBeaconFires(ctx: CanvasRenderingContext2D) {
  // L05: 烽火狼烟 — 6股黑烟，3层叠加，摇曳+脉冲，底部火光+火星
  for (const bf of beaconFires) {
    // 底部火光
    const glowPulse = 0.7 + 0.3 * Math.sin(time * 0.05 + bf.fireGlow.phase)
    const fireGrad = ctx.createRadialGradient(bf.baseX, bf.baseY, 0, bf.baseX, bf.baseY, bf.fireGlow.radius * 2)
    fireGrad.addColorStop(0, `rgba(255, 140, 30, ${bf.fireGlow.alpha * 2 * glowPulse})`)
    fireGrad.addColorStop(0.4, `rgba(200, 80, 20, ${bf.fireGlow.alpha * glowPulse})`)
    fireGrad.addColorStop(1, 'rgba(0, 0, 0, 0)')
    ctx.fillStyle = fireGrad
    ctx.beginPath()
    ctx.arc(bf.baseX, bf.baseY, bf.fireGlow.radius * 2, 0, Math.PI * 2)
    ctx.fill()

    // 火星飞溅
    for (let s = bf.sparkParticles.length - 1; s >= 0; s--) {
      const sp = bf.sparkParticles[s]
      sp.x += sp.vx
      sp.y += sp.vy
      sp.vy += 0.05 // 重力
      sp.life++
      if (sp.life > sp.maxLife) {
        bf.sparkParticles.splice(s, 1)
        continue
      }
      const alpha = sp.alpha * (1 - sp.life / sp.maxLife)
      ctx.fillStyle = `rgba(255, 180, 40, ${alpha})`
      ctx.beginPath()
      ctx.arc(sp.x, sp.y, 1.2, 0, Math.PI * 2)
      ctx.fill()
    }

    if (Math.random() < 0.3 && bf.sparkParticles.length < 20) {
      bf.sparkParticles.push({
        x: bf.baseX + (Math.random() - 0.5) * 10,
        y: bf.baseY - Math.random() * 5,
        vx: (Math.random() - 0.5) * 1.5,
        vy: -0.8 - Math.random() * 2.5,
        life: 0, maxLife: 20 + Math.random() * 30,
        alpha: 0.3 + Math.random() * 0.5,
      })
    }

    // 3层叠加烟雾
    for (const layer of bf.smokeLayers) {
      layer.phase += 0.02
      const sway = Math.sin(time * 0.02 + layer.phase) * layer.swayAmp
      const pulse = 0.8 + 0.2 * Math.sin(time * 0.03 + layer.phase * 1.5)
      const riseY = layer.offsetY - (time * 0.05 * layer.riseSpeed) % 200

      const cx = bf.baseX + sway
      const cy = bf.baseY + riseY

      // 烟雾椭圆
      const smokeGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, layer.width)
      smokeGrad.addColorStop(0, `rgba(40, 30, 20, ${layer.alpha * pulse * 1.3})`)
      smokeGrad.addColorStop(0.5, `rgba(30, 22, 16, ${layer.alpha * pulse})`)
      smokeGrad.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = smokeGrad
      ctx.beginPath()
      ctx.ellipse(cx, cy, layer.width, layer.height * 0.5, 0, 0, Math.PI * 2)
      ctx.fill()
    }
  }
}

function drawCavalries(ctx: CanvasRenderingContext2D) {
  // L06: 铁骑烟尘 — 8队骑兵剪影从右向左横向掠过，带8帧拖尾烟尘
  for (const cav of cavalries) {
    cav.x -= cav.speed

    if (cav.x < -100) {
      Object.assign(cav, createCavalry())
      cav.x = W + Math.random() * 200
    }

    // 拖尾烟尘（存储最近位置）
    cav.trailFrames.unshift({ x: cav.x, y: cav.y, alpha: 1 })
    if (cav.trailFrames.length > 8) cav.trailFrames.length = 8

    // 绘制拖尾烟尘
    for (let t = 0; t < cav.trailFrames.length; t++) {
      const frame = cav.trailFrames[t]
      const alpha = (1 - t / cav.trailFrames.length) * 0.04
      const dustGrad = ctx.createRadialGradient(frame.x, frame.y, 0, frame.x, frame.y, 15 - t)
      dustGrad.addColorStop(0, `rgba(140, 120, 80, ${alpha})`)
      dustGrad.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = dustGrad
      ctx.beginPath()
      ctx.arc(frame.x, frame.y, 15 - t, 0, Math.PI * 2)
      ctx.fill()
    }

    // 骑兵剪影
    ctx.fillStyle = 'rgba(20, 16, 12, 0.5)'
    const hx = cav.x
    const hy = cav.y - cav.riderHeight

    // 马身
    ctx.beginPath()
    ctx.ellipse(hx, cav.y, cav.horseWidth * 0.5, cav.riderHeight * 0.35, 0, 0, Math.PI * 2)
    ctx.fill()

    // 马头
    ctx.beginPath()
    ctx.ellipse(hx + cav.horseWidth * 0.4, cav.y - cav.riderHeight * 0.15, cav.horseWidth * 0.2, cav.riderHeight * 0.2, 0.3, 0, Math.PI * 2)
    ctx.fill()

    // 骑手
    ctx.beginPath()
    ctx.ellipse(hx, hy + cav.riderHeight * 0.3, cav.horseWidth * 0.2, cav.riderHeight * 0.35, 0, 0, Math.PI * 2)
    ctx.fill()

    // 头部
    ctx.beginPath()
    ctx.arc(hx, hy, cav.riderHeight * 0.18, 0, Math.PI * 2)
    ctx.fill()

    // 长矛
    if (cav.hasSpear) {
      ctx.strokeStyle = 'rgba(20, 16, 12, 0.4)'
      ctx.lineWidth = 0.8
      ctx.beginPath()
      ctx.moveTo(hx, hy + cav.riderHeight * 0.2)
      ctx.lineTo(hx + cav.horseWidth * 0.6, hy - cav.riderHeight * 0.4)
      ctx.stroke()
    }
  }
}

function drawRedScarves(ctx: CanvasRenderingContext2D) {
  // L07: 红巾飘飞 — 12片红色不规则布片碎片飘散，旋转+破边+布纹褶皱
  for (let i = redScarves.length - 1; i >= 0; i--) {
    const rs = redScarves[i]
    rs.x += rs.vx
    rs.y += rs.vy
    rs.rotation += rs.rotSpeed
    rs.life++

    if (rs.life > rs.maxLife || rs.x < -60 || rs.x > W + 60 || rs.y < -60 || rs.y > H + 60) {
      redScarves[i] = createRedScarf(false)
      continue
    }

    ctx.save()
    ctx.translate(rs.x, rs.y)
    ctx.rotate(rs.rotation)
    ctx.scale(rs.scale, rs.scale)

    // 布纹褶皱（水平条纹）
    const foldAlpha = rs.alpha * (0.7 + 0.3 * Math.sin(rs.foldPhase + rs.life * 0.03))

    // 不规则布片形状（带破边）
    ctx.beginPath()
    const w = 16, h = 10
    ctx.moveTo(-w * 0.5, -h * 0.5)
    // 上边破边
    for (let e = 0; e < 5; e++) {
      const ex = -w * 0.5 + (e + 1) * w / 5
      ctx.lineTo(ex, -h * 0.5 + rs.edgeRoughness[e] * 3)
    }
    // 右边破边
    ctx.lineTo(w * 0.5 + rs.edgeRoughness[0] * 2, -h * 0.3)
    ctx.lineTo(w * 0.5, h * 0.3)
    // 下边破边
    ctx.lineTo(-w * 0.3, h * 0.5 + rs.edgeRoughness[3] * 2)
    ctx.lineTo(-w * 0.5, h * 0.3)
    ctx.closePath()

    // 红色填充 + 布纹
    const clothGrad = ctx.createLinearGradient(0, -h * 0.5, 0, h * 0.5)
    clothGrad.addColorStop(0, `rgba(196, 40, 40, ${foldAlpha * 1.1})`)
    clothGrad.addColorStop(0.3, `rgba(170, 30, 30, ${foldAlpha})`)
    clothGrad.addColorStop(0.6, `rgba(180, 35, 35, ${foldAlpha * 0.9})`)
    clothGrad.addColorStop(1, `rgba(150, 25, 25, ${foldAlpha * 0.8})`)
    ctx.fillStyle = clothGrad
    ctx.fill()

    // 布纹褶皱线
    ctx.strokeStyle = `rgba(120, 20, 20, ${foldAlpha * 0.4})`
    ctx.lineWidth = 0.4
    for (let f = -2; f <= 2; f++) {
      const fy = f * h * 0.15 + Math.sin(f * 0.8 + rs.foldPhase) * 1.5
      ctx.beginPath()
      ctx.moveTo(-w * 0.4, fy)
      ctx.lineTo(w * 0.4, fy + Math.sin(f * 1.2) * 1)
      ctx.stroke()
    }

    ctx.restore()
  }
}

function drawMeteors(ctx: CanvasRenderingContext2D) {
  // L08: 陨星划落 — 2%概率/帧，带长拖尾光晕，金橙色渐变
  if (Math.random() < 0.02 && meteors.length < 2) {
    const fromTop = Math.random() < 0.5
    meteors.push({
      x: fromTop ? W * 0.3 + Math.random() * W * 0.5 : W * 0.6 + Math.random() * W * 0.3,
      y: fromTop ? -10 : H * 0.1 + Math.random() * H * 0.2,
      vx: -1.5 - Math.random() * 3,
      vy: 3 + Math.random() * 5,
      alpha: 0.7 + Math.random() * 0.3,
      life: 0,
      maxLife: 60 + Math.random() * 80,
      trailLength: 60 + Math.random() * 100,
      size: 1.5 + Math.random() * 2.5,
    })
  }

  for (let i = meteors.length - 1; i >= 0; i--) {
    const m = meteors[i]
    m.x += m.vx
    m.y += m.vy
    m.life++

    if (m.life > m.maxLife || m.y > H + 50 || m.x < -50) {
      meteors.splice(i, 1)
      continue
    }

    const lifeProgress = m.life / m.maxLife
    const fadeAlpha = lifeProgress < 0.15 ? lifeProgress / 0.15 : (1 - lifeProgress)

    // 拖尾光晕
    const trailGrad = ctx.createLinearGradient(
      m.x, m.y,
      m.x - m.vx * m.trailLength * 0.3,
      m.y - m.vy * m.trailLength * 0.3
    )
    trailGrad.addColorStop(0, `rgba(255, 200, 80, ${m.alpha * fadeAlpha})`)
    trailGrad.addColorStop(0.3, `rgba(255, 160, 40, ${m.alpha * fadeAlpha * 0.6})`)
    trailGrad.addColorStop(1, 'rgba(0, 0, 0, 0)')

    ctx.strokeStyle = trailGrad
    ctx.lineWidth = m.size * 3
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(m.x, m.y)
    ctx.lineTo(
      m.x - m.vx * m.trailLength * 0.15,
      m.y - m.vy * m.trailLength * 0.15
    )
    ctx.stroke()

    // 头部光点
    const headGlow = ctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, m.size * 4)
    headGlow.addColorStop(0, `rgba(255, 240, 200, ${m.alpha * fadeAlpha})`)
    headGlow.addColorStop(0.3, `rgba(255, 180, 60, ${m.alpha * fadeAlpha * 0.6})`)
    headGlow.addColorStop(1, 'rgba(0, 0, 0, 0)')
    ctx.fillStyle = headGlow
    ctx.beginPath()
    ctx.arc(m.x, m.y, m.size * 4, 0, Math.PI * 2)
    ctx.fill()
  }
}

function drawBambooLines(ctx: CanvasRenderingContext2D) {
  // L09: 竹简竖纹 — 3px间隔金色极淡竖线，微动偏移
  bambooOffset += 0.08
  const offsetX = Math.sin(bambooOffset * 0.3) * 1.5

  ctx.strokeStyle = 'rgba(184, 150, 62, 0.03)'
  ctx.lineWidth = 0.5

  for (let x = offsetX; x < W; x += BAMBOO_SPACING) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, H)
    ctx.stroke()
  }

  // 偶有稍粗的编绳横线（竹简编连痕迹）
  ctx.strokeStyle = 'rgba(184, 150, 62, 0.02)'
  ctx.lineWidth = 0.6
  const ropeY1 = H * 0.25 + Math.sin(bambooOffset * 0.1) * 3
  const ropeY2 = H * 0.6 + Math.cos(bambooOffset * 0.12) * 3
  const ropeY3 = H * 0.85 + Math.sin(bambooOffset * 0.08) * 2
  for (const ry of [ropeY1, ropeY2, ropeY3]) {
    ctx.beginPath()
    ctx.moveTo(0, ry)
    ctx.lineTo(W, ry)
    ctx.stroke()
  }
}

function drawVignette(ctx: CanvasRenderingContext2D) {
  // L10: 墨晕暗角 — 径向渐变 + 上下遮幅渐暗
  // 径向暗角（聚焦中央）
  const vignette = ctx.createRadialGradient(W / 2, H / 2, W * 0.25, W / 2, H / 2, W * 0.75)
  vignette.addColorStop(0, 'rgba(0, 0, 0, 0)')
  vignette.addColorStop(0.6, 'rgba(0, 0, 0, 0.08)')
  vignette.addColorStop(1, 'rgba(0, 0, 0, 0.35)')
  ctx.fillStyle = vignette
  ctx.fillRect(0, 0, W, H)

  // 上下遮幅渐暗
  const topBar = ctx.createLinearGradient(0, 0, 0, H * 0.15)
  topBar.addColorStop(0, 'rgba(0, 0, 0, 0.3)')
  topBar.addColorStop(1, 'rgba(0, 0, 0, 0)')
  ctx.fillStyle = topBar
  ctx.fillRect(0, 0, W, H * 0.15)

  const bottomBar = ctx.createLinearGradient(0, H * 0.85, 0, H)
  bottomBar.addColorStop(0, 'rgba(0, 0, 0, 0)')
  bottomBar.addColorStop(1, 'rgba(0, 0, 0, 0.25)')
  ctx.fillStyle = bottomBar
  ctx.fillRect(0, H * 0.85, W, H * 0.15)
}

// ─── 主循环 ───
function animate() {
  const c = canvas.value
  if (!c) return
  const ctx = c.getContext('2d')
  if (!ctx) return

  time++

  // 10层递进渲染（由远及近）
  drawSky(ctx)          // L01: 暗色苍穹
  drawMists(ctx)        // L02: 远山雾气
  drawMountains(ctx)    // L03: 远山残垣
  drawRiver(ctx)        // L04: 黄河决堤
  drawBeaconFires(ctx)  // L05: 烽火狼烟
  drawCavalries(ctx)    // L06: 铁骑烟尘
  drawRedScarves(ctx)   // L07: 红巾飘飞
  drawMeteors(ctx)      // L08: 陨星划落
  drawBambooLines(ctx)  // L09: 竹简竖纹
  drawVignette(ctx)     // L10: 墨晕暗角

  animId = requestAnimationFrame(animate)
}
</script>

<style scoped>
.bg-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}
</style>
