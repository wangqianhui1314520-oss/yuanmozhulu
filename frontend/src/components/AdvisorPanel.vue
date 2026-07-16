<template>
  <Teleport to="body">
    <transition name="modal">
      <div class="advisor-overlay" @click.self="$emit('close')" v-if="visible">
        <div class="advisor-dialog artifact-panel artifact-personnel">
          <!-- 标题栏 -->
          <div class="adv-header">
            <h2>策策问 · 谋臣献策</h2>
            <span class="adv-subtitle">军师幕僚，运筹帷幄</span>
            <button class="adv-close" @click="$emit('close')">✕</button>
          </div>

          <!-- NPC 选择标签栏 -->
          <div class="adv-npc-tabs">
            <!-- 势力谋士团标签 -->
            <div class="faction-label" v-if="advisor.factionAdvisers.value.length > 0" :title="advisor.factionAdviserTitle.value">
              {{ advisor.factionAdviserTitle.value }}
            </div>
            <button
              v-for="npc in npcTabs"
              :key="npc.npc_id"
              class="npc-tab"
              :class="{ active: advisor.selectedNpcId.value === npc.npc_id, 'is-wanderer': npc.faction === '_wandering' }"
              @click="selectNPC(npc.npc_id)"
              :title="`${npc.name} · ${npc.role_label}${npc.faction === '_wandering' ? '（流浪谋士）' : ''}`"
            >
              <span class="npc-tab-name">
                {{ npc.name }}
                <span v-if="npc.faction === '_wandering'" class="wanderer-dot">·</span>
              </span>
              <span class="npc-tab-role">{{ npc.role_label }}</span>
            </button>
            <!-- 更多谋士按钮 -->
            <button
              v-if="advisor.npcList.value.length > npcTabs.length"
              class="npc-tab more-tab"
              @click="showAllAdvisers = !showAllAdvisers"
              :title="showAllAdvisers ? '收起' : '查看更多谋士'"
            >
              <span class="npc-tab-name">{{ showAllAdvisers ? '收起' : '更多' }}</span>
              <span class="npc-tab-role">{{ advisor.npcList.value.length }}位</span>
            </button>
            <!-- 廷议按钮 -->
            <button
              class="npc-tab debate-tab"
              :class="{ active: advisor.debateMode.value }"
              @click="toggleDebateMode"
              title="召集群臣廷议"
            >
              <span class="npc-tab-name">廷议</span>
              <span class="npc-tab-role">群臣奏对</span>
            </button>
          </div>

          <!-- 对话区 -->
          <div class="adv-chat-area" ref="chatAreaRef">
            <!-- 通用模式欢迎 -->
            <div v-if="!advisor.selectedNpcId.value && !advisor.debateMode.value && advisor.messages.value.length === 0" class="adv-welcome">
              <div class="welcome-seal">策</div>
              <p>君主有何军国大事相询？</p>
              <p class="welcome-sub">上方可选择具体文臣问策，或直接询问谋士团。</p>
            </div>

            <!-- NPC 模式介绍 -->
            <div v-if="advisor.selectedNpcId.value && advisor.currentNPC.value && advisor.messages.value.length === 0" class="npc-intro">
              <div class="npc-intro-avatar-frame">
                <CharacterPortrait
                  v-if="advisor.currentNPC.value"
                  :portrait-data="getNPCPortraitData(advisor.currentNPC.value)"
                  :size="80"
                  :style="getNPCStyle(advisor.currentNPC.value.role)"
                />
              </div>
              <div class="npc-intro-header">
                <span class="npc-intro-name">{{ advisor.currentNPC.value.name }}</span>
                <span class="npc-intro-style">字{{ advisor.currentNPC.value.style_name }}</span>
              </div>
              <div class="npc-intro-title">{{ advisor.currentNPC.value.title }} · {{ advisor.currentNPC.value.role_label }}</div>
              <div class="npc-intro-tags">
                <span v-for="s in advisor.currentNPC.value.specialties" :key="s" class="npc-tag">{{ s }}</span>
              </div>
              <div class="npc-intro-stats">
                <span class="npc-stat" title="才智">智{{ advisor.currentNPC.value.wisdom || '?' }}</span>
                <span class="npc-stat" title="忠诚">忠{{ advisor.currentNPC.value.loyalty || '?' }}</span>
                <span class="npc-stat" title="野心">野{{ advisor.currentNPC.value.ambition || '?' }}</span>
              </div>
              <div class="npc-intro-personality">{{ advisor.currentNPC.value.personality }}</div>
              <div class="npc-intro-greeting">「{{ advisor.currentNPC.value.greeting }}」</div>
            </div>

            <!-- 廷议模式 -->
            <div v-if="advisor.debateMode.value && advisor.debateMessages.value.length === 0" class="debate-intro">
              <div class="debate-seal">议</div>
              <p>请颁布廷议议题</p>
              <p class="welcome-sub">众臣将各抒己见，为君分忧。</p>
            </div>

            <!-- 通用/单NPC对话消息 -->
            <template v-if="!advisor.debateMode.value">
              <div
                v-for="(msg, i) in advisor.messages.value"
                :key="i"
                class="adv-message"
                :class="msg.role === 'user' ? 'msg-user' : msg.role === 'system' ? 'msg-system' : 'msg-ai'"
              >
                <div class="msg-label">
                  <template v-if="msg.role === 'user'">君主奏疏</template>
                  <template v-else-if="msg.role === 'system'">邸报</template>
                  <template v-else>
                    <span v-if="msg.npcName">{{ msg.npcName }}</span>
                    <span v-else>谋士上书</span>
                  </template>
                </div>
                <div class="msg-content">{{ msg.content }}</div>
                <div class="msg-time" v-if="msg.time">{{ msg.time }}</div>
              </div>
            </template>

            <!-- 廷议消息 -->
            <template v-if="advisor.debateMode.value">
              <div v-if="advisor.debateMessages.value.length === 0 && advisor.debateLoading.value" class="adv-message msg-system">
                <div class="msg-label">廷议进行中</div>
                <div class="msg-content">群臣正在思虑，请稍候...</div>
                <div class="debate-progress">
                  <span class="progress-dot" v-for="i in 4" :key="i" :class="{ active: i <= debateProgress }">●</span>
                </div>
              </div>
              <div
                v-for="(dmsg, i) in advisor.debateMessages.value"
                :key="'d' + i"
                class="adv-message msg-ai debate-msg"
                :style="{ borderLeftColor: getNPCColor(dmsg.npc_id) }"
              >
                <div class="msg-label">
                  <span class="debate-npc-name">{{ dmsg.npc_name }}</span>
                  <span class="debate-npc-title">{{ dmsg.title }}</span>
                </div>
                <div class="msg-content">{{ dmsg.opinion || (dmsg as any).content }}</div>
              </div>
              <!-- 廷议总结 -->
              <div v-if="advisor.debateSummary.value" class="adv-message msg-system debate-summary">
                <div class="msg-label">廷议纪要</div>
                <div class="msg-content">{{ advisor.debateSummary.value }}</div>
              </div>
              <!-- 廷议决议选项 -->
              <div v-if="advisor.debateSummary.value && !advisor.debateResolved.value" class="debate-resolution">
                <div class="resolution-title">请陛下裁决</div>
                <div class="resolution-options">
                  <button class="resolution-btn accept" @click="applyResolution('accept_consensus')" :disabled="advisor.resolutionApplying.value">
                    <span class="rb-icon">✅</span>
                    <span class="rb-label">采纳众议</span>
                    <span class="rb-desc">从善如流，朝野归心</span>
                    <span class="rb-effect" style="color:#5b8c5a">朝纲+8</span>
                  </button>
                  <button class="resolution-btn partial" @click="applyResolution('partial_accept')" :disabled="advisor.resolutionApplying.value">
                    <span class="rb-icon">🔶</span>
                    <span class="rb-label">择善而从</span>
                    <span class="rb-desc">取其精华，去其糟粕</span>
                    <span class="rb-effect" style="color:#5b8c5a">朝纲+3</span>
                  </button>
                  <button class="resolution-btn table" @click="applyResolution('table_discussion')" :disabled="advisor.resolutionApplying.value">
                    <span class="rb-icon">⏸</span>
                    <span class="rb-label">容后再议</span>
                    <span class="rb-desc">此事不急，容后再议</span>
                    <span class="rb-effect" style="color:#c44b3c">朝纲-2</span>
                  </button>
                  <button class="resolution-btn override" @click="applyResolution('override_decision')" :disabled="advisor.resolutionApplying.value">
                    <span class="rb-icon">👑</span>
                    <span class="rb-label">乾纲独断</span>
                    <span class="rb-desc">朕意已决，无需再议</span>
                    <span class="rb-effect" style="color:#c44b3c">朝纲-5</span>
                  </button>
                </div>
                <!-- 独断输入 -->
                <div v-if="showOverrideInput" class="override-input-area">
                  <textarea v-model="overrideText" class="override-textarea" rows="2" placeholder="颁布您的决策..."></textarea>
                  <button class="btn-tiny" @click="applyResolution('override_decision')" :disabled="advisor.resolutionApplying.value">颁布</button>
                  <button class="btn-tiny" @click="showOverrideInput = false">取消</button>
                </div>
              </div>
              <!-- 决议已确认 -->
              <div v-if="advisor.debateResolved.value" class="adv-message msg-system debate-resolved">
                <div class="msg-label">圣裁已定</div>
                <div class="msg-content">{{ advisor.resolutionResultText.value }}</div>
              </div>
            </template>
          </div>

          <!-- 输入区 -->
          <div class="adv-input-area">
            <!-- 廷议议题 -->
            <div v-if="advisor.debateMode.value" class="debate-input-hint">
              <span>议题：</span>
              <input
                v-model="advisor.debateTopic.value"
                class="debate-topic-input"
                placeholder="例如：是否应出兵北伐？当前应结盟何方？"
                @keydown.enter="startDebate"
              />
            </div>
            <!-- 快捷提问 -->
            <div class="adv-quick-asks" v-if="!advisor.debateMode.value">
              <button
                v-for="q in quickAsks"
                :key="q"
                class="quick-ask-btn"
                @click="inputText = q"
              >{{ q }}</button>
            </div>
            <div class="adv-input-row">
              <textarea
                v-model="inputText"
                class="adv-input"
                :placeholder="inputPlaceholder"
                rows="3"
                @keydown.enter.ctrl="advisor.debateMode.value ? startDebate() : sendMessage()"
              ></textarea>
              <button
                class="adv-send-btn"
                @click="advisor.debateMode.value ? startDebate() : sendMessage()"
                :disabled="(!inputText.trim() && !advisor.debateMode.value) || advisor.loading.value"
              >
                {{ advisor.loading.value ? (advisor.debateMode.value ? '群臣思虑中...' : '谋士思虑中...') : (advisor.debateMode.value ? '开议' : '奏报') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import { useAdvisorChat } from '@/composables/useAdvisorChat'
import type { NPCAdviser, ChatMessage, DebateMessage } from '@/composables/useAdvisorChat'
import CharacterPortrait from '@/components/CharacterPortrait.vue'
import type { PortraitData } from '@/components/CharacterPortrait.vue'
import { RULER_IMAGE_MAP } from '@/components/CharacterPortrait.vue'

defineProps<{ visible: boolean }>()
defineEmits<{ close: [] }>()

const store = useGameStore()
const advisor = useAdvisorChat()

const inputText = ref('')
const chatAreaRef = ref<HTMLDivElement>()
const showAllAdvisers = ref(false)

const debateProgress = ref(0)
let progressTimer: ReturnType<typeof setInterval> | null = null

const showOverrideInput = ref(false)
const overrideText = ref('')

// ---- 计算属性 ----

/** NPC 标签栏：优先本势力谋士团 + 廷议 */
const npcTabs = computed(() => {
  const nativeAdvisers = advisor.factionAdvisers.value?.length > 0
    ? advisor.factionAdvisers.value
    : advisor.npcList.value.filter(n => n.faction === store.playerFactionId)

  const wanderers = advisor.npcList.value.filter(n => n.faction === '_wandering')

  if (showAllAdvisers.value) {
    return [...nativeAdvisers, ...wanderers]
  }

  const display = nativeAdvisers.length > 0 ? nativeAdvisers.slice(0, 6) : advisor.npcList.value.slice(0, 6)

  // 兜底
  if (advisor.npcList.value.length === 0) {
    return [
      { npc_id: 'liu_ji', name: '刘基', role_label: '军师谋主', role: 'strategist', faction: 'faction_zhuyuanzhang' },
      { npc_id: 'li_shanchang', name: '李善长', role_label: '开国宰辅', role: 'chancellor', faction: 'faction_zhuyuanzhang' },
      { npc_id: 'xu_da', name: '徐达', role_label: '三军统帅', role: 'general', faction: 'faction_zhuyuanzhang' },
      { npc_id: 'zhu_sheng', name: '朱升', role_label: '隐士谋臣', role: 'strategist', faction: 'faction_zhuyuanzhang' },
      { npc_id: 'song_lian', name: '宋濂', role_label: '帝师文宗', role: 'scholar', faction: 'faction_zhuyuanzhang' },
      { npc_id: 'su_qin', name: '苏秦', role_label: '纵横大家', role: 'diplomat', faction: '_wandering' },
      { npc_id: 'fan_li', name: '范蠡', role_label: '商圣智者', role: 'economist', faction: '_wandering' },
    ] as any[]
  }
  return display
})

const inputPlaceholder = computed(() => {
  if (advisor.selectedNpcId.value && advisor.currentNPC.value) {
    return `向${advisor.currentNPC.value.name}问策...（例：当前局势如何？当先取何地？）`
  }
  return '策问谋士...（例：当前局势如何？当先取何地？）'
})

const quickAsks = computed(() => {
  const npc = advisor.currentNPC.value
  if (npc) {
    const roleMap: Record<string, string[]> = {
      general: ['当前当攻何处？', '我军兵力如何调度？', '如何防守边境？', '敌军有何破绽？'],
      diplomat: ['当前当与何国结盟？', '如何离间敌国？', '外交策略当如何？', '可否联姻求和？'],
      economist: ['国库收入如何增加？', '粮草储备可充足？', '如何开源节流？', '商业贸易当如何发展？'],
      chancellor: ['朝中可有人才可荐？', '当前内政当如何？', '法律制度需完善否？', '地方治理有何良策？'],
    }
    return roleMap[npc.role] || ['当前天下大势如何？', '有何良策献上？', '当如何应对时局？']
  }
  return ['当前天下大势如何？', '我军当先取何地？', '如何应对邻国威胁？', '国策当如何调整？', '朝中可有隐患？']
})

// ---- 方法 ----

function getNPCColor(npcId: string): string {
  const npc = advisor.npcList.value.find(n => n.npc_id === npcId)
  return advisor.getNPCColor(npc?.role || '')
}

function getNPCPortraitData(npc: NPCAdviser): PortraitData {
  const isRuler = npc.role === 'ruler'
  return {
    name: npc.name,
    title: npc.title,
    role: npc.role,
    roleLabel: npc.role_label,
    personality: npc.personality || '',
    color: getNPCColor(npc.npc_id),
    wisdom: npc.wisdom,
    loyalty: npc.loyalty,
    ambition: npc.ambition,
    styleName: npc.style_name,
    specialties: npc.specialties || [],
    isRuler,
    imageUrl: isRuler ? RULER_IMAGE_MAP[npc.faction] : undefined,
  }
}

function getNPCStyle(role: string): string {
  const map: Record<string, string> = {
    general: 'general', strategist: 'strategist', chancellor: 'chancellor',
    diplomat: 'diplomat', scholar: 'scholar', economist: 'chancellor',
    reformer: 'chancellor', ruler: 'ruler',
  }
  return map[role] || 'default'
}

function selectNPC(npcId: string) {
  advisor.selectNPC(npcId)
}

function toggleDebateMode() {
  advisor.debateMode.value = !advisor.debateMode.value
  advisor.debateTopic.value = ''
  showOverrideInput.value = false
  overrideText.value = ''
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  await advisor.sendMessage(text)
  await nextTick()
  scrollToBottom()
}

async function startDebate() {
  const topic = advisor.debateTopic.value.trim() || inputText.value.trim()
  if (!topic) return
  inputText.value = ''

  // 进度动画
  progressTimer = setInterval(() => {
    if (debateProgress.value < 3) debateProgress.value++
  }, 800)

  await advisor.startDebate(topic)
  clearInterval(progressTimer!)
  debateProgress.value = 4
  await nextTick()
  scrollToBottom()
}

async function applyResolution(resolutionType: string) {
  if (resolutionType === 'override_decision' && !showOverrideInput.value) {
    showOverrideInput.value = true
    return
  }
  await advisor.applyResolution(resolutionType, overrideText.value)
  showOverrideInput.value = false
}

function handleOpenCourtDebate() {
  advisor.debateMode.value = true
  advisor.debateTopic.value = ''
  showOverrideInput.value = false
  overrideText.value = ''
}

onMounted(() => {
  window.addEventListener('open-court-debate', handleOpenCourtDebate)
})

onUnmounted(() => {
  if (progressTimer) clearInterval(progressTimer)
  window.removeEventListener('open-court-debate', handleOpenCourtDebate)
})

function scrollToBottom() {
  if (chatAreaRef.value) {
    chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
  }
}
</script>

<style scoped>
/* 遮罩 */
.advisor-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3500;
}

/* 弹窗主体 */
.advisor-dialog {
  width: 90vw;
  max-width: 700px;
  height: 80vh;
  max-height: 720px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.5);
  clip-path: polygon(3px 0, calc(100% - 3px) 0, 100% 3px, 100% calc(100% - 3px), calc(100% - 3px) 100%, 3px 100%, 0 calc(100% - 3px), 0 3px);
}

