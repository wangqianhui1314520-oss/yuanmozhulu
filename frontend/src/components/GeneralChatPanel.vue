<template>
  <div class="gc-root" v-if="visible">
    <div class="gc-window">
      <!-- 标题栏 -->
      <div class="gc-header">
        <div class="gc-title-row">
          <span class="gc-seal">将</span>
          <div>
            <h2>将台问策</h2>
            <span class="gc-subtitle">营帐点将 · 运筹帷幄</span>
          </div>
        </div>
        <button class="gc-close" @click="$emit('close')">✕</button>
      </div>

      <!-- 武将选择标签栏 -->
      <div class="gc-tabs">
        <div class="gc-faction-label" v-if="generals.length > 0">
          {{ factionLabel }}
        </div>
        <button
          v-for="g in generals"
          :key="g.npc_id"
          class="gc-tab"
          :class="{ active: selectedGeneralId === g.npc_id }"
          @click="selectGeneral(g.npc_id)"
          :title="`${g.name} · ${g.role_label}`"
        >
          <span class="gc-tab-icon">{{ getRoleEmoji(g.role) }}</span>
          <span class="gc-tab-name">{{ g.name }}</span>
          <span class="gc-tab-role">{{ g.role_label }}</span>
        </button>
        <!-- 联合军议按钮 -->
        <button
          class="gc-tab gc-war-council"
          :class="{ active: warCouncilMode }"
          @click="toggleWarCouncil"
          title="召集众将联合军议"
        >
          <span class="gc-tab-name">军议</span>
          <span class="gc-tab-role">众将合议</span>
        </button>
      </div>

      <!-- 对话区 -->
      <div class="gc-chat-area" ref="chatAreaRef">
        <!-- 欢迎 -->
        <div v-if="!selectedGeneralId && !warCouncilMode && messages.length === 0" class="gc-welcome">
          <div class="gc-welcome-seal">将</div>
          <p>请选一将问策，或召开军议与众将共商大事。</p>
          <p class="gc-welcome-sub">每位武将皆有独立人格与AI智脑，知无不言。</p>
        </div>

        <!-- 武将介绍卡片 -->
        <div v-if="selectedGeneralId && currentGeneral && messages.length === 0" class="gc-intro">
          <div class="gc-intro-frame">
            <CharacterPortrait
              v-if="currentGeneral"
              :portrait-data="getPortraitData(currentGeneral)"
              :size="72"
              :style="'general'"
            />
          </div>
          <div class="gc-intro-header">
            <span class="gc-intro-name">{{ currentGeneral.name }}</span>
            <span class="gc-intro-style" v-if="currentGeneral.style_name">字{{ currentGeneral.style_name }}</span>
          </div>
          <div class="gc-intro-title">{{ currentGeneral.title }} · {{ currentGeneral.role_label }}</div>
          <div class="gc-intro-tags">
            <span v-for="s in currentGeneral.specialties" :key="s" class="gc-tag">{{ s }}</span>
          </div>
          <div class="gc-intro-stats">
            <span class="gc-stat" title="忠诚">忠{{ currentGeneral.loyalty ?? '?' }}</span>
            <span class="gc-stat" title="才智">智{{ currentGeneral.wisdom ?? '?' }}</span>
            <span class="gc-stat" title="武力">⚔{{ currentGeneral.might ?? '?' }}</span>
          </div>
          <div class="gc-intro-personality">{{ currentGeneral.personality }}</div>
          <div class="gc-intro-greeting">「{{ currentGeneral.greeting }}」</div>
        </div>

        <!-- 军议模式介绍 -->
        <div v-if="warCouncilMode && councilMessages.length === 0" class="gc-council-intro">
          <div class="gc-council-seal">议</div>
          <p>请下达军议议题</p>
          <p class="gc-welcome-sub">众将各抒己见，共定军国大计。</p>
        </div>

        <!-- 单武将对话消息 -->
        <template v-if="!warCouncilMode">
          <div
            v-for="(msg, i) in messages" :key="i"
            class="gc-message"
            :class="msg.role === 'user' ? 'msg-user' : msg.role === 'system' ? 'msg-system' : 'msg-ai'"
          >
            <div class="gc-msg-label">
              <template v-if="msg.role === 'user'">主公令</template>
              <template v-else-if="msg.role === 'system'">军报</template>
              <template v-else>{{ msg.npcName || '将领回禀' }}</template>
            </div>
            <div class="gc-msg-content">{{ msg.content }}</div>
            <div class="gc-msg-time" v-if="msg.time">{{ msg.time }}</div>
          </div>
        </template>

        <!-- 军议消息 -->
        <template v-if="warCouncilMode">
          <div v-if="councilMessages.length === 0 && councilLoading" class="gc-message msg-system">
            <div class="gc-msg-label">军议进行中</div>
            <div class="gc-msg-content">众将正在思量，请稍候...</div>
            <div class="gc-council-progress">
              <span class="gc-dot" v-for="i in 4" :key="i" :class="{ active: i <= councilProgress }">●</span>
            </div>
          </div>
          <div
            v-for="(cmsg, i) in councilMessages" :key="'c'+i"
            class="gc-message msg-ai council-msg"
            :style="{ borderLeftColor: getGeneralColor(cmsg.npc_id) }"
          >
            <div class="gc-msg-label">
              <span class="gc-council-name">{{ cmsg.npc_name }}</span>
              <span class="gc-council-title">{{ cmsg.title }}</span>
            </div>
            <div class="gc-msg-content">{{ cmsg.opinion || cmsg.content }}</div>
          </div>
          <!-- 军议总结 -->
          <div v-if="councilSummary" class="gc-message msg-system gc-council-summary">
            <div class="gc-msg-label">军议纪要</div>
            <div class="gc-msg-content">{{ councilSummary }}</div>
          </div>
        </template>
      </div>

      <!-- 输入区 -->
      <div class="gc-input-area">
        <!-- 军议议题 -->
        <div v-if="warCouncilMode" class="gc-council-input-row">
          <span class="gc-council-input-label">军议议题：</span>
          <input
            v-model="councilTopic"
            class="gc-council-input"
            placeholder="例如：当先攻何处？如何布防？粮道如何保障？"
            @keydown.enter="startWarCouncil"
          />
        </div>
        <!-- 快捷提问 -->
        <div class="gc-quick-asks" v-if="!warCouncilMode">
          <button v-for="q in quickAsks" :key="q" class="gc-quick-btn" @click="inputText = q">{{ q }}</button>
        </div>
        <div class="gc-input-row">
          <textarea
            v-model="inputText"
            class="gc-input"
            :placeholder="inputPlaceholder"
            rows="3"
            @keydown.enter.ctrl="warCouncilMode ? startWarCouncil() : sendMessage()"
          ></textarea>
          <button
            class="gc-send-btn"
            @click="warCouncilMode ? startWarCouncil() : sendMessage()"
            :disabled="sendDisabled || loading"
          >
            {{ loading ? (warCouncilMode ? '众将思量中...' : '将军思量中...') : (warCouncilMode ? '开议' : '发令') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import CharacterPortrait from '@/components/CharacterPortrait.vue'
import type { PortraitData } from '@/components/CharacterPortrait.vue'
import * as API from '@/services/api'

defineProps<{ visible: boolean }>()
defineEmits<{ close: [] }>()

const store = useGameStore()
const inputText = ref('')
const loading = ref(false)
const chatAreaRef = ref<HTMLDivElement>()
const selectedGeneralId = ref('')
const warCouncilMode = ref(false)
const councilTopic = ref('')
const councilLoading = ref(false)
const councilSummary = ref('')
const councilProgress = ref(0)
let progressTimer: ReturnType<typeof setInterval> | null = null

interface ChatMessage {
  role: 'user' | 'ai' | 'system'
  content: string
  time?: string
  npcName?: string
  npcTitle?: string
}

interface CouncilMessage {
  npc_id: string
  npc_name: string
  title: string
  role_label: string
  opinion: string
  content?: string
}

const messages = ref<ChatMessage[]>([])
const councilMessages = ref<CouncilMessage[]>([])
const generals = ref<any[]>([])

const npcColors: Record<string, string> = {
  general: '#E07060',
  strategist: '#C9AC78',
  chancellor: '#B89B68',
  diplomat: '#78A0C9',
  ruler: '#A07850',
}

function getRoleEmoji(role: string): string {
  return {
    general: '⚔️', strategist: '🎯', chancellor: '📜',
    diplomat: '🕊️', scholar: '📖', economist: '💰',
    reformer: '🔧', ruler: '👑',
  }[role] || '👤'
}

const factionLabel = computed(() => {
  const name = store.playerFaction?.name || ''
  return store.playerFactionId.includes('zhuyuan') ? '西吴将士'
    : store.playerFactionId.includes('yuan') ? '元廷将士'
    : store.playerFactionId.includes('chen') ? '汉军将士'
    : `${name}将士`
})

const currentGeneral = computed(() => {
  return generals.value.find((g: any) => g.npc_id === selectedGeneralId.value) || null
})

const inputPlaceholder = computed(() => {
  if (selectedGeneralId.value && currentGeneral.value) {
    return `向${currentGeneral.value.name}问策...（例：当前当攻何处？敌军有何破绽？）`
  }
  return '问策于将...（例：当前当攻何处？敌军有何破绽？）'
})

const sendDisabled = computed(() => {
  if (warCouncilMode.value) {
    return !councilTopic.value.trim() && !inputText.value.trim()
  }
  return !inputText.value.trim()
})

const quickAsks = computed(() => {
  const base = ['当前当攻何处？', '敌军有何破绽？', '我军兵力如何调度？', '如何防守边境？']
  if (currentGeneral.value) {
    const sp = currentGeneral.value.specialties || []
    if (sp.some((s: string) => s.includes('水') || s.includes('舟'))) {
      return ['水战如何部署？', '水师可曾备妥？', ...base.slice(0,2)]
    }
    if (sp.some((s: string) => s.includes('骑'))) {
      return ['骑兵当如何突击？', '何处可用骑兵？', ...base.slice(0,2)]
    }
    if (sp.some((s: string) => s.includes('攻') || s.includes('城'))) {
      return ['何处城池可攻？', '攻城当用何策？', ...base.slice(0,2)]
    }
  }
  return base
})

function getGeneralColor(npcId: string): string {
  const g = generals.value.find((n: any) => n.npc_id === npcId)
  return npcColors[g?.role] || '#E07060'
}

function getPortraitData(npc: any): PortraitData {
  return {
    name: npc.name,
    title: npc.title,
    role: npc.role,
    roleLabel: npc.role_label,
    personality: npc.personality || '',
    color: getGeneralColor(npc.npc_id),
    wisdom: npc.wisdom,
    loyalty: npc.loyalty,
    ambition: npc.ambition,
    styleName: npc.style_name,
    specialties: npc.specialties || [],
    isRuler: npc.role === 'ruler',
  }
}

// 加载武将列表
watch(() => store.isGameStarted, async (started) => {
  if (started) {
    await loadGenerals()
  }
}, { immediate: true })

async function loadGenerals() {
  try {
    const result = await API.listGenerals(store.playerFactionId)
    generals.value = result?.generals || []
    // 后端兜底
    if (generals.value.length === 0) {
      generals.value = (await store.loadNPCList()).filter(
        (n: any) => n.role === 'general' && (n.faction === store.playerFactionId || n.faction === '_wandering')
      )
    }
  } catch {
    // fallback: 使用 store.npcList 过滤
    if (store.npcList.length === 0) await store.loadNPCList(undefined, store.playerFactionId)
    generals.value = store.npcList.filter(
      (n: any) => n.role === 'general'
    )
  }
}

function selectGeneral(npcId: string) {
  if (selectedGeneralId.value === npcId) {
    selectedGeneralId.value = ''
    return
  }
  selectedGeneralId.value = npcId
  warCouncilMode.value = false
  messages.value = []
  // 恢复历史对话
  const history = store.npcConversations[npcId]
  if (history) {
    for (const h of history) {
      if (h.role === 'user') {
        messages.value.push({ role: 'user', content: h.content })
      } else {
        const g = currentGeneral.value
        messages.value.push({
          role: 'ai', content: h.content,
          npcName: g?.name || '', npcTitle: g?.title || '',
        })
      }
    }
  }
}

function toggleWarCouncil() {
  warCouncilMode.value = !warCouncilMode.value
  if (warCouncilMode.value) {
    selectedGeneralId.value = ''
    messages.value = []
    councilMessages.value = []
    councilSummary.value = ''
    councilTopic.value = ''
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  messages.value.push({ role: 'user', content: text, time: now })
  inputText.value = ''
  loading.value = true

  await nextTick()
  scrollToBottom()

  try {
    const gm = currentGeneral.value
    const npcId = selectedGeneralId.value

    if (npcId) {
      const response = await store.chatWithNPC(npcId, text)
      if (response?.response) {
        messages.value.push({
          role: 'ai', content: response.response,
          npcName: response.npc_name || gm?.name || '',
          npcTitle: response.npc_title || gm?.title || '',
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        })
      } else {
        fallbackReply(text)
      }
    } else {
      // 无选中武将，使用通用军事顾问
      const result = await store.chatWithMinister(text)
      if (result?.response) {
        messages.value.push({
          role: 'ai', content: result.response,
          npcName: '军中谋士',
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        })
      } else {
        fallbackReply(text)
      }
    }
  } catch {
    fallbackReply(text)
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function fallbackReply(text: string) {
  const pf = store.playerFaction
  messages.value.push({
    role: 'ai',
    content: `中军回禀：\n\n至正${store.currentYear}年${store.currentSeason}季，我军${pf?.name || ''}麾下${store.playerTiles.length}块领地，总兵力${store.totalTroops}人。\n\n「${text}」之事，末将已记下。待军务稍暇，必当详议。\n（AI将台暂未就绪，此为本地军报）`,
    npcName: currentGeneral.value?.name || '中军',
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
  })
}

async function startWarCouncil() {
  const topic = councilTopic.value.trim() || inputText.value.trim()
  if (!topic || loading.value) return
  inputText.value = ''
  councilTopic.value = ''

  councilLoading.value = true
  loading.value = true
  councilMessages.value = []
  councilSummary.value = ''
  councilProgress.value = 0

  await nextTick()
  scrollToBottom()

  progressTimer = setInterval(() => {
    if (councilProgress.value < 3) councilProgress.value++
  }, 800)

  try {
    // 从武将中选3-4人参与军议
    const generalIds = generals.value.filter((g: any) => g.role === 'general').slice(0, 4).map((g: any) => g.npc_id)
    const result = await store.startCourtDebate(topic, generalIds.length > 0 ? generalIds : undefined)
    clearInterval(progressTimer!)
    councilProgress.value = 4
    if (result?.opinions) {
      councilMessages.value = result.opinions
      councilSummary.value = result.summary || ''
    } else {
      councilMessages.value = [{
        npc_id: '', npc_name: '军议司', title: '奏报',
        role_label: '', opinion: '众将意见未达，请稍后再议。',
      }]
    }
  } catch {
    clearInterval(progressTimer!)
    councilProgress.value = 0
    councilMessages.value = [{
      npc_id: '', npc_name: '军议司', title: '奏报',
      role_label: '', opinion: '军议暂无法举行，AI将台未就绪。',
    }]
  } finally {
    councilLoading.value = false
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

onUnmounted(() => {
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
})

function scrollToBottom() {
  if (chatAreaRef.value) {
    chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
  }
}
</script>

<style scoped>
/* 窗口样式 */
.gc-root {
  position: fixed; inset: 0; z-index: 100;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.65); backdrop-filter: blur(2px);
}
.gc-window {
  width: 90vw; max-width: 700px; height: 80vh; max-height: 750px;
  background: linear-gradient(180deg, #1c1e2a 0%, #151720 100%);
  border: 2px solid #5a4030;
  display: flex; flex-direction: column;
  box-shadow: 0 12px 48px rgba(0,0,0,0.6);
  border-radius: 4px;
}

/* 标题栏 */
.gc-header {
  display: flex; align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #3a3028;
  background: linear-gradient(180deg, #252630 0%, #1e1f28 100%);
}
.gc-title-row { display: flex; align-items: center; gap: 12px; flex: 1; }
.gc-seal {
  font-size: 26px; color: #D07050;
  font-family: "STKaiti","KaiTi",serif;
  writing-mode: vertical-rl; letter-spacing: 4px;
  border: 2px solid #D07050; padding: 4px 8px; border-radius: 2px;
}
.gc-title-row h2 {
  font-size: 18px; font-family: "STKaiti","KaiTi",serif;
  color: #D07050; letter-spacing: 3px; margin: 0;
}
.gc-subtitle {
  font-size: 11px; color: var(--text-dim); letter-spacing: 2px;
  font-family: "FangSong",serif;
}
.gc-close {
  width: 28px; height: 28px; border: 1px solid #5a4030;
  background: var(--bg-card); color: var(--text-dim); font-size: 16px;
  cursor: pointer; border-radius: 2px; display: flex; align-items: center; justify-content: center;
}
.gc-close:hover { color: #D07050; border-color: #D07050; }

/* 武将标签栏 */
.gc-tabs {
  display: flex; gap: 0; border-bottom: 1px solid #3a3028;
  background: rgba(0,0,0,0.2); overflow-x: auto;
  padding: 0 8px; align-items: stretch;
}
.gc-faction-label {
  padding: 8px 12px; font-family: "STKaiti","KaiTi",serif;
  font-size: 10px; color: rgba(208,112,80,0.5);
  background: rgba(208,112,80,0.05); border-right: 1px solid rgba(208,112,80,0.1);
  white-space: nowrap; display: flex; align-items: center; letter-spacing: 2px;
}
.gc-tab {
  padding: 6px 12px; font-family: "FangSong",serif; font-size: 11px;
  background: transparent; border: none; border-bottom: 2px solid transparent;
  color: var(--text-dim); cursor: pointer; white-space: nowrap;
  display: flex; flex-direction: column; align-items: center; gap: 1px;
  transition: all 0.15s;
}
.gc-tab:hover { color: #E0D5C0; background: rgba(208,112,80,0.05); }
.gc-tab.active { color: #D07050; border-bottom-color: #D07050; background: rgba(208,112,80,0.08); }
.gc-tab-icon { font-size: 14px; }
.gc-tab-name { font-size: 12px; font-family: "STKaiti","KaiTi",serif; letter-spacing: 1px; }
.gc-tab-role { font-size: 9px; color: var(--text-muted); }
.gc-tab.active .gc-tab-role { color: rgba(208,112,80,0.6); }
.gc-war-council { margin-left: auto; }
.gc-war-council.active { color: #E8A040; border-bottom-color: #E8A040; }

/* 对话区 */
.gc-chat-area {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column; gap: 10px;
  background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(208,112,80,0.01) 2px, rgba(208,112,80,0.01) 4px);
}
.gc-welcome { text-align: center; padding: 48px 20px; }
.gc-welcome-seal {
  width: 56px; height: 56px; margin: 0 auto 16px;
  border: 2px solid #D07050; border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  font-size: 28px; color: #D07050; font-family: "STKaiti","KaiTi",serif;
  transform: rotate(-3deg);
}
.gc-welcome p { font-size: 16px; color: var(--text-main); letter-spacing: 2px; }
.gc-welcome-sub { font-size: 12px !important; color: var(--text-dim) !important; margin-top: 6px; }

/* 武将介绍卡片 */
.gc-intro {
  text-align: center; padding: 20px;
  border: 1px solid rgba(208,112,80,0.15);
  border-radius: 3px;
  background: linear-gradient(180deg, rgba(208,112,80,0.06) 0%, rgba(208,112,80,0.02) 100%);
}
.gc-intro-frame { margin: 0 auto 10px; display: flex; justify-content: center; border-radius: 4px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.4); }
.gc-intro-header { display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 4px; }
.gc-intro-name { font-size: 20px; font-family: "STKaiti","KaiTi",serif; color: #D07050; letter-spacing: 4px; }
.gc-intro-style { font-size: 12px; color: var(--text-dim); font-family: "FangSong",serif; }
.gc-intro-title { font-size: 13px; color: var(--text-dim); margin-bottom: 8px; }
.gc-intro-tags { display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; margin-bottom: 8px; }
.gc-tag {
  padding: 2px 10px; font-size: 10px; font-family: "FangSong",serif;
  background: rgba(208,112,80,0.1); border: 1px solid rgba(208,112,80,0.2);
  color: #D0A070; border-radius: 2px;
}
.gc-intro-stats { display: flex; gap: 14px; justify-content: center; margin-bottom: 8px; }
.gc-stat {
  font-size: 10px; font-family: "FangSong",serif; color: var(--text-dim);
  padding: 1px 8px; border: 1px solid rgba(208,112,80,0.12);
  border-radius: 2px; background: rgba(208,112,80,0.04);
}
.gc-intro-personality { font-size: 12px; color: var(--text-dim); margin-bottom: 8px; font-family: "FangSong",serif; }
.gc-intro-greeting { font-size: 14px; color: var(--text-main); font-family: "STKaiti","KaiTi",serif; letter-spacing: 2px; }

/* 军议介绍 */
.gc-council-intro { text-align: center; padding: 48px 20px; }
.gc-council-seal {
  width: 56px; height: 56px; margin: 0 auto 16px;
  border: 2px solid #E8A040; border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  font-size: 28px; color: #E8A040; font-family: "STKaiti","KaiTi",serif;
  transform: rotate(-3deg);
}
.gc-council-intro p { font-size: 16px; color: var(--text-main); letter-spacing: 2px; }

/* 军议进度 */
.gc-council-progress { display: flex; gap: 8px; justify-content: center; margin-top: 8px; }
.gc-dot { font-size: 10px; color: rgba(208,112,80,0.2); transition: color 0.4s ease; }
.gc-dot.active { color: #D07050; }

/* 消息气泡 */
.gc-message {
  max-width: 85%; padding: 12px 16px;
  border-radius: 3px; font-size: 13px; line-height: 1.8;
}
.msg-user {
  align-self: flex-end;
  background: linear-gradient(180deg, rgba(146,60,40,0.15) 0%, rgba(146,60,40,0.06) 100%);
  border: 1px solid rgba(146,60,40,0.25);
}
.msg-user .gc-msg-label { color: #D07050; font-family: "STKaiti","KaiTi",serif; }
.msg-ai {
  align-self: flex-start;
  background: linear-gradient(180deg, rgba(208,112,80,0.06) 0%, rgba(208,112,80,0.02) 100%);
  border: 1px solid rgba(208,112,80,0.15);
  border-left: 3px solid #D07050;
}
.msg-ai .gc-msg-label { color: #D07050; font-family: "STKaiti","KaiTi",serif; }
.msg-system {
  align-self: stretch;
  background: rgba(208,112,80,0.05);
  border: 1px solid rgba(208,112,80,0.1);
  border-radius: 2px; text-align: center; font-size: 12px;
}
.msg-system .gc-msg-label { color: rgba(208,112,80,0.7); }
.gc-msg-label { font-size: 10px; margin-bottom: 6px; letter-spacing: 2px; }
.gc-msg-content { white-space: pre-wrap; }
.gc-msg-time { font-size: 9px; color: var(--text-muted); margin-top: 6px; text-align: right; font-family: "FangSong",serif; }

/* 军议消息 */
.council-msg { border-left-width: 4px !important; }
.gc-council-name { font-size: 12px; font-weight: bold; }
.gc-council-title { font-size: 9px; color: var(--text-muted); margin-left: 6px; }
.gc-council-summary {
  border: 1px solid rgba(232,160,64,0.2) !important;
  background: rgba(232,160,64,0.05) !important;
}
.gc-council-summary .gc-msg-label { color: #E8A040 !important; }

/* 输入区 */
.gc-input-area {
  border-top: 1px solid #3a3028; padding: 10px 14px;
  background: rgba(0,0,0,0.2);
}
.gc-council-input-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 8px; font-size: 13px; color: #E8A040;
  font-family: "STKaiti","KaiTi",serif;
}
.gc-council-input {
  flex: 1; padding: 6px 12px; background: var(--bg-input);
  border: 1px solid var(--border-main); border-radius: 2px;
  font-family: "SimSun",serif; font-size: 13px; color: var(--text-main);
}
.gc-council-input:focus { outline: none; border-color: #E8A040; }
.gc-quick-asks { display: flex; gap: 4px; margin-bottom: 8px; flex-wrap: wrap; }
.gc-quick-btn {
  padding: 4px 12px; font-size: 10px; font-family: "FangSong",serif;
  background: rgba(208,112,80,0.06); border: 1px solid rgba(208,112,80,0.15);
  color: var(--text-dim); cursor: pointer; border-radius: 2px; letter-spacing: 1px;
  transition: all 0.15s;
}
.gc-quick-btn:hover { background: rgba(208,112,80,0.15); color: #D07050; border-color: rgba(208,112,80,0.3); }
.gc-input-row { display: flex; gap: 8px; align-items: flex-start; }
.gc-input {
  flex: 1; padding: 10px 14px; background: var(--bg-input);
  border: 1px solid var(--border-main); border-radius: 2px;
  font-family: "SimSun",serif; font-size: 13px; color: var(--text-main);
  resize: none; min-height: 60px; line-height: 1.7;
  background-image: repeating-linear-gradient(0deg, transparent, transparent 19px, rgba(208,112,80,0.03) 19px, rgba(208,112,80,0.03) 20px);
}
.gc-input::placeholder { color: var(--text-muted); font-family: "FangSong",serif; }
.gc-input:focus { outline: none; border-color: #D07050; box-shadow: 0 0 0 2px rgba(208,112,80,0.1); }
.gc-send-btn {
  padding: 10px 20px; font-family: "STKaiti","KaiTi",serif; font-size: 15px;
  background: linear-gradient(180deg, #D07050 0%, #A05030 100%);
  color: #fff; border: 1px solid #D07050; border-radius: 2px;
  cursor: pointer; letter-spacing: 3px; writing-mode: vertical-rl;
  white-space: nowrap; font-weight: bold; transition: all 0.15s;
}
.gc-send-btn:hover:not(:disabled) {
  background: linear-gradient(180deg, #E08060 0%, #B05838 100%);
  box-shadow: 0 2px 12px rgba(208,112,80,0.2);
}
.gc-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
