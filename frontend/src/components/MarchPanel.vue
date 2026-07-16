<template>
  <div
    v-if="visible"
    class="march-overlay"
    @click.self="$emit('close')"
  >
    <div class="march-panel animate-fade-in artifact-panel artifact-dispatch">
      <!-- 标题栏 -->
      <div class="mp-header">
        <div class="mp-title-row">
          <span class="mp-icon">⚔</span>
          <h3 class="mp-title">出兵征伐</h3>
          <span class="mp-subtitle">— 调兵遣将，运筹帷幄 —</span>
        </div>
        <button v-audio class="mp-close" @click="$emit('close')">✕</button>
      </div>

      <div class="mp-body">
        <!-- ===== 第1步：选择出发地 ===== -->
        <div class="mp-section">
          <div class="mp-section-header">
            <span class="mp-step-badge">1</span>
            <span class="mp-section-title">选择出发地</span>
            <span class="mp-section-hint">— 点击地图上己方城池或从下方列表选择</span>
          </div>

          <!-- 地图点击提示 -->
          <div v-if="!marchConfig.fromTile" class="mp-select-hint">
            <span class="hint-icon">👆</span>
            请在地图上<span class="hint-em">左键点击</span>一个己方城池作为出发地
          </div>

          <!-- 已选出发地卡片 -->
          <div v-if="fromTileData" class="mp-tile-card from-tile">
            <div class="mtc-top">
              <span class="mtc-name">{{ fromTileData.tile_name }}</span>
              <span class="mtc-type">{{ tileTypeName(fromTileData.tile_type) }}</span>
              <span v-if="fromTileData.is_capital" class="mtc-capital">★都城</span>
            </div>
            <div class="mtc-stats">
              <div class="mtc-stat">
                <span class="mtc-sl">驻军</span>
                <span class="mtc-sv troop-text">{{ formatNum(fromTileData.troops) }}</span>
              </div>
              <div class="mtc-stat">
                <span class="mtc-sl">粮草</span>
                <span class="mtc-sv grain-text">{{ formatNum(fromTileData.grain) }}</span>
              </div>
              <div class="mtc-stat">
                <span class="mtc-sl">民心</span>
                <span class="mtc-sv" :class="getStatClass(fromTileData.morale)">{{ fromTileData.morale }}</span>
              </div>
              <div class="mtc-stat">
                <span class="mtc-sl">城防</span>
                <span class="mtc-sv">Lv.{{ fromTileData.fortification }}</span>
              </div>
            </div>
            <button v-audio class="mtc-change-btn" @click="marchConfig.fromTile = ''">更换出发地</button>
          </div>

          <!-- 己方城池快捷列表 -->
          <div v-if="!marchConfig.fromTile" class="mp-tile-list">
            <div
              v-for="t in playerTilesWithTroops"
              :key="t.tile_id"
              class="mp-tile-option"
              :class="{ selected: marchConfig.fromTile === t.tile_id }"
              @click="selectFromTile(t.tile_id)"
            >
              <div class="mto-header">
                <span class="mto-name">{{ t.tile_name }}</span>
                <span v-if="t.is_capital" class="mto-capital">★</span>
                <span class="mto-type">{{ tileTypeName(t.tile_type) }}</span>
              </div>
              <div class="mto-stats">
                <span class="mto-stat">⚔ {{ formatNum(t.troops) }}兵</span>
                <span class="mto-stat">🌾 {{ formatNum(t.grain) }}粮</span>
                <span class="mto-stat" :class="t.morale < 30 ? 'danger-text' : ''">❤ {{ t.morale }}民心</span>
              </div>
            </div>
            <div v-if="playerTilesWithTroops.length === 0" class="mp-empty">
              无可出征的城池（所有城池无驻军）
            </div>
          </div>
        </div>

        <!-- ===== 第2步：选择进攻目标 ===== -->
        <div class="mp-section">
          <div class="mp-section-header">
            <span class="mp-step-badge">2</span>
            <span class="mp-section-title">选择进攻目标</span>
            <span class="mp-section-hint">— 左键点击地图上敌方/中立的相邻地块</span>
          </div>

          <div v-if="!marchConfig.toTile && attackableNeighbors.length === 0 && !neighborLoading" class="mp-select-hint">
            <span class="hint-icon">🎯</span>
            请在地图上<span class="hint-em">左键点击</span>目标地块，或从下方邻接列表中选择
          </div>

          <!-- 已选目标卡片 -->
          <div v-if="toTileData" class="mp-tile-card to-tile">
            <div class="mtc-top">
              <span class="mtc-name">{{ toTileData.tile_name }}</span>
              <span class="mtc-type">{{ tileTypeName(toTileData.tile_type) }}</span>
              <span v-if="toTileData.faction_id" class="mtc-owner" :style="{ color: getFactionColor(toTileData.faction_id) }">
                {{ getFactionName(toTileData.faction_id) }}
              </span>
              <span v-else class="mtc-owner neutral">中立</span>
            </div>
            <div class="mtc-stats">
              <div class="mtc-stat">
                <span class="mtc-sl">驻军</span>
                <span class="mtc-sv danger-text">{{ formatNum(toTileData.troops) }}</span>
              </div>
              <div class="mtc-stat">
                <span class="mtc-sl">城防</span>
                <span class="mtc-sv">Lv.{{ toTileData.fortification }}</span>
              </div>
              <div class="mtc-stat">
                <span class="mtc-sl">民心</span>
                <span class="mtc-sv">{{ toTileData.morale }}</span>
              </div>
              <div class="mtc-stat">
                <span class="mtc-sl">地形</span>
                <span class="mtc-sv terrain-badge" :class="'terrain-' + toTileData.tile_type">{{ tileTypeName(toTileData.tile_type) }}</span>
              </div>
            </div>
            <button v-audio class="mtc-change-btn" @click="marchConfig.toTile = ''">更换目标</button>
          </div>

          <!-- 邻接地块列表 -->
          <div v-if="marchConfig.fromTile" class="mp-tile-list">
            <div v-if="neighborLoading" class="mp-loading">正在搜索可攻击目标...</div>
            <div
              v-for="n in attackableNeighbors"
              :key="n.tile_id"
              class="mp-tile-option"
              :class="{ selected: marchConfig.toTile === n.tile_id }"
              @click="selectToTile(n.tile_id)"
            >
              <div class="mto-header">
                <span class="mto-name">{{ n.tile_name }}</span>
                <span v-if="n.faction_id" class="mto-owner-tag" :style="{ color: getFactionColor(n.faction_id), borderColor: getFactionColor(n.faction_id) }">
                  {{ getFactionName(n.faction_id) }}
                </span>
                <span v-else class="mto-owner-tag neutral">中立</span>
              </div>
              <div class="mto-stats">
                <span class="mto-stat">⚔ {{ formatNum(n.troops) }}守军</span>
                <span class="mto-stat">🏰 城防{{ n.fortification }}级</span>
                <span class="mto-stat terrain-label" :class="'terrain-' + n.tile_type">{{ tileTypeName(n.tile_type) }}</span>
              </div>
            </div>
            <div v-if="!neighborLoading && attackableNeighbors.length === 0" class="mp-empty">
              周围无可攻击目标（所有邻接地块均为己方领地或不可通行）
            </div>
          </div>
        </div>

        <!-- ===== 第3步：兵力与粮草配置 ===== -->
        <div class="mp-section" v-if="marchConfig.fromTile && marchConfig.toTile">
          <div class="mp-section-header">
            <span class="mp-step-badge">3</span>
            <span class="mp-section-title">兵力与粮草</span>
            <span class="mp-section-hint">— 调配出征兵力与随军粮草</span>
          </div>

          <!-- 兵力滑块 -->
          <div class="mp-config-row">
            <div class="mcr-label">
              <span class="mcr-icon">⚔</span>
              <span>出征兵力</span>
            </div>
            <div class="mcr-control">
              <input
                type="range"
                class="mp-slider"
                :min="minTroops"
                :max="maxTroops"
                :step="sliderStep"
                v-model.number="marchConfig.troops"
                @input="onTroopsChange"
              />
              <div class="mcr-value-row">
                <input
                  type="number"
                  class="mp-number-input"
                  :min="minTroops"
                  :max="maxTroops"
                  v-model.number="marchConfig.troops"
                  @input="onTroopsInput"
                />
                <span class="mcr-unit">人</span>
                <span class="mcr-range">/ {{ formatNum(maxTroops) }}可调遣</span>
              </div>
            </div>
          </div>

          <!-- 兵力快捷按钮 -->
          <div class="mp-quick-btns">
            <button
              v-for="ratio in troopRatios"
              :key="ratio.label"
              v-audio class="mp-quick-btn"
              :class="{ active: marchConfig.troops === ratio.value }"
              @click="setTroopsRatio(ratio)"
            >
              {{ ratio.label }}
            </button>
          </div>

          <!-- 兵力配置详情 -->
          <div class="mp-troops-detail" v-if="marchConfig.troops > 0">
            <div class="mtd-item">
              <span class="mtd-label">精锐兵</span>
              <span class="mtd-value">{{ eliteTroops }}</span>
              <span class="mtd-sub">（精锐比例 {{ eliteRatio }}%）</span>
            </div>
            <div class="mtd-item">
              <span class="mtd-label">骑兵</span>
              <span class="mtd-value">{{ cavalryTroops }}</span>
              <span class="mtd-sub" v-if="(fromTileData?.stable ?? 0) > 0">（马场Lv.{{ fromTileData?.stable ?? 0 }}）</span>
              <span class="mtd-sub" v-else>（无马场，不可出征骑兵）</span>
            </div>
            <div class="mtd-item">
              <span class="mtd-label">留守兵力</span>
              <span class="mtd-value">{{ remainingTroops }}</span>
              <span class="mtd-sub">（出征后出发地剩余）</span>
            </div>
          </div>

          <!-- 粮草配置 -->
          <div class="mp-config-row">
            <div class="mcr-label">
              <span class="mcr-icon">🌾</span>
              <span>随军粮草</span>
            </div>
            <div class="mcr-control">
              <input
                type="range"
                class="mp-slider grain-slider"
                :min="minGrain"
                :max="maxGrain"
                :step="Math.max(1, Math.floor(maxGrain / 100))"
                v-model.number="marchConfig.grain"
              />
              <div class="mcr-value-row">
                <input
                  type="number"
                  class="mp-number-input"
                  :min="minGrain"
                  :max="maxGrain"
                  v-model.number="marchConfig.grain"
                />
                <span class="mcr-unit">石</span>
                <span class="mcr-range">/ {{ formatNum(maxGrain) }}可用</span>
              </div>
            </div>
          </div>

          <!-- 粮草预估 -->
          <div class="mp-grain-info">
            <div class="mgi-row">
              <span class="mgi-label">预估消耗</span>
              <span class="mgi-value grain-text">{{ estimatedGrainCost }}石</span>
              <span class="mgi-note">（{{ pathInfo?.turns_required || 1 }}回合行军）</span>
            </div>
            <div class="mgi-row">
              <span class="mgi-label">可维持</span>
              <span class="mgi-value" :class="sustainClass">{{ sustainRounds }}回合</span>
              <span class="mgi-note">（含围城消耗）</span>
            </div>
            <div class="mgi-warning" v-if="marchConfig.grain < estimatedGrainCost">
              ⚠ 粮草不足以支撑行军至目标！请增加粮草或减少兵力。
            </div>
          </div>
        </div>

        <!-- ===== 行军预览 ===== -->
        <div class="mp-section" v-if="marchConfig.fromTile && marchConfig.toTile">
          <div class="mp-section-header">
            <span class="mp-step-badge">→</span>
            <span class="mp-section-title">行军预览</span>
          </div>
          <div class="mp-path-preview">
            <div class="mpp-from">
              <span class="mpp-dot from"></span>
              <span>{{ fromTileData?.tile_name || marchConfig.fromTile }}</span>
            </div>
            <div class="mpp-arrow">
              <span class="mpp-line"></span>
              <span class="mpp-dist">{{ pathInfo?.steps || '?' }}步</span>
            </div>
            <div class="mpp-to">
              <span class="mpp-dot to"></span>
              <span>{{ toTileData?.tile_name || marchConfig.toTile }}</span>
            </div>
          </div>
          <div class="mp-path-info">
            <span>地形系数：{{ terrainMultiplier }}x</span>
            <span>预计回合：{{ pathInfo?.turns_required || 1 }}</span>
            <span>路程消耗：{{ pathInfo?.total_cost || 0 }}</span>
          </div>
        </div>

        <!-- ===== 消耗与收益总览 ===== -->
        <div class="mp-section" v-if="marchConfig.fromTile && marchConfig.toTile && marchConfig.troops > 0">
          <div class="mp-section-header">
            <span class="mp-step-badge">📋</span>
            <span class="mp-section-title">消耗与收益预估</span>
            <span class="mp-section-hint">— 出征所需与战后所得</span>
          </div>
          <div class="mp-cost-benefit">
            <!-- 消耗栏 -->
            <div class="mcb-column mcb-cost">
              <div class="mcb-col-title">📤 消耗</div>
              <div class="mcb-row">
                <span class="mcb-label">出征兵力</span>
                <span class="mcb-value danger-text">-{{ formatNum(marchConfig.troops) }}人</span>
              </div>
              <div class="mcb-row">
                <span class="mcb-label">随军粮草</span>
                <span class="mcb-value grain-text">-{{ formatNum(marchConfig.grain) }}石</span>
              </div>
              <div class="mcb-row">
                <span class="mcb-label">预估路途粮耗</span>
                <span class="mcb-value grain-text">~{{ estimatedGrainCost }}石</span>
              </div>
              <div class="mcb-row">
                <span class="mcb-label">出发地留守兵力</span>
                <span class="mcb-value">{{ formatNum(remainingTroops) }}人</span>
              </div>
            </div>
            <!-- 分隔 -->
            <div class="mcb-divider">
              <span class="mcb-arrow">→</span>
            </div>
            <!-- 收益栏 -->
            <div class="mcb-column mcb-gain">
              <div class="mcb-col-title">📥 可能收益</div>
              <div class="mcb-row">
                <span class="mcb-label">占领地块</span>
                <span class="mcb-value good-text">{{ toTileData?.tile_name || '目标' }}</span>
              </div>
              <div class="mcb-row" v-if="toTileData?.is_capital">
                <span class="mcb-label">攻占都城缴获</span>
                <span class="mcb-value gold-text">银500两+粮1000石</span>
              </div>
              <div class="mcb-row">
                <span class="mcb-label">战后剩余兵力</span>
                <span class="mcb-value">视战斗而定</span>
              </div>
              <div class="mcb-row">
                <span class="mcb-label">可能俘虏敌将</span>
                <span class="mcb-value" v-if="toTileData?.faction_id">概率25%</span>
                <span class="mcb-value" v-else>中立地块无俘虏</span>
              </div>
              <div class="mcb-row">
                <span class="mcb-label">声望变化</span>
                <span class="mcb-value" :class="toTileData?.faction_id ? 'danger-text' : ''">
                  {{ toTileData?.faction_id ? '对外宣战-声望' : '扩张领土+声望' }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- ===== 操作按钮 ===== -->
        <div class="mp-actions" v-if="marchConfig.fromTile && marchConfig.toTile">
          <button v-audio class="mp-btn mp-btn-secondary" @click="onPreviewMarch">
            👁 预览行军路线
          </button>
          <button
            v-audio class="mp-btn mp-btn-primary"
            :disabled="!canMarch"
            @click="onConfirmMarch"
          >
            ⚔ 颁布出征敕令
          </button>
        </div>
      </div>

      <!-- 底部资源总览 -->
      <div class="mp-footer">
        <div class="mpf-item">
          <span class="mpf-icon">⚔</span>
          <span class="mpf-label">可调遣</span>
          <span class="mpf-value">{{ formatNum(maxTroops) }}人</span>
        </div>
        <div class="mpf-item">
          <span class="mpf-icon">🌾</span>
          <span class="mpf-label">出发地粮</span>
          <span class="mpf-value">{{ formatNum(fromTileData?.grain) }}石</span>
        </div>
        <div class="mpf-item">
          <span class="mpf-icon">💰</span>
          <span class="mpf-label">国库</span>
          <span class="mpf-value">{{ formatNum(playerFaction?.treasury) }}两</span>
        </div>
        <div class="mpf-item">
          <span class="mpf-icon">⚔</span>
          <span class="mpf-label">总兵力</span>
          <span class="mpf-value">{{ formatNum(store.totalTroops) }}人</span>
        </div>
        <div class="mpf-item">
          <span class="mpf-icon">🐴</span>
          <span class="mpf-label">战马</span>
          <span class="mpf-value">{{ formatNum(playerFaction?.horses) }}</span>
        </div>
      </div>
      <div class="mp-footer-hint" v-if="marchConfig.fromTile">
        ※ 出征消耗出发地粮草与兵力，不从国库直接扣除
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
  targetTileId?: string   // 预选目标地块（从右键菜单传入）
}>()

