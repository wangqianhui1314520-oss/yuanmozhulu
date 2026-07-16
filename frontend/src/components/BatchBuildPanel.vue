<template>
  <Teleport to="body">
    <transition name="modal">
      <div class="batch-build-overlay" v-if="visible" @click.self="$emit('close')">
        <div class="batch-build-dialog artifact-panel artifact-memorial">
          <!-- 标题栏 -->
          <div class="bb-header">
            <h2>营造司 · 批量城建</h2>
            <span class="bb-subtitle">一次下旨，多地兴建</span>
            <button class="bb-close" @click="$emit('close')">✕</button>
          </div>

          <!-- 步骤指示器 -->
          <div class="bb-steps">
            <div class="step" :class="{ active: currentStep === 1, done: currentStep > 1 }">
              <span class="step-num">❶</span>选地
            </div>
            <div class="step-line" :class="{ done: currentStep > 1 }"></div>
            <div class="step" :class="{ active: currentStep === 2, done: currentStep > 2 }">
              <span class="step-num">❷</span>选建筑
            </div>
            <div class="step-line" :class="{ done: currentStep > 2 }"></div>
            <div class="step" :class="{ active: currentStep === 3 }">
              <span class="step-num">❸</span>确认
            </div>
          </div>

          <!-- 步骤1: 选择地块 -->
          <div v-if="currentStep === 1" class="bb-step-content">
            <div class="bb-step-header">
              <span>选择要建造的地块（可多选）</span>
              <div class="bb-quick-actions">
                <button class="quick-btn" @click="selectAllTiles">全选</button>
                <button class="quick-btn" @click="deselectAllTiles">清空</button>
                <button class="quick-btn" @click="selectCapitalTiles">仅都城</button>
                <button class="quick-btn" @click="selectFrontierTiles">仅前线</button>
              </div>
            </div>
            <div class="bb-tile-grid">
              <div v-if="ownedTiles.length === 0" class="bb-empty">
              ⚠ 未检测到己方领地数据<br>
              <span style="font-size:10px;color:var(--text-dim)">请确认游戏已正常开局</span>
            </div>
              <div
                v-for="tile in ownedTiles"
                :key="tile.tile_id"
                class="bb-tile-card"
                :class="{ selected: selectedTileIds.has(tile.tile_id) }"
                @click="toggleTile(tile.tile_id)"
              >
                <div class="bb-tile-check">{{ selectedTileIds.has(tile.tile_id) ? '☑' : '☐' }}</div>
                <div class="bb-tile-info">
                  <div class="bb-tile-name">
                    <span :class="tile.is_capital ? 'capital-star' : ''">{{ tile.tile_name }}</span>
                    <span class="bb-tile-type">{{ tileTypeName(tile.tile_type) }}</span>
                  </div>
                  <div class="bb-tile-resources">
                    <span>👥{{ fmtNum(tile.population) }}</span>
                    <span>⚔️{{ fmtNum(tile.troops) }}</span>
                    <span>💰{{ fmtNum(tile.treasury) }}</span>
                  </div>
                  <div class="bb-tile-buildings" v-if="getTileBuildingSummary(tile.tile_id)">
                    <span class="bb-existing-bld">已建: {{ getTileBuildingSummary(tile.tile_id) }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="bb-step-footer">
              <span>已选 <strong>{{ selectedTileIds.size }}</strong> 块地</span>
              <button class="bb-btn primary" :disabled="selectedTileIds.size === 0" @click="currentStep = 2">
                下一步 →
              </button>
            </div>
          </div>

          <!-- 步骤2: 选择建筑类型 -->
          <div v-if="currentStep === 2" class="bb-step-content">
            <div class="bb-step-header">
              <span>选择建筑类型（将批量建造在已选 {{ selectedTileIds.size }} 块地上）</span>
            </div>
            <div class="bb-building-grid">
              <div
                v-for="bt in availableBuildingTypes"
                :key="bt.key"
                class="bb-bld-card"
                :class="{ selected: selectedBuilding === bt.key }"
                @click="selectedBuilding = bt.key"
              >
                <div class="bb-bld-icon">{{ bt.icon }}</div>
                <div class="bb-bld-name">{{ bt.name }}</div>
                <div class="bb-bld-cost">💎{{ bt.cost }}</div>
                <div class="bb-bld-effect">{{ bt.effect }}</div>
                <div class="bb-bld-count" v-if="selectedBuilding === bt.key">
                  将建造 {{ selectedTileIds.size }} 座
                </div>
              </div>
            </div>
            <div class="bb-cost-preview" v-if="selectedBuilding">
              <div class="bb-cost-row">
                <span>预计总花费</span>
                <span class="bb-cost-val">💎 {{ totalCost.toLocaleString() }}</span>
              </div>
              <div class="bb-cost-row">
                <span>当前国库</span>
                <span class="bb-cost-val" :class="store.playerFaction?.treasury ?? 0 >= totalCost ? '' : 'insufficient'">
                  💎 {{ fmtNum(store.playerFaction?.treasury ?? 0) }}
                </span>
              </div>
            </div>
            <div class="bb-step-footer">
              <button class="bb-btn" @click="currentStep = 1">← 返回</button>
              <button class="bb-btn primary" :disabled="!selectedBuilding || totalCost > (store.playerFaction?.treasury ?? 0)" @click="currentStep = 3">
                下一步 →
              </button>
            </div>
          </div>

          <!-- 步骤3: 确认建造 -->
          <div v-if="currentStep === 3" class="bb-step-content">
            <div class="bb-confirm-info">
              <h3>确认建造</h3>
              <div class="bb-confirm-row">
                <span>目标地块</span>
                <span>{{ selectedTileIds.size }}块</span>
              </div>
              <div class="bb-confirm-row">
                <span>建筑类型</span>
                <span>{{ getBuildingName(selectedBuilding) }}</span>
              </div>
              <div class="bb-confirm-row">
                <span>总花费</span>
                <span class="bb-cost-val">💎 {{ totalCost.toLocaleString() }}</span>
              </div>
              <div class="bb-confirm-tiles">
                <span v-for="tid in [...selectedTileIds].slice(0, 8)" :key="tid" class="bb-confirm-tile-tag">
                  {{ store.tiles[tid]?.tile_name || tid }}
                </span>
                <span v-if="selectedTileIds.size > 8" class="bb-confirm-tile-tag">...等{{ selectedTileIds.size }}处</span>
              </div>
            </div>
            <!-- 生成圣旨预览 -->
            <div class="bb-edict-preview" v-if="edictPreview">
              <div class="bb-edict-label">将生成圣旨</div>
              <div class="bb-edict-text">{{ edictPreview }}</div>
            </div>
            <div class="bb-step-footer">
              <button class="bb-btn" @click="currentStep = 2">← 返回</button>
              <button class="bb-btn primary" :disabled="isBuilding" @click="executeBatchBuild">
                {{ isBuilding ? '建造中...' : '颁布圣旨，批量建造' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'
import type { TileState } from '@/types'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: []; edictFill: [text: string] }>()

const store = useGameStore()

const currentStep = ref(1)
const selectedTileIds = ref<Set<string>>(new Set())
const selectedBuilding = ref('')
const isBuilding = ref(false)

// 己方地块（优先 store.playerTiles，为空时回退到 store.tiles）
const ownedTiles = computed(() => {
  const pts = store.playerTiles
  if (pts.length > 0) {
    return pts.sort((a, b) => {
      if (a.is_capital && !b.is_capital) return -1
      if (!a.is_capital && b.is_capital) return 1
      return (b.population || 0) - (a.population || 0)
    })
  }
  // 回退：直接从 store.tiles 按 faction_id 过滤
  return Object.values(store.tiles)
    .filter(t => t.faction_id === store.playerFactionId && t.faction_id !== '')
    .sort((a, b) => {
      if (a.is_capital && !b.is_capital) return -1
      if (!a.is_capital && b.is_capital) return 1
      return (b.population || 0) - (a.population || 0)
    })
})

// 可用建筑类型
const availableBuildingTypes = [
  { key: 'farmland', icon: '🌾', name: '农田', cost: 300, effect: '粮食+80/回合', maxLevel: 5 },
  { key: 'workshop', icon: '🔧', name: '工坊', cost: 500, effect: '银两+60/回合', maxLevel: 4 },
  { key: 'barracks', icon: '🏇', name: '征兵营', cost: 350, effect: '自动募兵+15/回合', maxLevel: 4 },
  { key: 'granary', icon: '🏚️', name: '粮仓', cost: 250, effect: '储粮上限+500', maxLevel: 5 },
  { key: 'beacon', icon: '🔥', name: '烽燧', cost: 200, effect: '视野+2', maxLevel: 3 },
  { key: 'wall', icon: '🏰', name: '城墙', cost: 600, effect: '城防+1/级', maxLevel: 5 },
  { key: 'temple', icon: '🛕', name: '宗庙', cost: 400, effect: '民心+2/回合', maxLevel: 3 },
  { key: 'clinic', icon: '🏥', name: '医馆', cost: 200, effect: '瘟疫抵抗+0.3', maxLevel: 3 },
  { key: 'armory', icon: '⚒️', name: '军械所', cost: 800, effect: '兵器+5/回合', maxLevel: 4 },
  { key: 'stable', icon: '🐴', name: '马场', cost: 600, effect: '战马+2/回合', maxLevel: 4 },
  { key: 'dock', icon: '⛵', name: '码头', cost: 400, effect: '贸易加成+25%', maxLevel: 3 },
]

// 总花费
const totalCost = computed(() => {
  const bt = availableBuildingTypes.find(b => b.key === selectedBuilding.value)
  return bt ? bt.cost * selectedTileIds.value.size : 0
})

// 圣旨预览
const edictPreview = computed(() => {
  if (!selectedBuilding.value || selectedTileIds.value.size === 0) return ''
  const bldName = getBuildingName(selectedBuilding.value)
  const tileNames = [...selectedTileIds.value]
    .map(tid => store.tiles[tid]?.tile_name || tid)
    .slice(0, 5)
  if (selectedTileIds.value.size <= 5) {
    return `在${tileNames.join('、')}各建一座${bldName}`
  }
  return `在${tileNames.join('、')}等${selectedTileIds.value.size}地各建一座${bldName}`
})

function toggleTile(tileId: string) {
  const s = new Set(selectedTileIds.value)
  if (s.has(tileId)) s.delete(tileId)
  else s.add(tileId)
  selectedTileIds.value = s
}

function selectAllTiles() {
  selectedTileIds.value = new Set(ownedTiles.value.map(t => t.tile_id))
}

function deselectAllTiles() {
  selectedTileIds.value = new Set()
}

function selectCapitalTiles() {
  selectedTileIds.value = new Set(ownedTiles.value.filter(t => t.is_capital).map(t => t.tile_id))
}

function selectFrontierTiles() {
  // 挑选有邻接地敌方领土的前线地块
  const frontier = ownedTiles.value.filter(t => {
    const neighbors = store.tileNeighbors[t.tile_id] || []
    return neighbors.some(nid => {
      const nt = store.tiles[nid]
      return nt && nt.faction_id !== store.playerFactionId && nt.faction_id !== ''
    })
  })
  selectedTileIds.value = new Set(frontier.map(t => t.tile_id))
}

function getTileBuildingSummary(tileId: string): string {
  const data = store.tileBuildingData[tileId] || []
  return data.map((b: any) => `${b.name || b.type}`).join('·')
}

function getBuildingName(key: string): string {
  return availableBuildingTypes.find(b => b.key === key)?.name || key
}

function tileTypeName(type: string): string {
  const m: Record<string, string> = {
    farmland: '农田', mountain: '山地', water: '水域',
    city: '城池', pass: '关隘', port: '港口',
    desert: '漠地', grassland: '草原', coast: '海岸',
  }
  return m[type] || type
}

function fmtNum(n: number | undefined): string {
  if (n === undefined) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return String(Math.floor(n))
}

async function executeBatchBuild() {
  if (!selectedBuilding.value || selectedTileIds.value.size === 0) return
  isBuilding.value = true

  try {
    // 直接调用批量建造专用API（确定性执行，不走AI推演）
    const result = await API.batchConstructBuildings({
      tile_ids: [...selectedTileIds.value],
      building_type: selectedBuilding.value,
      faction_id: store.playerFactionId,
    })

    if (result) {
      // 刷新世界状态以同步建造后的数据
      await store.refreshWorldState()
      // 提示成功
      try {
        const { showToast } = await import('@/services/api')
        showToast(result.message || `已在${selectedTileIds.value.size}地各建一座${getBuildingName(selectedBuilding.value)}`, 'success')
      } catch { /* 忽略toast错误 */ }
      emit('close')
    }
  } catch (e: any) {
    console.error('批量建造失败:', e)
    try {
      const { showToast } = await import('@/services/api')
      showToast(e?.message || '建造失败，请检查资源是否充足', 'error')
    } catch { /* 忽略toast错误 */ }
  } finally {
    isBuilding.value = false
  }
}

// 重置步骤
watch(() => props.visible, (v) => {
  if (v) {
    currentStep.value = 1
    selectedTileIds.value = new Set()
    selectedBuilding.value = ''
    isBuilding.value = false
  }
})
</script>

<style scoped>
.batch-build-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 400;
  display: flex;
  align-items: center;
  justify-content: center;
}

.batch-build-dialog {
  width: 680px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: inset 3px 0 0 var(--wuxing-earth);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
}

.bb-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(184, 155, 104, 0.2);
  position: relative;
}

