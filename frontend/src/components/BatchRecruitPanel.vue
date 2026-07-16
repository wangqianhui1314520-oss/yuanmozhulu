<template>
  <Teleport to="body">
    <transition name="modal">
      <div class="batch-recruit-overlay" v-if="visible" @click.self="$emit('close')">
        <div class="batch-recruit-dialog artifact-panel artifact-dispatch">
          <!-- 标题栏 -->
          <div class="br-header">
            <h2>兵部 · 批量征兵</h2>
            <span class="br-subtitle">多地征调，整军备战</span>
            <button class="br-close" @click="$emit('close')">✕</button>
          </div>

          <!-- 征兵配比设置 -->
          <div class="br-config">
            <div class="br-config-row">
              <label>总征调兵力</label>
              <div class="br-slider-wrap">
                <input type="range" v-model.number="totalRecruitTarget" :min="0" :max="maxPossible" step="100" class="br-slider" />
                <span class="br-slider-val">{{ totalRecruitTarget.toLocaleString() }}人</span>
              </div>
            </div>
            <div class="br-config-row">
              <label>分配策略</label>
              <div class="br-strategy-btns">
                <button :class="{ active: strategy === 'equal' }" @click="strategy = 'equal'">均分</button>
                <button :class="{ active: strategy === 'proportional' }" @click="strategy = 'proportional'">按人口比例</button>
                <button :class="{ active: strategy === 'frontier' }" @click="strategy = 'frontier'">优先前线</button>
                <button :class="{ active: strategy === 'capital' }" @click="strategy = 'capital'">优先都城</button>
              </div>
            </div>
            <div class="br-config-row" v-if="strategy === 'frontier'">
              <label>前线地块征兵倍率</label>
              <div class="br-slider-wrap">
                <input type="range" v-model.number="frontierMultiplier" :min="1" :max="5" step="0.5" class="br-slider" />
                <span class="br-slider-val">×{{ frontierMultiplier }}</span>
              </div>
            </div>
          </div>

          <!-- 地块征兵预览列表 -->
          <div class="br-tile-list">
            <div class="br-tile-list-header">
              <span>地块</span>
              <span>人口</span>
              <span>现有驻军</span>
              <span>将征调</span>
              <span>可调上限</span>
            </div>
            <div
              v-for="tr in recruitTiles"
              :key="tr.tile_id"
              class="br-tile-row"
              :class="{ 'is-frontier': tr.isFrontier }"
            >
              <div class="br-tile-name">
                <span>{{ tr.tile_name }}</span>
                <span v-if="tr.isFrontier" class="frontier-tag">前线</span>
                <span v-if="tr.is_capital" class="capital-tag">都城</span>
              </div>
              <div class="br-tile-pop">{{ fmtNum(tr.population) }}</div>
              <div class="br-tile-existing">{{ fmtNum(tr.troops) }}</div>
              <div class="br-tile-recruit">
                <input
                  type="number"
                  v-model.number="recruitAllocations[tr.tile_id]"
                  :max="tr.maxRecruit"
                  :min="0"
                  step="10"
                  class="br-recruit-input"
                  @change="onAllocationChange"
                />
              </div>
              <div class="br-tile-max">{{ fmtNum(tr.maxRecruit) }}</div>
            </div>
          </div>

          <!-- 汇总 -->
          <div class="br-summary">
            <div class="br-summary-row">
              <span>总计征调</span>
              <span class="br-sum-val">{{ totalAllocated.toLocaleString() }}人</span>
            </div>
            <div class="br-summary-row">
              <span>预计花费粮草</span>
              <span class="br-sum-val grain">{{ fmtNum(totalGrainCost) }}</span>
            </div>
            <div class="br-summary-row">
              <span>当前粮草储备</span>
              <span class="br-sum-val" :class="(store.playerFaction?.grain ?? 0) >= totalGrainCost ? '' : 'insufficient'">
                {{ fmtNum(store.playerFaction?.grain ?? 0) }}
              </span>
            </div>
          </div>

          <!-- 圣旨预览 -->
          <div class="br-edict-preview" v-if="recruitEdictText">
            <div class="br-edict-label">将生成圣旨</div>
            <div class="br-edict-text">{{ recruitEdictText }}</div>
          </div>

          <!-- 底部操作 -->
          <div class="br-footer">
            <button class="br-btn" @click="$emit('close')">取消</button>
            <button class="br-btn primary" :disabled="totalAllocated === 0 || isRecruiting" @click="executeBatchRecruit">
              {{ isRecruiting ? '征调中...' : '颁布圣旨，征调兵马' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, reactive } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import { getRecruitInfo, batchRecruitTroops } from '@/services/api'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: []; edictFill: [text: string] }>()