const emit = defineEmits<{
  close: []
  marchConfirm: [config: MarchConfig]
}>()

const store = useGameStore()

// ===== 出征配置 =====
export interface MarchConfig {
  fromTile: string
  toTile: string
  troops: number
  grain: number
}

const marchConfig = ref<MarchConfig>({
  fromTile: '',
  toTile: '',
  troops: 0,
  grain: 0,
})

const neighborLoading = ref(false)
const attackableNeighbors = ref<any[]>([])
const pathInfo = ref<any>(null)

// ===== 监听面板打开/关闭 =====
watch(() => props.visible, (val) => {
  if (val) {
    // 打开面板时初始化
    marchConfig.value = {
      fromTile: store.playerFaction?.capital_tile || '',
      toTile: props.targetTileId || '',
      troops: 0,
      grain: 0,
    }
    // 默认兵力设为最大可调遣的50%
    if (marchConfig.value.fromTile) {
      const fromData = store.tiles[marchConfig.value.fromTile]
      if (fromData) {
        marchConfig.value.troops = Math.max(50, Math.floor(fromData.troops * 0.5))
        marchConfig.value.grain = Math.floor(fromData.grain * 0.3)
      }
    }
    // 加载邻接目标（无论是否已有预选目标，都加载列表供用户切换）
    if (marchConfig.value.fromTile) {
      loadNeighbors()
    }
    // 如果已有预选目标，加载路径信息
    if (marchConfig.value.fromTile && marchConfig.value.toTile) {
      loadPathInfo()
    }
    // 注册地图点击监听
    window.addEventListener('march-panel-select-tile', onMapTileSelect as any)
    // 注册外部设置出发地监听（TileInfoPanel / 右键菜单）
    window.addEventListener('march-panel-set-from', onSetFromTile as any)
  } else {
    window.removeEventListener('march-panel-select-tile', onMapTileSelect as any)
    window.removeEventListener('march-panel-set-from', onSetFromTile as any)
  }
})