.bb-header h2 {
  font-size: 18px;
  font-family: "STKaiti", "KaiTi", serif;
  color: var(--gold);
  letter-spacing: 3px;
  margin: 0;
}

.bb-subtitle {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 2px;
}

.bb-close {
  position: absolute;
  right: 16px;
  top: 14px;
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

.bb-close:hover { color: var(--danger); border-color: var(--danger); }

/* 步骤 */
.bb-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 20px;
  gap: 0;
}

.step {
  font-size: 12px;
  color: var(--text-dim);
  font-family: "SimSun", serif;
  display: flex;
  align-items: center;
  gap: 4px;
}

.step.active { color: var(--gold); font-weight: bold; }
.step.done { color: #7AB87A; }

.step-num { font-size: 14px; }

.step-line {
  width: 32px;
  height: 1px;
  background: rgba(184, 155, 104, 0.2);
  margin: 0 8px;
}

.step-line.done { background: rgba(122, 184, 122, 0.5); }

/* 步骤内容 */
.bb-step-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px 20px;
  display: flex;
  flex-direction: column;
}

.bb-step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-wrap: wrap;
  gap: 6px;
}

.bb-quick-actions {
  display: flex;
  gap: 3px;
}

.quick-btn {
  padding: 2px 8px;
  font-size: 10px;
  font-family: "SimSun", serif;
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.15);
  color: var(--text-dim);
  cursor: pointer;
  border-radius: 2px;
}