const store = useGameStore()

const totalRecruitTarget = ref(1000)
const strategy = ref<'equal' | 'proportional' | 'frontier' | 'capital'>('equal')
const frontierMultiplier = ref(2)
const isRecruiting = ref(false)
const recruitAllocations = reactive<Record<string, number>>({})

// 可征兵地块数据
const recruitTiles = computed(() => {
  const tiles = Object.values(store.tiles)
    .filter(t => t.faction_id === store.playerFactionId && t.population > 0)

  return tiles.map(t => {
    const neighbors = store.tileNeighbors[t.tile_id] || []
    const isFrontier = neighbors.some(nid => {
      const nt = store.tiles[nid]
      return nt && nt.faction_id !== store.playerFactionId && nt.faction_id !== ''
    })
    const maxRecruit = Math.floor(t.population * 0.15) // 15% 人口上限（与RecruitPanel一致）
    return {
      ...t,
      isFrontier,
      maxRecruit,
    }
  }).sort((a, b) => {
    if (a.is_capital && !b.is_capital) return -1
    if (b.is_capital && !a.is_capital) return 1
    return (b.population || 0) - (a.population || 0)
  })
})

const maxPossible = computed(() => {
  return recruitTiles.value.reduce((sum, t) => sum + t.maxRecruit, 0)
})

const totalAllocated = computed(() => {
  return Object.values(recruitAllocations).reduce((sum, v) => sum + (v || 0), 0)
})

const totalGrainCost = computed(() => {
  return Math.floor(totalAllocated.value * 0.5) // 每人0.5粮草
})

const recruitEdictText = computed(() => {
  if (totalAllocated.value === 0) return ''
  const topTiles = Object.entries(recruitAllocations)
    .filter(([_, v]) => v > 0)
    .slice(0, 5)
  const tileNames = topTiles.map(([tid, v]) => {
    const tile = store.tiles[tid]
    return tile ? `${tile.tile_name}征${v}人` : `${tid}征${v}人`
  })
  if (topTiles.length <= 5) {
    return `从${tileNames.join('、')}`
  }
  return `从${tileNames.join('、')}等${topTiles.length}地共征兵${totalAllocated.value}人`
})

// 分配策略
function applyStrategy() {
  const tiles = recruitTiles.value
  const alloc: Record<string, number> = {}
  let remaining = totalRecruitTarget.value

  const sorted = [...tiles]
  if (strategy.value === 'frontier') {
    sorted.sort((a, b) => {
      if (a.isFrontier && !b.isFrontier) return -1
      if (!a.isFrontier && b.isFrontier) return 1
      return 0
    })
  } else if (strategy.value === 'capital') {
    sorted.sort((a, b) => {
      if (a.is_capital && !b.is_capital) return -1
      if (!a.is_capital && b.is_capital) return 1
      return 0
    })
  }

  // 第一轮：按比例分配
  const weights = sorted.map(t => {
    if (strategy.value === 'equal') return 1
    if (strategy.value === 'proportional') return t.population
    if (strategy.value === 'frontier') return t.isFrontier ? frontierMultiplier.value : 1
    if (strategy.value === 'capital') return t.is_capital ? 3 : 1
    return 1
  })
  const totalWeight = weights.reduce((sum, w) => sum + w, 0)

  for (let i = 0; i < sorted.length && remaining > 0; i++) {
    const t = sorted[i]
    let amount = Math.floor(totalRecruitTarget.value * (weights[i] / totalWeight))
    amount = Math.min(amount, t.maxRecruit, remaining)
    amount = Math.floor(amount / 10) * 10 // 取整到10
    alloc[t.tile_id] = amount
    remaining -= amount
  }

  // 剩余分配到容量未满的地块
  if (remaining > 0) {
    for (const t of sorted) {
      if (remaining <= 0) break
      const extra = Math.min(t.maxRecruit - (alloc[t.tile_id] || 0), remaining)
      if (extra > 0) {
        alloc[t.tile_id] = (alloc[t.tile_id] || 0) + extra
        remaining -= extra
      }
    }
  }

  // 更新 reactive
  for (const key of Object.keys(recruitAllocations)) {
    delete recruitAllocations[key]
  }
  for (const [k, v] of Object.entries(alloc)) {
    recruitAllocations[k] = v
  }
}