onUnmounted(() => {
  window.removeEventListener('march-panel-select-tile', onMapTileSelect as any)
  window.removeEventListener('march-panel-set-from', onSetFromTile as any)
})

// ===== 外部设置出发地事件 =====
function onSetFromTile(e: CustomEvent) {
  const { tileId } = e.detail
  if (tileId) selectFromTile(tileId)
}

// ===== 地图点击事件处理 =====
function onMapTileSelect(e: CustomEvent) {
  const { tileId } = e.detail
  const tile = store.tiles[tileId]
  if (!tile) return

  // 判断点击的是己方还是敌方地块
  if (tile.faction_id === store.playerFactionId) {
    // 点击己方地块 → 设为出发地
    selectFromTile(tileId)
  } else if (marchConfig.value.fromTile) {
    // 已选出发地，点击其他地块 → 尝试设为进攻目标
    selectToTile(tileId)
  }
}

// ===== 出发地相关 =====
const playerTilesWithTroops = computed(() => {
  return store.playerTiles
    .filter(t => t.troops > 0)
    .sort((a, b) => b.troops - a.troops)
})

const fromTileData = computed(() => {
  if (!marchConfig.value.fromTile) return null
  return store.tiles[marchConfig.value.fromTile] || null
})

function selectFromTile(tileId: string) {
  marchConfig.value.fromTile = tileId
  marchConfig.value.toTile = ''
  marchConfig.value.troops = 0
  marchConfig.value.grain = 0
  pathInfo.value = null

  const fromData = store.tiles[tileId]
  if (fromData) {
    marchConfig.value.troops = Math.max(50, Math.floor(fromData.troops * 0.5))
    marchConfig.value.grain = Math.floor(fromData.grain * 0.3)
  }
  loadNeighbors()
}

