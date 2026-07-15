<script setup lang="ts">
/**
 * 外交权谋面板 - 远交近攻、离间、招安、合纵连横策略分析
 */
import { ref, watch, onMounted, computed } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'

const store = useGameStore()
const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

const activeSection = ref<'strategy' | 'discord' | 'coopt' | 'overview'>('strategy')
const loading = ref(false)
const message = ref('')
const resultNarrative = ref('')

// 策略分析
const strategyResult = ref<any>(null)

// 离间
const discordTargetA = ref('')
const discordTargetB = ref('')
const discordType = ref('sow_discord')

// 招安
const cooptTarget = ref('')
const cooptType = ref('offer_title')

// 势力列表（除自己）
const factions = computed(() =>
  Object.values(store.factions || {})
    .filter((f: any) => f.faction_id !== store.playerFactionId && f.is_alive)
)

async function analyzeStrategy() {
  loading.value = true
  try {
    const data = await API.analyzeStrategicPosition(store.playerFactionId)
    strategyResult.value = data
  } catch (e: any) {
    message.value = '策略分析失败'
  } finally { loading.value = false }
}

async function executeDiscord() {
  if (!discordTargetA.value || !discordTargetB.value) {
    message.value = '请选择要离间的两方势力'; return
  }
  loading.value = true
  try {
    const data = await API.sowDiscord({
      schemer_faction: store.playerFactionId,
      target_a: discordTargetA.value,
      target_b: discordTargetB.value,
      discord_type: discordType.value,
    })
    resultNarrative.value = data.narrative || data.message
    message.value = data.message
    if (data.success) {
      discordTargetA.value = ''; discordTargetB.value = ''
    }
  } catch (e: any) {
    message.value = '离间计发动失败'
  } finally { loading.value = false }
}

async function executeCoopt() {
  if (!cooptTarget.value) { message.value = '请选择招安目标'; return }
  loading.value = true
  try {
    const data = await API.attemptCoopt({
      coopter_faction: store.playerFactionId,
      target_faction: cooptTarget.value,
      coopt_type: cooptType.value,
    })
    resultNarrative.value = data.narrative || data.message
    message.value = data.message
    if (data.success) cooptTarget.value = ''
  } catch (e: any) {
    message.value = '招安失败'
  } finally { loading.value = false }
}

function getStanceLabel(s: string) {
  return { war: '⚔️ 交战', neutral: '➖ 中立', truce: '🕊️ 停战', alliance: '🤝 同盟', vassal: '🏰 附庸' }[s] || s
}
function getStrategyLabel(s: string) {
  return {
    far_friend_near_attack: '远交近攻', near_friend_far_attack: '近交远伐',
    balance_of_power: '均势制衡', expansionist: '步步蚕食', isolationist: '闭关自守',
  }[s] || s
}

/** 查询两个势力之间的外交关系（后端 key 使用 '|' 拼接） */
function getRelation(fidA: string, fidB: string): any {
  if (!fidA || !fidB || !store.relations) return null
  const rels = store.relations as Record<string, any>
  const key = [fidA, fidB].sort().join('|')
  return rels[key] || null
}

onMounted(() => { if (props.visible) analyzeStrategy() })
watch(() => props.visible, (v) => { if (v) analyzeStrategy() })
</script>

