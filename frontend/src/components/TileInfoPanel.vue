<template>
  <div
    v-if="visible && tileDetail"
    class="tile-info-overlay"
  >
    <div class="tile-info-panel animate-slide-in" :style="panelStyle">
      <!-- 标题栏 -->
      <div class="tip-header" :style="{ borderColor: ownerColor }">
        <div class="tip-title-row">
          <span class="tip-icon">{{ terrainIcon(tileDetail.tile_type) }}</span>
          <h3 class="tip-title">{{ tileDetail.tile_name || tileInfo?.tile_name }}</h3>
          <span class="tip-type">{{ tileTypeName(tileDetail.tile_type) }}</span>
          <span v-if="isCapital" class="tip-capital">★都城</span>
          <span v-if="tileDetail.is_port" class="tip-badge port">⚓港口</span>
          <span v-if="tileDetail.is_pass" class="tip-badge pass">🏔关隘</span>
        </div>
        <button v-audio class="tip-close" @click="$emit('close')">✕</button>
      </div>

      <!-- 势力归属 -->
      <div class="tip-owner" v-if="owner">
        <span class="owner-dot" :style="{ background: ownerColor }"></span>
        <span class="owner-name" :style="{ color: ownerColor }">{{ owner.name }}</span>
        <span v-if="isOwnTile" class="owner-tag mine">己方领地</span>
        <span v-else-if="isEnemyTile" class="owner-tag enemy">敌方领土</span>
        <span v-else class="owner-tag neutral">中立地</span>
      </div>

      <!-- 行政区划 -->
      <div class="tip-admin" v-if="tileDetail.region">
        <span class="admin-item">{{ tileDetail.province }}</span>
        <span class="admin-sep">·</span>
        <span class="admin-item">{{ tileDetail.prefecture }}</span>
      </div>

      <!-- 数据网格 -->
      <div class="tip-stats-grid">
        <div class="tip-stat" v-if="tileDetail.population !== undefined">
          <span class="ts-label">人口</span>
          <span class="ts-value">{{ formatNum(tileDetail.population) }}</span>
        </div>
        <div class="tip-stat">
          <span class="ts-label">驻军</span>
          <span class="ts-value" :class="tileDetail.troops > 0 ? 'troop-text' : ''">{{ formatNum(tileDetail.troops) }}</span>
        </div>
        <div class="tip-stat">
          <span class="ts-label">粮草</span>
          <span class="ts-value grain-text">{{ formatNum(tileDetail.grain) }}</span>
        </div>
        <div class="tip-stat">
          <span class="ts-label">民心</span>
          <span class="ts-value" :class="getStatClass(tileDetail.morale)">{{ tileDetail.morale }}</span>
        </div>
        <div class="tip-stat">
          <span class="ts-label">城防</span>
          <span class="ts-value">Lv.{{ tileDetail.fortification }}</span>
        </div>
        <div class="tip-stat">
          <span class="ts-label">开发</span>
          <span class="ts-value">{{ getDevLevel(tileDetail) }}</span>
        </div>
        <div class="tip-stat" v-if="tileDetail.stable > 0">
          <span class="ts-label">马场</span>
          <span class="ts-value">Lv.{{ tileDetail.stable }}</span>
        </div>
        <div class="tip-stat" v-if="tileDetail.armory > 0">
          <span class="ts-label">武库</span>
          <span class="ts-value">Lv.{{ tileDetail.armory }}</span>
        </div>
      </div>

      <!-- 地形特性 -->
      <div class="tip-terrain-info">
        <span class="terrain-icon">{{ terrainIcon(tileDetail.tile_type) }}</span>
        <span class="terrain-name">{{ tileTypeName(tileDetail.tile_type) }}</span>
        <span class="terrain-bonus" v-if="tileDetail.defense_bonus">防御+{{ tileDetail.defense_bonus }}</span>
        <span class="terrain-bonus" v-if="tileDetail.movement_cost">行军消耗×{{ tileDetail.movement_cost }}0%</span>
      </div>

      <!-- 特殊标记 -->
      <div class="tip-badges" v-if="hasBadges">
        <span v-if="isCapital" class="tip-tag capital">★ 都城</span>
        <span v-if="tileDetail.is_port" class="tip-tag port">⚓ 港口</span>
        <span v-if="tileDetail.is_pass" class="tip-tag pass">🏔 关隘</span>
        <span v-if="tileDetail.is_ferry" class="tip-tag ferry">⛵ 渡口</span>
        <span v-if="tileDetail.is_coastal" class="tip-tag coastal">🌊 沿海</span>
        <span v-if="tileDetail.is_strategic" class="tip-tag strategic">🏰 战略要地</span>
        <span v-if="tileDetail.special_effect" class="tip-tag special">✨ {{ tileDetail.special_effect }}</span>
      </div>

      <!-- 灾害信息 -->
      <div class="tip-disasters" v-if="tileDetail.disasters && tileDetail.disasters.length > 0">
        <span class="disaster-icon">⚠</span>
        <span v-for="d in tileDetail.disasters" :key="d" class="disaster-tag">{{ disasterName(d) }}</span>
      </div>

      <!-- 围城状态 -->
      <div class="tip-siege" v-if="tileDetail.siege_state">
        <span class="siege-icon">🏰</span>
        <span class="siege-text">围城中：{{ tileDetail.siege_state }}</span>
      </div>

      <!-- ===== 可用操作 ===== -->
      <div class="tip-actions" v-if="availableActions.length > 0">
        <div class="tip-section-title">可用操作</div>
        <div class="tip-action-grid">
          <template v-for="action in visibleActions" :key="action.id">
            <button
              v-audio
              class="tip-action-btn"
              :class="action.class"
              :data-action="action.id"
              :disabled="action.disabled"
              @click="onAction(action)"
              :title="action.hint || ''"
            >
              <span class="ta-icon">{{ action.icon }}</span>
              <span class="ta-label">{{ action.label }}</span>
            </button>
          </template>
        </div>
      </div>

      <!-- 快捷跳转 -->
      <div class="tip-quick-links" v-if="isOwnTile">
        <button v-audio class="tip-quick-btn" @click="openPanel('recruit')">
          ⚔ 征兵所
        </button>
        <button v-audio class="tip-quick-btn" @click="openPanel('construction')">
          🏗 营造司
        </button>
        <button class="tip-quick-btn" @click="openPanel('military')">
          📋 军务处
        </button>
      </div>

      <!-- 右键提示 -->
      <div class="tip-context-hint" v-if="isOwnTile">
        👆 左键已选中 | 🖱 右键可快速行军至邻接地块
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'