// ===== 进攻目标相关 =====
const toTileData = computed(() => {
  if (!marchConfig.value.toTile) return null
  return store.tiles[marchConfig.value.toTile] || null
})

async function loadNeighbors() {
  if (!marchConfig.value.fromTile) return
  neighborLoading.value = true
  try {
    const result = await API.getMarchNeighbors(
      marchConfig.value.fromTile,
      store.playerFactionId,
    )
    attackableNeighbors.value = result.neighbors || []
  } catch {
    console.warn('加载邻接关系失败')
    attackableNeighbors.value = []
  } finally {
    neighborLoading.value = false
  }
}

function selectToTile(tileId: string) {
  marchConfig.value.toTile = tileId
  // 根据目标守军调整兵力建议
  const toData = store.tiles[tileId]
  if (toData && fromTileData.value) {
    const suggested = Math.max(50, Math.floor(toData.troops * 1.5))
    marchConfig.value.troops = Math.min(suggested, fromTileData.value.troops)
    marchConfig.value.grain = Math.floor(fromTileData.value.grain * 0.3)
  }
  loadPathInfo()
}

// ===== 行军路径信息 =====
async function loadPathInfo() {
  if (!marchConfig.value.fromTile || !marchConfig.value.toTile) return
  try {
    const result = await API.getMarchPath({
      from_tile: marchConfig.value.fromTile,
      to_tile: marchConfig.value.toTile,
      troops: marchConfig.value.troops || 100,
    })
    pathInfo.value = result
  } catch {
    pathInfo.value = { turns_required: 1, steps: 1, total_cost: 0, grain_cost_estimate: 0 }
  }
}

