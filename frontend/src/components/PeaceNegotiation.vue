<template>
  <div v-if="visible" class="peace-overlay" @click.self="$emit('close')">
    <div class="peace-panel glass-card">
      <div class="panel-header">
        <h2>议和谈判</h2>
        <span class="war-title">{{ warName }}</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <!-- 战争分数摘要 -->
      <div class="score-summary" v-if="scoreStatus">
        <div class="score-number" :class="scoreClass">
          {{ scoreStatus.war_score > 0 ? '+' : '' }}{{ scoreStatus.war_score }}%
        </div>
        <div class="score-hint">{{ advantageLabel }}</div>
      </div>

      <!-- 提议方选择 -->
      <div class="side-select">
        <label>我方立场：</label>
        <button
          :class="{ active: isAttackerOffer }"
          @click="isAttackerOffer = true"
          :disabled="playerIsDefender"
        >进攻方</button>
        <button
          :class="{ active: !isAttackerOffer }"
          @click="isAttackerOffer = false"
          :disabled="playerIsAttacker"
        >防守方</button>
      </div>

      <!-- 可用条款 -->
      <div class="terms-section" v-if="availableTerms.length">
        <h3>可选条款</h3>
        <div
          v-for="term in availableTerms"
          :key="term.term"
          class="term-item"
          :class="{ selected: selectedTerms.includes(term.term) }"
          @click="toggleTerm(term)"
        >
          <span class="term-check">{{ selectedTerms.includes(term.term) ? '☑' : '☐' }}</span>
          <div class="term-info">
            <span class="term-name">{{ term.name }}</span>
            <span class="term-desc">{{ term.description }}</span>
          </div>
          <span class="term-cost" v-if="term.cost > 0">-{{ term.cost }}分</span>
          <span class="term-cost free" v-else>免费</span>
        </div>
      </div>

      <!-- 地块选择（如果选择了割地条款） -->
      <div class="tile-select" v-if="needsTileSelection">
        <h3>选择割让地块 ({{ selectedTileIds.length }}/{{ maxTiles }})</h3>
        <div class="tile-hint">从地图上已占领的敌方地块中选择</div>
        <div v-if="selectedTileIds.length" class="selected-tiles">
          <span v-for="tid in selectedTileIds" :key="tid" class="tile-tag">
            {{ getTileName(tid) }}
            <button @click="removeTile(tid)">✕</button>
          </span>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-row">
        <button class="btn btn-secondary" @click="$emit('close')">取消</button>
        <button
          class="btn btn-primary"
          @click="evaluateProposal"
          :disabled="!selectedTerms.length"
        >
          预判对方态度
        </button>
        <button
          class="btn btn-confirm"
          @click="submitProposal"
          :disabled="!selectedTerms.length"
        >
          正式提出和议
        </button>
      </div>

      <!-- 评估/执行结果 -->
      <div class="result-box" v-if="proposalResult">
        <div class="result-text" :class="{ accepted: proposalResult.accepted, rejected: !proposalResult.accepted }">
          {{ proposalResult.accepted ? '✅' : '❌' }} {{ proposalResult.reason }}
        </div>
        <div class="result-score" v-if="proposalResult.acceptance_score !== undefined">
          接受度：{{ proposalResult.acceptance_score }}
        </div>
        <div class="result-execution" v-if="proposalResult.execution?.message">
          {{ proposalResult.execution.message }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'

const props = defineProps<{
  visible: boolean
  war: any
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const store = useGameStore()
const isAttackerOffer = ref(true)
const selectedTerms = ref<string[]>([])
const selectedTileIds = ref<string[]>([])
const availableTerms = ref<any[]>([])
const scoreStatus = ref<any>(null)
const proposalResult = ref<any>(null)

const warName = computed(() =>
  `${props.war?.attacker_name || '?'} ⚔ ${props.war?.defender_name || '?'}`
)

const playerIsAttacker = computed(() => props.war?.attacker === store.playerFactionId)
const playerIsDefender = computed(() => props.war?.defender === store.playerFactionId)

const scoreClass = computed(() => {
  const s = scoreStatus.value?.war_score || 0
  if (s > 25) return 'attacker'
  if (s < -25) return 'defender'
  return 'neutral'
})

const advantageLabel = computed(() => {
  const map: Record<string, string> = {
    attacker_crushing: '碾压优势·可强制要求',
    attacker_winning: '占据上风·可要求苛刻条款',
    attacker_slight: '小有优势',
    stalemate: '势均力敌',
    defender_slight: '小有劣势',
    defender_winning: '处于下风',
    defender_crushing: '惨败边缘',
  }
  return map[scoreStatus.value?.advantage || ''] || ''
})

const needsTileSelection = computed(() =>
  selectedTerms.value.some(t => t === 'cede_tile' || t === 'cede_multiple')
)

const maxTiles = computed(() =>
  selectedTerms.value.includes('cede_multiple') ? 3 : 1
)

watch(() => props.visible, async (v) => {
  if (!v) return
  selectedTerms.value = []
  selectedTileIds.value = []
  proposalResult.value = null
  isAttackerOffer.value = playerIsAttacker.value

  if (props.war?.war_id) {
    try {
      const data = await API.getAvailablePeaceTerms(props.war.war_id)
      scoreStatus.value = data?.war_score || null
      availableTerms.value = data?.available_terms?.[
        isAttackerOffer.value ? 'for_attacker' : 'for_defender'
      ] || []
    } catch { scoreStatus.value = null; availableTerms.value = [] }
  }
})

watch(isAttackerOffer, async () => {
  if (!props.war?.war_id) return
  selectedTerms.value = []
  try {
    const data = await API.getAvailablePeaceTerms(props.war.war_id)
    availableTerms.value = data?.available_terms?.[
      isAttackerOffer.value ? 'for_attacker' : 'for_defender'
    ] || []
  } catch {}
})

function toggleTerm(term: any) {
  const idx = selectedTerms.value.indexOf(term.term)
  if (idx >= 0) {
    selectedTerms.value.splice(idx, 1)
  } else {
    selectedTerms.value.push(term.term)
    // 最多选 3 个条款
    if (selectedTerms.value.length > 3) selectedTerms.value.shift()
  }
}

function removeTile(tileId: string) {
  selectedTileIds.value = selectedTileIds.value.filter(t => t !== tileId)
}

function getTileName(tileId: string): string {
  return store.tiles[tileId]?.tile_name || tileId
}

async function evaluateProposal() {
  proposalResult.value = null
  try {
    const data = await API.evaluatePeaceProposal({
      war_id: props.war.war_id,
      terms: selectedTerms.value,
      is_from_attacker: isAttackerOffer.value,
      tile_ids: selectedTileIds.value,
    })
    proposalResult.value = data
  } catch (e: any) {
    proposalResult.value = { accepted: false, reason: `评估失败: ${e?.message || e}` }
  }
}

async function submitProposal() {
  proposalResult.value = null
  try {
    const data = await API.proposePeace({
      war_id: props.war.war_id,
      terms: selectedTerms.value,
      is_from_attacker: isAttackerOffer.value,
      tile_ids: selectedTileIds.value,
    })
    proposalResult.value = data
    if (data?.accepted) {
      // 成功后 2 秒自动关闭
      setTimeout(() => {
        emit('close')
        store.refreshWorldState()
      }, 2500)
    }
  } catch (e: any) {
    proposalResult.value = { accepted: false, reason: `提议失败: ${e?.message || e}` }
  }
}
</script>

<style scoped>
.peace-overlay {
  position: fixed; inset: 0; z-index: 2100;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0, 0, 0, 0.6);
}
.peace-panel {
  width: 480px; max-height: 85vh; overflow-y: auto;
  background: linear-gradient(135deg, #1a1a2e, #16213e, #1a1a2e);
  border: 1px solid rgba(255, 200, 60, 0.3);
  border-radius: 12px; padding: 20px; color: #e0d5c1;
}
.panel-header {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 16px; padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 200, 60, 0.15);
}
.panel-header h2 { margin: 0; font-size: 18px; color: #ffc83d; }
.war-title { font-size: 12px; color: #8a8; }
.close-btn { margin-left: auto; background: none; border: none; color: #888; font-size: 18px; cursor: pointer; }

.score-summary { text-align: center; margin-bottom: 16px; }
.score-number { font-size: 32px; font-weight: bold; }
.score-number.attacker { color: #e74c3c; }
.score-number.defender { color: #3498db; }
.score-number.neutral { color: #95a5a6; }
.score-hint { font-size: 12px; color: #8a8; margin-top: 4px; }

.side-select {
  display: flex; align-items: center; gap: 8px; margin-bottom: 16px;
  font-size: 13px;
}
.side-select button {
  padding: 4px 12px; border: 1px solid rgba(255,255,255,0.15);
  border-radius: 4px; background: transparent; color: #e0d5c1;
  cursor: pointer; font-size: 12px;
}
.side-select button.active {
  background: rgba(255, 200, 60, 0.2); border-color: #ffc83d; color: #ffc83d;
}
.side-select button:disabled { opacity: 0.5; cursor: not-allowed; }

.terms-section { margin-bottom: 16px; }
.terms-section h3 { font-size: 14px; margin-bottom: 8px; color: #ffc83d; }
.term-item {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border: 1px solid rgba(255,255,255,0.06); border-radius: 6px;
  margin-bottom: 4px; cursor: pointer; transition: all 0.15s;
}
.term-item:hover { background: rgba(255,255,255,0.04); }
.term-item.selected {
  background: rgba(255, 200, 60, 0.08); border-color: rgba(255, 200, 60, 0.3);
}
.term-check { font-size: 16px; width: 20px; }
.term-info { flex: 1; }
.term-name { display: block; font-size: 13px; font-weight: bold; }
.term-desc { display: block; font-size: 11px; color: #8a8; }
.term-cost { font-size: 12px; font-weight: bold; color: #e74c3c; }
.term-cost.free { color: #27ae60; }

.tile-select { margin-bottom: 16px; }
.tile-select h3 { font-size: 14px; color: #ffc83d; margin-bottom: 4px; }
.tile-hint { font-size: 11px; color: #888; margin-bottom: 8px; }
.selected-tiles { display: flex; flex-wrap: wrap; gap: 4px; }
.tile-tag {
  background: rgba(231, 76, 60, 0.15); color: #e74c3c;
  padding: 2px 8px; border-radius: 4px; font-size: 11px;
  display: flex; align-items: center; gap: 4px;
}
.tile-tag button { background: none; border: none; color: #e74c3c; cursor: pointer; font-size: 10px; }

.action-row { display: flex; gap: 10px; margin-top: 8px; }
.btn { padding: 8px 16px; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-secondary { background: rgba(255,255,255,0.05); color: #e0d5c1; }
.btn-primary { background: rgba(52, 152, 219, 0.15); color: #3498db; border-color: rgba(52, 152, 219, 0.3); }
.btn-confirm { background: rgba(231, 76, 60, 0.15); color: #e74c3c; border-color: rgba(231, 76, 60, 0.3); }
.btn:hover:not(:disabled) { background: rgba(255,255,255,0.1); }

.result-box { margin-top: 12px; padding: 12px; border-radius: 8px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.08); }
.result-text { font-size: 13px; }
.result-text.accepted { color: #27ae60; }
.result-text.rejected { color: #e74c3c; }
.result-score { font-size: 11px; color: #8a8; margin-top: 4px; }
.result-execution { font-size: 12px; color: #ffc83d; margin-top: 6px; }
</style>
