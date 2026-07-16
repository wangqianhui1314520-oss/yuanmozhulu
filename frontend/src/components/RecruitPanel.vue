<template>
  <div v-if="store.activePanel === 'recruit'" class="float-panel animate-fade-in artifact-panel artifact-memorial" style="top:60px;left:52px;width:460px;max-height:85vh;">
    <div class="fp-header">
      <h3>🛡 招兵买马</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('recruit')">✕</button>
    </div>
    <div class="fp-body" style="max-height:70vh;overflow-y:auto;">

      <!-- 当前选中地块 -->
      <div class="recruit-tile-info" v-if="selectedTile">
        <div class="tile-header">
          <span class="tile-name">{{ selectedTile.tile_name }}</span>
          <span class="tile-type-badge">{{ tileTypeName(selectedTile.tile_type) }}</span>
          <span v-if="selectedTileId && selectedTileId !== store.playerFaction?.capital_tile && isFrontline(selectedTileId)" class="tile-tag frontline">前线</span>
          <span v-if="selectedTileId === store.playerFaction?.capital_tile" class="tile-tag capital">都城</span>
        </div>
        <div class="tile-stats-grid">
          <div class="ts-item"><span class="ts-label">人口</span><span class="ts-value">{{ formatNum(selectedTile.population) }}</span></div>
          <div class="ts-item"><span class="ts-label">驻军</span><span class="ts-value troop-text">{{ formatNum(selectedTile.troops) }}</span></div>
          <div class="ts-item"><span class="ts-label">民心</span><span class="ts-value" :class="getStatClass(selectedTile.morale)">{{ selectedTile.morale }}</span></div>
          <div class="ts-item"><span class="ts-label">城防</span><span class="ts-value">{{ selectedTile.fortification }}级</span></div>
        </div>
        <div class="garrison-bar">
          <div class="bar-label">驻军容量</div>
          <div class="bar-track">
            <div class="bar-fill" :style="{ width: garrisonPercent + '%' }" :class="garrisonPercent > 80 ? 'bar-full' : ''"></div>
          </div>
          <span class="bar-text">{{ formatNum(selectedTile.troops) }} / {{ formatNum(maxGarrison) }}</span>
        </div>
      </div>

      <!-- 资源总览 -->
      <div class="kv-divider"></div>
      <div class="resource-row">
        <div class="res-item">
          <span class="res-icon">💰</span>
          <span class="res-label">银两</span>
          <span class="res-value gold-text">{{ formatNum(playerFaction?.treasury) }}</span>
        </div>
        <div class="res-item">
          <span class="res-icon">🌾</span>
          <span class="res-label">粮草</span>
          <span class="res-value grain-text">{{ formatNum(playerFaction?.grain) }}</span>
        </div>
        <div class="res-item">
          <span class="res-icon">🔧</span>
          <span class="res-label">军械</span>
          <span class="res-value">{{ formatNum(playerFaction?.arms) }}</span>
        </div>
        <div class="res-item">
          <span class="res-icon">🐴</span>
          <span class="res-label">战马</span>
          <span class="res-value">{{ formatNum(playerFaction?.horses) }}</span>
        </div>
      </div>

      <!-- 各城征兵需求 -->
      <div class="kv-divider"></div>
      <div class="demand-section">
        <h4 class="section-subtitle">
          📋 各城征兵需求
          <span class="demand-badge" v-if="urgentDemands.length > 0">⚠ {{ urgentDemands.length }}城急缺</span>
        </h4>
        <div v-if="store.playerTiles.length === 0" class="empty-note">暂无领地</div>
        <div v-for="tile in store.playerTiles" :key="tile.tile_id" class="demand-row" @click="selectTileForRecruit(tile.tile_id)" :class="{ 'selected-row': selectedTileId === tile.tile_id }">
          <div class="dr-left">
            <span class="dr-name">{{ tile.tile_name }}</span>
            <span class="dr-tag" v-if="isFrontline(tile.tile_id)">前线</span>
            <span class="dr-tag capital-tag" v-if="tile.tile_id === store.playerFaction?.capital_tile">都城</span>
          </div>
          <div class="dr-right">
            <span class="dr-troops" :class="getDemandClass(tile)">
              {{ formatNum(tile.troops) }}兵
            </span>
            <span class="dr-capacity">/{{ formatNum(5000 + tile.fortification * 2000) }}</span>
            <span class="dr-pop">{{ formatNum(tile.population) }}口</span>
          </div>
          <!-- 征兵可行性快速预览 -->
          <div class="dr-feasibility">
            <span v-if="getMaxRecruitForTile(tile) >= 500" class="feas-tag ok">可征{{ formatNum(getMaxRecruitForTile(tile)) }}人</span>
            <span v-else-if="getMaxRecruitForTile(tile) >= 100" class="feas-tag warn">仅{{ formatNum(getMaxRecruitForTile(tile)) }}人</span>
            <span v-else class="feas-tag bad">人口不足</span>
            <span v-if="getDemandReason(tile)" class="feas-reason">{{ getDemandReason(tile) }}</span>
          </div>
        </div>
      </div>

      <div class="kv-divider"></div>

      <!-- Tab 切换 -->
      <div class="recruit-tabs">
        <button :class="{ active: recruitTab === 'recruit' }" @click="recruitTab = 'recruit'">🛡 征兵</button>
        <button :class="{ active: recruitTab === 'horses' }" @click="recruitTab = 'horses'">🐴 买马</button>
        <button :class="{ active: recruitTab === 'train' }" @click="recruitTab = 'train'">⚔ 训练</button>
      </div>

      <!-- ========== 征兵 Tab ========== -->
      <div v-if="recruitTab === 'recruit'" class="tab-content">
        <div class="kv-divider"></div>
        <h4 class="section-subtitle">征召新兵</h4>
        <p class="hint-text" v-if="!selectedTile">请先在地图或上方列表中选一个己方地块。</p>
        <p class="hint-text" v-else>
          每人{{ recruitCostPer }}银两，消耗1件军械/3人，降低民心3点。<br/>
          最多征用该地块人口的<b>15%</b>（上限{{ formatNum(Math.floor(selectedTile.population * 0.15)) }}人）。
        </p>

        <!-- 征兵失败理由详细展示 -->
        <div v-if="selectedTile && recruitCheckResults.length > 0" class="check-list">
          <div v-for="check in recruitCheckResults" :key="check.key" class="check-item" :class="check.pass ? 'check-pass' : 'check-fail'">
            <span class="check-icon">{{ check.pass ? '✓' : '✗' }}</span>
            <span class="check-label">{{ check.label }}</span>
            <span class="check-detail">{{ check.detail }}</span>
          </div>
        </div>

        <div class="recruit-form" v-if="selectedTile">
          <div class="slider-row">
            <label>征兵数量</label>
            <input type="range" v-model.number="recruitAmount" :min="100" :max="maxRecruit" :step="100" />
            <span class="slider-value">{{ formatNum(recruitAmount) }}人</span>
          </div>
          <div class="quick-amounts">
            <button v-for="q in recruitQuickAmounts" :key="q" class="quick-amt-btn" @click="recruitAmount = q" :class="{ active: recruitAmount === q }">
              {{ formatNum(q) }}
            </button>
          </div>
          <div class="cost-preview">
            <div class="cost-line">
              <span>银两消耗：</span>
              <span class="gold-text">{{ formatNum(recruitAmount * recruitCostPer) }}</span>
            </div>
            <div class="cost-line">
              <span>军械消耗：</span>
              <span>{{ formatNum(Math.max(0, Math.floor(recruitAmount / 3))) }}</span>
            </div>
            <div class="cost-line">
              <span>人口减少：</span>
              <span class="warn-text">{{ formatNum(recruitAmount) }}</span>
            </div>
            <div class="cost-line">
              <span>民心降低：</span>
              <span class="warn-text">-3</span>
            </div>
            <div class="cost-line">
              <span>征兵后驻军：</span>
              <span class="troop-text">{{ formatNum(selectedTile.troops + recruitAmount) }}</span>
            </div>
          </div>
          <button class="btn-gold btn-block" @click="doRecruit" :disabled="!canRecruit || isProcessing">
            {{ isProcessing ? '征兵中...' : `征召 ${formatNum(recruitAmount)} 新兵` }}
          </button>
          <!-- 征兵失败原因明细 -->
          <div v-if="selectedTile && !canRecruit && recruitFailReasons.length > 0" class="fail-reasons">
            <div class="fail-title">无法征兵，原因如下：</div>
            <div v-for="(reason, idx) in recruitFailReasons" :key="idx" class="fail-item">• {{ reason }}</div>
          </div>
          <p class="error-hint" v-if="recruitError">{{ recruitError }}</p>
        </div>
      </div>

      <!-- ========== 买马 Tab ========== -->
      <div v-if="recruitTab === 'horses'" class="tab-content">
        <div class="kv-divider"></div>
        <h4 class="section-subtitle">购买战马</h4>
        <p class="hint-text">
          每匹战马5银两。战马可提升骑兵战力，用于组建精锐骑兵。<br/>
          <span v-if="!hasStable" class="warn-text">⚠ 需要先建造马场（营造司 → 马场）才能购买战马。</span>
          <span v-else class="good-text">✓ 已有马场，可购买战马。</span>
        </p>

        <!-- 买马失败理由详细展示 -->
        <div v-if="horseCheckResults.length > 0" class="check-list">
          <div v-for="check in horseCheckResults" :key="check.key" class="check-item" :class="check.pass ? 'check-pass' : 'check-fail'">
            <span class="check-icon">{{ check.pass ? '✓' : '✗' }}</span>
            <span class="check-label">{{ check.label }}</span>
            <span class="check-detail">{{ check.detail }}</span>
          </div>
        </div>

        <div class="recruit-form">
          <div class="slider-row">
            <label>购买数量</label>
            <input type="range" v-model.number="horseAmount" :min="50" :max="maxHorses" :step="50" />
            <span class="slider-value">{{ formatNum(horseAmount) }}匹</span>
          </div>
          <div class="quick-amounts">
            <button v-for="q in horseQuickOptions" :key="q" class="quick-amt-btn" @click="horseAmount = Math.min(q, maxHorses)" :class="{ active: horseAmount === q }">
              {{ formatNum(q) }}
            </button>
          </div>
          <div class="cost-preview">
            <div class="cost-line">
              <span>银两消耗：</span>
              <span class="gold-text">{{ formatNum(horseAmount * 5) }}</span>
            </div>
            <div class="cost-line">
              <span>购买后战马：</span>
              <span>{{ formatNum((playerFaction?.horses || 0) + horseAmount) }}匹</span>
            </div>
            <div class="cost-line">
              <span>可武装骑兵：</span>
              <span class="troop-text">约{{ formatNum(Math.floor((playerFaction?.horses || 0) + horseAmount) / 3) }}人</span>
            </div>
          </div>
          <button class="btn-gold btn-block" @click="doBuyHorses" :disabled="!canBuyHorses || isProcessing">
            {{ isProcessing ? '购买中...' : `购买 ${formatNum(horseAmount)} 匹战马` }}
          </button>
          <!-- 买马失败原因明细 -->
          <div v-if="!canBuyHorses && horseFailReasons.length > 0" class="fail-reasons">
            <div class="fail-title">无法购买战马，原因如下：</div>
            <div v-for="(reason, idx) in horseFailReasons" :key="idx" class="fail-item">• {{ reason }}</div>
          </div>
          <p class="error-hint" v-if="horseError">{{ horseError }}</p>
        </div>
      </div>

      <!-- ========== 训练 Tab ========== -->
      <div v-if="recruitTab === 'train'" class="tab-content">
        <div class="kv-divider"></div>
        <h4 class="section-subtitle">训练士卒</h4>
        <p class="hint-text" v-if="!selectedTile">请先在地图或上方列表中选一个己方地块。</p>
        <p class="hint-text" v-else>
          每人1银两、每2人1粮草。提升地块士气<b>+10</b>，增加精锐比例。<br/>
          当前驻军 {{ formatNum(selectedTile.troops) }} 人，士气 {{ selectedTile.morale }}。
        </p>

        <!-- 训练失败理由详细展示 -->
        <div v-if="selectedTile && trainCheckResults.length > 0" class="check-list">
          <div v-for="check in trainCheckResults" :key="check.key" class="check-item" :class="check.pass ? 'check-pass' : 'check-fail'">
            <span class="check-icon">{{ check.pass ? '✓' : '✗' }}</span>
            <span class="check-label">{{ check.label }}</span>
            <span class="check-detail">{{ check.detail }}</span>
          </div>
        </div>

        <div class="recruit-form" v-if="selectedTile">
          <div class="slider-row">
            <label>训练数量</label>
            <input type="range" v-model.number="trainAmount" :min="100" :max="maxTrain" :step="100" />
            <span class="slider-value">{{ formatNum(trainAmount) }}人</span>
          </div>
          <div class="quick-amounts">
            <button v-for="q in trainQuickAmounts" :key="q" class="quick-amt-btn" @click="trainAmount = q" :class="{ active: trainAmount === q }">
              {{ formatNum(q) }}
            </button>
          </div>
          <div class="cost-preview">
            <div class="cost-line">
              <span>银两消耗：</span>
              <span class="gold-text">{{ formatNum(trainAmount) }}</span>
            </div>
            <div class="cost-line">
              <span>粮草消耗：</span>
              <span class="grain-text">{{ formatNum(Math.floor(trainAmount / 2)) }}</span>
            </div>
            <div class="cost-line">
              <span>训练后士气：</span>
              <span class="good-text">{{ Math.min(100, selectedTile.morale + 10) }}</span>
            </div>
            <div class="cost-line">
              <span>精锐比例提升：</span>
              <span class="good-text">+{{ (trainAmount / Math.max(selectedTile.troops, 1) * 10).toFixed(1) }}%</span>
            </div>
          </div>
          <button class="btn-gold btn-block" @click="doTrain" :disabled="!canTrain || isProcessing">
            {{ isProcessing ? '训练中...' : `训练 ${formatNum(trainAmount)} 士卒` }}
          </button>
          <!-- 训练失败原因明细 -->
          <div v-if="selectedTile && !canTrain && trainFailReasons.length > 0" class="fail-reasons">
            <div class="fail-title">无法训练，原因如下：</div>
            <div v-for="(reason, idx) in trainFailReasons" :key="idx" class="fail-item">• {{ reason }}</div>
          </div>
          <p class="error-hint" v-if="trainError">{{ trainError }}</p>
        </div>
      </div>

      <!-- 操作结果 -->
      <div v-if="actionResult" class="action-result" :class="actionResult.success ? 'result-success' : 'result-fail'">
        {{ actionResult.message }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import { useFormat } from '@/composables/useFormat'

const store = useGameStore()
const { formatNum } = useFormat()

const recruitTab = ref<'recruit' | 'horses' | 'train'>('recruit')
const recruitAmount = ref(500)
const horseAmount = ref(100)
const trainAmount = ref(500)
const isProcessing = ref(false)
const recruitError = ref('')
const horseError = ref('')
const trainError = ref('')
const actionResult = ref<{ success: boolean; message: string } | null>(null)

const playerFaction = computed(() => store.playerFaction)
const selectedTileId = computed(() => store.selectedTile)
const selectedTile = computed(() => {
  if (!selectedTileId.value) return null
  return store.tiles[selectedTileId.value] || null
})

// ============ 前线判断 ============
function isFrontline(tileId: string): boolean {
  // 检查该地块是否与敌方地块相邻
  const neighbors = store.tileNeighbors[tileId]
  if (!neighbors || !Array.isArray(neighbors)) return false
  return neighbors.some((nid: string) => {
    const nt = store.tiles[nid]
    return nt && nt.faction_id && nt.faction_id !== store.playerFactionId
  })
}

// ============ 各城征兵需求 ============
function getMaxRecruitForTile(tile: any): number {
  if (!tile) return 0
  return Math.max(100, Math.floor(tile.population * 0.15))
}

function getDemandClass(tile: any): string {
  if (!tile) return ''
  const maxG = 5000 + tile.fortification * 2000
  const ratio = tile.troops / maxG
  if (ratio < 0.3) return 'demand-urgent'
  if (ratio < 0.6) return 'demand-warn'
  return 'demand-ok'
}

function getDemandReason(tile: any): string {
  if (!tile) return ''
  const reasons: string[] = []
  const maxG = 5000 + tile.fortification * 2000
  if (tile.troops < maxG * 0.3) reasons.push('兵力空虚')
  if (isFrontline(tile.tile_id)) reasons.push('前线需兵')
  if (tile.tile_id === store.playerFaction?.capital_tile && tile.troops < 2000) reasons.push('都城守备不足')
  if (getMaxRecruitForTile(tile) < 200) reasons.push('人口枯竭')
  return reasons.join('，')
}

const urgentDemands = computed(() => {
  return store.playerTiles.filter((t: any) => {
    const maxG = 5000 + t.fortification * 2000
    return t.troops < maxG * 0.3
  })
})

// ============ 征兵参数与校验 ============
const recruitCostPer = computed(() => {
  if (!selectedTile.value) return 2
  const tt: any = selectedTile.value.tile_type
  const tv = typeof tt === 'string' ? tt : (tt?.value || tt || '')
  if (tv === 'city' || tv === 'port') return 3
  return 2
})

const maxRecruit = computed(() => {
  if (!selectedTile.value) return 0
  return Math.max(100, Math.floor(selectedTile.value.population * 0.15))
})

const recruitQuickAmounts = computed(() => {
  const max = maxRecruit.value
  const options = [100, 300, 500, 1000, 2000, 3000]
  return [...new Set(options.filter(o => o <= max).concat(max > 0 ? [max] : []))]
})

// 征兵各项条件检查结果（详细展示）
const recruitCheckResults = computed(() => {
  const tile = selectedTile.value
  const pf = playerFaction.value
  if (!tile || !pf) return []

  const isOwn = tile.faction_id === store.playerFactionId
  const maxPop = Math.floor(tile.population * 0.15)
  const cost = recruitAmount.value * recruitCostPer.value
  const armsNeeded = Math.max(0, Math.floor(recruitAmount.value / 3))
  const maxG = 5000 + tile.fortification * 2000
  const roomLeft = maxG - tile.troops

  return [
    {
      key: 'ownership',
      label: '地块归属',
      pass: isOwn,
      detail: isOwn ? '己方地块' : '非己方地块，不可征兵',
    },
    {
      key: 'population',
      label: '人口充足',
      pass: recruitAmount.value <= maxPop,
      detail: recruitAmount.value <= maxPop
        ? `可征${maxPop}人，当前选${recruitAmount.value}人`
        : `人口不足！最多可征${maxPop}人（当前人口${tile.population}）`,
    },
    {
      key: 'treasury',
      label: '银两充足',
      pass: (pf.treasury || 0) >= cost,
      detail: (pf.treasury || 0) >= cost
        ? `需要${cost}两，现有${pf.treasury}两`
        : `银两不足！需要${cost}两，现有${pf.treasury}两`,
    },
    {
      key: 'arms',
      label: '军械充足',
      pass: (pf.arms || 0) >= armsNeeded,
      detail: (pf.arms || 0) >= armsNeeded
        ? `需要${armsNeeded}件，现有${pf.arms}件`
        : `军械不足！需要${armsNeeded}件，现有${pf.arms}件`,
    },
    {
      key: 'garrison',
      label: '驻军容量',
      pass: roomLeft >= recruitAmount.value,
      detail: roomLeft >= recruitAmount.value
        ? `剩余容量${roomLeft}人`
        : `驻军上限${maxG}人，现有${tile.troops}人，仅余${roomLeft}人`,
    },
  ]
})

// 征兵失败原因列表
const recruitFailReasons = computed(() => {
  return recruitCheckResults.value
    .filter(c => !c.pass)
    .map(c => c.detail)
})

const canRecruit = computed(() => {
  return recruitCheckResults.value.every(c => c.pass) && recruitAmount.value >= 100
})

// ============ 买马参数与校验 ============
const hasStable = computed(() => {
  return store.playerTiles.some((t: any) => (t.stable || 0) > 0)
})

const maxHorses = computed(() => {
  const treasury = playerFaction.value?.treasury || 0
  return Math.max(50, Math.floor(treasury / 5))
})

const horseQuickOptions = computed(() => {
  const max = maxHorses.value
  return [100, 200, 500, 1000].filter(o => o <= max)
})

const horseCheckResults = computed(() => {
  const pf = playerFaction.value
  if (!pf) return []

  const cost = horseAmount.value * 5
  return [
    {
      key: 'stable',
      label: '拥有马场',
      pass: hasStable.value,
      detail: hasStable.value ? '已建造马场' : '未建造马场（营造司 → 马场）',
    },
    {
      key: 'amount',
      label: '数量有效',
      pass: horseAmount.value > 0 && horseAmount.value <= 1000,
      detail: horseAmount.value > 1000
        ? `单次最多1000匹（请求${horseAmount.value}）`
        : `购买${horseAmount.value}匹`,
    },
    {
      key: 'treasury',
      label: '银两充足',
      pass: (pf.treasury || 0) >= cost,
      detail: (pf.treasury || 0) >= cost
        ? `需要${cost}两，现有${pf.treasury}两`
        : `银两不足！需要${cost}两，现有${pf.treasury}两`,
    },
  ]
})

const horseFailReasons = computed(() => {
  return horseCheckResults.value
    .filter(c => !c.pass)
    .map(c => c.detail)
})

const canBuyHorses = computed(() => {
  return horseCheckResults.value.every(c => c.pass)
})

// ============ 训练参数与校验 ============
const maxTrain = computed(() => {
  if (!selectedTile.value) return 0
  return Math.max(100, selectedTile.value.troops)
})

const trainQuickAmounts = computed(() => {
  const max = maxTrain.value
  const options = [100, 300, 500, 1000, 2000]
  return [...new Set(options.filter(o => o <= max))]
})

const trainCheckResults = computed(() => {
  const tile = selectedTile.value
  const pf = playerFaction.value
  if (!tile || !pf) return []

  const isOwn = tile.faction_id === store.playerFactionId
  const cost = trainAmount.value * 1
  const grainCost = Math.floor(trainAmount.value / 2)

  return [
    {
      key: 'ownership',
      label: '地块归属',
      pass: isOwn,
      detail: isOwn ? '己方地块' : '非己方地块，不可训练',
    },
    {
      key: 'troops',
      label: '驻军充足',
      pass: trainAmount.value > 0 && trainAmount.value <= tile.troops,
      detail: trainAmount.value > 0 && trainAmount.value <= tile.troops
        ? `驻军${tile.troops}人，训练${trainAmount.value}人`
        : `驻军不足！仅有${tile.troops}人`,
    },
    {
      key: 'treasury',
      label: '银两充足',
      pass: (pf.treasury || 0) >= cost,
      detail: (pf.treasury || 0) >= cost
        ? `需要${cost}两，现有${pf.treasury}两`
        : `银两不足！需要${cost}两，现有${pf.treasury}两`,
    },
    {
      key: 'grain',
      label: '粮草充足',
      pass: (pf.grain || 0) >= grainCost,
      detail: (pf.grain || 0) >= grainCost
        ? `需要${grainCost}石，现有${pf.grain}石`
        : `粮草不足！需要${grainCost}石，现有${pf.grain}石`,
    },
    {
      key: 'morale',
      label: '士气上限',
      pass: tile.morale < 100,
      detail: tile.morale < 100
        ? `当前${tile.morale}，可提升至${Math.min(100, tile.morale + 10)}`
        : `士气已满(100)，训练无增益`,
    },
  ]
})

const trainFailReasons = computed(() => {
  return trainCheckResults.value
    .filter(c => !c.pass)
    .map(c => c.detail)
})

const canTrain = computed(() => {
  return trainCheckResults.value.every(c => c.pass)
})

// ============ 驻军容量 ============
const maxGarrison = computed(() => {
  if (!selectedTile.value) return 5000
  return 5000 + selectedTile.value.fortification * 2000
})

const garrisonPercent = computed(() => {
  if (!selectedTile.value) return 0
  return Math.min(100, (selectedTile.value.troops / maxGarrison.value) * 100)
})

// ============ 选择地块 ============
function selectTileForRecruit(tileId: string) {
  store.selectedTile = tileId
}

// ============ 监听面板打开 ============
watch(() => store.activePanel, (panel) => {
  if (panel === 'recruit') {
    recruitError.value = ''
    horseError.value = ''
    trainError.value = ''
    actionResult.value = null
    if (selectedTile.value) {
      recruitAmount.value = Math.min(500, maxRecruit.value)
      trainAmount.value = Math.min(500, maxTrain.value)
    }
  }
})

// ============ 执行征兵 ============
async function doRecruit() {
  if (!canRecruit.value || isProcessing.value || !selectedTile.value) return
  isProcessing.value = true
  recruitError.value = ''
  actionResult.value = null
  try {
    const result = await store.submitCommand('recruit', {
      tile_id: selectedTile.value.tile_id,
      amount: recruitAmount.value,
    })
    if (result?.warning) {
      actionResult.value = { success: false, message: `⚠ ${result.warning}` }
      recruitError.value = result.warning
    } else {
      // submitCommand 已自动同步到圣旨台待办
      actionResult.value = {
        success: true,
        message: `已提交征兵敕令：从${selectedTile.value.tile_name}招募${recruitAmount.value}士兵（消耗${recruitAmount.value * recruitCostPer.value}银两、${Math.floor(recruitAmount.value / 3)}军械），将在回合推进时执行。`
      }
    }
  } catch (e: any) {
    recruitError.value = e?.message || '征兵请求异常'
    actionResult.value = { success: false, message: recruitError.value }
  } finally {
    isProcessing.value = false
  }
}

// ============ 执行买马 ============
async function doBuyHorses() {
  if (!canBuyHorses.value || isProcessing.value) return
  isProcessing.value = true
  horseError.value = ''
  actionResult.value = null
  try {
    const result = await store.submitCommand('buy_horses', {
      amount: horseAmount.value,
    })
    if (result?.warning) {
      actionResult.value = { success: false, message: `⚠ ${result.warning}` }
      horseError.value = result.warning
    } else {
      // submitCommand 已自动同步到圣旨台待办
      actionResult.value = {
        success: true,
        message: `已提交买马敕令：购买${horseAmount.value}匹战马（消耗${horseAmount.value * 5}银两），将在回合推进时执行。`
      }
    }
  } catch (e: any) {
    horseError.value = e?.message || '买马请求异常'
    actionResult.value = { success: false, message: horseError.value }
  } finally {
    isProcessing.value = false
  }
}

// ============ 执行训练 ============
async function doTrain() {
  if (!canTrain.value || isProcessing.value || !selectedTile.value) return
  isProcessing.value = true
  trainError.value = ''
  actionResult.value = null
  try {
    const result = await store.submitCommand('train_troops', {
      tile_id: selectedTile.value.tile_id,
      amount: trainAmount.value,
    })
    if (result?.warning) {
      actionResult.value = { success: false, message: `⚠ ${result.warning}` }
      trainError.value = result.warning
    } else {
      // submitCommand 已自动同步到圣旨台待办
      actionResult.value = {
        success: true,
        message: `已提交训练敕令：在${selectedTile.value.tile_name}训练${trainAmount.value}士卒（消耗${trainAmount.value}银两、${Math.floor(trainAmount.value / 2)}粮草），将在回合推进时执行。`
      }
    }
  } catch (e: any) {
    trainError.value = e?.message || '训练请求异常'
    actionResult.value = { success: false, message: trainError.value }
  } finally {
    isProcessing.value = false
  }
}

function tileTypeName(type: any): string {
  const names: Record<string, string> = {
    farmland: '农田', mountain: '山地', water: '水域', coast: '海岸',
    city: '城池', pass: '关隘', port: '港口', desert: '漠地', grassland: '草原',
  }
  if (typeof type === 'string') return names[type] || type
  if (type?.value) return names[type.value] || type.value
  return String(type)
}

function getStatClass(v: number): string {
  if (v >= 70) return 'stat-good'
  if (v >= 40) return 'stat-warn'
  return 'stat-bad'
}
</script>

<style scoped>
.float-panel {
  position: fixed;
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-panel) 100%);
  border: 2px solid var(--text-dim);
  border-radius: 3px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  z-index: 2000;
  overflow: hidden;
}