watch(() => marchConfig.value.toTile, () => {
  if (marchConfig.value.toTile) loadPathInfo()
})

// ===== 兵力配置 =====
const minTroops = computed(() => 50)
const maxTroops = computed(() => fromTileData.value?.troops || 0)
const sliderStep = computed(() => Math.max(1, Math.floor(maxTroops.value / 200)))

const eliteRatio = computed(() => {
  if (!fromTileData.value) return 0
  const baseRatio = 10
  const armoryBonus = (fromTileData.value.armory || 0) * 10
  return Math.min(50, baseRatio + armoryBonus)
})

const eliteTroops = computed(() => {
  return Math.floor(marchConfig.value.troops * eliteRatio.value / 100)
})

const cavalryTroops = computed(() => {
  if (!fromTileData.value || !fromTileData.value.stable || fromTileData.value.stable <= 0) return 0
  const maxCav = Math.floor(marchConfig.value.troops * 0.2)
  const horseLimit = store.playerFaction?.horses || 0
  return Math.min(maxCav, horseLimit)
})

const remainingTroops = computed(() => {
  return Math.max(0, (fromTileData.value?.troops || 0) - marchConfig.value.troops)
})

const troopRatios = computed(() => {
  const max = maxTroops.value
  return [
    { label: '1/4', value: Math.floor(max * 0.25) },
    { label: '1/2', value: Math.floor(max * 0.5) },
    { label: '3/4', value: Math.floor(max * 0.75) },
    { label: '全部', value: max },
  ]
})

function setTroopsRatio(ratio: { label: string; value: number }) {
  marchConfig.value.troops = Math.max(50, ratio.value)
}

function onTroopsChange() {
  // 拖动滑块时自动调整粮草
  if (fromTileData.value) {
    const grainRatio = marchConfig.value.troops / Math.max(1, fromTileData.value.troops)
    marchConfig.value.grain = Math.floor(fromTileData.value.grain * grainRatio * 0.5)
  }
}

function onTroopsInput() {
  marchConfig.value.troops = Math.max(minTroops.value, Math.min(maxTroops.value, marchConfig.value.troops || 0))
  onTroopsChange()
}

// ===== 粮草配置 =====
const minGrain = computed(() => 0)
const maxGrain = computed(() => fromTileData.value?.grain || 0)

const terrainMultiplier = computed(() => {
  const t = toTileData.value
  if (!t) return 1.0
  const mults: Record<string, number> = { mountain: 2.0, water: 1.5, desert: 1.3, grassland: 0.9 }
  return mults[t.tile_type] || 1.0
})

const estimatedGrainCost = computed(() => {
  return Math.floor(marchConfig.value.troops * 0.02 * terrainMultiplier.value)
})

const sustainRounds = computed(() => {
  if (estimatedGrainCost.value <= 0) return 99
  return Math.floor(marchConfig.value.grain / estimatedGrainCost.value)
})

const sustainClass = computed(() => {
  const r = sustainRounds.value
  if (r < 1) return 'danger-text'
  if (r < 3) return 'warning-text'
  return 'success-text'
})

// ===== 是否可以出征 =====
const canMarch = computed(() => {
  return (
    marchConfig.value.fromTile &&
    marchConfig.value.toTile &&
    marchConfig.value.troops >= minTroops.value &&
    marchConfig.value.troops <= maxTroops.value &&
    marchConfig.value.grain >= 0
  )
})

// ===== 玩家势力 =====
const playerFaction = computed(() => store.playerFaction)

// ===== 操作 =====
function onPreviewMarch() {
  // 通知地图组件显示行军预览线
  window.dispatchEvent(new CustomEvent('march-preview', {
    detail: {
      fromTile: marchConfig.value.fromTile,
      toTile: marchConfig.value.toTile,
      path: pathInfo.value?.path || [marchConfig.value.fromTile, marchConfig.value.toTile],
    },
  }))
}

async function onConfirmMarch() {
  if (!canMarch.value) return

  // 直接提交行军指令到后端指令队列（链路2）
  try {
    await store.submitCommand('march', {
      from_tile: marchConfig.value.fromTile,
      to_tile: marchConfig.value.toTile,
      troops: marchConfig.value.troops,
      grain: marchConfig.value.grain,
    })

    // 同时加入前端待办显示列表（给用户视觉反馈）
    store.pendingEdictCommands.push({
      action: 'march',
      params: {
        from_tile: marchConfig.value.fromTile,
        to_tile: marchConfig.value.toTile,
        troops: marchConfig.value.troops,
        grain: marchConfig.value.grain,
      },
      label: `出兵征伐 ${toTileData.value?.tile_name || marchConfig.value.toTile}（${formatNum(marchConfig.value.troops)}兵·${marchConfig.value.grain}粮）`,
    })

    // 提示用户：指令已提交，需推进月份执行
    const { showToast } = await import('@/services/api')
    const capitalLoot = toTileData.value?.is_capital ? '，攻占都城可缴获银500+粮1000' : ''
    showToast(`行军令已下：【消耗】${formatNum(marchConfig.value.troops)}兵+${marchConfig.value.grain}粮 → 【目标】${toTileData.value?.tile_name || marchConfig.value.toTile}${capitalLoot}，请「推进月份」执行`, 'success')

    // 将行军路线添加到地图显示
    if (pathInfo.value?.path && pathInfo.value.path.length > 1) {
      store.activeRoutes.push({
        type: 'march',
        path: pathInfo.value.path,
        id: `march_${Date.now()}`,
      })
      // 最多保留 20 条路线
      if (store.activeRoutes.length > 20) {
        store.activeRoutes.shift()
      }
    }
  } catch (e: any) {
    const { showToast } = await import('@/services/api')
    showToast(e?.message || '行军令提交失败', 'error')
    return  // 提交失败则不关闭面板
  }

  emit('marchConfirm', { ...marchConfig.value })
  emit('close')
}