const props = defineProps<{
  visible: boolean
  tileId: string
  /** 面板位置（从地图点击坐标算）*/
  position?: { x: number; y: number }
}>()

const emit = defineEmits<{
  close: []
  openPanel: [panel: string]
  openMarch: [tileId: string]
}>()

const store = useGameStore()

const tileDetail = ref<any>(null)
const owner = ref<any>(null)
const availableActions = ref<string[]>([])

// 计算面板位置
const panelStyle = computed(() => {
  if (!props.position) return {}
  // 面板约 400px 宽，尽量靠右但不超出屏幕
  const x = Math.min(props.position.x + 15, window.innerWidth - 420)
  const y = Math.min(props.position.y + 10, window.innerHeight - 600)
  return {
    left: x + 'px',
    top: y + 'px',
  }
})

const tileInfo = computed(() => {
  if (!props.tileId) return null
  return store.tiles[props.tileId] || null
})

const isOwnTile = computed(() => {
  return tileDetail.value?.faction_id === store.playerFactionId
})

const isEnemyTile = computed(() => {
  const fid = tileDetail.value?.faction_id
  return fid && fid !== store.playerFactionId
})

const isCapital = computed(() => {
  return tileDetail.value?.is_capital || (tileDetail.value?.tile_id === store.playerFaction?.capital_tile)
})

const ownerColor = computed(() => {
  if (!tileDetail.value?.faction_id) return '#8B7355'
  const f = store.factions[tileDetail.value.faction_id]
  return f?.color || '#8B7355'
})

const hasBadges = computed(() => {
  const t = tileDetail.value
  if (!t) return false
  return t.is_capital || t.is_port || t.is_pass || t.is_ferry || t.is_coastal || t.is_strategic || t.special_effect
})