function onAllocationChange() {
  // 更新总目标以匹配实际分配
  totalRecruitTarget.value = totalAllocated.value
}

async function executeBatchRecruit() {
  if (totalAllocated.value === 0) return
  isRecruiting.value = true

  try {
    // 直接调用批量征兵专用API（确定性执行，不走AI推演）
    const recruitments = Object.entries(recruitAllocations)
      .filter(([_, v]) => v > 0)
      .map(([tid, v]) => ({ tile_id: tid, amount: v }))

    const result = await batchRecruitTroops({
      recruitments,
      faction_id: store.playerFactionId,
    })

    if (result) {
      // 刷新世界状态以同步征兵后的数据
      await store.refreshWorldState()
      try {
        const { showToast } = await import('@/services/api')
        showToast(result.message || `已从${recruitments.length}地征调${totalAllocated.value}人`, 'success')
      } catch { /* 忽略toast错误 */ }
      emit('close')
    }
  } catch (e: any) {
    console.error('批量征兵失败:', e)
    try {
      const { showToast } = await import('@/services/api')
      showToast(e?.message || '征兵失败，请检查资源是否充足', 'error')
    } catch { /* 忽略toast错误 */ }
  } finally {
    isRecruiting.value = false
  }
}

function fmtNum(n: number | undefined): string {
  if (n === undefined) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return String(Math.floor(n))
}

// 监听目标和策略变化，重新分配
watch([totalRecruitTarget, strategy, frontierMultiplier], () => {
  applyStrategy()
})

watch(() => props.visible, (v) => {
  if (v) {
    totalRecruitTarget.value = Math.min(1000, maxPossible.value)
    isRecruiting.value = false
    applyStrategy()
  }
})
</script>

<style scoped>
.batch-recruit-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 400;
  display: flex;
  align-items: center;
  justify-content: center;
}

.batch-recruit-dialog {
  width: 680px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: inset 3px 0 0 var(--wuxing-earth);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
}

.br-header {
  padding: 14px 20px;
  border-bottom: 1px solid rgba(184, 155, 104, 0.2);
  position: relative;
}

.br-header h2 {
  font-size: 18px;
  font-family: "STKaiti", "KaiTi", serif;
  color: var(--gold);
  letter-spacing: 3px;
  margin: 0;
}

.br-subtitle {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 2px;
}

.br-close {
  position: absolute;
  right: 14px;
  top: 12px;
  background: none;
  border: 1px solid var(--text-dim);
  color: var(--text-dim);
  font-size: 16px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 2px;
}

.br-close:hover { color: var(--danger); border-color: var(--danger); }

/* 配置区 */
.br-config {
  padding: 12px 20px;
  border-bottom: 1px solid rgba(139, 115, 85, 0.1);
}

.br-config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}

.br-config-row label {
  font-size: 12px;
  color: var(--text-dim);
  width: 90px;
  flex-shrink: 0;
  letter-spacing: 1px;
}

.br-slider-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.br-slider {
  flex: 1;
  accent-color: var(--gold);
}