// ===== 辅助函数 =====
function formatNum(n: number | undefined | null): string {
  if (n == null) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function getStatClass(v: number): string {
  if (v >= 70) return 'success-text'
  if (v >= 40) return 'warning-text'
  return 'danger-text'
}

const TILE_TYPE_NAMES: Record<string, string> = {
  farmland: '农田', mountain: '山地', water: '水域', coast: '海岸',
  city: '城池', pass: '关隘', port: '港口', desert: '漠地', grassland: '草原',
}
function tileTypeName(t: string): string {
  return TILE_TYPE_NAMES[t] || t
}

function getFactionColor(id: string): string {
  const f = store.factions[id]
  return f?.color || '#888'
}
function getFactionName(id: string): string {
  const f = store.factions[id]
  return f?.name || id
}
</script>

<style scoped>
/* ===== 遮罩层 ===== */
.march-overlay {
  position: fixed;
  inset: 0;
  z-index: 5000;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 40px;
  backdrop-filter: blur(2px);
}

/* ===== 面板主体（背景/边框/阴影由 artifact-dispatch 全局器物系统接管） ===== */
.march-panel {
  width: 520px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  font-family: "SimSun", "FangSong", serif;
  position: relative;
  overflow: hidden;
  box-shadow: inset 3px 0 0 var(--wuxing-fire);
}

/* ===== 标题栏 ===== */
.mp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(139, 115, 85, 0.3);
  background: linear-gradient(180deg, #3A2E1E 0%, #2C2416 100%);
  position: relative;
  z-index: 1;
}

.mp-title-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.mp-icon {
  font-size: 22px;
}

.mp-title {
  font-size: 20px;
  font-weight: normal;
  color: #C9A94E;
  letter-spacing: 4px;
  margin: 0;
  font-family: "STKaiti", "KaiTi", serif;
}

.mp-subtitle {
  font-size: 12px;
  color: #8B7355;
  letter-spacing: 2px;
}

.mp-close {
  width: 28px;
  height: 28px;
  border: 1px solid rgba(139, 115, 85, 0.3);
  background: rgba(0, 0, 0, 0.2);
  color: #8B7355;
  font-size: 16px;
  cursor: pointer;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.mp-close:hover {
  border-color: #C94040;
  color: #C94040;
  background: rgba(201, 64, 64, 0.1);
}

/* ===== 内容区 ===== */
.mp-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
  position: relative;
  z-index: 1;
}

.mp-body::-webkit-scrollbar {
  width: 4px;
}
.mp-body::-webkit-scrollbar-track {
  background: transparent;
}
.mp-body::-webkit-scrollbar-thumb {
  background: rgba(139, 115, 85, 0.3);
  border-radius: 2px;
}

/* ===== 分区 ===== */
.mp-section {
  margin-bottom: 18px;
  padding-bottom: 16px;
  border-bottom: 1px dotted rgba(139, 115, 85, 0.2);
}

.mp-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.mp-section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.mp-step-badge {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #C9A94E, #8B6914);
  color: #1A1815;
  font-size: 12px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.mp-section-title {
  font-size: 15px;
  color: #D4C490;
  font-weight: bold;
  letter-spacing: 2px;
}

.mp-section-hint {
  font-size: 11px;
  color: #6B5B4A;
  letter-spacing: 1px;
}

/* ===== 选择提示 ===== */
.mp-select-hint {
  padding: 16px;
  background: rgba(139, 115, 85, 0.08);
  border: 1px dashed rgba(139, 115, 85, 0.25);
  border-radius: 3px;
  text-align: center;
  color: #8B7355;
  font-size: 13px;
  letter-spacing: 1px;
}

.hint-icon {
  font-size: 20px;
  display: block;
  margin-bottom: 4px;
}

.hint-em {
  color: #C9A94E;
  font-weight: bold;
}

/* ===== 地块卡片 ===== */
.mp-tile-card {
  background: rgba(44, 36, 22, 0.6);
  border: 1px solid rgba(139, 115, 85, 0.3);
  border-radius: 3px;
  padding: 12px 14px;
  position: relative;
}

.mp-tile-card.from-tile {
  border-left: 3px solid #4CAF50;
}

.mp-tile-card.to-tile {
  border-left: 3px solid #E53935;
}

.mtc-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.mtc-name {
  font-size: 16px;
  font-weight: bold;
  color: #E8D5A3;
  letter-spacing: 2px;
}

.mtc-type {
  font-size: 11px;
  color: #8B7355;
  background: rgba(139, 115, 85, 0.15);
  padding: 1px 6px;
  border-radius: 2px;
}

.mtc-capital {
  font-size: 11px;
  color: #FFD700;
  font-weight: bold;
}

.mtc-owner {
  font-size: 12px;
  font-weight: bold;
  padding: 1px 6px;
  border: 1px solid currentColor;
  border-radius: 2px;
}

.mtc-owner.neutral {
  color: #8B7355;
}

.mtc-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}

.mtc-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.mtc-sl {
  font-size: 10px;
  color: #6B5B4A;
}

.mtc-sv {
  font-size: 14px;
  font-weight: bold;
  color: #D4C490;
}

.mtc-change-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 10px;
  padding: 2px 8px;
  background: rgba(139, 115, 85, 0.15);
  border: 1px solid rgba(139, 115, 85, 0.3);
  color: #8B7355;
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s;
}

