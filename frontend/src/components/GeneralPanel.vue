<script setup lang="ts">
/**
 * 武将面板 - 管理武将、军团编制、委任自主作战
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'
import GeneralChatPanel from '@/components/GeneralChatPanel.vue'

const store = useGameStore()

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: []; openTalentMarket: [] }>()

// 标签页
const activeTab = ref<'generals' | 'legions' | 'dispatch' | 'wence'>('generals')

// 问策聊兵
const showGeneralChat = ref(false)

// 武将数据
const generals = ref<any[]>([])
const legions = ref<any[]>([])
const selectedGeneral = ref<any>(null)
const selectedLegion = ref<any>(null)
const loading = ref(false)
const message = ref('')

// 新建军团
const showCreateLegion = ref(false)
const newLegionName = ref('')
const newLegionFormation = ref('balanced')

// 委任设置
const autonomousEnabled = ref(false)
const autoPriority = ref('defensive')

// 兵种编成 (新建军团)
const unitComposition = ref({
  infantry: 0,
  cavalry: 0,
  archer: 0,
  spearman: 0,
  navy: 0,
  siege: 0,
})

onMounted(() => { if (props.visible) loadData() })
watch(() => props.visible, (v) => { if (v) loadData() })

async function loadData() {
  loading.value = true
  try {
    const pf = store.playerFaction
    if (!pf || !store.playerFactionId) return
    const fid = pf.faction_id || store.playerFactionId
    const [genData, legData] = await Promise.all([
      API.getFactionGenerals(fid).catch(() => ({ generals: [] })),
      API.getFactionLegions(fid).catch(() => ({ legions: [] })),
    ])
    generals.value = genData.generals || []
    legions.value = legData.legions || []
  } catch (e) {
    console.error(e)
  } finally { loading.value = false }
}

async function createLegion() {
  if (!newLegionName.value.trim()) { message.value = '请输入军团名称'; return }
  const total = Object.values(unitComposition.value).reduce((a: number, b: number) => a + b, 0)
  if (total <= 0) { message.value = '至少编入一个兵种'; return }
  if (!selectedGeneral.value) { message.value = '请选择主将'; return }

  loading.value = true
  try {
    const pf = store.playerFaction
    const fid = pf?.faction_id || store.playerFactionId
    const data = await API.createLegion({
      name: newLegionName.value,
      faction_id: fid,
      commander_id: selectedGeneral.value.general_id,
      unit_composition: unitComposition.value,
      formation: newLegionFormation.value,
    })
    message.value = `军团"${newLegionName.value}"创建成功`
    showCreateLegion.value = false
    newLegionName.value = ''
    unitComposition.value = { infantry: 0, cavalry: 0, archer: 0, spearman: 0, navy: 0, siege: 0 }
    await loadData()
  } catch (e: any) {
    message.value = e?.response?.data?.message || '创建失败'
  } finally { loading.value = false }
}

async function toggleAutonomous() {
  if (!selectedLegion.value) return
  try {
    await API.setLegionAutonomous({
      legion_id: selectedLegion.value.legion_id,
      enabled: autonomousEnabled.value,
      priority: autoPriority.value,
    })
    message.value = autonomousEnabled.value ? '军团已设为自主作战' : '军团已取消委任'
    await loadData()
  } catch (e: any) {
    message.value = '设置失败'
  }
}

async function saveDispatch() {
  if (!selectedGeneral.value || !selectedLegion.value) { message.value = '请选择武将和军团'; return }
  try {
    const data = await API.assignGeneralToLegion({
      general_id: selectedGeneral.value.general_id,
      legion_id: selectedLegion.value.legion_id,
    })
    message.value = data.message || `${selectedGeneral.value.name}已配属至${selectedLegion.value.name}`
    await loadData()
  } catch (e: any) { message.value = e?.response?.data?.message || '分配失败' }
}

async function disbandLegion(legionId: string) {
  if (!confirm('确定要解散该军团吗？主将和副将将返回待命状态。')) return
  try {
    const data = await API.disbandLegion({ legion_id: legionId })
    message.value = data.message || '军团已解散'
    if (selectedLegion.value?.legion_id === legionId) selectedLegion.value = null
    await loadData()
  } catch (e: any) { message.value = '解散失败' }
}

async function removeSubcommander(legionId: string, generalId: string) {
  try {
    await API.removeSubcommander({ legion_id: legionId, general_id: generalId })
    message.value = '副将已移除'
    await loadData()
  } catch (e: any) { message.value = '移除失败' }
}

const availableGenerals = computed(() => generals.value.filter((g: any) => g.alive && !g.is_assigned))
const activeLegions = computed(() => legions.value.filter((l: any) => l.total_troops > 0))

const unitTypes = [
  { key: 'infantry', label: '步兵', icon: '⚔️', color: '#6366f1' },
  { key: 'cavalry', label: '骑兵', icon: '🐴', color: '#f59e0b' },
  { key: 'archer', label: '弓兵', icon: '🏹', color: '#10b981' },
  { key: 'spearman', label: '枪兵', icon: '🔱', color: '#ef4444' },
  { key: 'navy', label: '水军', icon: '⛵', color: '#06b6d4' },
  { key: 'siege', label: '攻城', icon: '🏗️', color: '#8b5cf6' },
]

function getRarityColor(r: string) {
  return { legendary: '#fbbf24', elite: '#a78bfa', veteran: '#60a5fa', common: '#9ca3af' }[r] || '#9ca3af'
}
function getRarityLabel(r: string) {
  return { legendary: '传奇', elite: '精英', veteran: '老将', common: '普通' }[r] || r
}
function openTalentMarket() {
  emit('close')
  store.togglePanel('talent-market' as any)
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
  <div v-if="visible" class="general-panel-overlay" @click.self="emit('close')">
    <div class="general-panel">
      <div class="panel-header">
        <h3>🏯 武将统御</h3>
        <button @click="emit('close')" class="close-btn">✕</button>
      </div>

      <div class="tab-bar">
        <button :class="{ active: activeTab === 'generals' }" @click="activeTab = 'generals'">👤 武将名录</button>
        <button :class="{ active: activeTab === 'legions' }" @click="activeTab = 'legions'">🏴 军团编制</button>
        <button :class="{ active: activeTab === 'dispatch' }" @click="activeTab = 'dispatch'">📋 调兵遣将</button>
        <button :class="{ active: activeTab === 'wence' }" @click="activeTab = 'wence'">💬 问策聊兵</button>
      </div>

      <div class="panel-body">
        <!-- 武将名录 -->
        <div v-if="activeTab === 'generals'" class="tab-content">
          <div v-if="loading" class="loading">加载中...</div>
          <div v-else-if="!generals.length" class="empty">
            暂无武将<br>
            <button class="goto-talent-btn" @click="openTalentMarket">🏛 前往人才市场</button>
          </div>
          <div v-else class="generals-grid">
            <div
              v-for="g in generals" :key="g.general_id"
              class="general-card"
              :class="{ selected: selectedGeneral?.general_id === g.general_id, dead: !g.alive }"
              @click="selectedGeneral = g"
            >
              <div class="gen-header">
                <span class="gen-name">{{ g.name }}</span>
                <span class="gen-rarity" :style="{ color: getRarityColor(g.rarity) }">
                  {{ getRarityLabel(g.rarity) }}
                </span>
              </div>
              <div class="gen-stats">
                <span class="stat">统{{ g.command }}</span>
                <span class="stat">武{{ g.might }}</span>
                <span class="stat">智{{ g.intellect }}</span>
                <span class="stat">忠{{ g.loyalty }}</span>
                <span class="stat">魅{{ g.charisma }}</span>
              </div>
              <div class="gen-tactics" v-if="g.tactics?.length">
                <span v-for="t in g.tactics" :key="t" class="tactic-tag">{{ getTacticLabel(t) }}</span>
              </div>
              <div class="gen-meta">
                <span v-if="g.is_assigned" class="tag assigned">已出任</span>
                <span v-else class="tag idle">待命</span>
                <span class="gen-personality">{{ g.personality }}</span>
              </div>
            </div>
          </div>
          <!-- 武将详情 -->
          <div v-if="selectedGeneral" class="detail-panel">
            <h4>{{ selectedGeneral.name }}</h4>
            <p class="bio">{{ selectedGeneral.biography }}</p>
            <div class="proficiency-bars">
              <div v-for="ut in unitTypes" :key="ut.key" class="prof-row">
                <span>{{ ut.icon }} {{ ut.label }}</span>
                <div class="bar-bg"><div class="bar-fill" :style="{ width: (selectedGeneral[ut.key + '_proficiency'] || 50) + '%', backgroundColor: ut.color }" /></div>
                <span class="val">{{ selectedGeneral[ut.key + '_proficiency'] || 50 }}</span>
              </div>
            </div>
            <div class="detail-stats">
              <div>战绩：{{ selectedGeneral.battles_won }}/{{ selectedGeneral.battles_fought }} 胜，歼敌 {{ selectedGeneral.troops_killed }}</div>
              <div>攻城：{{ selectedGeneral.cities_captured }} 座</div>
            </div>
          </div>
        </div>

        <!-- 军团编制 -->
        <div v-if="activeTab === 'legions'" class="tab-content">
          <div class="action-bar">
            <button @click="showCreateLegion = true" :disabled="!availableGenerals.length" class="btn-primary">
              + 新建军团
            </button>
          </div>
          <div v-if="loading" class="loading">加载中...</div>
          <div v-else-if="!legions.length" class="empty">暂无军团，请先创建</div>
          <div v-else class="legion-list">
            <div
              v-for="l in legions" :key="l.legion_id"
              class="legion-card"
              :class="{ selected: selectedLegion?.legion_id === l.legion_id, autonomous: l.is_autonomous }"
              @click="selectedLegion = l"
            >
              <div class="leg-header">
                <span class="leg-name">{{ l.name }}</span>
                <span class="leg-actions">
                  <span v-if="l.is_autonomous" class="auto-badge">🤖 委任</span>
                  <button class="disband-btn" @click.stop="disbandLegion(l.legion_id)" title="解散军团">✕</button>
                </span>
              </div>
              <div class="leg-info">
                兵力 {{ l.total_troops }} | 士气 {{ l.morale }}
              </div>
              <div class="leg-composition">
                <span v-for="(count, utype) in l.unit_composition" :key="utype" class="unit-count" v-show="count > 0">
                  {{ unitTypes.find(u => u.key === utype)?.icon }} {{ count }}
                </span>
              </div>
              <div class="leg-meta">
                主将：{{ generals.find((g: any) => g.general_id === l.commander_id)?.name || '空缺' }}
                | 阵型：{{ l.formation }}
                | 驻地：{{ l.current_tile || '未部署' }}
              </div>
              <div v-if="l.sub_commander_ids?.length" class="leg-subcommanders">
                副将：
                <span v-for="sid in l.sub_commander_ids" :key="sid" class="sub-tag">
                  {{ generals.find((g: any) => g.general_id === sid)?.name || sid }}
                  <button class="sub-remove" @click.stop="removeSubcommander(l.legion_id, sid)" title="移除副将">✕</button>
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 调兵遣将 -->
        <div v-if="activeTab === 'dispatch'" class="tab-content">
          <div class="dispatch-grid">
            <div class="dispatch-col">
              <h4>武将</h4>
              <select v-model="selectedGeneral" class="dispatch-select">
                <option :value="null">-- 选择武将 --</option>
                <option v-for="g in availableGenerals" :key="g.general_id" :value="g">
                  {{ g.name }} [{{ getRarityLabel(g.rarity) }}] 统{{ g.command }}
                </option>
              </select>
              <div v-if="selectedGeneral" class="gen-mini">
                <div class="gen-stats">
                  <span>统{{ selectedGeneral.command }}</span>
                  <span>武{{ selectedGeneral.might }}</span>
                  <span>智{{ selectedGeneral.intellect }}</span>
                  <span>忠{{ selectedGeneral.loyalty }}</span>
                </div>
                <div class="gen-tactics" v-if="selectedGeneral.tactics?.length">
                  <span v-for="t in selectedGeneral.tactics" :key="t" class="tactic-tag">{{ getTacticLabel(t) }}</span>
                </div>
              </div>
            </div>
            <div class="dispatch-arrow">→</div>
            <div class="dispatch-col">
              <h4>军团</h4>
              <select v-model="selectedLegion" class="dispatch-select">
                <option :value="null">-- 选择军团 --</option>
                <option v-for="l in legions" :key="l.legion_id" :value="l">
                  {{ l.name }} ({{ l.total_troops }}兵)
                </option>
              </select>
            </div>
          </div>
          <button @click="saveDispatch" class="btn-primary dispatch-btn" :disabled="!selectedGeneral || !selectedLegion">
            确认分配
          </button>

          <!-- 委任设置 -->
          <div v-if="selectedLegion" class="autonomous-section">
            <h4>🤖 委任自主作战</h4>
            <label class="toggle-label">
              <input type="checkbox" v-model="autonomousEnabled" @change="toggleAutonomous" />
              启用军团委任（AI自动指挥）
            </label>
            <div v-if="autonomousEnabled" class="auto-settings">
              <label>作战优先级：
                <select v-model="autoPriority">
                  <option value="defensive">防守优先</option>
                  <option value="offensive">进攻优先</option>
                  <option value="raid">劫掠优先</option>
                  <option value="support">支援盟友</option>
                </select>
              </label>
              <button @click="toggleAutonomous" class="btn-secondary">更新设置</button>
            </div>
          </div>
        </div>

        <!-- 问策聊兵 -->
        <div v-if="activeTab === 'wence'" class="tab-content wence-tab">
          <div class="wence-intro">
            <div class="wence-intro-icon">⚔️💬</div>
            <h4>将台问策</h4>
            <p class="wence-intro-text">
              每位武将皆接入AI智能体，拥有独立人格、行军经验与战术偏好。<br/>
              可单独向某位将军问策，亦可召开军议与众将共商大计。
            </p>
            <button class="wence-enter-btn" @click="showGeneralChat = true">
              🏯 进入将台
            </button>
          </div>
          <GeneralChatPanel :visible="showGeneralChat" @close="showGeneralChat = false" />
        </div>

        <!-- 新建军团弹窗 -->
        <div v-if="showCreateLegion" class="modal-mask" @click.self="showCreateLegion = false">
          <div class="modal-content">
            <h4>🏴 组建军团</h4>
            <div class="form-group">
              <label>军团名称</label>
              <input v-model="newLegionName" placeholder="如：神机营 / 铁骑营" class="form-input" />
            </div>
            <div class="form-group">
              <label>主将</label>
              <select v-model="selectedGeneral" class="form-select">
                <option :value="null">-- 选择主将 --</option>
                <option v-for="g in availableGenerals" :key="g.general_id" :value="g">{{ g.name }} ({{ getRarityLabel(g.rarity) }})</option>
              </select>
            </div>
            <div class="form-group">
              <label>阵型</label>
              <select v-model="newLegionFormation" class="form-select">
                <option value="balanced">均衡阵</option>
                <option value="aggressive">锋矢阵 (+攻)</option>
                <option value="defensive">方圆阵 (+防)</option>
                <option value="mobile">长蛇阵 (+速)</option>
              </select>
            </div>
            <div class="form-group">
              <label>兵种编成</label>
              <div class="unit-grid">
                <div v-for="ut in unitTypes" :key="ut.key" class="unit-row">
                  <span class="unit-label">{{ ut.icon }} {{ ut.label }}</span>
                  <input type="number" v-model.number="unitComposition[ut.key]" min="0" max="9999" class="unit-input" />
                </div>
              </div>
            </div>
            <div class="modal-actions">
              <button @click="createLegion" class="btn-primary">组建</button>
              <button @click="showCreateLegion = false" class="btn-secondary">取消</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="message" class="panel-message">{{ message }}</div>
    </div>
  </div>
</template>

<style scoped>
.general-panel-overlay {
  position: fixed; inset: 0; z-index: 100;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.6);
}
.general-panel {
  width: 720px; max-height: 85vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border: 1px solid #4a5568; border-radius: 12px;
  display: flex; flex-direction: column;
  color: #e2e8f0; font-size: 13px;
}
.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid #2d3748;
}
.panel-header h3 { margin: 0; font-size: 16px; }
.close-btn { background: none; border: none; color: #a0aec0; font-size: 18px; cursor: pointer; }
.tab-bar {
  display: flex; border-bottom: 1px solid #2d3748;
  padding: 0 12px;
}
.tab-bar button {
  padding: 8px 16px; background: none; border: none; color: #a0aec0;
  cursor: pointer; border-bottom: 2px solid transparent; font-size: 13px;
}
.tab-bar button.active { color: #fbbf24; border-bottom-color: #fbbf24; }
.panel-body { flex: 1; overflow-y: auto; padding: 12px; }
.tab-content { min-height: 200px; }
.loading, .empty { text-align: center; padding: 40px; color: #718096; }
.goto-talent-btn {
  margin-top: 10px; padding: 6px 18px;
  font-size: 12px; font-family: "STKaiti","KaiTi",serif;
  background: linear-gradient(180deg, rgba(251,191,36,0.2) 0%, rgba(251,191,36,0.08) 100%);
  border: 1px solid rgba(251,191,36,0.4); color: #fbbf24;
  border-radius: 4px; cursor: pointer; letter-spacing: 2px;
  transition: all 0.15s;
}
.goto-talent-btn:hover {
  background: linear-gradient(180deg, rgba(251,191,36,0.3) 0%, rgba(251,191,36,0.12) 100%);
}

/* 武将卡片 */
.generals-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.general-card {
  background: #1e293b; border: 1px solid #334155; border-radius: 8px;
  padding: 8px; cursor: pointer; transition: all 0.2s;
}
.general-card:hover { border-color: #fbbf24; }
.general-card.selected { border-color: #fbbf24; box-shadow: 0 0 8px rgba(251,191,36,0.3); }
.general-card.dead { opacity: 0.5; }
.gen-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.gen-name { font-weight: bold; font-size: 14px; }
.gen-stats { display: flex; gap: 6px; font-size: 11px; }
.stat { background: #1e293b; padding: 1px 4px; border-radius: 3px; }
.gen-tactics { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px; }
.tactic-tag { font-size: 10px; background: #312e81; color: #c7d2fe; padding: 1px 5px; border-radius: 3px; }
.gen-meta { display: flex; gap: 6px; margin-top: 4px; font-size: 11px; }
.tag { padding: 1px 6px; border-radius: 3px; font-size: 10px; }
.tag.assigned { background: #065f46; color: #6ee7b7; }
.tag.idle { background: #4a5568; color: #a0aec0; }

/* 详情面板 */
.detail-panel { margin-top: 12px; padding: 12px; background: #1e293b; border-radius: 8px; }
.detail-panel h4 { margin: 0 0 4px; }
.bio { font-size: 12px; color: #94a3b8; margin: 4px 0 8px; }
.proficiency-bars { display: flex; flex-direction: column; gap: 3px; }
.prof-row { display: flex; align-items: center; gap: 6px; font-size: 11px; }
.prof-row span:first-child { width: 56px; }
.bar-bg { flex: 1; height: 8px; background: #334155; border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
.val { width: 24px; text-align: right; }

/* 军团 */
.action-bar { margin-bottom: 8px; }
.legion-list { display: flex; flex-direction: column; gap: 6px; }
.legion-card {
  background: #1e293b; border: 1px solid #334155; border-radius: 8px;
  padding: 10px; cursor: pointer; font-size: 12px;
}
.legion-card:hover { border-color: #fbbf24; }
.legion-card.selected { border-color: #fbbf24; }
.legion-card.autonomous { border-left: 3px solid #10b981; }
.leg-header { display: flex; justify-content: space-between; align-items: center; }
.leg-name { font-weight: bold; font-size: 14px; }
.leg-actions { display: flex; align-items: center; gap: 6px; }
.auto-badge { font-size: 10px; background: #065f46; color: #6ee7b7; padding: 2px 6px; border-radius: 4px; }
.disband-btn {
  width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;
  background: rgba(220, 38, 38, 0.15); border: 1px solid rgba(220, 38, 38, 0.25);
  color: #f87171; font-size: 9px; cursor: pointer; border-radius: 50%; padding: 0;
  transition: all 0.15s;
}
.disband-btn:hover { background: rgba(220, 38, 38, 0.3); color: #ef4444; }
.leg-info { color: #94a3b8; margin: 2px 0; }
.leg-composition { display: flex; gap: 6px; margin: 4px 0; }
.unit-count { font-size: 11px; }
.leg-meta { font-size: 11px; color: #64748b; }
.leg-subcommanders { font-size: 11px; color: #94a3b8; margin-top: 4px; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.sub-tag {
  display: inline-flex; align-items: center; gap: 3px;
  background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.2);
  color: #a5b4fc; padding: 1px 6px; border-radius: 3px; font-size: 10px;
}
.sub-remove {
  width: 12px; height: 12px; display: inline-flex; align-items: center; justify-content: center;
  background: transparent; border: none; color: rgba(160, 100, 60, 0.5);
  font-size: 8px; cursor: pointer; border-radius: 50%; padding: 0;
}
.sub-remove:hover { color: #f87171; background: rgba(220, 38, 38, 0.12); }

/* 调兵遣将 */
.dispatch-grid { display: flex; gap: 12px; align-items: flex-start; }
.dispatch-col { flex: 1; }
.dispatch-arrow { font-size: 24px; padding-top: 24px; }
.dispatch-select { width: 100%; padding: 8px; background: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #e2e8f0; }
.gen-mini { margin-top: 8px; padding: 8px; background: #1e293b; border-radius: 6px; }
.dispatch-btn { margin-top: 12px; width: 100%; }

/* 委任设置 */
.autonomous-section { margin-top: 16px; padding: 12px; background: #1e293b; border-radius: 8px; }
.toggle-label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.auto-settings { margin-top: 8px; }
.auto-settings select { padding: 4px 8px; background: #334155; border: 1px solid #4a5568; border-radius: 4px; color: #e2e8f0; margin: 0 6px; }

/* 表单 */
.modal-mask { position: fixed; inset: 0; z-index: 110; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
.modal-content { background: #1a1a2e; border: 1px solid #4a5568; border-radius: 12px; padding: 20px; width: 500px; max-height: 80vh; overflow-y: auto; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; margin-bottom: 4px; font-size: 12px; color: #94a3b8; }
.form-input, .form-select { width: 100%; padding: 8px; background: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #e2e8f0; }
.unit-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
.unit-row { display: flex; align-items: center; gap: 6px; }
.unit-label { width: 56px; font-size: 12px; }
.unit-input { width: 72px; padding: 4px; background: #1e293b; border: 1px solid #334155; border-radius: 4px; color: #e2e8f0; text-align: center; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

.btn-primary { padding: 8px 20px; background: #fbbf24; color: #1a1a2e; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { padding: 8px 16px; background: #334155; color: #e2e8f0; border: none; border-radius: 6px; cursor: pointer; }

.panel-message { padding: 8px 16px; background: #1e3a5f; color: #93c5fd; font-size: 12px; border-top: 1px solid #2d3748; }

/* 问策聊兵 */
.wence-tab { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 300px; }
.wence-intro { text-align: center; padding: 32px 20px; }
.wence-intro-icon { font-size: 48px; margin-bottom: 12px; }
.wence-intro h4 {
  font-size: 18px; color: #D07050; font-family: "STKaiti","KaiTi",serif;
  letter-spacing: 3px; margin: 0 0 8px;
}
.wence-intro-text { font-size: 13px; color: #94a3b8; line-height: 1.8; margin: 0 0 20px; }
.wence-enter-btn {
  padding: 12px 32px; font-size: 16px; font-family: "STKaiti","KaiTi",serif;
  background: linear-gradient(180deg, #D07050 0%, #A05030 100%);
  color: #fff; border: 1px solid #D07050; border-radius: 6px;
  cursor: pointer; letter-spacing: 3px; transition: all 0.2s;
}
.wence-enter-btn:hover {
  background: linear-gradient(180deg, #E08060 0%, #B05838 100%);
  box-shadow: 0 4px 16px rgba(208,112,80,0.3);
}
</style>