.quick-btn:hover {
  border-color: var(--gold);
  color: var(--gold);
}

/* 地块网格 */
.bb-tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 6px;
  max-height: 400px;
  overflow-y: auto;
}

.bb-empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: 30px;
  color: var(--text-dim);
}

.bb-tile-card {
  padding: 8px 10px;
  background: rgba(139, 115, 85, 0.06);
  border: 1px solid rgba(139, 115, 85, 0.15);
  border-radius: 2px;
  cursor: pointer;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  transition: all 0.15s;
}

.bb-tile-card:hover {
  background: rgba(184, 155, 104, 0.08);
  border-color: rgba(184, 155, 104, 0.3);
}

.bb-tile-card.selected {
  background: rgba(184, 155, 104, 0.12);
  border-color: var(--gold);
}

.bb-tile-check {
  font-size: 14px;
  color: var(--gold);
  padding-top: 2px;
}

.bb-tile-info { flex: 1; min-width: 0; }

.bb-tile-name {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  font-size: 12px;
  color: var(--text-main);
}

.capital-star { color: var(--gold); }
.capital-star::after { content: ' ★'; }

.bb-tile-type {
  font-size: 9px;
  color: var(--text-dim);
  white-space: nowrap;
}

.bb-tile-resources {
  display: flex;
  gap: 8px;
  font-size: 10px;
  color: var(--text-dim);
  margin-top: 3px;
}