.mtc-change-btn:hover {
  background: rgba(139, 115, 85, 0.25);
  color: #C9A94E;
}

/* ===== 地块列表 ===== */
.mp-tile-list {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mp-tile-list::-webkit-scrollbar {
  width: 3px;
}
.mp-tile-list::-webkit-scrollbar-thumb {
  background: rgba(139, 115, 85, 0.2);
}

.mp-tile-option {
  padding: 10px 12px;
  background: rgba(44, 36, 22, 0.4);
  border: 1px solid rgba(139, 115, 85, 0.15);
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s;
}

.mp-tile-option:hover {
  background: rgba(201, 169, 78, 0.08);
  border-color: rgba(201, 169, 78, 0.3);
}

.mp-tile-option.selected {
  background: rgba(201, 169, 78, 0.12);
  border-color: #C9A94E;
}

.mto-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.mto-name {
  font-size: 14px;
  color: #D4C490;
  font-weight: bold;
  letter-spacing: 1px;
}

.mto-capital {
  color: #FFD700;
  font-size: 12px;
}

.mto-type {
  font-size: 10px;
  color: #6B5B4A;
  background: rgba(139, 115, 85, 0.1);
  padding: 1px 5px;
  border-radius: 2px;
}

.mto-owner-tag {
  font-size: 10px;
  padding: 1px 5px;
  border: 1px solid;
  border-radius: 2px;
  margin-left: auto;
}

.mto-owner-tag.neutral {
  color: #6B5B4A;
  border-color: #6B5B4A;
}

.mto-stats {
  display: flex;
  gap: 12px;
}

.mto-stat {
  font-size: 11px;
  color: #8B7355;
}

/* ===== 空状态 ===== */
.mp-empty {
  padding: 20px;
  text-align: center;
  color: #6B5B4A;
  font-size: 12px;
  letter-spacing: 1px;
}

.mp-loading {
  padding: 20px;
  text-align: center;
  color: #8B7355;
  font-size: 12px;
}

/* ===== 配置行 ===== */
.mp-config-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.mcr-label {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 80px;
  padding-top: 6px;
  font-size: 13px;
  color: #D4C490;
  letter-spacing: 1px;
}

.mcr-icon {
  font-size: 16px;
}

.mcr-control {
  flex: 1;
}

/* ===== 滑块 ===== */
.mp-slider {
  width: 100%;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: linear-gradient(90deg, #3A2E1E, #C9A94E);
  border-radius: 3px;
  outline: none;
  margin-bottom: 6px;
}

.mp-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #C9A94E;
  border: 2px solid #1A1815;
  cursor: pointer;
  box-shadow: 0 0 8px rgba(201, 169, 78, 0.4);
}

.mp-slider.grain-slider {
  background: linear-gradient(90deg, #3A2E1E, #81C784);
}

.mp-slider.grain-slider::-webkit-slider-thumb {
  background: #81C784;
  box-shadow: 0 0 8px rgba(129, 199, 132, 0.4);
}

.mcr-value-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mp-number-input {
  width: 80px;
  padding: 4px 8px;
  background: rgba(26, 24, 21, 0.6);
  border: 1px solid rgba(139, 115, 85, 0.3);
  color: #E8D5A3;
  font-size: 14px;
  font-family: "SimSun", serif;
  border-radius: 2px;
  text-align: center;
}

.mp-number-input:focus {
  border-color: #C9A94E;
  outline: none;
}

.mcr-unit {
  font-size: 12px;
  color: #8B7355;
}

.mcr-range {
  font-size: 11px;
  color: #6B5B4A;
}

/* ===== 快捷按钮 ===== */
.mp-quick-btns {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  padding-left: 92px;
}

.mp-quick-btn {
  padding: 4px 10px;
  font-size: 11px;
  background: rgba(139, 115, 85, 0.1);
  border: 1px solid rgba(139, 115, 85, 0.2);
  color: #8B7355;
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s;
  font-family: "SimSun", serif;
}

.mp-quick-btn:hover {
  background: rgba(201, 169, 78, 0.1);
  border-color: rgba(201, 169, 78, 0.3);
}

.mp-quick-btn.active {
  background: rgba(201, 169, 78, 0.2);
  border-color: #C9A94E;
  color: #C9A94E;
}

/* ===== 兵力详情 ===== */
.mp-troops-detail {
  padding: 8px 12px;
  background: rgba(44, 36, 22, 0.3);
  border-radius: 2px;
  margin-bottom: 12px;
  margin-left: 92px;
}

.mtd-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
}

.mtd-label {
  font-size: 11px;
  color: #8B7355;
  min-width: 50px;
}

.mtd-value {
  font-size: 14px;
  color: #E8D5A3;
  font-weight: bold;
  min-width: 40px;
  text-align: right;
}

.mtd-sub {
  font-size: 10px;
  color: #6B5B4A;
}

/* ===== 粮草信息 ===== */
.mp-grain-info {
  padding: 10px 12px;
  background: rgba(44, 36, 22, 0.3);
  border-radius: 2px;
  margin-left: 92px;
}

.mgi-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}

.mgi-label {
  font-size: 11px;
  color: #8B7355;
  min-width: 60px;
}

.mgi-value {
  font-size: 14px;
  font-weight: bold;
}

.mgi-note {
  font-size: 10px;
  color: #6B5B4A;
}

.mgi-warning {
  margin-top: 6px;
  padding: 6px 10px;
  background: rgba(201, 64, 64, 0.1);
  border: 1px solid rgba(201, 64, 64, 0.2);
  border-radius: 2px;
  color: #E57373;
  font-size: 11px;
  letter-spacing: 1px;
}