.fp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(180deg, var(--bg-hover) 0%, var(--border-main) 100%);
}

.fp-header h3 {
  font-size: 15px;
  font-weight: normal;
  color: var(--text-main);
  letter-spacing: 2px;
}

.fp-close {
  width: 24px;
  height: 24px;
  border: none;
  background: none;
  font-size: 16px;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.fp-close:hover { color: #8b0000; }

.fp-body {
  padding: 12px 16px;
}

/* 地块信息 */
.recruit-tile-info {
  padding: 10px;
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.15);
  border-radius: 3px;
}

.tile-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.tile-name {
  font-size: 14px;
  font-weight: bold;
  color: var(--text-main);
}

.tile-type-badge {
  font-size: 10px;
  padding: 1px 8px;
  background: rgba(184, 155, 104, 0.12);
  color: var(--text-secondary);
  border-radius: 2px;
}

.tile-tag {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 2px;
  font-weight: bold;
}

.tile-tag.frontline {
  background: rgba(196, 75, 60, 0.15);
  color: #c44b3c;
  border: 1px solid rgba(196, 75, 60, 0.3);
}

.tile-tag.capital {
  background: rgba(184, 155, 104, 0.15);
  color: #b8860b;
  border: 1px solid rgba(184, 155, 104, 0.3);
}

.tile-stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.ts-item {
  display: flex;
  justify-content: space-between;
  padding: 3px 6px;
  font-size: 12px;
  background: rgba(240, 228, 204, 0.3);
  border-radius: 2px;
}

.ts-label { color: var(--text-dim); }
.ts-value { color: var(--text-main); font-weight: bold; }

.garrison-bar {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-label {
  font-size: 10px;
  color: var(--text-dim);
  flex-shrink: 0;
}

.bar-track {
  flex: 1;
  height: 6px;
  background: rgba(240, 228, 204, 0.3);
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: #5b8c5a;
  border-radius: 3px;
  transition: width 0.3s;
}

.bar-fill.bar-full {
  background: #c44b3c;
}

.bar-text {
  font-size: 10px;
  color: var(--text-dim);
  flex-shrink: 0;
}

/* 资源 */
.resource-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  gap: 6px;
}

.res-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 4px;
  background: rgba(240, 228, 204, 0.3);
  border-radius: 3px;
}

