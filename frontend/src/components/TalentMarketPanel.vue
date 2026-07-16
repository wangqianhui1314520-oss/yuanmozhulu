<script setup lang="ts">
/**
 * 人才市场面板 - 浏览并招募流浪武将
 */
import { ref, watch, computed } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'

const store = useGameStore()

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

const talents = ref<any[]>([])
const loading = ref(false)
const message = ref('')
const recruitingId = ref<string | null>(null)

watch(() => props.visible, (v) => { if (v) loadTalents() })

async function loadTalents() {
  loading.value = true
  try {
    const data = await API.getTalentMarket()
    talents.value = data.talents || []
  } catch (e: any) {
    console.error('[TalentMarket] 加载失败:', e)
    message.value = '人才市场暂无消息'
  } finally {
    loading.value = false
  }
}

async function recruit(general: any) {
  if (!store.playerFactionId || recruitingId.value) return
  recruitingId.value = general.general_id
  try {
    const result = await API.recruitTalent(store.playerFactionId, general.general_id)
    if (result.data?.success || result.success) {
      message.value = `成功招揽 ${general.name} 入朝！`
      // 从列表中移除
      talents.value = talents.value.filter((t: any) => t.general_id !== general.general_id)
    } else {
      message.value = result.data?.message || result.message || '招揽失败'
    }
  } catch (e: any) {
    message.value = e?.response?.data?.message || '招揽失败'
  } finally {
    recruitingId.value = null
  }
}

const playerTreasury = computed(() => store.playerFaction?.treasury || 0)

function getRarityColor(r: string) {
  return { legendary: '#fbbf24', elite: '#a78bfa', veteran: '#60a5fa', common: '#9ca3af' }[r] || '#9ca3af'
}
function getRarityLabel(r: string) {
  return { legendary: '传奇', elite: '精英', veteran: '老将', common: '普通' }[r] || r
}
function getTacticLabel(t: string) {
  const map: Record<string, string> = {
    shock_cavalry: '铁骑冲锋', ambush_master: '伏击大师', siege_expert: '攻城专家',
    flank_commander: '侧翼包抄', naval_raider: '水战枭雄', fortress_defender: '固若金汤',
    mountain_guard: '山地坚守', river_defender: '水寨固守', last_stand: '背水一战',
    logistics_master: '粮道精通', forced_march: '强行军', field_recruiter: '就地征募',
    fire_attack: '火攻', night_raid: '夜袭', psychological_war: '攻心为上',
    loyal_commander: '忠勇无双', river_crossing: '渡河强袭',
  }
  return map[t] || t
}
</script>

<template>
  <div v-if="visible" class="talent-overlay" @click.self="emit('close')">
    <div class="talent-panel artifact-panel artifact-personnel">
      <div class="panel-header">
        <h3>🏛 人才市场</h3>
        <button class="close-btn" @click="emit('close')">✕</button>
      </div>

      <div class="panel-body">
        <div class="talent-info-bar">
          <span>💰 国库 {{ playerTreasury }} 两</span>
          <span class="cost-hint">每位武将需 500 两</span>
        </div>

        <div class="kv-divider"></div>

        <div v-if="loading" class="loading">寻觅天下英才…</div>
        <div v-else-if="!talents.length" class="empty">
          天下英才皆有所属<br><small>请择日再来打探</small>
        </div>
        <div v-else class="talents-grid">
          <div
            v-for="t in talents" :key="t.general_id"
            class="talent-card"
            :class="{ recruiting: recruitingId === t.general_id }"
          >
            <div class="talent-header">
              <span class="talent-name">{{ t.name }}</span>
              <span class="talent-rarity" :style="{ color: getRarityColor(t.rarity) }">
                {{ getRarityLabel(t.rarity) }}
              </span>
            </div>
            <div class="talent-stats">
              <span class="stat" title="统率">统{{ t.command }}</span>
              <span class="stat" title="武力">武{{ t.might }}</span>
              <span class="stat" title="智谋">智{{ t.intellect }}</span>
              <span class="stat" title="忠诚">忠{{ t.loyalty }}</span>
              <span class="stat" title="魅力">魅{{ t.charisma }}</span>
            </div>
            <div class="talent-profs">
              <span v-if="t.cavalry_proficiency > 70" class="prof-tag">🐴骑</span>
              <span v-if="t.infantry_proficiency > 70" class="prof-tag">⚔️步</span>
              <span v-if="t.archer_proficiency > 70" class="prof-tag">🏹弓</span>
              <span v-if="t.navy_proficiency > 70" class="prof-tag">⛵水</span>
              <span v-if="t.siege_proficiency > 70" class="prof-tag">🏗️攻</span>
            </div>
            <div class="talent-tactics" v-if="t.tactics?.length">
              <span v-for="tc in t.tactics" :key="tc" class="tactic-tag">{{ getTacticLabel(tc) }}</span>
            </div>
            <div class="talent-bio">{{ t.biography }}</div>
            <button
              class="recruit-btn"
              :disabled="playerTreasury < 500 || !!recruitingId"
              @click="recruit(t)"
            >
              {{ recruitingId === t.general_id ? '招揽中…' : playerTreasury < 500 ? '银两不足' : `招揽入朝 · 500两` }}
            </button>
          </div>
        </div>

        <div class="kv-divider"></div>
        <button class="refresh-btn" @click="loadTalents" :disabled="loading">
          {{ loading ? '打探中…' : '🔄 打探英才下落' }}
        </button>
      </div>

      <div v-if="message" class="panel-message">{{ message }}</div>
    </div>
  </div>
