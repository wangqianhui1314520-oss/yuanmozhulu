<template>
  <canvas
    ref="canvasRef"
    class="char-portrait-canvas"
    :width="size"
    :height="size"
    :style="{ width: size + 'px', height: size + 'px' }"
  />
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

export interface PortraitData {
  name: string
  title?: string
  role?: string
  roleLabel?: string
  personality?: string
  personalityTags?: string[]
  color?: string
  factionName?: string
  difficulty?: string
  specialties?: string[]
  wisdom?: number
  loyalty?: number
  ambition?: number
  styleName?: string
  background?: string
  isRuler?: boolean
}

const props = withDefaults(defineProps<{
  portraitData: PortraitData
  size?: number
  style?: 'ruler' | 'general' | 'strategist' | 'chancellor' | 'diplomat' | 'scholar' | 'default'
}>(), {
  size: 200,
  style: 'default'
})

const canvasRef = ref<HTMLCanvasElement>()

// 根据角色类型和性格生成种子
function seedFromCharacter(data: PortraitData): number {
  let hash = 0
  const str = data.name + (data.personality || '') + (data.role || '')
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

function seededRandom(seed: number): () => number {
  let s = seed
  return () => {
    s = (s * 16807 + 0) % 2147483647
    return (s - 1) / 2147483646
  }
}

// 解析势力色
function parseColor(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return [r, g, b]
}

// 获取角色类型默认颜色
function getRoleColor(data: PortraitData): [number, number, number] {
  if (data.color) return parseColor(data.color)

  const role = data.role || data.roleLabel || ''
  if (role.includes('将') || role.includes('帅') || role.includes('军') || role.includes('武')) return [180, 60, 40]
  if (role.includes('谋') || role.includes('策') || role.includes('军师')) return [120, 80, 160]
  if (role.includes('丞') || role.includes('宰') || role.includes('辅')) return [40, 100, 140]
  if (role.includes('帝') || role.includes('王') || role.includes('主') || role.includes('皇') || role.includes('君')) return [160, 120, 20]
  if (role.includes('文') || role.includes('学') || role.includes('书')) return [60, 100, 80]
  if (role.includes('使') || role.includes('交') || role.includes('客')) return [80, 120, 140]
  return [120, 100, 80]
}

// 获取性格色彩倾向
function getPersonalityTone(personality: string, tags: string[]): { warm: number; dark: number; sharp: number } {
  let warm = 0.3, dark = 0.3, sharp = 0.3
  const allTraits = [personality, ...tags].join('')

  if (/仁|善|和|宽|温|柔|爱|忠|义|厚|贤|惠/.test(allTraits)) warm += 0.3
  if (/勇|猛|烈|刚|锐|果|决|英/.test(allTraits)) warm += 0.2
  if (/疑|忌|奸|诈|阴|狠|残|酷|暴/.test(allTraits)) dark += 0.3
  if (/谋|智|机|变|巧|算/.test(allTraits)) sharp += 0.2
  if (/野|雄|霸|贪|欲/.test(allTraits)) { dark += 0.15; sharp += 0.15 }
  if (/沉|稳|重|守|固/.test(allTraits)) dark += 0.15
  if (/豪|放|粗|莽|直/.test(allTraits)) warm += 0.15

  return {
    warm: Math.min(1, Math.max(0, warm)),
    dark: Math.min(1, Math.max(0, dark)),
    sharp: Math.min(1, Math.max(0, sharp))
  }
}

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const size = props.size
  const data = props.portraitData
  const seed = seedFromCharacter(data)
  const rand = seededRandom(seed)
  const [baseR, baseG, baseB] = getRoleColor(data)
  const tags = data.personalityTags || []
  const tone = getPersonalityTone(data.personality || '', tags)

  // ========== 1. 背景 ==========
  const bgGrad = ctx.createRadialGradient(size * 0.3, size * 0.3, 0, size * 0.5, size * 0.5, size * 0.75)
  const bgR = Math.round(baseR * 0.15 + tone.dark * 30)
  const bgG = Math.round(baseG * 0.12 + tone.dark * 20)
  const bgB = Math.round(baseB * 0.1 + tone.dark * 25)
  bgGrad.addColorStop(0, `rgb(${Math.min(255, bgR + 30)},${Math.min(255, bgG + 25)},${Math.min(255, bgB + 20)})`)
  bgGrad.addColorStop(0.5, `rgb(${bgR},${bgG},${bgB})`)
  bgGrad.addColorStop(1, `rgb(${Math.max(0, bgR - 20)},${Math.max(0, bgG - 15)},${Math.max(0, bgB - 10)})`)
  ctx.fillStyle = bgGrad
  ctx.fillRect(0, 0, size, size)

  // 竹简竖纹
  ctx.globalAlpha = 0.04
  ctx.strokeStyle = '#b8963e'
  ctx.lineWidth = 1
  for (let i = 0; i < size; i += 6) {
    ctx.beginPath()
    ctx.moveTo(i, 0)
    ctx.lineTo(i + rand() * 3 - 1.5, size)
    ctx.stroke()
  }
  ctx.globalAlpha = 1

  // 光晕
  const haloGrad = ctx.createRadialGradient(size * 0.45, size * 0.35, size * 0.05, size * 0.45, size * 0.35, size * 0.5)
  haloGrad.addColorStop(0, `rgba(${baseR},${baseG},${baseB},0.12)`)
  haloGrad.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.fillStyle = haloGrad
  ctx.fillRect(0, 0, size, size)

  // ========== 2. 衣袍/身躯 ==========
  const robeColor = `rgb(${Math.round(baseR * 0.5 + tone.dark * 60)},${Math.round(baseG * 0.45 + tone.dark * 45)},${Math.round(baseB * 0.4 + tone.dark * 50)})`
  const robeDark = `rgb(${Math.round(baseR * 0.3 + tone.dark * 40)},${Math.round(baseG * 0.25 + tone.dark * 30)},${Math.round(baseB * 0.2 + tone.dark * 35)})`

  // 肩膀/衣领
  const shoulderY = size * 0.72
  const collarWidth = size * 0.22

  ctx.fillStyle = robeColor
  ctx.beginPath()
  // 左肩
  ctx.moveTo(size * 0.15, size)
  ctx.quadraticCurveTo(size * 0.2, shoulderY, size * 0.38, shoulderY + size * 0.02)
  ctx.lineTo(size * 0.5 - collarWidth * 0.1, shoulderY - size * 0.02)
  // 领口
  ctx.quadraticCurveTo(size * 0.5, shoulderY - size * 0.08, size * 0.5 + collarWidth * 0.1, shoulderY - size * 0.02)
  ctx.lineTo(size * 0.62, shoulderY + size * 0.02)
  ctx.quadraticCurveTo(size * 0.8, shoulderY, size * 0.85, size)
  ctx.closePath()
  ctx.fill()

  // 衣领边饰
  ctx.strokeStyle = robeDark
  ctx.lineWidth = size * 0.015
  ctx.beginPath()
  ctx.moveTo(size * 0.38, shoulderY + size * 0.02)
  ctx.quadraticCurveTo(size * 0.5, shoulderY - size * 0.08, size * 0.62, shoulderY + size * 0.02)
  ctx.stroke()

  // 衣领内衬
  const innerCollarGrad = ctx.createLinearGradient(size * 0.35, shoulderY - size * 0.06, size * 0.65, shoulderY - size * 0.06)
  innerCollarGrad.addColorStop(0, `rgb(${Math.min(255, baseR + 30)},${Math.min(255, baseG + 25)},${Math.min(255, baseB + 20)})`)
  innerCollarGrad.addColorStop(0.5, `rgb(${Math.min(255, baseR + 50)},${Math.min(255, baseG + 40)},${Math.min(255, baseB + 30)})`)
  innerCollarGrad.addColorStop(1, `rgb(${Math.min(255, baseR + 30)},${Math.min(255, baseG + 25)},${Math.min(255, baseB + 20)})`)
  ctx.fillStyle = innerCollarGrad
  ctx.beginPath()
  ctx.moveTo(size * 0.4, shoulderY - size * 0.02)
  ctx.quadraticCurveTo(size * 0.5, shoulderY - size * 0.1, size * 0.6, shoulderY - size * 0.02)
  ctx.quadraticCurveTo(size * 0.5, shoulderY - size * 0.04, size * 0.4, shoulderY - size * 0.02)
  ctx.fill()

  // ========== 3. 头部 ==========
  const headCX = size * 0.5
  const headCY = size * 0.32
  const headW = size * 0.26
  const headH = size * 0.31

  // 肤色
  const skinTone = 0.7 + tone.warm * 0.2 - tone.dark * 0.15
  const skinR = Math.round(200 * skinTone + 30)
  const skinG = Math.round(170 * skinTone + 20)
  const skinB = Math.round(135 * skinTone + 15)
  const skinColor = `rgb(${skinR},${skinG},${skinB})`
  const skinShadow = `rgb(${Math.round(skinR * 0.75)},${Math.round(skinG * 0.72)},${Math.round(skinB * 0.7)})`

  // 脸型微调
  const faceWidthVar = 0.85 + rand() * 0.3
  const faceHeightVar = 0.9 + rand() * 0.2

  // 脸
  ctx.fillStyle = skinColor
  ctx.beginPath()
  ctx.ellipse(headCX, headCY, headW * faceWidthVar * 0.5, headH * faceHeightVar * 0.5, 0, 0, Math.PI * 2)
  ctx.fill()

  // 面部阴影（颧骨下方）
  const cheekGrad = ctx.createRadialGradient(headCX, headCY + headH * 0.15, headW * 0.1, headCX, headCY + headH * 0.15, headW * 0.5)
  cheekGrad.addColorStop(0, 'rgba(0,0,0,0)')
  cheekGrad.addColorStop(0.6, 'rgba(0,0,0,0)')
  cheekGrad.addColorStop(1, `rgba(0,0,0,${0.08 + tone.dark * 0.1})`)
  ctx.fillStyle = cheekGrad
  ctx.beginPath()
  ctx.ellipse(headCX, headCY, headW * faceWidthVar * 0.5, headH * faceHeightVar * 0.5, 0, 0, Math.PI * 2)
  ctx.fill()

  // ========== 4. 五官 ==========

  // 眉毛
  ctx.strokeStyle = skinShadow
  ctx.lineWidth = size * 0.012
  ctx.lineCap = 'round'

  const browY = headCY - headH * 0.12
  const browLen = headW * 0.22
  const browGap = headW * 0.12
  const browAngle = (rand() * 0.2 - 0.1) * (tone.sharp > 0.5 ? -1 : 1)

  // 左眉
  ctx.beginPath()
  ctx.moveTo(headCX - browGap - browLen * 0.6, browY + browAngle * browLen * 0.3)
  ctx.quadraticCurveTo(headCX - browGap - browLen * 0.1, browY - browAngle * browLen * 0.15, headCX - browGap + browLen * 0.4, browY + browAngle * browLen * 0.1)
  ctx.stroke()

  // 右眉
  ctx.beginPath()
  ctx.moveTo(headCX + browGap - browLen * 0.4, browY + browAngle * browLen * 0.1)
  ctx.quadraticCurveTo(headCX + browGap + browLen * 0.1, browY - browAngle * browLen * 0.15, headCX + browGap + browLen * 0.6, browY + browAngle * browLen * 0.3)
  ctx.stroke()

  // 眼睛
  const eyeY = headCY - headH * 0.02
  const eyeW = headW * 0.1
  const eyeH = headW * 0.06
  const eyeGap = headW * 0.14

  // 眼白
  ctx.fillStyle = '#f5f0e8'
  ctx.beginPath()
  ctx.ellipse(headCX - eyeGap, eyeY, eyeW, eyeH, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.ellipse(headCX + eyeGap, eyeY, eyeW, eyeH, 0, 0, Math.PI * 2)
  ctx.fill()

  // 瞳孔
  const irisColor = tone.dark > 0.5 ? '#2a1a0a' : '#3a2210'
  ctx.fillStyle = irisColor
  const irisR = eyeW * 0.45
  ctx.beginPath()
  ctx.arc(headCX - eyeGap, eyeY, irisR, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(headCX + eyeGap, eyeY, irisR, 0, Math.PI * 2)
  ctx.fill()

  // 眼神锐利度
  if (tone.sharp > 0.4) {
    ctx.fillStyle = 'rgba(0,0,0,0.3)'
    ctx.beginPath()
    ctx.ellipse(headCX - eyeGap, eyeY - eyeH * 0.15, eyeW * 0.7, eyeH * 0.55, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.ellipse(headCX + eyeGap, eyeY - eyeH * 0.15, eyeW * 0.7, eyeH * 0.55, 0, 0, Math.PI * 2)
    ctx.fill()
  }

  // 鼻子
  const noseY = headCY + headH * 0.08
  ctx.strokeStyle = skinShadow
  ctx.lineWidth = size * 0.008
  ctx.beginPath()
  ctx.moveTo(headCX, noseY - headH * 0.08)
  ctx.quadraticCurveTo(headCX + headW * 0.03, noseY, headCX, noseY + headH * 0.06)
  ctx.stroke()

  // 鼻孔微描
  ctx.fillStyle = skinShadow
  ctx.globalAlpha = 0.4
  ctx.beginPath()
  ctx.arc(headCX - headW * 0.03, noseY + headH * 0.04, size * 0.006, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(headCX + headW * 0.03, noseY + headH * 0.04, size * 0.006, 0, Math.PI * 2)
  ctx.fill()
  ctx.globalAlpha = 1

  // 嘴
  const mouthY = headCY + headH * 0.2
  const mouthW = headW * 0.16
  const mouthCurve = tone.warm > 0.5 ? -0.3 : tone.dark > 0.5 ? 0.2 : 0

  ctx.strokeStyle = skinShadow
  ctx.lineWidth = size * 0.01
  ctx.beginPath()
  ctx.moveTo(headCX - mouthW, mouthY)
  ctx.quadraticCurveTo(headCX, mouthY + mouthCurve * mouthW, headCX + mouthW, mouthY)
  ctx.stroke()

  // 下唇阴影
  ctx.fillStyle = `rgba(${Math.round(skinR * 0.9)},${Math.round(skinG * 0.85)},${Math.round(skinB * 0.8)},0.3)`
  ctx.beginPath()
  ctx.ellipse(headCX, mouthY + headH * 0.06, mouthW * 0.6, headH * 0.04, 0, 0, Math.PI * 2)
  ctx.fill()

  // ========== 5. 胡须（根据角色） ==========
  const ageHint = data.wisdom ? (data.wisdom > 80 ? 1 : data.wisdom > 60 ? 0.5 : 0) : 0.3
  const hasBeard = rand() > 0.2 || ageHint > 0.5

  if (hasBeard) {
    const beardLen = headH * (0.2 + rand() * 0.3)
    ctx.fillStyle = skinShadow
    ctx.globalAlpha = 0.5 + tone.dark * 0.3

    // 山羊胡
    ctx.beginPath()
    ctx.moveTo(headCX - headW * 0.06, mouthY + headH * 0.03)
    ctx.quadraticCurveTo(headCX, mouthY + beardLen, headCX + headW * 0.06, mouthY + headH * 0.03)
    ctx.quadraticCurveTo(headCX, mouthY + beardLen * 0.7, headCX - headW * 0.06, mouthY + headH * 0.03)
    ctx.fill()

    // 鬓须
    if (ageHint > 0.4) {
      ctx.beginPath()
      ctx.moveTo(headCX - headW * 0.35, headCY + headH * 0.05)
      ctx.quadraticCurveTo(headCX - headW * 0.45, headCY + headH * 0.3, headCX - headW * 0.3, headCY + headH * 0.35)
      ctx.quadraticCurveTo(headCX - headW * 0.25, headCY + headH * 0.25, headCX - headW * 0.35, headCY + headH * 0.05)
      ctx.fill()

      ctx.beginPath()
      ctx.moveTo(headCX + headW * 0.35, headCY + headH * 0.05)
      ctx.quadraticCurveTo(headCX + headW * 0.45, headCY + headH * 0.3, headCX + headW * 0.3, headCY + headH * 0.35)
      ctx.quadraticCurveTo(headCX + headW * 0.25, headCY + headH * 0.25, headCX + headW * 0.35, headCY + headH * 0.05)
      ctx.fill()
    }
    ctx.globalAlpha = 1
  }

  // ========== 6. 头冠/官帽 ==========
  const hatY = headCY - headH * 0.48

  // 君主戴冕冠，文臣戴乌纱/梁冠，武将戴盔
  if (props.style === 'ruler' || data.isRuler) {
    drawImperialCrown(ctx, headCX, hatY, headW, headH, baseR, baseG, baseB, tone)
  } else if (props.style === 'general' || (data.roleLabel && /将|帅|军|武/.test(data.roleLabel))) {
    drawMilitaryHelmet(ctx, headCX, hatY, headW, headH, baseR, baseG, baseB, tone)
  } else if (props.style === 'strategist' || (data.roleLabel && /谋|策|军师/.test(data.roleLabel || ''))) {
    drawScholarHat(ctx, headCX, hatY, headW, headH, baseR, baseG, baseB, tone)
  } else {
    drawOfficialHat(ctx, headCX, hatY, headW, headH, baseR, baseG, baseB, tone)
  }

  // ========== 7. 装饰元素 ==========

  // 势力色光点
  ctx.globalAlpha = 0.15 + tone.warm * 0.1
  for (let i = 0; i < 6; i++) {
    const px = rand() * size * 0.8 + size * 0.1
    const py = rand() * size * 0.3 + size * 0.55
    const pr = 1 + rand() * 2
    ctx.fillStyle = `rgb(${baseR},${baseG},${baseB})`
    ctx.beginPath()
    ctx.arc(px, py, pr, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.globalAlpha = 1

  // 底部势力色条
  const barGrad = ctx.createLinearGradient(0, size * 0.92, 0, size)
  barGrad.addColorStop(0, `rgba(${baseR},${baseG},${baseB},0)`)
  barGrad.addColorStop(0.5, `rgba(${baseR},${baseG},${baseB},0.25)`)
  barGrad.addColorStop(1, `rgba(${baseR},${baseG},${baseB},0.5)`)
  ctx.fillStyle = barGrad
  ctx.fillRect(0, size * 0.92, size, size * 0.08)

  // ========== 8. 文字标注 ==========
  ctx.fillStyle = `rgba(${baseR},${baseG},${baseB},0.6)`
  ctx.font = `bold ${Math.round(size * 0.08)}px "Noto Serif SC", "SimSun", serif`
  ctx.textAlign = 'center'

  // 名号
  ctx.fillText(data.name, size * 0.5, size * 0.89)

  // 称号
  if (data.title) {
    ctx.fillStyle = `rgba(${baseR},${baseG},${baseB},0.35)`
    ctx.font = `${Math.round(size * 0.055)}px "Noto Serif SC", "SimSun", serif`
    ctx.fillText(data.title, size * 0.5, size * 0.96)
  }
}

// 冕冠
function drawImperialCrown(ctx: CanvasRenderingContext2D, cx: number, topY: number, hw: number, _hh: number, r: number, g: number, b: number, _tone: any) {
  const crownW = hw * 0.9
  const crownH = hw * 0.45

  // 冠体
  const crownGrad = ctx.createLinearGradient(cx, topY, cx, topY + crownH)
  crownGrad.addColorStop(0, `rgb(${Math.min(255, r + 80)},${Math.min(255, g + 60)},${Math.min(255, b + 40)})`)
  crownGrad.addColorStop(0.5, `rgb(${r},${g},${b})`)
  crownGrad.addColorStop(1, `rgb(${Math.max(0, r - 30)},${Math.max(0, g - 25)},${Math.max(0, b - 20)})`)
  ctx.fillStyle = crownGrad
  ctx.beginPath()
  ctx.moveTo(cx - crownW, topY + crownH)
  ctx.lineTo(cx - crownW * 0.8, topY)
  ctx.lineTo(cx + crownW * 0.8, topY)
  ctx.lineTo(cx + crownW, topY + crownH)
  ctx.closePath()
  ctx.fill()

  // 冠顶横梁
  ctx.strokeStyle = `rgb(${Math.min(255, r + 100)},${Math.min(255, g + 80)},${Math.min(255, b + 60)})`
  ctx.lineWidth = hw * 0.06
  ctx.beginPath()
  ctx.moveTo(cx - crownW * 0.6, topY + crownH * 0.1)
  ctx.lineTo(cx + crownW * 0.6, topY + crownH * 0.1)
  ctx.stroke()

  // 冕旒（珠串）
  ctx.strokeStyle = `rgba(${Math.min(255, r + 100)},${Math.min(255, g + 80)},${Math.min(255, b + 60)},0.6)`
  ctx.lineWidth = hw * 0.02
  for (let i = -2; i <= 2; i++) {
    ctx.beginPath()
    const sx = cx + i * crownW * 0.18
    ctx.moveTo(sx, topY + crownH * 0.15)
    for (let j = 0; j < 5; j++) {
      ctx.lineTo(sx, topY + crownH * 0.15 + j * crownH * 0.18)
    }
    ctx.stroke()

    // 旒珠
    ctx.fillStyle = `rgba(240,220,180,${0.3 + j * 0.05})`
    for (let j = 0; j < 5; j++) {
      ctx.beginPath()
      ctx.arc(sx, topY + crownH * 0.2 + j * crownH * 0.18, hw * 0.025, 0, Math.PI * 2)
      ctx.fill()
    }
  }
}

// 武盔
function drawMilitaryHelmet(ctx: CanvasRenderingContext2D, cx: number, topY: number, hw: number, _hh: number, r: number, g: number, b: number, _tone: any) {
  const helmW = hw * 0.7
  const helmH = hw * 0.4

  const helmGrad = ctx.createLinearGradient(cx, topY, cx, topY + helmH)
  helmGrad.addColorStop(0, `rgb(${Math.min(255, r + 40)},${Math.min(255, g + 30)},${Math.min(255, b + 20)})`)
  helmGrad.addColorStop(0.5, `rgb(${r},${g},${b})`)
  helmGrad.addColorStop(1, `rgb(${Math.max(0, r - 40)},${Math.max(0, g - 30)},${Math.max(0, b - 25)})`)
  ctx.fillStyle = helmGrad
  ctx.beginPath()
  ctx.ellipse(cx, topY + helmH * 0.6, helmW, helmH, 0, Math.PI, 0)
  ctx.fill()

  // 盔缨
  ctx.fillStyle = `rgb(${Math.min(255, r + 60)},${Math.min(255, g + 30)},${Math.min(255, b + 20)})`
  ctx.beginPath()
  ctx.moveTo(cx - hw * 0.05, topY)
  ctx.quadraticCurveTo(cx + hw * 0.03, topY - hw * 0.2, cx + hw * 0.08, topY)
  ctx.fill()

  // 盔顶尖
  ctx.fillStyle = '#c0a060'
  ctx.beginPath()
  ctx.moveTo(cx - hw * 0.03, topY - hw * 0.02)
  ctx.lineTo(cx, topY - hw * 0.2)
  ctx.lineTo(cx + hw * 0.03, topY - hw * 0.02)
  ctx.fill()
}

// 儒巾
function drawScholarHat(ctx: CanvasRenderingContext2D, cx: number, topY: number, hw: number, _hh: number, r: number, g: number, b: number, _tone: any) {
  const hatW = hw * 0.65
  const hatH = hw * 0.25

  ctx.fillStyle = `rgb(${Math.round(r * 0.5)},${Math.round(g * 0.45)},${Math.round(b * 0.4)})`
  ctx.beginPath()
  ctx.moveTo(cx - hatW * 0.6, topY + hatH * 0.5)
  ctx.quadraticCurveTo(cx - hatW * 0.5, topY - hatH * 0.2, cx - hatW * 0.1, topY - hatH * 0.1)
  ctx.lineTo(cx + hatW * 0.1, topY - hatH * 0.1)
  ctx.quadraticCurveTo(cx + hatW * 0.5, topY - hatH * 0.2, cx + hatW * 0.6, topY + hatH * 0.5)
  ctx.closePath()
  ctx.fill()

  // 帽翅
  ctx.fillStyle = `rgb(${Math.round(r * 0.4)},${Math.round(g * 0.35)},${Math.round(b * 0.3)})`
  ctx.beginPath()
  ctx.ellipse(cx, topY - hatH * 0.05, hatW * 0.7, hatH * 0.4, 0, 0, Math.PI * 2)
  ctx.fill()
}

// 乌纱/官帽
function drawOfficialHat(ctx: CanvasRenderingContext2D, cx: number, topY: number, hw: number, _hh: number, r: number, g: number, b: number, _tone: any) {
  const hatW = hw * 0.6
  const hatH = hw * 0.22

  ctx.fillStyle = `rgb(${Math.round(r * 0.5)},${Math.round(g * 0.45)},${Math.round(b * 0.4)})`
  ctx.beginPath()
  ctx.moveTo(cx - hatW, topY + hatH * 0.3)
  ctx.lineTo(cx - hatW * 0.7, topY - hatH * 0.2)
  ctx.lineTo(cx + hatW * 0.7, topY - hatH * 0.2)
  ctx.lineTo(cx + hatW, topY + hatH * 0.3)
  ctx.closePath()
  ctx.fill()

  // 帽翅（文官有翅）
  ctx.fillStyle = `rgb(${Math.round(r * 0.4)},${Math.round(g * 0.35)},${Math.round(b * 0.3)})`
  ctx.fillRect(cx - hatW * 1.1, topY - hatH * 0.1, hatW * 0.5, hatH * 0.15)
  ctx.fillRect(cx + hatW * 0.6, topY - hatH * 0.1, hatW * 0.5, hatH * 0.15)
}

// 暴露方法让父组件可以调用重绘
defineExpose({ redraw: draw })

onMounted(() => { draw() })
watch(() => props.portraitData, () => { draw() }, { deep: true })
watch(() => props.size, () => { draw() })
</script>

<style scoped>
.char-portrait-canvas {
  display: block;
  border-radius: 4px;
}
</style>