/* 动画 */
.modal-enter-active { animation: scrollUnfold 0.35s cubic-bezier(0.34, 1.56, 0.64, 1); }
.modal-leave-active { animation: scrollFold 0.25s ease-in; }

@keyframes scrollUnfold {
  0% { opacity: 0; transform: scaleY(0.3) scaleX(0.7); transform-origin: top center; filter: blur(4px); }
  60% { opacity: 1; transform: scaleY(1.02) scaleX(1.01); filter: blur(0); }
  100% { opacity: 1; transform: scaleY(1) scaleX(1); filter: blur(0); }
}

@keyframes scrollFold {
  0% { opacity: 1; transform: scaleY(1) scaleX(1); }
  100% { opacity: 0; transform: scaleY(0.3) scaleX(0.7); transform-origin: top center; filter: blur(4px); }
}

/* 标题栏 */
.adv-header {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(180deg, #36312A 0%, #2C2824 100%);
}

.adv-header h2 {
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
  font-size: 19px;
  font-weight: normal;
  color: var(--gold);
  letter-spacing: 4px;
}

.adv-subtitle {
  font-size: 11px;
  color: var(--text-dim);
  margin-left: 12px;
  flex: 1;
  letter-spacing: 2px;
  font-family: "FangSong", "FangSong_GB2312", serif;
}

.adv-close {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-main);
  background: var(--bg-card);
  color: var(--text-dim);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast);
}
.adv-close:hover {
  color: var(--danger);
  border-color: var(--danger);
}

