/**
 * useAdvisorChat - 策问模块状态管理 Composable
 *
 * 职责：
 * 1. 势力↔谋士映射与动态加载
 * 2. 独立对话上下文管理（每NPC隔离）
 * 3. API 调用封装（解耦 UI 与后端交互）
 * 4. 对话历史持久化（localStorage 备份）
 *
 * 将原本散落在 gameStore.ts / AdvisorPanel.vue / AdvisorPopup.vue
 * 中的状态和逻辑统一收拢到这里。
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'

// ---- 角色列表 ----
export const ADVISER_ROLES = [
  { key: 'strategist', label: '军师谋主', color: '#C9AC78' },
  { key: 'chancellor', label: '宰辅重臣', color: '#B89B68' },
  { key: 'general', label: '大将统帅', color: '#E07060' },
  { key: 'scholar', label: '文宗学士', color: '#8EB89B' },
  { key: 'diplomat', label: '纵横使节', color: '#78A0C9' },
  { key: 'economist', label: '理财能臣', color: '#C9B878' },
  { key: 'reformer', label: '变法志士', color: '#C97878' },
  { key: 'ruler', label: '封疆之主', color: '#A07850' },
] as const

// ---- 势力↔谋士团名称映射表 ----
const FACTION_ADVISER_LABELS: Record<string, string> = {
  faction_zhuyuanzhang: '西吴谋士团',
  faction_yuan: '元廷谋士团',
  faction_chenyouliang: '汉国谋士团',
  faction_zhangshicheng: '周国谋士团',
  faction_fangguozhen: '浙东谋士团',
  faction_xushouhui: '天完谋士团',
  faction_mingyuzhen: '大夏谋士团',
  faction_wangbaobao: '河南谋士团',
  faction_mobei: '漠北谋士团',
  // 旧格式兼容
  ruler_zhuyuan: '西吴谋士团',
  ruler_yuan: '元廷谋士团',
  ruler_chen: '汉国谋士团',
  ruler_zhang: '周国谋士团',
  ruler_wang: '河南谋士团',
  ruler_ming: '大夏谋士团',
  ruler_fang: '浙东谋士团',
  ruler_tatar: '漠北谋士团',
  ruler_xushou: '天完谋士团',
}

// ---- 类型定义 ----

export interface NPCAdviser {
  npc_id: string
  name: string
  style_name: string
  title: string
  role: string
  role_label: string
  specialties: string[]
  personality: string
  greeting: string
  speaking_style: string
  faction: string
  model_temp: number
  wisdom: number
  loyalty: number
  ambition: number
}

export interface ChatMessage {
  role: 'user' | 'ai' | 'system'
  content: string
  time?: string
  npcId?: string
  npcName?: string
  npcTitle?: string
}

export interface DebateMessage {
  npc_id: string
  npc_name: string
  title: string
  role_label: string
  role: string
  opinion: string
}

export interface ConversationSession {
  npc_id: string
  messages: ChatMessage[]
  lastActiveAt: number
}

// ---- Composable ----

export function useAdvisorChat() {
  const store = useGameStore()

  // ===================== 状态 =====================

  /** 全部 NPC 列表 */
  const npcList = ref<NPCAdviser[]>([])
  /** 当前势力专属谋士 */
  const factionAdvisers = ref<NPCAdviser[]>([])
  /** 当前选中的 NPC ID */
  const selectedNpcId = ref('')
  /** 通用对话消息（未选中 NPC 时） */
  const messages = ref<ChatMessage[]>([])
  /** 廷议消息 */
  const debateMessages = ref<DebateMessage[]>([])

  /** 加载状态 */
  const loading = ref(false)
  const npcsLoading = ref(false)

  /** 廷议状态 */
  const debateMode = ref(false)
  const debateTopic = ref('')
  const debateLoading = ref(false)
  const debateSummary = ref('')
  const debateResolved = ref(false)
  const resolutionApplying = ref(false)
  const resolutionResultText = ref('')

  /** 每个 NPC 独立对话历史: npc_id -> ChatMessage[] */
  const npcConversations = ref<Record<string, ChatMessage[]>>({})

  // ===================== 计算属性 =====================

  const currentNPC = computed<NPCAdviser | null>(() => {
    if (!selectedNpcId.value) return null
    return npcList.value.find(n => n.npc_id === selectedNpcId.value) || null
  })

  const factionAdviserTitle = computed(() => {
    return FACTION_ADVISER_LABELS[store.playerFactionId] || `${store.playerFaction?.name || ''}谋士团`
  })

  /** NPC 颜色映射 */
  function getNPCColor(role: string): string {
    const entry = ADVISER_ROLES.find(r => r.key === role)
    return entry?.color || '#B89B68'
  }

  // ===================== 数据加载 =====================

  /** 加载 NPC 列表（按势力动态加载） */
  async function loadNPCs(role?: string, factionId?: string) {
    npcsLoading.value = true
    try {
      const fid = factionId || store.playerFactionId
      const result = await API.listNPCs(role, fid)
      npcList.value = (result?.npcs || []).map((n: any) => ({
        npc_id: n.npc_id,
        name: n.name,
        style_name: n.style_name || '',
        title: n.title || '',
        role: n.role || '',
        role_label: n.role_label || '',
        specialties: n.specialties || [],
        personality: n.personality || '',
        greeting: n.greeting || '',
        speaking_style: n.speaking_style || '',
        faction: n.faction || '',
        model_temp: n.model_temp || 0.7,
        wisdom: n.wisdom || 80,
        loyalty: n.loyalty || 80,
        ambition: n.ambition || 30,
      }))
      factionAdvisers.value = npcList.value.filter(n => n.faction === fid)
      return npcList.value
    } catch (err) {
      console.warn('NPC列表加载失败:', err)
      return []
    } finally {
      npcsLoading.value = false
    }
  }

  /** 加载势力谋士团详情（含元信息） */
  async function loadFactionAdvisers(factionId?: string) {
    try {
      const fid = factionId || store.playerFactionId
      const result = await API.getFactionAdvisers(fid)
      if (result?.advisers) {
        factionAdvisers.value = result.advisers
          .filter((a: any) => a.faction === fid)
          .map((a: any) => ({
            npc_id: a.npc_id,
            name: a.name,
            style_name: a.style_name || '',
            title: a.title || '',
            role: a.role || '',
            role_label: a.role_label || '',
            specialties: a.specialties || [],
            personality: a.personality || '',
            greeting: a.greeting || '',
            speaking_style: a.speaking_style || '',
            faction: a.faction || '',
            model_temp: a.model_temp || 0.7,
            wisdom: a.wisdom || 80,
            loyalty: a.loyalty || 80,
            ambition: a.ambition || 30,
          }))
        return result
      }
    } catch (err) {
      console.warn('势力谋士团加载失败:', err)
    }
    return null
  }

  // ===================== NPC 选择与对话上下文切换 =====================

  /** 选择 NPC（自动切换独立对话上下文） */
  function selectNPC(npcId: string) {
    if (selectedNpcId.value === npcId) {
      selectedNpcId.value = ''
      return
    }
    selectedNpcId.value = npcId
    debateMode.value = false

    // 切换到该 NPC 的独立对话历史
    const history = npcConversations.value[npcId]
    if (history && history.length > 0) {
      messages.value = [...history]
    } else {
      messages.value = []
    }
  }

  /** 取消选择 NPC */
  function deselectNPC() {
    selectedNpcId.value = ''
    messages.value = []
  }

  // ===================== 对话发送 =====================

  /** 发送消息（自动根据 selectedNpcId 路由到通用/指定NPC对话） */
  async function sendMessage(text: string): Promise<ChatMessage | null> {
    if (!text.trim() || loading.value) return null

    const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    const userMsg: ChatMessage = { role: 'user', content: text.trim(), time: now }
    messages.value.push(userMsg)

    if (selectedNpcId.value) {
      // 同步到独立对话历史
      if (!npcConversations.value[selectedNpcId.value]) {
        npcConversations.value[selectedNpcId.value] = []
      }
      npcConversations.value[selectedNpcId.value].push(userMsg)
    }

    loading.value = true

    try {
      let response: any = null

      if (selectedNpcId.value) {
        // 与指定 NPC 对话
        response = await _chatWithNPC(selectedNpcId.value, text.trim())
      } else {
        // 通用谋臣对话
        response = await _chatWithMinister(text.trim())
      }

      if (response?.response) {
        const aiMsg: ChatMessage = {
          role: 'ai',
          content: response.response,
          npcId: response.npc_id || '',
          npcName: response.npc_name || '',
          npcTitle: response.npc_title || '',
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        }
        messages.value.push(aiMsg)

        if (selectedNpcId.value) {
          npcConversations.value[selectedNpcId.value].push(aiMsg)
          // 限制历史长度
          const hist = npcConversations.value[selectedNpcId.value]
          if (hist.length > 30) {
            npcConversations.value[selectedNpcId.value] = hist.slice(-30)
          }
        }

        persistConversations()
        return aiMsg
      }
      return null
    } catch (err: any) {
      console.warn('谋臣对话失败:', err)
      const errorMsg: ChatMessage = {
        role: 'system',
        content: _buildFallbackAdvice(),
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      }
      messages.value.push(errorMsg)
      return errorMsg
    } finally {
      loading.value = false
    }
  }

  /** 与指定 NPC 对话（内部） */
  async function _chatWithNPC(npcId: string, message: string): Promise<any> {
    const result = await API.npcChat({
      npc_id: npcId,
      faction_id: store.playerFactionId,
      message,
      world_state: _buildWorldSnapshot(),
    })
    return result
  }

  /** 通用谋臣对话（内部） */
  async function _chatWithMinister(message: string): Promise<any> {
    const result = await API.strategicAdvice({
      faction_id: store.playerFactionId,
      question: message,
      world_state: _buildWorldSnapshot(),
      round: store.currentRound,
    })
    return result
  }

  // ===================== 廷议 =====================

  async function startDebate(topic: string, npcIds?: string[]) {
    if (!topic || loading.value) return

    debateLoading.value = true
    loading.value = true
    debateMessages.value = []
    debateSummary.value = ''
    debateResolved.value = false
    resolutionResultText.value = ''

    try {
      const result = await API.courtDebate({
        topic,
        faction_id: store.playerFactionId,
        npc_ids: npcIds,
        world_state: _buildWorldSnapshot(),
      })
      if (result?.opinions) {
        debateMessages.value = result.opinions
        debateSummary.value = result.summary || ''
      }
    } catch {
      debateMessages.value = [{
        npc_id: '',
        npc_name: '廷议官',
        title: '奏报',
        role_label: '',
        role: '',
        opinion: '廷议暂无法举行。',
      }]
    } finally {
      debateLoading.value = false
      loading.value = false
    }
  }

  async function applyResolution(resolutionType: string, overrideText: string = '') {
    if (resolutionApplying.value) return
    resolutionApplying.value = true

    try {
      const result = await API.applyDebateResult({
        faction_id: store.playerFactionId,
        topic: debateTopic.value || '未记录议题',
        summary: debateSummary.value || '',
        resolution: resolutionType,
        override_text: overrideText,
        debate_npcs: debateMessages.value.map(o => ({
          npc_id: o.npc_id,
          npc_name: o.npc_name,
          role_label: o.role_label,
        })),
      })

      debateResolved.value = true

      const labels: Record<string, string> = {
        accept_consensus: '采纳众议', partial_accept: '择善而从',
        table_discussion: '容后再议', override_decision: '乾纲独断',
      }

      let text = `陛下${labels[resolutionType] || '裁决已定'}。`
      if (result?.stability_change !== undefined) {
        const sign = result.stability_change >= 0 ? '+' : ''
        text += ` 朝纲${sign}${result.stability_change}。`
      }
      resolutionResultText.value = text

      await store.refreshWorldState()
    } catch (e) {
      console.warn('廷议决议失败:', e)
      resolutionResultText.value = '廷议决议未能生效。'
      debateResolved.value = true
    } finally {
      resolutionApplying.value = false
    }
  }

  // ===================== 对话管理 =====================

  /** 清除指定 NPC 的独立对话历史 */
  function clearNPCConversation(npcId: string) {
    delete npcConversations.value[npcId]
    if (selectedNpcId.value === npcId) {
      messages.value = []
    }
    persistConversations()
  }

  /** 清除全部对话历史 */
  function clearAllConversations() {
    messages.value = []
    npcConversations.value = {}
    debateMessages.value = []
    debateSummary.value = ''
    persistConversations()
  }

  // ===================== 持久化（localStorage） =====================

  function getStorageKey(): string {
    return `yuanmo_advisor_conv_${store.playerFactionId}`
  }

  function persistConversations() {
    try {
      const data = {
        general: messages.value.slice(-40),
        npcConversations: npcConversations.value,
        debateSummary: debateSummary.value,
      }
      localStorage.setItem(getStorageKey(), JSON.stringify(data))
    } catch { /* 忽略 */ }
  }

  function restoreConversations() {
    try {
      const saved = localStorage.getItem(getStorageKey())
      if (saved) {
        const data = JSON.parse(saved)
        if (data.general) messages.value = data.general
        if (data.npcConversations) npcConversations.value = data.npcConversations
        if (data.debateSummary) debateSummary.value = data.debateSummary
      }
    } catch { /* 忽略 */ }
  }

  // ===================== 辅助 =====================

  function _buildWorldSnapshot(): any {
    return {
      factions: store.factions || {},
      current_round: store.currentRound,
      current_year: store.currentYear,
      current_season: store.currentSeason,
      player_faction_id: store.playerFactionId,
      relations: store.relations || {},
      events_log: [],
    }
  }

  function _buildFallbackAdvice(): string {
    const pf = store.playerFaction
    const tiles = store.playerTiles || []
    const troops = store.totalTroops || 0

    const enemies: string[] = []
    const allies: string[] = []
    for (const [k, r] of Object.entries(store.relations as Record<string, any> || {})) {
      const parts = k.split('|')
      if (!parts.includes(store.playerFactionId)) continue
      const otherId = parts[0] === store.playerFactionId ? parts[1] : parts[0]
      const otherFaction = (store.factions as Record<string, any>)?.[otherId]
      if (r.stance === 'war') enemies.push(otherFaction?.name || otherId)
      else if (r.stance === 'alliance') allies.push(otherFaction?.name || otherId)
    }

    const lines = [
      `【天下大势】至正${store.currentYear}年${store.currentSeason}季，第${store.currentRound}回合。${pf?.name || '我方'}占据${tiles.length}块领地，总兵力${troops}人。`,
    ]
    if (enemies.length) lines.push(`当前与${enemies.join('、')}处于敌对状态。`)
    if (allies.length) lines.push(`与${allies.join('、')}结盟。`)
    lines.push('')
    if (store.realmStability < 40) lines.push(`【内政要务】民心不稳(${store.realmStability})，建议优先安抚百姓。`)
    else if (troops < 2000) lines.push(`【军事方略】兵力不足(${troops}人)，建议征兵加强防线。`)
    else lines.push(`【军事方略】审视地图，对薄弱邻国发动进攻，扩充疆土。`)
    return lines.join('\n')
  }

  // ===================== 重置 =====================

  function reset() {
    npcList.value = []
    factionAdvisers.value = []
    selectedNpcId.value = ''
    messages.value = []
    debateMessages.value = []
    npcConversations.value = {}
    debateMode.value = false
    debateTopic.value = ''
    debateSummary.value = ''
    debateResolved.value = false
    resolutionResultText.value = ''
  }

  // ---- 游戏开局时自动加载 ----
  watch(() => store.isGameStarted, async (started) => {
    if (started && store.playerFactionId) {
      await loadNPCs(undefined, store.playerFactionId)
      await loadFactionAdvisers(store.playerFactionId)
      restoreConversations()
    }
  }, { immediate: true })

  return {
    // 状态
    npcList,
    factionAdvisers,
    selectedNpcId,
    currentNPC,
    messages,
    debateMessages,
    npcConversations,
    // 加载状态
    loading,
    npcsLoading,
    // 廷议
    debateMode,
    debateTopic,
    debateLoading,
    debateSummary,
    debateResolved,
    resolutionApplying,
    resolutionResultText,
    factionAdviserTitle,
    // 方法
    loadNPCs,
    loadFactionAdvisers,
    selectNPC,
    deselectNPC,
    sendMessage,
    startDebate,
    applyResolution,
    clearNPCConversation,
    clearAllConversations,
    getNPCColor,
    reset,
  }
}