.bb-tile-buildings {
  margin-top: 2px;
}

.bb-existing-bld {
  font-size: 9px;
  color: var(--text-dim);
}

/* 建筑选择 */
.bb-building-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
  max-height: 350px;
  overflow-y: auto;
}

.bb-bld-card {
  padding: 12px;
  background: rgba(139, 115, 85, 0.06);
  border: 1px solid rgba(139, 115, 85, 0.15);
  border-radius: 3px;
  cursor: pointer;
  text-align: center;
  transition: all 0.15s;
}

.bb-bld-card:hover {
  background: rgba(184, 155, 104, 0.08);
  border-color: rgba(184, 155, 104, 0.3);
}

.bb-bld-card.selected {
  background: rgba(184, 155, 104, 0.12);
  border-color: var(--gold);
}

.bb-bld-icon { font-size: 28px; }
.bb-bld-name { font-size: 13px; color: var(--gold); margin: 4px 0; letter-spacing: 2px; }
.bb-bld-cost { font-size: 11px; color: var(--text-secondary); }
.bb-bld-effect { font-size: 10px; color: var(--text-dim); }
.bb-bld-count { font-size: 10px; color: var(--jade); margin-top: 4px; }

/* 花费预览 */
.bb-cost-preview {
  margin-top: 12px;
  padding: 10px;
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.15);
  border-radius: 2px;
}