/* NPC 标签栏 */
.adv-npc-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-main);
  background: var(--bg-card);
  overflow-x: auto;
  padding: 0 8px;
  align-items: stretch;
}

/* 势力标签 */
.faction-label {
  padding: 8px 12px;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 10px;
  color: var(--gold-dim);
  background: rgba(184, 155, 104, 0.06);
  border-right: 1px solid rgba(184, 155, 104, 0.12);
  white-space: nowrap;
  display: flex;
  align-items: center;
  letter-spacing: 2px;
}

.npc-tab {
  padding: 8px 14px;
  font-family: "FangSong", "FangSong_GB2312", serif;
  font-size: 12px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-dim);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--duration-fast);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.npc-tab:hover {
  color: var(--text-main);
  background: rgba(184, 155, 104, 0.05);
}
.npc-tab.active {
  color: var(--gold);
  border-bottom-color: var(--gold);
  background: rgba(184, 155, 104, 0.08);
}

/* 流浪谋士样式 */
.npc-tab.is-wanderer {
  opacity: 0.75;
}
.npc-tab.is-wanderer .npc-tab-name {
  color: var(--text-dim);
}
.npc-tab.is-wanderer.active {
  opacity: 1;
}
.wanderer-dot {
  color: var(--text-muted);
  font-size: 10px;
}