// 监听 tileId 变化，加载地块详情
watch(() => props.tileId, async (newId) => {
  if (!newId) {
    tileDetail.value = null
    owner.value = null
    availableActions.value = []
    return
  }
  try {
    const result = await API.getTileDetail(newId)
    if (result?.tile) {
      tileDetail.value = result.tile
      owner.value = result.owner || null
      availableActions.value = result.available_actions || []
    }
  } catch {
    // 如果 API 不可用，使用 store 中的 tile 数据
    const localTile = store.tiles[newId]
    if (localTile) {
      tileDetail.value = localTile
      availableActions.value = []
    }
  }
}, { immediate: true })

// 监听 visible 重新加载
watch(() => props.visible, (val) => {
  if (val && props.tileId) {
    loadTileDetail()
  }
})

async function loadTileDetail() {
  if (!props.tileId) return
  try {
    const result = await API.getTileDetail(props.tileId)
    if (result?.tile) {
      tileDetail.value = result.tile
      owner.value = result.owner || null
      availableActions.value = result.available_actions || []
    }
  } catch {
    const localTile = store.tiles[props.tileId]
    if (localTile) {
      tileDetail.value = localTile
      availableActions.value = []
    }
  }
}

// ===== 可见操作列表 =====
interface TileAction {
  id: string
  icon: string
  label: string
  class: string
  disabled: boolean
  hint: string
}

const visibleActions = computed<TileAction[]>(() => {
  const actions: TileAction[] = []

  // 行军（己方→目标地块，或敌方/中立地块可出征）
  if (isOwnTile.value) {
    actions.push({
      id: 'march_from',
      icon: '⚔',
      label: '出兵征伐',
      class: 'action-march',
      disabled: (tileDetail.value?.troops || 0) <= 0,
      hint: '由此地出兵进攻邻接地块',
    })
  } else if (!isOwnTile.value) {
    // 非己方地块：查看是否可以从己方邻接地块行军至此
    const hasAdjacentOwn = props.tileId && hasOwnNeighbor(props.tileId)
    actions.push({
      id: 'march_to',
      icon: '🎯',
      label: '定为攻击目标',
      class: 'action-attack',
      disabled: !hasAdjacentOwn,
      hint: hasAdjacentOwn ? '从己方邻接地块出兵征伐' : '没有己方邻接地块可出征',
    })
  }

  // 征兵（仅己方）
  if (isOwnTile.value && canAction('recruit_troops')) {
    actions.push({
      id: 'recruit',
      icon: '🏋',
      label: '征兵',
      class: 'action-recruit',
      disabled: (tileDetail.value?.population || 0) < 100,
      hint: '从本地征募新兵（消耗人口与银两）',
    })
  }

  // 开发（仅己方可开发地块）
  if (isOwnTile.value && canAction('develop_land')) {
    actions.push({
      id: 'develop',
      icon: '🌾',
      label: '开发土地',
      class: 'action-develop',
      disabled: false,
      hint: '提升本地产出（消耗银两与人力）',
    })
  }

  // 筑城（仅己方）
  if (isOwnTile.value && canAction('fortify')) {
    actions.push({
      id: 'fortify',
      icon: '🏰',
      label: '加固城防',
      class: 'action-fortify',
      disabled: false,
      hint: '提升城墙等级（消耗银两与石材）',
    })
  }

  // 赈灾（仅己方）
  if (isOwnTile.value) {
    const hasDisaster = tileDetail.value?.disasters && tileDetail.value.disasters.length > 0
    actions.push({
      id: 'relief',
      icon: '🩹',
      label: '赈灾抚民',
      class: 'action-relief',
      disabled: !hasDisaster && (tileDetail.value?.morale || 50) > 60,
      hint: hasDisaster ? '赈济灾民，恢复民心' : '安抚百姓，提升民心',
    })
  }

  // 课税（仅己方）
  if (isOwnTile.value) {
    actions.push({
      id: 'tax',
      icon: '💰',
      label: '征收课税',
      class: 'action-tax',
      disabled: false,
      hint: '征收赋税（降低民心，增加库银）',
    })
  }

  // 派遣细作（己方→敌方）
  if (isEnemyTile.value) {
    actions.push({
      id: 'spy',
      icon: '🕵',
      label: '派遣细作',
      class: 'action-spy',
      disabled: false,
      hint: '向该势力派遣细作，获取情报',
    })
  }

  // 查看详情
  actions.push({
    id: 'view_detail',
    icon: '📋',
    label: '查看详情',
    class: 'action-detail',
    disabled: false,
    hint: '查看地块完整信息',
  })

  return actions
})