.res-icon { font-size: 16px; }
.res-label { font-size: 10px; color: var(--text-dim); margin-top: 2px; }
.res-value { font-size: 12px; font-weight: bold; margin-top: 1px; }

/* 各城征兵需求 */
.demand-section {
  margin-bottom: 4px;
}

.demand-badge {
  font-size: 10px;
  padding: 1px 8px;
  background: rgba(196, 75, 60, 0.12);
  color: #c44b3c;
  border-radius: 10px;
  margin-left: 8px;
  font-weight: normal;
}

.demand-row {
  padding: 6px 8px;
  font-size: 12px;
  border-bottom: 1px dotted var(--border-light);
  cursor: pointer;
  transition: background 0.15s;
}

.demand-row:hover {
  background: rgba(184, 155, 104, 0.06);
}

.demand-row.selected-row {
  background: rgba(184, 155, 104, 0.1);
  border-left: 2px solid var(--gold);
}

.dr-left {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.dr-name {
  font-weight: bold;
  color: var(--text-main);
}

.dr-tag {
  font-size: 9px;
  padding: 0 5px;
  border-radius: 2px;
  background: rgba(196, 75, 60, 0.12);
  color: #c44b3c;
}

.dr-tag.capital-tag {
  background: rgba(184, 155, 104, 0.12);
  color: #b8860b;
}

.dr-right {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.dr-troops {
  font-weight: bold;
  font-size: 13px;
}

.dr-troops.demand-urgent { color: #c44b3c; }
.dr-troops.demand-warn { color: #c9a94e; }
.dr-troops.demand-ok { color: #5b8c5a; }

.dr-capacity {
  font-size: 10px;
  color: var(--text-dim);
}

.dr-pop {
  font-size: 10px;
  color: var(--text-dim);
  margin-left: auto;
}

.dr-feasibility {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
}

.feas-tag {
  padding: 0 5px;
  border-radius: 2px;
  font-size: 9px;
}

.feas-tag.ok {
  background: rgba(91, 140, 90, 0.1);
  color: #5b8c5a;
}

.feas-tag.warn {
  background: rgba(201, 169, 78, 0.1);
  color: #c9a94e;
}

.feas-tag.bad {
  background: rgba(196, 75, 60, 0.1);
  color: #c44b3c;
}

.feas-reason {
  color: #c44b3c;
  font-size: 9px;
}

/* Tab */
.recruit-tabs {
  display: flex;
  gap: 4px;
}

.recruit-tabs button {
  flex: 1;
  padding: 8px 12px;
  font-size: 12px;
  font-family: "SimSun", serif;
  background: rgba(240, 228, 204, 0.3);
  border: 1px solid var(--border-light);
  color: var(--text-dim);
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s;
}

.recruit-tabs button:hover {
  background: rgba(184, 155, 104, 0.1);
}

.recruit-tabs button.active {
  background: linear-gradient(180deg, rgba(184, 155, 104, 0.15) 0%, rgba(184, 155, 104, 0.05) 100%);
  border-color: var(--gold);
  color: var(--gold);
  font-weight: bold;
}

.tab-content {
  animation: fadeIn 0.2s ease-out;
}

/* 条件检查列表 */
.check-list {
  margin: 8px 0;
  padding: 8px 10px;
  background: rgba(240, 228, 204, 0.15);
  border-radius: 3px;
  border: 1px solid var(--border-light);
}

.check-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  font-size: 11px;
}

.check-item + .check-item {
  border-top: 1px dotted rgba(240, 228, 204, 0.15);
}

.check-icon {
  width: 16px;
  text-align: center;
  font-weight: bold;
  flex-shrink: 0;
}

.check-pass .check-icon {
  color: #5b8c5a;
}

.check-fail .check-icon {
  color: #c44b3c;
}

.check-label {
  color: var(--text-secondary);
  min-width: 56px;
  flex-shrink: 0;
}

.check-detail {
  color: var(--text-dim);
  font-size: 10px;
}

.check-fail .check-detail {
  color: #c44b3c;
  font-weight: bold;
}

/* 征兵表单 */
.recruit-form {
  margin-top: 8px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.slider-row label {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.slider-row input[type="range"] {
  flex: 1;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--border-light);
  border-radius: 2px;
  outline: none;
}

.slider-row input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  background: var(--gold);
  border-radius: 50%;
  cursor: pointer;
}

.slider-value {
  font-size: 13px;
  font-weight: bold;
  color: var(--text-main);
  flex-shrink: 0;
  min-width: 60px;
  text-align: right;
}

.quick-amounts {
  display: flex;
  gap: 4px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.quick-amt-btn {
  padding: 3px 10px;
  font-size: 10px;
  font-family: "FangSong", serif;
  background: rgba(240, 228, 204, 0.3);
  border: 1px solid var(--border-light);
  color: var(--text-dim);
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s;
}

.quick-amt-btn:hover {
  background: rgba(184, 155, 104, 0.1);
}

.quick-amt-btn.active {
  background: rgba(184, 155, 104, 0.15);
  border-color: var(--gold);
  color: var(--gold);
}

.cost-preview {
  padding: 8px 12px;
  background: rgba(240, 228, 204, 0.2);
  border-radius: 3px;
  margin-bottom: 10px;
}

.cost-line {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  padding: 2px 0;
  color: var(--text-dim);
}

/* 失败原因列表 */
.fail-reasons {
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(196, 75, 60, 0.08);
  border: 1px solid rgba(196, 75, 60, 0.2);
  border-radius: 3px;
}

.fail-title {
  font-size: 11px;
  font-weight: bold;
  color: #c44b3c;
  margin-bottom: 4px;
}

.fail-item {
  font-size: 10px;
  color: #c44b3c;
  padding: 1px 0;
  padding-left: 4px;
}

.btn-gold {
  width: 100%;
  padding: 10px 20px;
  font-size: 13px;
  font-family: "SimSun", serif;
  background: linear-gradient(180deg, rgba(184, 155, 104, 0.2) 0%, rgba(184, 155, 104, 0.08) 100%);
  border: 1px solid var(--gold);
  color: var(--gold);
  cursor: pointer;
  border-radius: 3px;
  letter-spacing: 2px;
  transition: all 0.15s;
}

.btn-gold:hover:not(:disabled) {
  background: linear-gradient(180deg, rgba(184, 155, 104, 0.3) 0%, rgba(184, 155, 104, 0.12) 100%);
}

.btn-gold:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-block { display: block; }

/* 通用 */
.kv-divider {
  height: 1px;
  background: var(--border-light);
  margin: 10px 0;
}

.section-subtitle {
  font-size: 13px;
  font-weight: normal;
  color: var(--text-secondary);
  letter-spacing: 2px;
  margin-bottom: 6px;
}

.hint-text {
  font-size: 11px;
  color: var(--text-dim);
  line-height: 1.6;
  margin: 4px 0 8px;
}

.empty-note {
  text-align: center;
  padding: 16px;
  color: var(--text-dim);
  font-size: 12px;
  letter-spacing: 2px;
}

.error-hint {
  font-size: 11px;
  color: #c44b3c;
  margin-top: 6px;
}

.action-result {
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 3px;
  font-size: 12px;
  text-align: center;
  animation: fadeIn 0.3s ease-out;
  line-height: 1.5;
}

.result-success {
  background: rgba(91, 140, 90, 0.1);
  border: 1px solid rgba(91, 140, 90, 0.3);
  color: #5b8c5a;
}

.result-fail {
  background: rgba(196, 75, 60, 0.1);
  border: 1px solid rgba(196, 75, 60, 0.3);
  color: #c44b3c;
}

.gold-text { color: #b8860b; }
.grain-text { color: #5b8c5a; }
.troop-text { color: #c44b3c; }
.warn-text { color: #c44b3c; }
.good-text { color: #5b8c5a; }
.stat-good { color: #5b8c5a; }
.stat-warn { color: #c9a94e; }
.stat-bad { color: #c44b3c; }

.animate-fade-in {
  animation: fadeIn 0.25s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