.npc-tab-name {
  font-size: 13px;
  font-family: "STKaiti", "KaiTi", serif;
  letter-spacing: 1px;
}
.npc-tab-role {
  font-size: 9px;
  color: var(--text-muted);
}
.npc-tab.active .npc-tab-role {
  color: var(--gold-dim);
}

/* 更多按钮 */
.more-tab {
  border-left: 1px solid rgba(184, 155, 104, 0.1);
}
.more-tab .npc-tab-name {
  font-size: 11px;
  color: var(--text-muted);
}

.debate-tab {
  margin-left: auto;
}
.debate-tab.active {
  color: #C97878;
  border-bottom-color: #C97878;
  background: rgba(201, 120, 120, 0.08);
}

/* 对话区 */
.adv-chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background:
    repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(184, 155, 104, 0.015) 2px, rgba(184, 155, 104, 0.015) 4px);
}

.adv-welcome {
  text-align: center;
  padding: 48px 20px;
}

.welcome-seal {
  width: 60px;
  height: 60px;
  margin: 0 auto 16px;
  border: 2px solid var(--danger);
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  color: var(--danger);
  font-family: "STKaiti", "KaiTi", serif;
  transform: rotate(-3deg);
}

.adv-welcome p {
  font-size: 16px;
  color: var(--text-main);
  letter-spacing: 2px;
}