function canAction(action: string): boolean {
  return availableActions.value.includes(action)
}

function hasOwnNeighbor(tileId: string): boolean {
  return (store.tileNeighbors[tileId] || []).some(
    nid => store.tiles[nid]?.faction_id === store.playerFactionId
  )
}

// ===== 操作处理 =====

async function onAction(action: TileAction) {
  switch (action.id) {
    case 'march_from':
      // 设置该地块为出发地，打开行军面板
      store.marchTargetTileId = ''
      store.showMarchPanel = true
      // 短暂延迟后设置出发地（等 MarchPanel 初始化）
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('march-panel-set-from', {
          detail: { tileId: props.tileId }
        }))
      }, 100)
      emit('openMarch', props.tileId)
      break

    case 'march_to':
      // 设置该地块为攻击目标，打开行军面板
      store.marchTargetTileId = props.tileId
      store.showMarchPanel = true
      emit('openMarch', props.tileId)
      break

    case 'recruit':
      await submitTileCommand('recruit', {
        tile_id: props.tileId,
        faction_id: store.playerFactionId,
      })
      break

    case 'develop':
      await submitTileCommand('develop', {
        tile_id: props.tileId,
        faction_id: store.playerFactionId,
      })
      break

    case 'fortify':
      await submitTileCommand('fortify', {
        tile_id: props.tileId,
        faction_id: store.playerFactionId,
      })
      break

    case 'relief':
      await submitTileCommand('relief', {
        tile_id: props.tileId,
        faction_id: store.playerFactionId,
      })
      break

    case 'tax':
      await submitTileCommand('tax', {
        tile_id: props.tileId,
        faction_id: store.playerFactionId,
      })
      break

    case 'spy':
      if (tileDetail.value?.faction_id) {
        await store.deploySpy(tileDetail.value.faction_id)
      }
      break

    case 'view_detail':
      // 面板已展示详情，无需额外操作
      break
  }
}

async function submitTileCommand(action: string, params: Record<string, any>) {
  try {
    await store.submitCommand(action, params)
    const { showToast } = await import('@/services/api')
    const tileName = tileDetail.value?.tile_name || props.tileId
    const actionNames: Record<string, string> = {
      recruit: '征兵', develop: '开发', fortify: '筑城',
      relief: '赈灾', tax: '课税', build: '建造',
      train_troops: '训练',
    }
    const actionName = actionNames[action] || action
    showToast(`【${tileName}】${actionName}指令已提交，请推进月份执行`, 'info')
  } catch (e: any) {
    // 错误由 API 层处理
    console.warn('地块指令提交失败:', e)
  }
}

function openPanel(panel: string) {
  emit('openPanel', panel)
  // 选中该地块供面板使用
  store.selectTile(props.tileId)
}

// ===== 辅助函数 =====

function formatNum(n: number | undefined | null): string {
  if (n == null) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function getStatClass(v: number): string {
  if (v >= 70) return 'good-text'
  if (v >= 40) return 'warn-text'
  return 'danger-text'
}

const TILE_TYPE_NAMES: Record<string, string> = {
  farmland: '农田', mountain: '山地', water: '水域', coast: '海岸',
  city: '城池', pass: '关隘', port: '港口', desert: '漠地', grassland: '草原',
}
function tileTypeName(t: string): string {
  return TILE_TYPE_NAMES[t] || t || '未知'
}

function terrainIcon(t: string): string {
  const icons: Record<string, string> = {
    farmland: '🌾', mountain: '⛰', water: '🌊', coast: '🏖',
    city: '🏘', pass: '🏔', port: '⚓', desert: '🏜', grassland: '🟩',
  }
  return icons[t] || '🗺'
}

function disasterName(d: string): string {
  const names: Record<string, string> = {
    flood: '洪水', drought: '旱灾', locust: '蝗灾', plague: '瘟疫',
    war_devastation: '战乱', rebellion: '叛乱', famine: '饥荒',
  }
  return names[d] || d
}

function getDevLevel(tile: any): string {
  // 基于各设施等级估算开发度
  const levels = [
    tile.granary || 0,
    tile.stable || 0,
    tile.armory || 0,
    tile.clinic || 0,
    tile.water_works || 0,
    tile.fortification || 0,
  ]
  const avg = levels.length > 0 ? levels.reduce((a: number, b: number) => a + b, 0) / levels.length : 0
  if (avg >= 4) return '繁华'
  if (avg >= 2) return '普通'
  return '偏远'
}
</script>

<style scoped>
/* ===== 遮罩与面板定位 ===== */
.tile-info-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  pointer-events: none;
}