.br-slider-val {
  font-size: 12px;
  color: var(--gold);
  min-width: 50px;
  text-align: right;
}

.br-strategy-btns {
  display: flex;
  gap: 4px;
}

.br-strategy-btns button {
  padding: 3px 10px;
  font-size: 10px;
  font-family: "SimSun", serif;
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.15);
  color: var(--text-dim);
  cursor: pointer;
  border-radius: 2px;
}

.br-strategy-btns button.active {
  background: rgba(184, 155, 104, 0.15);
  border-color: var(--gold);
  color: var(--gold);
}

/* 地块列表 */
.br-tile-list {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.br-tile-list-header {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
  gap: 4px;
  padding: 8px 20px;
  font-size: 10px;
  color: var(--text-dim);
  border-bottom: 1px solid rgba(139, 115, 85, 0.1);
  position: sticky;
  top: 0;
  background: #1a1510;
}

.br-tile-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
  gap: 4px;
  padding: 6px 20px;
  font-size: 11px;
  border-bottom: 1px solid rgba(139, 115, 85, 0.06);
  align-items: center;
}

.br-tile-row.is-frontier {
  background: rgba(184, 155, 104, 0.03);
}

.br-tile-row:hover {
  background: rgba(184, 155, 104, 0.05);
}

.br-tile-name {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-main);
}

.frontier-tag {
  font-size: 8px;
  padding: 0 4px;
  background: rgba(200, 60, 40, 0.15);
  border: 1px solid rgba(200, 60, 40, 0.3);
  color: #D07070;
  border-radius: 1px;
}

.capital-tag {
  font-size: 8px;
  padding: 0 4px;
  background: rgba(184, 155, 104, 0.15);
  border: 1px solid rgba(184, 155, 104, 0.3);
  color: var(--gold);
  border-radius: 1px;
}

.br-tile-pop, .br-tile-existing, .br-tile-max {
  color: var(--text-dim);
  text-align: center;
}

.br-recruit-input {
  width: 60px;
  padding: 3px 6px;
  background: var(--bg-input);
  border: 1px solid var(--border-main);
  color: var(--gold);
  font-size: 11px;
  text-align: center;
  border-radius: 2px;
  font-family: "SimSun", serif;
}

.br-recruit-input:focus {
  outline: none;
  border-color: var(--gold);
}

/* 汇总 */
.br-summary {
  padding: 10px 20px;
  border-top: 1px solid rgba(184, 155, 104, 0.2);
  background: rgba(184, 155, 104, 0.04);
}

.br-summary-row {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 12px;
}

.br-summary-row span:first-child {
  color: var(--text-dim);
}

.br-sum-val {
  color: var(--gold);
  font-weight: bold;
}

.br-sum-val.grain { color: #7AB87A; }
.br-sum-val.insufficient { color: #D07070; }

/* 圣旨预览 */
.br-edict-preview {
  margin: 0 20px 8px;
  padding: 8px 12px;
  background: rgba(90, 140, 90, 0.05);
  border: 1px solid rgba(90, 140, 90, 0.15);
  border-radius: 2px;
}

.br-edict-label {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 2px;
  margin-bottom: 3px;
}

.br-edict-text {
  font-size: 12px;
  color: #7AB87A;
  font-family: "STKaiti", "KaiTi", serif;
  letter-spacing: 1px;
}

/* 底部 */
.br-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid rgba(139, 115, 85, 0.1);
}

.br-btn {
  padding: 8px 20px;
  font-family: "SimSun", serif;
  font-size: 12px;
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.2);
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 2px;
  letter-spacing: 2px;
}

.br-btn:hover:not(:disabled) {
  background: rgba(184, 155, 104, 0.12);
  border-color: var(--gold);
  color: var(--gold);
}

.br-btn.primary {
  background: rgba(184, 155, 104, 0.15);
  border-color: var(--gold);
  color: var(--gold);
}

.br-btn.primary:hover:not(:disabled) {
  background: rgba(184, 155, 104, 0.25);
}

.br-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