.welcome-sub {
  font-size: 12px !important;
  color: var(--text-dim) !important;
  margin-top: 6px;
}

/* NPC 介绍卡片 */
.npc-intro {
  text-align: center;
  padding: 24px 20px;
  border: 1px solid rgba(184, 155, 104, 0.15);
  border-radius: 3px;
  background: linear-gradient(180deg, rgba(184, 155, 104, 0.05) 0%, rgba(184, 155, 104, 0.02) 100%);
}

.npc-intro-avatar-frame {
  margin: 0 auto 12px;
  display: flex;
  justify-content: center;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
}

.npc-intro-avatar {
  width: 48px;
  height: 48px;
  margin: 0 auto 12px;
  border-radius: 50%;
  border: 2px solid var(--gold-dim);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-family: "STKaiti", "KaiTi", serif;
  color: var(--gold);
  background: rgba(184, 155, 104, 0.08);
}

.npc-intro-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 4px;
}

.npc-intro-name {
  font-size: 20px;
  font-family: "STKaiti", "KaiTi", serif;
  color: var(--gold);
  letter-spacing: 4px;
}

.npc-intro-style {
  font-size: 12px;
  color: var(--text-dim);
  font-family: "FangSong", "FangSong_GB2312", serif;
}

.npc-intro-title {
  font-size: 13px;
  color: var(--text-dim);
  margin-bottom: 10px;
}