.tile-info-panel {
  position: absolute;
  width: 380px;
  max-height: 75vh;
  overflow-y: auto;
  background: linear-gradient(180deg, rgba(30, 25, 18, 0.97) 0%, rgba(20, 16, 12, 0.98) 100%);
  border: 1px solid rgba(139, 115, 85, 0.4);
  border-radius: 4px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 20px rgba(139, 115, 85, 0.1);
  font-family: "SimSun", "FangSong", serif;
  pointer-events: all;
  backdrop-filter: blur(8px);
}

.tile-info-panel::-webkit-scrollbar {
  width: 4px;
}
.tile-info-panel::-webkit-scrollbar-thumb {
  background: rgba(139, 115, 85, 0.25);
  border-radius: 2px;
}

/* ===== 标题栏 ===== */
.tip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(139, 115, 85, 0.25);
  background: rgba(139, 115, 85, 0.08);
  border-left: 3px solid #8B7355;
}

.tip-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.tip-icon { font-size: 18px; }
.tip-title {
  font-size: 16px;
  font-weight: bold;
  color: #E8D5A3;
  letter-spacing: 2px;
  margin: 0;
  font-family: "STKaiti", "KaiTi", serif;
}
.tip-type {
  font-size: 11px;
  color: #8B7355;
  background: rgba(139, 115, 85, 0.12);
  padding: 1px 6px;
  border-radius: 2px;
}
.tip-capital {
  font-size: 11px;
  color: #FFD700;
  font-weight: bold;
}
.tip-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 2px;
}
.tip-badge.port { color: #5B9ECF; background: rgba(91, 158, 207, 0.12); }
.tip-badge.pass { color: #8B7355; background: rgba(139, 115, 85, 0.12); }

.tip-close {
  width: 24px; height: 24px;
  border: 1px solid rgba(139, 115, 85, 0.2);
  background: rgba(0, 0, 0, 0.2);
  color: #8B7355;
  font-size: 14px;
  cursor: pointer;
  border-radius: 2px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
}
.tip-close:hover { color: #C94040; border-color: #C94040; }

/* ===== 势力归属 ===== */
.tip-owner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px 4px;
}
.owner-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
}
.owner-name {
  font-size: 14px;
  font-weight: bold;
  letter-spacing: 1px;
}
.owner-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 2px;
  margin-left: auto;
}
.owner-tag.mine { color: #81C784; background: rgba(129, 199, 132, 0.12); }
.owner-tag.enemy { color: #EF5350; background: rgba(239, 83, 80, 0.12); }
.owner-tag.neutral { color: #8B7355; background: rgba(139, 115, 85, 0.12); }

/* ===== 区划 ===== */
.tip-admin {
  padding: 0 14px 4px;
  font-size: 11px;
  color: #6B5B4A;
  letter-spacing: 1px;
}
.admin-sep { margin: 0 4px; }

/* ===== 数据网格 ===== */
.tip-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  margin: 8px 12px;
  background: rgba(139, 115, 85, 0.1);
  border-radius: 3px;
  overflow: hidden;
}
.tip-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  background: rgba(20, 16, 12, 0.5);
  gap: 2px;
}
.ts-label { font-size: 10px; color: #6B5B4A; }
.ts-value { font-size: 14px; font-weight: bold; color: #D4C490; }

/* ===== 地形信息 ===== */
.tip-terrain-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px;
  font-size: 11px;
}
.terrain-icon { font-size: 14px; }
.terrain-name { color: #8B7355; font-weight: bold; }
.terrain-bonus {
  font-size: 10px;
  color: #6B5B4A;
  background: rgba(139, 115, 85, 0.1);
  padding: 1px 5px;
  border-radius: 2px;
}

/* ===== 特殊标记 ===== */
.tip-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px 14px;
}
.tip-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 2px;
}
.tip-tag.capital   { background: rgba(200, 168, 74, 0.15); color: #C8A84A; }
.tip-tag.port      { background: rgba(91, 158, 207, 0.12); color: #5B9ECF; }
.tip-tag.pass      { background: rgba(139, 115, 85, 0.12); color: #8B7355; }
.tip-tag.ferry     { background: rgba(106, 122, 138, 0.12); color: #6B7A8A; }
.tip-tag.coastal   { background: rgba(122, 138, 130, 0.12); color: #7A8A82; }
.tip-tag.strategic { background: rgba(210, 160, 80, 0.12); color: #D2A050; }
.tip-tag.special   { background: rgba(180, 130, 200, 0.12); color: #B482C8; }

/* ===== 灾害 ===== */
.tip-disasters {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 14px;
  flex-wrap: wrap;
}
.disaster-icon { font-size: 13px; }
.disaster-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: rgba(239, 83, 80, 0.12);
  color: #EF5350;
  border-radius: 2px;
}

/* ===== 围城 ===== */
.tip-siege {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  margin: 4px 12px;
  background: rgba(239, 83, 80, 0.08);
  border: 1px solid rgba(239, 83, 80, 0.2);
  border-radius: 3px;
}
.siege-icon { font-size: 16px; }
.siege-text { font-size: 12px; color: #EF5350; }

/* ===== 可用操作区 ===== */
.tip-section-title {
  font-size: 12px;
  color: #C9A94E;
  letter-spacing: 2px;
  padding: 10px 14px 6px;
  border-top: 1px solid rgba(139, 115, 85, 0.15);
  font-weight: bold;
}

.tip-action-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px;
  padding: 0 12px 8px;
}

.tip-action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  background: rgba(44, 36, 22, 0.5);
  border: 1px solid rgba(139, 115, 85, 0.2);
  color: #D4C490;
  font-size: 12px;
  font-family: "SimSun", serif;
  letter-spacing: 1px;
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s;
}

.tip-action-btn:hover:not(:disabled) {
  background: rgba(201, 169, 78, 0.1);
  border-color: rgba(201, 169, 78, 0.3);
  color: #E8D5A3;
}

.tip-action-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.ta-icon { font-size: 14px; flex-shrink: 0; }
.ta-label { letter-spacing: 1px; }

/* 操作类型配色 */
.action-march { border-left: 2px solid #E53935; }
.action-attack { border-left: 2px solid #FF5722; }
.action-recruit { border-left: 2px solid #4A90D9; }
.action-develop { border-left: 2px solid #81C784; }
.action-fortify { border-left: 2px solid #8B7355; }
.action-relief { border-left: 2px solid #66BB6A; }
.action-tax { border-left: 2px solid #FFB74D; }
.action-spy { border-left: 2px solid #AB47BC; }
.action-detail { border-left: 2px solid #C9A94E; }

/* ===== 快捷跳转 ===== */
.tip-quick-links {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  border-top: 1px solid rgba(139, 115, 85, 0.15);
}
.tip-quick-btn {
  flex: 1;
  padding: 6px 8px;
  font-size: 11px;
  font-family: "SimSun", serif;
  background: rgba(139, 115, 85, 0.1);
  border: 1px solid rgba(139, 115, 85, 0.2);
  color: #8B7355;
  cursor: pointer;
  border-radius: 2px;
  letter-spacing: 1px;
  transition: all 0.15s;
}
.tip-quick-btn:hover {
  background: rgba(201, 169, 78, 0.12);
  border-color: rgba(201, 169, 78, 0.3);
  color: #C9A94E;
}

/* ===== 操作提示 ===== */
.tip-context-hint {
  padding: 6px 12px 8px;
  font-size: 10px;
  color: #4B3B2B;
  text-align: center;
  letter-spacing: 1px;
  border-top: 1px dotted rgba(139, 115, 85, 0.1);
}

/* ===== 文本颜色 ===== */
.troop-text { color: #EF5350; }
.grain-text { color: #81C784; }
.good-text { color: #81C784; }
.warn-text { color: #FFB74D; }
.danger-text { color: #EF5350; }

/* ===== 动画 ===== */
.animate-slide-in {
  animation: tileSlideIn 0.2s ease-out;
}
@keyframes tileSlideIn {
  from { opacity: 0; transform: translateX(-10px) scale(0.97); }
  to { opacity: 1; transform: translateX(0) scale(1); }
}
</style>