/* ===== 行军预览 ===== */
.mp-path-preview {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(44, 36, 22, 0.3);
  border-radius: 3px;
}

.mpp-from, .mpp-to {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #D4C490;
  font-size: 13px;
}

.mpp-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.mpp-dot.from { background: #4CAF50; }
.mpp-dot.to { background: #E53935; }

.mpp-arrow {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}

.mpp-line {
  flex: 1;
  height: 2px;
  background: linear-gradient(90deg, #4CAF50, #E53935);
  border-radius: 1px;
}

.mpp-dist {
  font-size: 11px;
  color: #8B7355;
  white-space: nowrap;
}

.mp-path-info {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  font-size: 11px;
  color: #6B5B4A;
}

/* ===== 操作按钮 ===== */
.mp-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding-top: 8px;
}

.mp-btn {
  padding: 10px 20px;
  font-size: 14px;
  font-family: "SimSun", serif;
  letter-spacing: 2px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.mp-btn-primary {
  background: linear-gradient(180deg, #8B2500 0%, #6B1C00 100%);
  border-color: #A04030;
  color: #F0D8A0;
  box-shadow: 0 2px 8px rgba(139, 37, 0, 0.3);
}

.mp-btn-primary:hover:not(:disabled) {
  background: linear-gradient(180deg, #A03000 0%, #8B2500 100%);
  border-color: #C05040;
  box-shadow: 0 4px 12px rgba(139, 37, 0, 0.5);
}

.mp-btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.mp-btn-secondary {
  background: rgba(139, 115, 85, 0.15);
  border-color: rgba(139, 115, 85, 0.3);
  color: #8B7355;
}

.mp-btn-secondary:hover {
  background: rgba(139, 115, 85, 0.25);
  border-color: rgba(139, 115, 85, 0.5);
  color: #C9A94E;
}

/* ===== 底部状态栏 ===== */
.mp-footer {
  display: flex;
  gap: 0;
  border-top: 1px solid rgba(139, 115, 85, 0.3);
  background: rgba(26, 24, 21, 0.4);
  padding: 8px 4px;
  position: relative;
  z-index: 1;
}

.mpf-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 4px 2px;
  border-right: 1px dotted rgba(139, 115, 85, 0.15);
}

.mpf-item:last-child {
  border-right: none;
}

.mp-footer-hint {
  text-align: center;
  padding: 4px 8px;
  font-size: 10px;
  color: #6B5B4A;
  background: rgba(44, 36, 22, 0.4);
  border-top: 1px dotted rgba(139, 115, 85, 0.15);
}

.mpf-icon {
  font-size: 14px;
}

.mpf-label {
  font-size: 10px;
  color: #6B5B4A;
}

.mpf-value {
  font-size: 13px;
  color: #D4C490;
  font-weight: bold;
}

/* ===== 颜色工具类 ===== */
.troop-text { color: #EF5350; }
.grain-text { color: #81C784; }
.success-text { color: #81C784; }
.warning-text { color: #FFB74D; }
.danger-text { color: #EF5350; }

.terrain-badge {
  font-size: 10px !important;
  padding: 1px 5px;
  border-radius: 2px;
}

.terrain-mountain { color: #8B7355; background: rgba(139, 115, 85, 0.15); }
.terrain-water { color: #4A90D9; background: rgba(74, 144, 217, 0.15); }
.terrain-desert { color: #D4C490; background: rgba(212, 196, 144, 0.15); }
.terrain-grassland { color: #7C9C4A; background: rgba(124, 156, 74, 0.15); }
.terrain-farmland { color: #8FBC8F; background: rgba(143, 188, 143, 0.15); }
.terrain-city { color: #C4A46C; background: rgba(196, 164, 108, 0.15); }
.terrain-pass { color: #7B6B5B; background: rgba(123, 107, 91, 0.15); }
.terrain-port { color: #3D8BB1; background: rgba(61, 139, 177, 0.15); }
.terrain-coast { color: #5B9ECF; background: rgba(91, 158, 207, 0.15); }

.terrain-label {
  font-size: 10px !important;
  padding: 1px 4px;
  border-radius: 2px;
}

/* ===== 消耗与收益卡片 ===== */
.mp-cost-benefit {
  display: flex;
  gap: 0;
  margin-top: 8px;
  border: 1px solid rgba(139, 115, 85, 0.25);
  border-radius: 4px;
  overflow: hidden;
}

.mcb-column {
  flex: 1;
  padding: 10px 12px;
  background: rgba(26, 24, 21, 0.5);
}

.mcb-column.mcb-cost {
  border-right: 1px solid rgba(139, 115, 85, 0.15);
}

.mcb-col-title {
  font-size: 12px;
  font-weight: bold;
  letter-spacing: 2px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px dotted rgba(139, 115, 85, 0.2);
  color: #C4A46C;
}

.mcb-cost .mcb-col-title {
  color: #E07060;
}

.mcb-gain .mcb-col-title {
  color: #81C784;
}

.mcb-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
  font-size: 11px;
}

.mcb-label {
  color: #8B7B6B;
}

.mcb-value {
  font-weight: bold;
}

.mcb-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  background: linear-gradient(180deg, rgba(196, 75, 60, 0.08) 0%, rgba(91, 140, 90, 0.08) 100%);
  flex-shrink: 0;
}

.mcb-arrow {
  font-size: 18px;
  color: #C4A46C;
  font-weight: bold;
}

/* ===== 动画 ===== */
.animate-fade-in {
  animation: marchFadeIn 0.3s ease-out;
}

@keyframes marchFadeIn {
  from {
    opacity: 0;
    transform: translateY(-12px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