.npc-intro-tags {
  display: flex;
  gap: 6px;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.npc-tag {
  padding: 2px 10px;
  font-size: 10px;
  font-family: "FangSong", "FangSong_GB2312", serif;
  background: rgba(184, 155, 104, 0.1);
  border: 1px solid rgba(184, 155, 104, 0.2);
  color: var(--gold-dim);
  border-radius: 2px;
}

.npc-intro-stats {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 10px;
}

.npc-stat {
  font-size: 10px;
  font-family: "FangSong", "FangSong_GB2312", serif;
  color: var(--text-dim);
  padding: 1px 8px;
  border: 1px solid rgba(184, 155, 104, 0.12);
  border-radius: 2px;
  background: rgba(184, 155, 104, 0.04);
}

.npc-intro-personality {
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 10px;
  font-family: "FangSong", "FangSong_GB2312", serif;
}

.npc-intro-greeting {
  font-size: 14px;
  color: var(--text-main);
  font-family: "STKaiti", "KaiTi", serif;
  letter-spacing: 2px;
}

/* 廷议介绍 */
.debate-intro {
  text-align: center;
  padding: 48px 20px;
}

.debate-seal {
  width: 60px;
  height: 60px;
  margin: 0 auto 16px;
  border: 2px solid #C97878;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  color: #C97878;
  font-family: "STKaiti", "KaiTi", serif;
  transform: rotate(-3deg);
}

.debate-intro p {
  font-size: 16px;
  color: var(--text-main);
  letter-spacing: 2px;
}

/* 廷议进度动画 */
.debate-progress {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 8px;
}

.progress-dot {
  font-size: 10px;
  color: rgba(184, 155, 104, 0.2);
  transition: color 0.4s ease;
}

.progress-dot.active {
  color: var(--gold);
}

/* 消息气泡 */
.adv-message {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.8;
}

.msg-user {
  align-self: flex-end;
  background: linear-gradient(180deg, rgba(158, 43, 37, 0.12) 0%, rgba(158, 43, 37, 0.06) 100%);
  border: 1px solid rgba(158, 43, 37, 0.25);
  border-radius: 3px;
}
.msg-user .msg-label { color: var(--danger); font-family: "STKaiti", "KaiTi", serif; }

.msg-ai {
  align-self: flex-start;
  background: linear-gradient(180deg, rgba(184, 155, 104, 0.06) 0%, rgba(184, 155, 104, 0.03) 100%);
  border: 1px solid rgba(184, 155, 104, 0.15);
  border-left: 3px solid var(--gold-dim);
}
.msg-ai .msg-label { color: var(--gold); font-family: "STKaiti", "KaiTi", serif; }

.msg-system {
  align-self: stretch;
  background: rgba(184, 155, 104, 0.05);
  border: 1px solid rgba(184, 155, 104, 0.1);
  border-radius: 2px;
  text-align: center;
  font-size: 12px;
}
.msg-system .msg-label { color: var(--gold-dim); }

.msg-label {
  font-size: 10px;
  margin-bottom: 6px;
  letter-spacing: 2px;
}

.msg-content {
  white-space: pre-wrap;
}

.msg-time {
  font-size: 9px;
  color: var(--text-muted);
  margin-top: 6px;
  text-align: right;
  font-family: "FangSong", "FangSong_GB2312", serif;
}

/* 廷议消息 */
.debate-msg {
  border-left-width: 4px !important;
}

.debate-npc-name {
  font-size: 12px;
  font-weight: bold;
}

.debate-npc-title {
  font-size: 9px;
  color: var(--text-muted);
  margin-left: 6px;
}

.debate-summary {
  border: 1px solid rgba(201, 120, 120, 0.2) !important;
  background: rgba(201, 120, 120, 0.05) !important;
}

.debate-summary .msg-label {
  color: #C97878 !important;
}

/* 廷议决议选项 */
.debate-resolution {
  padding: 12px 14px;
  margin-top: 4px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(184,150,62,0.15);
  border-radius: 4px;
}

.resolution-title {
  font-size: 13px; color: #b8963e; letter-spacing: 3px;
  text-align: center; margin-bottom: 10px;
  font-family: "STKaiti", "KaiTi", serif;
}

.resolution-options {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
}

.resolution-btn {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 8px 6px; border: 1px solid rgba(184,150,62,0.12);
  background: rgba(0,0,0,0.2); cursor: pointer;
  transition: all 0.2s; border-radius: 3px;
}
.resolution-btn:hover:not(:disabled) {
  background: rgba(184,150,62,0.08); border-color: rgba(184,150,62,0.3);
}
.resolution-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.rb-icon { font-size: 16px; }
.rb-label { font-size: 13px; color: #e0d5b8; letter-spacing: 2px; font-family: "STKaiti","KaiTi",serif; }
.rb-desc { font-size: 10px; color: rgba(184,150,62,0.35); }
.rb-effect { font-size: 10px; font-weight: bold; }

/* 独断输入 */
.override-input-area {
  display: flex; gap: 6px; margin-top: 8px; align-items: flex-end;
}
.override-textarea {
  flex: 1; padding: 6px 8px; background: rgba(0,0,0,0.3);
  border: 1px solid rgba(184,150,62,0.2); color: #e0d5b8;
  font-size: 12px; resize: vertical; font-family: inherit;
}
.override-textarea::placeholder { color: rgba(184,150,62,0.25); }

/* 决议已确认 */
.debate-resolved {
  border: 1px solid rgba(91,140,90,0.2) !important;
  background: rgba(91,140,90,0.05) !important;
}
.debate-resolved .msg-label { color: #5b8c5a !important; }

/* 输入区 */
.adv-input-area {
  border-top: 1px solid var(--border-main);
  padding: 10px 14px;
  background: var(--bg-card);
}

.debate-input-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--gold);
  font-family: "STKaiti", "KaiTi", serif;
}

.debate-topic-input {
  flex: 1;
  padding: 6px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border-main);
  border-radius: var(--radius-sm);
  font-family: "SimSun", serif;
  font-size: 13px;
  color: var(--text-main);
}
.debate-topic-input:focus {
  outline: none;
  border-color: var(--gold);
}

