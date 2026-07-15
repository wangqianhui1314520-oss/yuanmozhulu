<template>
  <div
    v-if="visible"
    class="war-panel-overlay"
    :style="overlayStyle"
    @click.self="$emit('close')"
  >
    <div class="war-panel glass-card">
      <!-- 头部 -->
      <div class="panel-header">
        <h2>天下兵戈</h2>
        <span class="war-count">{{ wars.length }} 场战事</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <!-- 战争列表 -->
      <div class="war-list" v-if="wars.length">
        <div
          v-for="war in wars"
          :key="war.war_id"
          class="war-card"
          :class="warAdvantageClass(war)"
          @click="selectWar(war)"
        >
          <!-- 对战双方 -->
          <div class="war-header">
            <span class="attacker-name">{{ war.attacker_name }}</span>
            <span class="vs-badge" :class="warAdvantageClass(war)">⚔</span>
            <span class="defender-name">{{ war.defender_name }}</span>
          </div>

          <!-- CB 标签 -->
          <div class="war-meta">
            <span class="cb-tag">{{ war.casus_belli_name || war.casus_belli || '征服' }}</span>
            <span class="round-tag">第{{ war.declared_round }}回合</span>
          </div>

          <!-- 战争分数条 -->
          <div class="score-section" v-if="war.war_score">
            <div class="score-bar-track">
              <div
                class="score-bar-fill"
                :class="warAdvantageClass(war)"
                :style="{ width: warScoreWidth(war) }"
              ></div>
              <div class="score-indicator" :style="{ left: warScoreIndicatorLeft(war) }">
                {{ war.war_score.war_score > 0 ? '+' : '' }}{{ war.war_score.war_score }}%
              </div>
            </div>
            <div class="score-labels">
              <span class="score-neg">-100</span>
              <span class="score-zero">0</span>
              <span class="score-pos">+100</span>
            </div>
            <!-- 态势文字 -->
            <div class="advantage-text" :class="warAdvantageClass(war)">
              {{ advantageText(war) }}
            </div>
          </div>

          <!-- 详情扩展 -->
          <div v-if="war._expanded" class="war-detail">
            <div class="score-breakdown" v-if="war.war_score?.breakdown">
              <div class="breakdown-item">
                <span class="label">⚔ 战斗</span>
                <span class="value">{{ war.war_score.breakdown.battle > 0 ? '+' : '' }}{{ war.war_score.breakdown.battle }}</span>
              </div>
              <div class="breakdown-item">
                <span class="label">🏴 占领</span>
                <span class="value">{{ war.war_score.breakdown.occupation > 0 ? '+' : '' }}{{ war.war_score.breakdown.occupation }}</span>
              </div>
              <div class="breakdown-item">
                <span class="label">⏳ 持续</span>
                <span class="value">{{ war.war_score.breakdown.ticking > 0 ? '+' : '' }}{{ war.war_score.breakdown.ticking }}</span>
              </div>
            </div>

            <div class="allies-row" v-if="war.allies">
              <span v-if="war.allies.attacker?.length">
                {{ war.attacker_name }}盟: {{ war.allies.attacker.join('、') }}
              </span>
              <span v-if="war.allies.defender?.length">
                | {{ war.defender_name }}盟: {{ war.allies.defender.join('、') }}
              </span>
            </div>

            <!-- 操作按钮 -->
            <div class="war-actions" v-if="isPlayerWar(war)">
              <button
                class="action-btn peace-btn"
                @click.stop="openPeace(war)"
                :disabled="!war.war_score?.can_enforce_demands && Math.abs(war.war_score?.war_score || 0) < 50"
              >
                议和谈判
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div class="empty-state" v-else>
        <span class="empty-icon">☮</span>
        <p>天下太平，暂无战事</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'openPeace', war: any): void
}>()

const store = useGameStore()
const wars = ref<any[]>([])
const selectedWarId = ref('')
let pollTimer: any = null

onMounted(() => { if (props.visible) fetchWars() })
onUnmounted(() => { clearInterval(pollTimer) })