<template>
  <div v-if="visible" class="diplomacy-overlay" @click.self="emit('close')">
    <div class="diplomacy-panel">
      <div class="panel-header">
        <h3>🕊️ 纵横权谋</h3>
        <button @click="emit('close')" class="close-btn">✕</button>
      </div>

      <div class="section-tabs">
        <button :class="{ active: activeSection === 'strategy' }" @click="activeSection = 'strategy'">📊 大势分析</button>
        <button :class="{ active: activeSection === 'discord' }" @click="activeSection = 'discord'">🕵️ 离间</button>
        <button :class="{ active: activeSection === 'coopt' }" @click="activeSection = 'coopt'">🎯 招安</button>
        <button :class="{ active: activeSection === 'overview' }" @click="activeSection = 'overview'">🌐 列国</button>
      </div>

      <div class="panel-body">
        <!-- 大势分析 -->
        <div v-if="activeSection === 'strategy'" class="tab-content">
          <button @click="analyzeStrategy" class="btn-gold" :disabled="loading">
            {{ loading ? '分析中...' : '🔄 重新分析局势' }}
          </button>
          <div v-if="strategyResult" class="strategy-result">
            <div class="strategy-main">
              <span class="strategy-badge">{{ getStrategyLabel(strategyResult.strategy) }}</span>
              <p>{{ strategyResult.strategy_reasoning }}</p>
            </div>
            <div class="strat-section" v-if="strategyResult.near_threats?.length">
              <h5>⚠️ 近敌 (应优先处理)</h5>
              <div v-for="n in strategyResult.near_threats" :key="n.faction_id" class="relation-row">
                <span class="fname">{{ n.name }}</span>
                <span class="fstance">{{ getStanceLabel(n.stance) }}</span>
                <span class="fpower" :style="{ color: n.power_ratio > 1.5 ? '#f87171' : n.power_ratio < 0.7 ? '#4ade80' : '#fbbf24' }">
                  {{ n.power_ratio > 1.5 ? '强于我方' : n.power_ratio < 0.7 ? '弱于我方' : '实力相当' }}
                </span>
              </div>
            </div>
            <div class="strat-section" v-if="strategyResult.far_potential_allies?.length">
              <h5>🤝 远邦 (可结盟)<button @click="activeSection = 'overview'" class="btn-mini">外交操作</button></h5>
              <div v-for="f in strategyResult.far_potential_allies" :key="f.faction_id" class="relation-row">
                <span class="fname">{{ f.name }}</span>
                <span class="fstance">{{ getStanceLabel(f.stance) }}</span>
                <span class="fdist">距离 {{ f.distance?.toFixed(0) }}km</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 离间 -->
        <div v-if="activeSection === 'discord'" class="tab-content">
          <p class="section-desc">离间敌方同盟，使其内讧。目标双方法须是同盟关系。</p>
          <div class="form-row">
            <label>离间目标A</label>
            <select v-model="discordTargetA" class="form-select">
              <option value="">-- 选择势力 --</option>
              <option v-for="f in factions" :key="f.faction_id" :value="f.faction_id">{{ f.name }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>离间目标B</label>
            <select v-model="discordTargetB" class="form-select">
              <option value="">-- 选择势力 --</option>
              <option v-for="f in factions" :key="f.faction_id" :value="f.faction_id">{{ f.name }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>离间手段</label>
            <select v-model="discordType" class="form-select">
              <option value="sow_discord">离间计 (800两)</option>
              <option value="bribe_official">贿赂官员 (1200两)</option>
              <option value="spread_rumor">散布谣言 (500两)</option>
              <option value="fake_letter">伪造书信 (1000两)</option>
            </select>
          </div>
          <button @click="executeDiscord" class="btn-gold" :disabled="loading">发动离间</button>
          <div v-if="resultNarrative" class="narrative-box">{{ resultNarrative }}</div>
        </div>

        <!-- 招安 -->
        <div v-if="activeSection === 'coopt'" class="tab-content">
          <p class="section-desc">招安他方势力，使其归附。不能对已交战势力使用。</p>
          <div class="form-row">
            <label>招安目标</label>
            <select v-model="cooptTarget" class="form-select">
              <option value="">-- 选择势力 --</option>
              <option v-for="f in factions" :key="f.faction_id" :value="f.faction_id">{{ f.name }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>招安方式</label>
            <select v-model="cooptType" class="form-select">
              <option value="offer_title">许以官爵 → 附庸 (2000两)</option>
              <option value="offer_gold">重金招揽 → 附庸 (5000两)</option>
              <option value="threaten">兵威胁迫 → 附庸 (1000两)</option>
              <option value="marry_alliance">联姻笼络 → 同盟 (3000两)</option>
            </select>
          </div>
          <button @click="executeCoopt" class="btn-gold" :disabled="loading">发动招安</button>
          <div v-if="resultNarrative" class="narrative-box">{{ resultNarrative }}</div>
        </div>

        <!-- 列国关系总览 -->
        <div v-if="activeSection === 'overview'" class="tab-content">
          <div class="faction-list">
            <div v-for="f in factions" :key="f.faction_id" class="faction-row">
              <div class="faction-info">
                <span class="fname">{{ f.name }}</span>
                <span class="ftitle">{{ f.title }}</span>
                <span class="ftags">
                  <span v-for="t in (f.personality_tags || [])" :key="t" class="person-tag">{{ t }}</span>
                </span>
              </div>
              <div class="faction-rel">
                <span class="fstance" :class="'stance-' + (getRelation(store.playerFactionId, f.faction_id)?.stance || 'neutral')">
                  {{ getStanceLabel(getRelation(store.playerFactionId, f.faction_id)?.stance || 'neutral') }}
                </span>
                <span class="fpower">兵{{ f.total_troops || '?' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="message" class="panel-message">{{ message }}</div>
    </div>
  </div>
</template>

<style scoped>
.diplomacy-overlay { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.6); }
.diplomacy-panel { width: 640px; max-height: 80vh; background: linear-gradient(135deg, #1a1a2e, #16213e); border: 1px solid #4a5568; border-radius: 12px; display: flex; flex-direction: column; color: #e2e8f0; font-size: 13px; }
.panel-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid #2d3748; }
.panel-header h3 { margin: 0; font-size: 16px; }
.close-btn { background: none; border: none; color: #a0aec0; font-size: 18px; cursor: pointer; }
.section-tabs { display: flex; border-bottom: 1px solid #2d3748; padding: 0 12px; }
.section-tabs button { padding: 8px 12px; background: none; border: none; color: #a0aec0; cursor: pointer; border-bottom: 2px solid transparent; font-size: 12px; }
.section-tabs button.active { color: #60a5fa; border-bottom-color: #60a5fa; }
.panel-body { flex: 1; overflow-y: auto; padding: 12px; }
.tab-content { min-height: 180px; }
.section-desc { font-size: 12px; color: #94a3b8; margin-bottom: 12px; }

/* 策略 */
.strategy-main { padding: 12px; background: #1e293b; border-radius: 8px; margin-bottom: 12px; }
.strategy-badge { display: inline-block; padding: 4px 12px; background: #fbbf24; color: #1a1a2e; border-radius: 6px; font-weight: bold; font-size: 14px; margin-bottom: 6px; }
.strat-section { margin-bottom: 10px; }
.strat-section h5 { font-size: 13px; color: #94a3b8; margin-bottom: 4px; display: flex; align-items: center; gap: 8px; }
.btn-mini { font-size: 10px; padding: 2px 8px; background: #334155; color: #93c5fd; border: none; border-radius: 4px; cursor: pointer; }

/* 关系行 */
.relation-row, .faction-row { display: flex; align-items: center; padding: 6px 8px; background: #1e293b; border-radius: 4px; margin-bottom: 4px; gap: 8px; font-size: 12px; }
.fname { font-weight: bold; flex: 1; }
.fstance { font-size: 11px; }
.fpower, .fdist { font-size: 11px; color: #94a3b8; }
.faction-info { flex: 1; display: flex; align-items: center; gap: 8px; }
.ftitle { font-size: 11px; color: #64748b; }
.ftags { display: flex; gap: 3px; }
.person-tag { font-size: 9px; background: #312e81; color: #c7d2fe; padding: 1px 4px; border-radius: 2px; }
.stance-war { color: #f87171; }
.stance-alliance { color: #4ade80; }
.stance-vassal { color: #fbbf24; }

/* 表单 */
.form-row { margin-bottom: 8px; }
.form-row label { display: block; font-size: 11px; color: #94a3b8; margin-bottom: 3px; }
.form-select { width: 100%; padding: 6px 8px; background: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 12px; }

.btn-gold { padding: 8px 20px; background: #fbbf24; color: #1a1a2e; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin: 6px 0; }
.btn-gold:disabled { opacity: 0.5; cursor: not-allowed; }

.narrative-box { margin-top: 12px; padding: 10px; background: #1e3a5f; border: 1px solid #3b82f6; border-radius: 6px; font-size: 13px; color: #93c5fd; line-height: 1.6; white-space: pre-line; }

.panel-message { padding: 8px 16px; background: #1e3a5f; color: #93c5fd; font-size: 12px; border-top: 1px solid #2d3748; }
</style>