.adv-quick-asks {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.quick-ask-btn {
  padding: 4px 12px;
  font-size: 10px;
  font-family: "FangSong", "FangSong_GB2312", serif;
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.15);
  color: var(--text-dim);
  cursor: pointer;
  border-radius: var(--radius-sm);
  letter-spacing: 1px;
  transition: all var(--duration-fast);
}
.quick-ask-btn:hover {
  background: rgba(184, 155, 104, 0.15);
  color: var(--gold);
  border-color: var(--gold-dim);
}

.adv-input-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.adv-input {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg-input);
  border: 1px solid var(--border-main);
  border-radius: var(--radius-sm);
  font-family: "SimSun", serif;
  font-size: 13px;
  color: var(--text-main);
  resize: none;
  min-height: 64px;
  line-height: 1.7;
  background-image:
    repeating-linear-gradient(0deg, transparent, transparent 19px, rgba(184, 155, 104, 0.04) 19px, rgba(184, 155, 104, 0.04) 20px);
}
.adv-input::placeholder {
  color: var(--text-muted);
  font-family: "FangSong", "FangSong_GB2312", serif;
}
.adv-input:focus {
  outline: none;
  border-color: var(--gold);
  box-shadow: 0 0 0 2px rgba(184, 155, 104, 0.1);
}

.adv-send-btn {
  padding: 10px 20px;
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
  font-size: 15px;
  background: linear-gradient(180deg, var(--gold) 0%, var(--gold-dim) 100%);
  color: #1A1815;
  border: 1px solid var(--gold);
  border-radius: var(--radius-sm);
  cursor: pointer;
  letter-spacing: 4px;
  writing-mode: vertical-rl;
  white-space: nowrap;
  font-weight: bold;
  transition: all var(--duration-fast);
}
.adv-send-btn:hover:not(:disabled) {
  background: linear-gradient(180deg, #C9AC78 0%, var(--gold) 100%);
  box-shadow: 0 2px 12px rgba(184, 155, 104, 0.2);
}
.adv-send-btn:active:not(:disabled) {
  transform: translateY(1px);
}
.adv-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
