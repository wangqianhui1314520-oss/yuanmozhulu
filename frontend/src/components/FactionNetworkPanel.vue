<template>
  <div class="network-panel float-panel artifact-panel artifact-secret">
    <div class="fp-header">
      <h3>🗺 天下势力·关系网络</h3>
      <div class="fp-tabs">
        <button :class="{ active: netTab === 'graph' }" @click="netTab = 'graph'">关系图</button>
        <button :class="{ active: netTab === 'matrix' }" @click="netTab = 'matrix'">关系矩阵</button>
      </div>
      <button v-audio class="fp-close" @click="store.togglePanel('faction_network')">✕</button>
    </div>

    <!-- 关系图谱视图 -->
    <div class="fp-body network-body" v-if="netTab === 'graph'">
      <div class="network-canvas-wrap" ref="canvasWrapRef">
        <canvas ref="canvasRef" @mousemove="onCanvasMouseMove" @mouseleave="onCanvasMouseLeave"
          @click="onCanvasClick" @wheel.prevent="onCanvasWheel"></canvas>
        <!-- 势力详情悬浮提示 -->
        <div v-if="tooltip.faction" class="network-tooltip"
          :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
          <div class="tt-name" :style="{ color: tooltip.faction.color }">{{ tooltip.faction.name }}</div>
          <div class="tt-title">{{ tooltip.faction.title }}</div>
          <div class="tt-stats">
            <span>兵{{ fmtNum(tooltip.faction.troops) }}</span>
            <span>银{{ fmtNum(tooltip.faction.treasury) }}</span>
            <span>地{{ tooltip.faction.tiles }}块</span>
          </div>
          <div class="tt-tags">
            <span v-for="t in tooltip.faction.tags" :key="t" class="tt-tag">{{ t }}</span>
          </div>
          <div class="tt-relation" v-if="tooltip.faction.relationText">
            {{ tooltip.faction.relationText }}
          </div>
        </div>
      </div>
      <!-- 图例 -->
      <div class="network-legend">
        <span class="legend-item"><span class="leg-line leg-war"></span>交战</span>
        <span class="legend-item"><span class="leg-line leg-hostile"></span>敌对</span>
        <span class="legend-item"><span class="leg-line leg-neutral"></span>中立</span>
        <span class="legend-item"><span class="leg-line leg-friendly"></span>友善</span>
        <span class="legend-item"><span class="leg-line leg-alliance"></span>同盟</span>
      </div>
    </div>

    <!-- 关系矩阵视图 -->
    <div class="fp-body matrix-body" v-if="netTab === 'matrix'">
      <div class="matrix-table-wrap">
        <table class="matrix-table">
          <thead>
            <tr>
              <th></th>
              <th v-for="f in factionList" :key="f.id" :style="{ color: f.color }"
                class="matrix-col-header">{{ f.shortName }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in factionList" :key="a.id">
              <td class="matrix-row-header" :style="{ color: a.color }">{{ a.shortName }}</td>
              <td v-for="b in factionList" :key="b.id"
                :class="['matrix-cell', getMatrixClass(a.id, b.id)]"
                :title="getMatrixTitle(a.id, b.id)">
                {{ getMatrixIcon(a.id, b.id) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useGameStore } from '@/stores/gameStore'

const store = useGameStore()
const netTab = ref<'graph' | 'matrix'>('graph')
const canvasRef = ref<HTMLCanvasElement>()
const canvasWrapRef = ref<HTMLDivElement>()
const tooltip = ref<{ faction: any; x: number; y: number }>({ faction: null, x: 0, y: 0 })

// ===== 九大势力配置（从 factions.json 提取） =====
interface FactionNode {
  id: string; name: string; shortName: string; title: string
  color: string; troops: number; treasury: number; tiles: number
  tags: string[]; difficulty: string
  x: number; y: number
}
const factionList = ref<FactionNode[]>([
  { id: 'faction_yuan', name: '元廷', shortName: '元', title: '大元皇帝', color: '#8B0000', troops: 6000, treasury: 20000, tiles: 19, tags: ['蒙古铁骑', '正统名分'], difficulty: '地狱', x: 0, y: 0 },
  { id: 'faction_zhuyuanzhang', name: '朱元璋', shortName: '朱', title: '吴国公', color: '#DC143C', troops: 3000, treasury: 8000, tiles: 11, tags: ['深谋远虑', '严刑峻法'], difficulty: '普通', x: 0, y: 0 },
  { id: 'faction_chenyouliang', name: '陈友谅', shortName: '陈', title: '汉帝', color: '#1E90FF', troops: 5000, treasury: 12000, tiles: 14, tags: ['野心勃勃', '水战精通'], difficulty: '困难', x: 0, y: 0 },
  { id: 'faction_zhangshicheng', name: '张士诚', shortName: '张', title: '周王', color: '#FF8C00', troops: 3500, treasury: 15000, tiles: 9, tags: ['偏安一隅', '富甲一方'], difficulty: '简单', x: 0, y: 0 },
  { id: 'faction_fangguozhen', name: '方国珍', shortName: '方', title: '浙东节度', color: '#20B2AA', troops: 2000, treasury: 6000, tiles: 4, tags: ['海上枭雄', '投机善变'], difficulty: '中等', x: 0, y: 0 },
  { id: 'faction_wangbaobao', name: '王保保', shortName: '王', title: '河南王', color: '#666699', troops: 4000, treasury: 8000, tiles: 6, tags: ['忠勇无双', '骑兵统帅'], difficulty: '中等', x: 0, y: 0 },
  { id: 'faction_xushouhui', name: '徐寿辉', shortName: '徐', title: '天完皇帝', color: '#996633', troops: 3500, treasury: 6000, tiles: 6, tags: ['弥勒信徒', '红巾领袖'], difficulty: '困难', x: 0, y: 0 },
  { id: 'faction_mingyuzhen', name: '明玉珍', shortName: '明', title: '大夏皇帝', color: '#B8860B', troops: 3000, treasury: 6500, tiles: 8, tags: ['仁厚之主', '蜀道自守'], difficulty: '简单', x: 0, y: 0 },
  { id: 'faction_mobei', name: '漠北诸部', shortName: '漠', title: '草原大汗', color: '#887766', troops: 4500, treasury: 5000, tiles: 5, tags: ['游牧骑射', '劫掠为生'], difficulty: '困难', x: 0, y: 0 },
])

// 预设关系矩阵（基于 counter_relations + 历史逻辑）
const relationMatrix: Record<string, Record<string, number>> = {
  faction_yuan: { faction_zhuyuanzhang: -30, faction_chenyouliang: -15, faction_zhangshicheng: -10, faction_fangguozhen: -5, faction_wangbaobao: 20, faction_xushouhui: -30, faction_mingyuzhen: -10, faction_mobei: -10 },
  faction_zhuyuanzhang: { faction_yuan: -30, faction_chenyouliang: -25, faction_zhangshicheng: -15, faction_fangguozhen: 5, faction_wangbaobao: -10, faction_xushouhui: 5, faction_mingyuzhen: 5, faction_mobei: 0 },
  faction_chenyouliang: { faction_yuan: -15, faction_zhuyuanzhang: -25, faction_zhangshicheng: -5, faction_fangguozhen: 0, faction_wangbaobao: -5, faction_xushouhui: -15, faction_mingyuzhen: 0, faction_mobei: 0 },
  faction_zhangshicheng: { faction_yuan: -10, faction_zhuyuanzhang: -10, faction_chenyouliang: -5, faction_fangguozhen: -5, faction_wangbaobao: 0, faction_xushouhui: 0, faction_mingyuzhen: 0, faction_mobei: 0 },
  faction_fangguozhen: { faction_yuan: -5, faction_zhuyuanzhang: 5, faction_chenyouliang: 0, faction_zhangshicheng: -5, faction_wangbaobao: 0, faction_xushouhui: 0, faction_mingyuzhen: 0, faction_mobei: 0 },
  faction_wangbaobao: { faction_yuan: 20, faction_zhuyuanzhang: -10, faction_chenyouliang: -5, faction_zhangshicheng: 0, faction_fangguozhen: 0, faction_xushouhui: -20, faction_mingyuzhen: -5, faction_mobei: -15 },
  faction_xushouhui: { faction_yuan: -30, faction_zhuyuanzhang: 5, faction_chenyouliang: -15, faction_zhangshicheng: 0, faction_fangguozhen: 0, faction_wangbaobao: -20, faction_mingyuzhen: 10, faction_mobei: 0 },
  faction_mingyuzhen: { faction_yuan: -10, faction_zhuyuanzhang: 5, faction_chenyouliang: 0, faction_zhangshicheng: 0, faction_fangguozhen: 0, faction_wangbaobao: -5, faction_xushouhui: 10, faction_mobei: 0 },
  faction_mobei: { faction_yuan: -10, faction_zhuyuanzhang: 0, faction_chenyouliang: 0, faction_zhangshicheng: 0, faction_fangguozhen: 0, faction_wangbaobao: -15, faction_xushouhui: 0, faction_mingyuzhen: 0 },
}

// 预设圆形布局坐标
const layoutPreset = [
  { angle: Math.PI * 2 * 0 / 9, radius: 0.75 },  // 元廷 - 正北
  { angle: Math.PI * 2 * 1 / 9, radius: 0.72 },  // 王保保
  { angle: Math.PI * 2 * 2 / 9, radius: 0.78 },  // 朱元璋
  { angle: Math.PI * 2 * 3 / 9, radius: 0.65 },  // 张士诚
  { angle: Math.PI * 2 * 4 / 9, radius: 0.55 },  // 方国珍
  { angle: Math.PI * 2 * 5 / 9, radius: 0.7 },   // 陈友谅
  { angle: Math.PI * 2 * 6 / 9, radius: 0.6 },   // 徐寿辉
  { angle: Math.PI * 2 * 7 / 9, radius: 0.5 },   // 明玉珍
  { angle: Math.PI * 2 * 8 / 9, radius: 0.6 },   // 漠北
]

let animFrameId = 0
let canvasW = 0, canvasH = 0
const nodePositions: { x: number; y: number }[] = []
let hoveredNodeIdx = -1

function fmtNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function getRelation(aId: string, bId: string): number {
  if (aId === bId) return 0
  return relationMatrix[aId]?.[bId] ?? relationMatrix[bId]?.[aId] ?? 0
}

function getRelationLabel(val: number): string {
  if (val <= -20) return '交战/深仇'
  if (val <= -10) return '敌对'
  if (val <= -5) return '冷淡'
  if (val <= 5) return '中立'
  if (val <= 15) return '友善'
  return '同盟/亲近'
}

function getRelationColor(val: number): string {
  if (val <= -20) return '#c43a3a'
  if (val <= -10) return '#d47050'
  if (val <= -5) return '#a08060'
  if (val <= 5) return '#8c8068'
  if (val <= 15) return '#5b9a5a'
  return '#4a9a4a'
}

// ===== Canvas 渲染 =====
function initLayout() {
  const list = factionList.value
  list.forEach((f, i) => {
    const preset = layoutPreset[i]
    f.x = preset.angle
    f.y = preset.radius
  })
}

function renderCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dpr = window.devicePixelRatio || 1
  const wrap = canvasWrapRef.value
  const w = wrap ? wrap.clientWidth : 600
  const h = wrap ? wrap.clientHeight : 500
  canvasW = w; canvasH = h
  canvas.width = w * dpr; canvas.height = h * dpr
  canvas.style.width = w + 'px'; canvas.style.height = h + 'px'
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const cx = w / 2; const cy = h / 2
  const maxR = Math.min(w, h) * 0.38
  const list = factionList.value

  // 计算所有节点的绝对坐标
  nodePositions.length = 0
  list.forEach((f, i) => {
    const angle = layoutPreset[i].angle - Math.PI / 2 // 从正北开始
    const radius = layoutPreset[i].radius * maxR
    nodePositions.push({ x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius })
  })

  // ===== 清屏 =====
  ctx.clearRect(0, 0, w, h)

  // ===== 背景粒子 =====
  ctx.fillStyle = 'rgba(180, 150, 60, 0.03)'
  for (let i = 0; i < 20; i++) {
    const px = (Math.sin(Date.now() * 0.0003 + i * 1.7) * 0.5 + 0.5) * w
    const py = (Math.cos(Date.now() * 0.0005 + i * 2.1) * 0.5 + 0.5) * h
    ctx.beginPath(); ctx.arc(px, py, 2, 0, Math.PI * 2); ctx.fill()
  }

  // ===== 绘制关系连线 =====
  for (let i = 0; i < list.length; i++) {
    for (let j = i + 1; j < list.length; j++) {
      const rel = getRelation(list[i].id, list[j].id)
      const from = nodePositions[i]
      const to = nodePositions[j]

      let alpha = 0.15
      let lineWidth = 0.8
      if (Math.abs(rel) >= 10) { alpha = 0.35; lineWidth = 1.5 }
      if (Math.abs(rel) >= 20) { alpha = 0.55; lineWidth = 2.5 }

      const color = getRelationColor(rel)

      // 虚线（敌对）或实线
      if (rel < 0) ctx.setLineDash([6, 4])
      else ctx.setLineDash([])

      ctx.beginPath()
      ctx.moveTo(from.x, from.y)
      ctx.lineTo(to.x, to.y)
      ctx.strokeStyle = color.replace(')', `, ${alpha})`).replace('rgb', 'rgba')
      if (color.startsWith('#')) {
        const r = parseInt(color.slice(1, 3), 16)
        const g = parseInt(color.slice(3, 5), 16)
        const b = parseInt(color.slice(5, 7), 16)
        ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`
      }
      ctx.lineWidth = lineWidth
      ctx.stroke()
      ctx.setLineDash([])

      // 关系标签（仅重要关系）
      if (Math.abs(rel) >= 15) {
        const mx = (from.x + to.x) / 2
        const my = (from.y + to.y) / 2
        ctx.fillStyle = `rgba(200, 180, 140, 0.5)`
        ctx.font = '9px SimSun, serif'
        ctx.textAlign = 'center'
        ctx.fillText(getRelationLabel(rel), mx, my - 4)
      }
    }
  }

  // ===== 绘制势力节点 =====
  list.forEach((f, i) => {
    const pos = nodePositions[i]
    const isHovered = i === hoveredNodeIdx
    const isPlayer = f.id === store.playerFactionId
    const nodeR = isHovered ? 34 : (isPlayer ? 30 : 25)

    // 光晕（玩家势力金色）
    if (isPlayer) {
      const glow = ctx.createRadialGradient(pos.x, pos.y, nodeR * 0.6, pos.x, pos.y, nodeR * 1.5)
      glow.addColorStop(0, 'rgba(184, 150, 62, 0.3)')
      glow.addColorStop(1, 'rgba(184, 150, 62, 0)')
      ctx.fillStyle = glow
      ctx.beginPath(); ctx.arc(pos.x, pos.y, nodeR * 1.5, 0, Math.PI * 2); ctx.fill()
    }

    // 节点圆
    const grad = ctx.createRadialGradient(pos.x - 3, pos.y - 3, nodeR * 0.1, pos.x, pos.y, nodeR)
    grad.addColorStop(0, '#ffffff')
    grad.addColorStop(0.2, f.color)
    grad.addColorStop(1, '#0a0806')
    ctx.fillStyle = grad
    ctx.beginPath(); ctx.arc(pos.x, pos.y, nodeR, 0, Math.PI * 2); ctx.fill()

    // 边框
    ctx.strokeStyle = isHovered ? '#e0d5b8' : 'rgba(180,150,60,0.3)'
    ctx.lineWidth = isHovered ? 2 : 1
    ctx.stroke()

    // 势力简称
    ctx.fillStyle = '#e0d5b8'
    ctx.font = `bold ${isHovered ? 16 : 13}px STKaiti, KaiTi, serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(f.shortName, pos.x, pos.y)

    // 名称标签
    ctx.fillStyle = 'rgba(200, 180, 140, 0.7)'
    ctx.font = '10px SimSun, serif'
    ctx.fillText(f.name, pos.x, pos.y + nodeR + 14)
  })

  // ===== 标题 =====
  ctx.fillStyle = 'rgba(200, 180, 140, 0.25)'
  ctx.font = '10px STKaiti, KaiTi, serif'
  ctx.textAlign = 'center'
  ctx.fillText('元末群雄·势力关系网络', cx, h - 16)

  animFrameId = requestAnimationFrame(renderCanvas)
}

function onCanvasMouseMove(e: MouseEvent) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const list = factionList.value

  hoveredNodeIdx = -1
  for (let i = 0; i < nodePositions.length; i++) {
    const dx = mx - nodePositions[i].x
    const dy = my - nodePositions[i].y
    if (Math.sqrt(dx * dx + dy * dy) < 30) {
      hoveredNodeIdx = i
      // 更新 tooltip
      const f = list[i]
      const rels: string[] = []
      list.forEach((other, j) => {
        if (i === j) return
        const rel = getRelation(f.id, other.id)
        if (Math.abs(rel) >= 10) rels.push(`${other.shortName}: ${getRelationLabel(rel)}`)
      })
      tooltip.value = {
        faction: {
          ...f,
          troops: f.troops, treasury: f.treasury, tiles: f.tiles,
          relationText: rels.length > 0 ? '重要关系: ' + rels.slice(0, 3).join(' | ') : '',
        },
        x: mx + 15,
        y: my - 10,
      }
      break
    }
  }
  if (hoveredNodeIdx === -1) {
    tooltip.value = { faction: null, x: 0, y: 0 }
  }
}

function onCanvasMouseLeave() {
  hoveredNodeIdx = -1
  tooltip.value = { faction: null, x: 0, y: 0 }
}

let zoomScale = 1
function onCanvasWheel(e: WheelEvent) {
  zoomScale = Math.max(0.6, Math.min(1.8, zoomScale + (e.deltaY > 0 ? -0.1 : 0.1)))
}

function onCanvasClick(e: MouseEvent) {
  if (hoveredNodeIdx >= 0) {
    // 可以扩展：点击势力查看详情
    const f = factionList.value[hoveredNodeIdx]
    if (store.livingFactions) {
      const liveFaction = store.livingFactions.find((lf: any) => lf.faction_id === f.id)
      if (liveFaction) {
        // 切换到天下大势面板查看
        store.togglePanel('factions')
      }
    }
  }
}

// ===== 关系矩阵视图 =====
function getMatrixClass(aId: string, bId: string): string {
  if (aId === bId) return 'matrix-self'
  const rel = getRelation(aId, bId)
  if (rel <= -20) return 'matrix-war'
  if (rel <= -10) return 'matrix-hostile'
  if (rel <= -5) return 'matrix-cool'
  if (rel <= 5) return 'matrix-neutral'
  if (rel <= 15) return 'matrix-friendly'
  return 'matrix-alliance'
}

function getMatrixIcon(aId: string, bId: string): string {
  if (aId === bId) return '●'
  const rel = getRelation(aId, bId)
  if (rel <= -20) return '⚔'
  if (rel <= -10) return '▲'
  if (rel <= -5) return '▽'
  if (rel <= 5) return '—'
  if (rel <= 15) return '○'
  return '◎'
}

function getMatrixTitle(aId: string, bId: string): string {
  if (aId === bId) return '本势力'
  const rel = getRelation(aId, bId)
  return getRelationLabel(rel) + ` (${rel > 0 ? '+' : ''}${rel})`
}

// ===== 生命周期 =====
onMounted(() => {
  initLayout()
  nextTick(() => {
    animFrameId = requestAnimationFrame(renderCanvas)
  })
})

onUnmounted(() => {
  if (animFrameId) cancelAnimationFrame(animFrameId)
})

watch(() => store.playerFactionId, () => {
  // 玩家势力改变时刷新
})
</script>

<style scoped>
.network-panel {
  position: fixed; top: 8%; left: 50%;
  transform: translateX(-50%);
  width: 700px; max-height: 80vh;
  z-index: 1000;
  display: flex; flex-direction: column;
  font-family: "STKaiti", "KaiTi", serif;
  color: #EAE3D6;
}
.fp-header {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 18px;
  border-bottom: 1px solid #443F38;
  background: rgba(0,0,0,0.3); flex-shrink: 0;
}
.fp-header h3 { margin: 0; font-size: 15px; color: #B89B68; letter-spacing: 2px; flex: 1; }
.fp-tabs { display: flex; gap: 4px; }
.fp-tabs button {
  padding: 4px 12px; font-size: 11px;
  background: transparent; border: 1px solid #443F38;
  color: #8A8276; cursor: pointer; border-radius: 3px;
  font-family: inherit; letter-spacing: 1px;
}
.fp-tabs button.active { background: rgba(184,155,104,0.15); border-color: #B89B68; color: #B89B68; }
.fp-close { border: none; background: none; color: #8A8276; cursor: pointer; font-size: 16px; padding: 4px; }
.fp-close:hover { color: #E07060; }
.fp-body { overflow: auto; flex: 1; }

.network-body { padding: 0; }
.network-canvas-wrap {
  position: relative; width: 100%; height: 440px;
  background: radial-gradient(ellipse at center, rgba(30,20,15,0.6) 0%, #0a0806 100%);
  overflow: hidden;
}
.network-canvas-wrap canvas { display: block; }

.network-tooltip {
  position: absolute; pointer-events: none;
  background: rgba(20,16,12,0.95); border: 1px solid #443F38;
  border-radius: 4px; padding: 10px 14px;
  min-width: 160px; z-index: 20;
  box-shadow: 0 4px 16px rgba(0,0,0,0.6);
}
.tt-name { font-size: 16px; font-weight: bold; letter-spacing: 3px; }
.tt-title { font-size: 11px; color: #8A8276; margin: 2px 0 6px; }
.tt-stats { display: flex; gap: 10px; font-size: 11px; color: #c0b090; margin-bottom: 6px; }
.tt-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 4px; }
.tt-tag { font-size: 9px; padding: 1px 6px; background: rgba(184,155,104,0.1); border: 1px solid rgba(184,155,104,0.2); border-radius: 2px; color: #B89B68; }
.tt-relation { font-size: 10px; color: #8A8276; margin-top: 4px; }

.network-legend {
  display: flex; justify-content: center; gap: 18px;
  padding: 10px; font-size: 11px; color: #8A8276;
  background: rgba(0,0,0,0.2);
}
.legend-item { display: flex; align-items: center; gap: 5px; }
.leg-line { display: inline-block; width: 24px; height: 2px; border-radius: 1px; }
.leg-war { background: #c43a3a; border-bottom: 2px dashed #c43a3a; }
.leg-hostile { background: #d47050; border-bottom: 1px dashed #d47050; }
.leg-neutral { background: #8c8068; }
.leg-friendly { background: #5b9a5a; }
.leg-alliance { background: #4a9a4a; height: 3px; }

/* 关系矩阵 */
.matrix-body { padding: 16px; }
.matrix-table-wrap { overflow-x: auto; }
.matrix-table { border-collapse: collapse; width: 100%; font-size: 19px; text-align: center; }
.matrix-table th, .matrix-table td {
  width: 40px; height: 36px;
  padding: 2px; border: 1px solid rgba(68,63,56,0.4);
}
.matrix-col-header, .matrix-row-header { font-size: 14px; font-weight: bold; letter-spacing: 2px; }
.matrix-self { background: rgba(184,155,104,0.1); }
.matrix-war { background: rgba(196,58,58,0.15); color: #c43a3a; }
.matrix-hostile { background: rgba(212,112,80,0.1); color: #d47050; }
.matrix-cool { background: rgba(160,128,96,0.06); color: #a08060; }
.matrix-neutral { color: #8c8068; }
.matrix-friendly { background: rgba(91,154,90,0.08); color: #5b9a5a; }
.matrix-alliance { background: rgba(74,154,74,0.12); color: #4a9a4a; }

/* scroll */
.fp-body::-webkit-scrollbar { width: 4px; }
.fp-body::-webkit-scrollbar-track { background: transparent; }
.fp-body::-webkit-scrollbar-thumb { background: #443F38; border-radius: 2px; }
</style>