// 每 10 秒轮询（仅在面板可见时）
import { watch } from 'vue'
watch(() => props.visible, (v) => {
  if (v) { fetchWars(); pollTimer = setInterval(fetchWars, 10000) }
  else { clearInterval(pollTimer) }
})

async function fetchWars() {
  try {
    const data = await API.getActiveWars()
    wars.value = (data?.wars || []).map((w: any) => ({
      ...w,
      _expanded: w.war_id === selectedWarId.value,
    }))
  } catch { /* 静默失败 */ }
}

function selectWar(war: any) {
  selectedWarId.value = war.war_id === selectedWarId.value ? '' : war.war_id
  wars.value.forEach(w => w._expanded = w.war_id === selectedWarId.value)
}

function openPeace(war: any) {
  emit('openPeace', war)
}

function isPlayerWar(war: any): boolean {
  return war.attacker === store.playerFactionId || war.defender === store.playerFactionId
}

function warAdvantageClass(war: any): string {
  const adv = war.war_score?.advantage || ''
  if (adv.includes('attacker')) return 'attacker-advantage'
  if (adv.includes('defender')) return 'defender-advantage'
  return 'stalemate'
}

function warScoreWidth(war: any): string {
  const score = war.war_score?.war_score || 0
  return `${Math.abs(score)}%`
}

function warScoreIndicatorLeft(war: any): string {
  const score = war.war_score?.war_score || 0
  return `${Math.max(0, Math.min(100, score + 100) / 2)}%`
}

function advantageText(war: any): string {
  const advantage = war.war_score?.advantage || ''
  const map: Record<string, string> = {
    attacker_crushing: `${war.attacker_name} 碾压之势`,
    attacker_winning: `${war.attacker_name} 占据上风`,
    attacker_slight: `${war.attacker_name} 小有优势`,
    stalemate: '战局胶着',
    defender_slight: `${war.defender_name} 小有优势`,
    defender_winning: `${war.defender_name} 占据上风`,
    defender_crushing: `${war.defender_name} 碾压之势`,
  }
  return map[advantage] || advantage
}

// 战场图映射：4张AI生成的战场场景用于面板背景
const BATTLEFIELD_BG_MAP: Record<string, string> = {
  plain: '/assets/factions/ai_generated/ai_battle_plain.png',
  naval: '/assets/factions/ai_generated/ai_battle_naval.png',
  siege: '/assets/factions/ai_generated/ai_battle_siege.png',
  pass: '/assets/factions/ai_generated/ai_battle_pass.png',
}
const BATTLEFIELD_KEYS = Object.keys(BATTLEFIELD_BG_MAP)

function battlefieldBgForWar(war: any): string {
  const type = war?.battlefield_type || war?.terrain || ''
  if (type === 'naval' || type === 'water' || type === 'coastal') return BATTLEFIELD_BG_MAP.naval
  if (type === 'siege' || type === 'fortress' || war?.is_siege) return BATTLEFIELD_BG_MAP.siege
  if (type === 'pass' || type === 'mountain') return BATTLEFIELD_BG_MAP.pass
  const hash = (war?.war_id || '').split('').reduce((s: number, c: string) => s + c.charCodeAt(0), 0)
  return BATTLEFIELD_BG_MAP[BATTLEFIELD_KEYS[hash % BATTLEFIELD_KEYS.length]]
}

const battlefieldBg = computed(() => {
  const war = wars.value.find((w: any) => w._expanded) || wars.value[0]
  return war ? battlefieldBgForWar(war) : BATTLEFIELD_BG_MAP.plain
})

const overlayStyle = computed(() => ({
  backgroundImage: `url(${battlefieldBg.value})`,
  backgroundSize: 'cover',
  backgroundPosition: 'center',
  backgroundBlendMode: 'overlay' as const,
}))
</script>