.bb-cost-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 2px 0;
}

.bb-cost-row span:first-child { color: var(--text-dim); }
.bb-cost-val { color: var(--gold); font-weight: bold; }
.bb-cost-val.insufficient { color: #D07070; }

/* 确认页 */
.bb-confirm-info {
  padding: 10px 0;
}

.bb-confirm-info h3 {
  font-size: 14px;
  color: var(--gold);
  letter-spacing: 2px;
  margin-bottom: 10px;
}

.bb-confirm-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px dotted rgba(139, 115, 85, 0.15);
  font-size: 12px;
}

.bb-confirm-row span:first-child { color: var(--text-dim); }
.bb-confirm-row span:last-child { color: var(--text-main); }

.bb-confirm-tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.bb-confirm-tile-tag {
  padding: 2px 8px;
  font-size: 10px;
  background: rgba(184, 155, 104, 0.08);
  border: 1px solid rgba(184, 155, 104, 0.2);
  border-radius: 2px;
  color: var(--text-secondary);
}

.bb-edict-preview {
  margin-top: 12px;
  padding: 10px;
  background: rgba(90, 140, 90, 0.06);
  border: 1px solid rgba(90, 140, 90, 0.2);
  border-radius: 2px;
}

.bb-edict-label {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 2px;
  margin-bottom: 4px;
}

.bb-edict-text {
  font-size: 13px;
  color: #7AB87A;
  font-family: "STKaiti", "KaiTi", serif;
  letter-spacing: 1px;
  line-height: 1.6;
}

/* 底部按钮 */
.bb-step-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0 0;
  border-top: 1px solid rgba(139, 115, 85, 0.15);
  margin-top: auto;
  font-size: 12px;
  color: var(--text-dim);
}

.bb-btn {
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

.bb-btn:hover:not(:disabled) {
  background: rgba(184, 155, 104, 0.12);
  border-color: var(--gold);
  color: var(--gold);
}

.bb-btn.primary {
  background: rgba(184, 155, 104, 0.15);
  border-color: var(--gold);
  color: var(--gold);
}

.bb-btn.primary:hover:not(:disabled) {
  background: rgba(184, 155, 104, 0.25);
}

.bb-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