</template>

<style scoped>
.talent-overlay {
  position: fixed; inset: 0; z-index: 100;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.6);
}
.talent-panel {
  width: 680px; max-width: 95vw; max-height: 85vh;
  display: flex; flex-direction: column;
  color: #e2e8f0; font-size: 13px;
  box-shadow: inset 3px 0 0 var(--wuxing-wood);
}
.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid #2d3748;
}
.panel-header h3 { margin: 0; font-size: 16px; }
.close-btn { background: none; border: none; color: #a0aec0; font-size: 18px; cursor: pointer; }
.panel-body { flex: 1; overflow-y: auto; padding: 12px 16px; }

.talent-info-bar {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 12px; padding: 4px 0;
}
.talent-info-bar span:first-child { color: #fbbf24; }
.cost-hint { color: #718096; font-size: 11px; }

.kv-divider { height: 1px; background: #2d3748; margin: 8px 0; }

.loading, .empty {
  text-align: center; padding: 40px; color: #718096; font-size: 13px;
}
.empty small { font-size: 11px; color: #4a5568; }

.talents-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }

.talent-card {
  background: #1e293b; border: 1px solid #334155; border-radius: 8px;
  padding: 10px; transition: all 0.2s;
}
.talent-card:hover { border-color: #fbbf24; }
.talent-card.recruiting { opacity: 0.6; }

.talent-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 4px;
}
.talent-name { font-weight: bold; font-size: 14px; }
.talent-rarity { font-size: 10px; font-weight: bold; }

.talent-stats { display: flex; gap: 5px; margin: 4px 0; }
.stat { font-size: 10px; background: #1e293b; padding: 1px 5px; border-radius: 3px; color: #94a3b8; }

.talent-profs { display: flex; gap: 4px; margin: 4px 0; }
.prof-tag { font-size: 12px; }

.talent-tactics { display: flex; flex-wrap: wrap; gap: 3px; margin: 4px 0; }
.tactic-tag { font-size: 10px; background: #312e81; color: #c7d2fe; padding: 1px 5px; border-radius: 3px; }

.talent-bio {
  font-size: 11px; color: #64748b; margin: 4px 0 8px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}

.recruit-btn {
  width: 100%; padding: 6px 0; font-size: 12px;
  background: linear-gradient(180deg, rgba(251,191,36,0.2) 0%, rgba(251,191,36,0.08) 100%);
  border: 1px solid rgba(251,191,36,0.4);
  color: #fbbf24; border-radius: 4px; cursor: pointer;
  transition: all 0.15s;
}
.recruit-btn:hover:not(:disabled) {
  background: linear-gradient(180deg, rgba(251,191,36,0.3) 0%, rgba(251,191,36,0.12) 100%);
}
.recruit-btn:disabled {
  opacity: 0.4; cursor: not-allowed;
}

.refresh-btn {
  width: 100%; padding: 8px; font-size: 12px;
  background: transparent; border: 1px solid #4a5568;
  color: #a0aec0; border-radius: 4px; cursor: pointer;
  transition: all 0.15s;
}
.refresh-btn:hover:not(:disabled) { border-color: #718096; color: #e2e8f0; }
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.panel-message {
  padding: 8px 16px; background: #1e3a5f; color: #93c5fd;
  font-size: 12px; border-top: 1px solid #2d3748;
}
</style>