<style scoped>
.war-panel-overlay {
  position: fixed; inset: 0; z-index: 2000;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0, 0, 0, 0.5);
}
.war-panel {
  width: 520px; max-height: 80vh; overflow-y: auto;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  border: 1px solid rgba(255, 200, 60, 0.25);
  border-radius: 12px; padding: 20px;
  color: #e0d5c1;
}
.panel-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
  border-bottom: 1px solid rgba(255, 200, 60, 0.15); padding-bottom: 12px;
}
.panel-header h2 { margin: 0; font-size: 18px; color: #ffc83d; }
.war-count { font-size: 12px; color: #8a8; margin-left: auto; }
.close-btn {
  background: none; border: none; color: #888; cursor: pointer;
  font-size: 18px; padding: 4px 8px; border-radius: 4px;
}
.close-btn:hover { color: #fff; background: rgba(255,255,255,0.1); }

.war-list { display: flex; flex-direction: column; gap: 10px; }
.war-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px; padding: 12px;
  cursor: pointer; transition: all 0.2s;
}
.war-card:hover { background: rgba(255, 255, 255, 0.08); }
.war-card.attacker-advantage { border-left: 3px solid #e74c3c; }
.war-card.defender-advantage { border-left: 3px solid #3498db; }
.war-card.stalemate { border-left: 3px solid #95a5a6; }

.war-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.attacker-name { color: #e74c3c; font-weight: bold; }
.defender-name { color: #3498db; font-weight: bold; }
.vs-badge { font-size: 14px; }
.vs-badge.attacker-advantage { color: #e74c3c; }
.vs-badge.defender-advantage { color: #3498db; }
.vs-badge.stalemate { color: #95a5a6; }

.war-meta { display: flex; gap: 8px; font-size: 11px; margin-bottom: 8px; }
.cb-tag {
  background: rgba(255, 200, 60, 0.15); color: #ffc83d;
  padding: 2px 6px; border-radius: 3px;
}
.round-tag { color: #8a8; }

/* 战争分数条 */
.score-section { margin-top: 4px; }
.score-bar-track {
  position: relative; height: 8px;
  background: linear-gradient(to right, #3498db, #95a5a6, #e74c3c);
  border-radius: 4px; margin: 4px 0;
  overflow: visible;
}
.score-bar-fill {
  position: absolute; top: 0; height: 100%;
  border-radius: 4px; transition: width 0.5s ease;
}
.score-bar-fill.attacker-advantage {
  right: 0; background: rgba(231, 76, 60, 0.4);
}
.score-bar-fill.defender-advantage {
  left: 0; background: rgba(52, 152, 219, 0.4);
}
.score-indicator {
  position: absolute; top: -4px; transform: translateX(-50%);
  font-size: 10px; font-weight: bold; color: #fff;
  background: rgba(0,0,0,0.7); padding: 1px 5px; border-radius: 3px;
  transition: left 0.5s ease;
}
.score-labels { display: flex; justify-content: space-between; font-size: 10px; color: #666; }
.advantage-text { font-size: 12px; text-align: center; margin-top: 4px; font-style: italic; }
.advantage-text.attacker-advantage { color: #e74c3c; }
.advantage-text.defender-advantage { color: #3498db; }
.advantage-text.stalemate { color: #95a5a6; }

/* 详情 */
.war-detail { margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.08); }
.score-breakdown { display: flex; gap: 16px; margin-bottom: 8px; }
.breakdown-item { display: flex; flex-direction: column; align-items: center; font-size: 11px; }
.breakdown-item .label { color: #8a8; }
.breakdown-item .value { color: #e0d5c1; font-weight: bold; }
.allies-row { font-size: 11px; color: #8a8; margin-bottom: 8px; }
.war-actions { display: flex; gap: 8px; }
.action-btn {
  padding: 6px 16px; border: 1px solid rgba(255,255,255,0.15);
  border-radius: 6px; background: rgba(255,255,255,0.05); color: #e0d5c1;
  cursor: pointer; font-size: 12px; transition: all 0.2s;
}
.action-btn:hover:not(:disabled) { background: rgba(255,255,255,0.15); }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.peace-btn { border-color: rgba(255, 200, 60, 0.3); color: #ffc83d; }

.empty-state {
  text-align: center; padding: 40px 0; color: #666;
}
.empty-icon { font-size: 40px; display: block; margin-bottom: 12px; }
.empty-state p { font-size: 14px; }
</style>
