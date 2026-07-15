/**
 * API 服务层 - 统一 axios 封装
 * 
 * 对接规范:
 * - 所有接口统一 code/msg/data 格式
 * - 请求拦截器: 超时/报错/加载提示
 * - 响应拦截器: 统一code处理/toast/日志
 * - 前端不存游戏核心逻辑，纯展示层
 */
import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import type {
  FactionConfig,
  CounterRelation,
  EdictResult,
  BattleResult,
  WorldState,
} from '@/types'

// ============================================================
// 超时/重试/中断信号配置
// ============================================================

const DEFAULT_TIMEOUT = 120000         // 默认120秒
const AI_TIMEOUT = 180000              // AI调用180秒
const RETRY_DELAY_BASE = 1000          // 重试基础延迟1秒
const MAX_RETRIES = 3                  // 最大重试次数

/** 判断是否为可重试的网络错误 */
function isRetryableError(error: any): boolean {
  // 网络超时
  if (error.code === 'ECONNABORTED') return true
  // 无响应（服务不可达）
  if (!error.response) return true
  // 服务端错误（5xx）
  if (error.response?.status >= 500) return true
  // 限流（429）
  if (error.response?.status === 429) return true
  return false
}

// ============================================================
// 统一响应结构
// ============================================================
export interface ApiResponse<T = any> {
  code: number
  msg: string
  data: T
}

// ============================================================
// Toast 提示（轻量级古风提示）
// ============================================================
let _toastTimer: ReturnType<typeof setTimeout> | null = null
let _toastEl: HTMLDivElement | null = null

export function showToast(msg: string, type: 'info' | 'error' | 'success' = 'info') {
  // 移除旧toast
  if (_toastEl) {
    _toastEl.remove()
    if (_toastTimer) clearTimeout(_toastTimer)
  }

  const el = document.createElement('div')
  el.className = `api-toast api-toast-${type}`
  el.textContent = msg
  el.style.cssText = `
    position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
    padding: 10px 24px; border-radius: 3px; z-index: 99999;
    font-family: "STKaiti","KaiTi",serif; font-size: 14px; letter-spacing: 2px;
    background: ${type === 'error' ? '#5C1A15' : type === 'success' ? '#2C3320' : '#2C2824'};
    color: ${type === 'error' ? '#E07060' : type === 'success' ? '#B89B68' : '#EAE3D6'};
    border: 1px solid ${type === 'error' ? '#9E2B25' : type === 'success' ? '#B89B68' : '#443F38'};
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    animation: toastFadeIn 0.3s ease;
  `
  document.body.appendChild(el)
  _toastEl = el

  _toastTimer = setTimeout(() => {
    el.style.opacity = '0'
    el.style.transition = 'opacity 0.3s'
    setTimeout(() => el.remove(), 300)
    _toastEl = null
  }, 3000)
}

// 注入 toast 动画样式
if (typeof document !== 'undefined') {
  const style = document.createElement('style')
  style.textContent = `
    @keyframes toastFadeIn {
      from { opacity: 0; transform: translateX(-50%) translateY(-10px); }
      to { opacity: 1; transform: translateX(-50%) translateY(0); }
    }
  `
  document.head.appendChild(style)
}

// ============================================================
// Axios 实例
// ============================================================

export const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: DEFAULT_TIMEOUT,
  headers: { 'Content-Type': 'application/json' },
})

// 内部别名，兼容已有代码
const api = apiClient

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 可在此添加 loading 状态
    return config
  },
  (error) => {
    showToast('请求发送失败', 'error')
    return Promise.reject(error)
  }
)

// 响应拦截器 - 统一 code 处理
api.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    // 防御: response 或 response.data 可能为 null/undefined
    if (!response || !response.data) {
      showToast('服务器返回空响应', 'error')
      return Promise.reject(new Error('服务器返回空响应'))
    }
    const { code, msg, data } = response.data

    if (code === 200) {
      // 成功 - 静默通过
      return response
    }

    // 业务错误
    if (code === 400) {
      showToast(msg || '参数有误', 'error')
    } else if (code === 403) {
      showToast(msg || '指令不合法', 'error')
    } else if (code === 404) {
      showToast(msg || '资源不存在', 'error')
    } else if (code === 503) {
      showToast(msg || 'AI服务不可用', 'error')
    } else if (code >= 500) {
      showToast(msg || '服务器异常', 'error')
    }

    return Promise.reject(new Error(msg || `请求失败 (${code})`))
  },
  (error) => {
    if (error.code === 'ECONNABORTED') {
      showToast('请求超时，请检查网络连接', 'error')
    } else if (!error.response) {
      showToast('无法连接服务器，请检查后端是否启动', 'error')
    } else {
      // 尝试从服务端响应中提取业务错误信息
      const respData = error.response?.data
      if (respData && typeof respData === 'object') {
        const bizMsg = respData.msg || respData.detail || respData.message
        if (bizMsg) {
          showToast(bizMsg, 'error')
        } else {
          showToast(`服务器错误 (${error.response.status})`, 'error')
        }
      } else {
        showToast(`服务器错误 (${error.response.status})`, 'error')
      }
    }
    return Promise.reject(error)
  }
)

// ============================================================
// 请求重试封装（增强版：支持中断信号 + 可配置重试）
// ============================================================

// Bug F2修复: 新增skipRetry参数，POST非幂等操作默认不重试
async function withRetry<T>(
  fn: () => Promise<T>,
  retries: number = MAX_RETRIES,
  delayBase: number = RETRY_DELAY_BASE,
  signal?: AbortSignal,
  skipRetry: boolean = false,
): Promise<T> {
  // 非幂等操作不重试
  const actualRetries = skipRetry ? 0 : retries
  for (let i = 0; i <= actualRetries; i++) {
    // 检查中断信号
    if (signal?.aborted) {
      throw new DOMException('请求已被取消', 'AbortError')
    }
    try {
      return await fn()
    } catch (err: any) {
      // 中断信号触发的错误直接抛出
      if (axios.isCancel(err) || err?.name === 'AbortError') {
        throw err
      }
      // 非可重试错误或已达最大重试次数
      if (!isRetryableError(err) || i === actualRetries) {
        throw err
      }
      // 指数退避：1s, 2s, 4s
      const delay = delayBase * Math.pow(2, i)
      console.warn(`[API] 第${i + 1}次重试，延迟${delay}ms...`, err?.message || err)
      await new Promise(r => setTimeout(r, delay))
    }
  }
  throw new Error('请求失败（已达最大重试次数）')
}

/**
 * 带 AbortSignal 的请求封装
 * 注意：axios 本身通过 config.signal 支持 AbortSignal
 *       此封装提供组件卸载时的自动取消
 */
export function createAbortController(): AbortController {
  return new AbortController()
}

/**
 * 给任意 API 调用附加中断信号
 * Bug F4修复: 将AbortSignal透传给axios
 * 用法: const ctrl = createAbortController(); await withSignal(apiCallFn, ctrl.signal)
 */
export async function withSignal<T>(
  fn: (config?: any) => Promise<T>,
  signal: AbortSignal,
): Promise<T> {
  if (signal.aborted) {
    throw new DOMException('请求已被取消', 'AbortError')
  }
  // Bug F4修复: 将signal透传给axios config
  return fn({ signal })
}

// ============================================================
// 错误转义（将后端ApiResponse格式转为前端友好的提示）
// ============================================================

export function getApiErrorMessage(error: any): string {
  if (typeof error === 'string') return error
  const respData = error?.response?.data
  if (respData?.msg) return respData.msg
  if (respData?.detail) return respData.detail
  if (respData?.message) return respData.message
  if (error?.message) return error.message
  return '未知错误'
}

// ============================================================
// API 方法
// ============================================================

// ----- 核心 -----

export async function healthCheck(): Promise<any> {
  const { data } = await api.get('/health')
  return data.data
}

// ----- 配置 -----

export async function loadFactionsConfig(): Promise<{
  version: string
  factions: Record<string, FactionConfig>
  counter_relations: CounterRelation[]
}> {
  const { data } = await api.get('/config/factions', { timeout: 10000 })
  return data.data
}

export async function loadFactionDetail(factionId: string): Promise<FactionConfig> {
  const { data } = await api.get(`/config/faction/${factionId}`)
  return data.data
}

export async function loadGameConstants(): Promise<Record<string, any>> {
  const { data } = await api.get('/config/constants')
  return data.data
}

export async function loadCounterRelations(): Promise<CounterRelation[]> {
  const { data } = await api.get('/config/counter-relations')
  return data.data
}

// ----- 运行时配置（设置面板） -----

export async function getRuntimeConfig(): Promise<Record<string, any>> {
  const { data } = await api.get('/config/runtime')
  return data.data
}

export async function updateRuntimeConfig(config: Record<string, any>): Promise<any> {
  const { data } = await api.post('/config/runtime', config)
  return data.data
}

export async function getDefaultConfig(): Promise<Record<string, any>> {
  const { data } = await api.get('/config/default')
  return data.data
}

/**
 * 真实 AI 模型连通性测试（逐模型发送测试请求）
 * @param models 要测试的模型列表，默认全部 ["advisor", "law", "enemy"]
 */
export async function testLLMConnection(models?: string[]): Promise<{
  passed: boolean
  configured: boolean
  message: string
  results: Record<string, { status: string; model_name: string; latency_ms: number; error?: string; api_base?: string; response_preview?: string }>
}> {
  const { data } = await api.post('/config/test-llm', { models: models || ['advisor', 'law', 'enemy'] })
  return data.data
}

// ----- 游戏控制（链路1: 开局初始化） -----

export async function initGame(params: {
  faction_id: string
  mode?: string
  custom_faction?: Record<string, any>
}): Promise<{
  world_state: WorldState
  player_faction: any
  player_faction_id: string
  factions: Record<string, any>
  tiles: Record<string, any>
  relations: Record<string, any>
  events_log: any[]
  mode_info?: any
}> {
  const { data } = await withRetry(() => api.post('/game/init', params))
  if (data.msg && data.msg !== 'success') {
    showToast(data.msg, 'error')  // Bug F3修复: 错误消息用error类型
  }
  return data.data
}

export async function restartGame(): Promise<any> {
  const { data } = await api.post('/game/restart')
  return data.data
}

export async function getGameStatus(): Promise<{
  running: boolean
  game_active: boolean
  world_state?: WorldState
  pending_commands?: number
  snapshots_count?: number
}> {
  const { data } = await api.get('/game/status')
  return data.data
}

// ----- 指令提交（链路2） -----

// P3: 防重复提交 — 同一端点正在 inflight 时拒绝重复调用
const _inflight = new Map<string, Promise<any>>()

function _withDedup<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const existing = _inflight.get(key)
  if (existing) {
    console.warn(`[API] 重复请求已拦截: ${key}`)
    return existing as Promise<T>
  }
  const promise = fn().finally(() => _inflight.delete(key))
  _inflight.set(key, promise)
  return promise
}

export function submitCommand(params: {
  action: string
  params: Record<string, any>
  faction_id?: string
}): Promise<{ command_id: string; pending_count: number; warning?: string }> {
  // Bug F1修复: 去重key包含指令内容哈希，防止不同指令被误拦截
  const dedupKey = `submitCommand:${params.action}:${JSON.stringify(params.params)}`
  return _withDedup(dedupKey, async () => {
    const { data } = await api.post('/game/command', params)
    return data.data
  })
}

export async function getPendingCommands(): Promise<any> {
  const { data } = await api.get('/game/commands')
  return data.data
}

export async function clearCommands(): Promise<any> {
  const { data } = await api.post('/game/commands/clear')
  return data.data
}

// ----- 回合推进（链路3: 游戏心跳） -----

export async function advanceTurn(): Promise<{
  round_summary: any
  world_state: WorldState
  new_events: any[]
  pending_commands_cleared: boolean
  snapshot: any
  ending: any
  tile_changes?: any[]
  mode_info?: any
  locked_actions?: string[]
  cooling_tiles?: Record<string, any[]>
  responsibility_stats?: any
}> {
  // P3: 防止同时多次推进回合
  return _withDedup('advanceTurn', async () => {
    // Bug F2修复: POST推进回合不重试，防止重复推进
    const { data } = await withRetry(() => api.post('/game/advance-turn'), 0, 1000, undefined, true)
    if (data.msg && data.msg !== 'success') {
      showToast(data.msg, 'info')
    }
    return data.data
  })
}

// ----- 圣旨 -----

export async function parseEdict(params: {
  edict_text: string
  faction_id: string
  turn?: number
  season?: string
  treasury?: number
  grain?: number
  troops?: number
  reputation?: number
  court_stability?: number
  realm_stability?: number
  development_level?: number
}): Promise<EdictResult> {
  const { data } = await api.post('/edict/parse', params)
  return data.data
}

/**
 * 圣旨 AI 推演执行（新版核心）
 * 玩家用自然语言输入圣旨 → AI 解析为操作指令 → 直接执行到游戏状态
 */
export interface GlobalDeduction {
  global_narrative: string
  faction_reactions: Array<{
    faction_id?: string
    faction_name: string
    stance: string
    narrative: string
    likely_action: string
    color: string
  }>
  diplomatic_shifts: Array<{
    from: string
    to: string
    change: number
    reason: string
  }>
  event_triggers: Array<{
    event_type: string
    title: string
    description: string
    severity: string
    affected_faction: string
  }>
  economic_ripples: string
  strategic_advice: string
  summary: string
}

export async function executeEdict(params: {
  edict_text: string
  faction_id: string
}): Promise<{
  edict_text: string
  ai_analysis: {
    intent_analysis: string
    narrative: string
    resource_assessment?: string
    edict_language?: string
    summary: string
    commands_count: number
    invalid_count: number
    ai_generated: boolean
    risk_warning?: string
    follow_up_suggestion?: string
  }
  execution: {
    executed: Array<{ action: string; params: any; result: any; ai_reason: string }>
    failed: Array<{ action: string; params: any; reason: string; ai_reason: string }>
    total_executed: number
    total_failed: number
  }
  global_deduction?: GlobalDeduction
  world_state: WorldState
  tile_changes: any[]
  locked_actions: string[]
  cooling_tiles: Record<string, any[]>
}> {
  const { data } = await api.post('/edict/execute', params)
  if (data.msg && data.msg !== 'success') {
    showToast(data.msg, 'error')  // Bug F3修复: 错误消息用error类型
  }
  return data.data
}

// ----- 统一圣旨NL处理（3.2 重构版）-----

export interface NLEdictResult {
  edict_text: string
  classification: {
    primary: string
    sub_intents: string[]
    confidence: number
  }
  entities: {
    faction_ids: string[]
    tile_ids: string[]
    numbers: Record<string, number>
    constraints?: string[]
  }
  validation: Array<{
    command: any
    valid: boolean
    errors: string[]
    warnings: string[]
  }>
  commands: any[]
  commands_count: number
  decomposed_steps: Array<{
    step: number
    turn_offset: number
    text: string
    desc: string
  }>
  ai_analysis: {
    intent_analysis: string
    narrative: string
    resource_assessment?: string
    edict_language?: string
    summary?: string
    risk_warning?: string
    follow_up_suggestion?: string
    ai_generated: boolean
  }
  execution?: {
    executed: any[]
    failed: any[]
    total_executed: number
    total_failed: number
  }
  edict_language: string
  error_prompt: string
  missing_info: Record<string, any>
  summary: string
  is_cancel: boolean
  needs_clarification: boolean
  route_to_advisor?: boolean
}

export async function nlProcessEdict(params: {
  edict_text: string
  faction_id: string
  direct_execute?: boolean
  use_ai?: boolean
}): Promise<NLEdictResult> {
  const { data } = await api.post('/edict/nl-process', params)
  if (data.msg && data.msg !== 'success') {
    showToast(data.msg, 'error')  // Bug F3修复: 错误消息用error类型
  }
  return data.data
}

export interface NLValidateResult {
  edict_text: string
  classification: {
    primary: string
    sub_intents: string[]
    confidence: number
  }
  entities: {
    faction_ids: string[]
    tile_ids: string[]
    numbers: Record<string, number>
  }
  missing_info: Record<string, boolean>
  error_prompt: string
  needs_clarification: boolean
  is_cancel?: boolean
}

export async function nlValidateEdict(text: string): Promise<NLValidateResult> {
  const { data } = await api.post('/edict/nl-validate', { edict_text: text })
  return data.data
}

export async function nlCancelCommands(params: {
  cancel_all?: boolean
  command_ids?: string[]
  cancel_text?: string
}): Promise<{ removed_count: number; remaining_count: number }> {
  const { data } = await api.post('/edict/nl-cancel', params)
  return data.data
}

export async function getEdictLLMConfig(): Promise<{
  api_base: string
  model_name: string
  temperature: number
  max_tokens: number
  available: boolean
}> {
  const { data } = await api.get('/edict/nl-config')
  return data.data
}

export async function updateEdictLLMConfig(config: {
  api_base?: string
  model_name?: string
  temperature?: number
  max_tokens?: number
}): Promise<any> {
  const { data } = await api.post('/edict/nl-config', config)
  return data.data
}

// ----- AI决策 -----

export async function factionAIDecision(params: {
  faction_id: string
  faction_name?: string
  tile_count?: number
  troops?: number
  treasury?: number
  grain?: number
  reputation?: number
  realm_stability?: number
  court_stability?: number
  turn?: number
  season?: string
  neighbors_info?: any[]
  global_situation?: string
}): Promise<any> {
  const { data } = await api.post('/faction/ai-decision', params)
  return data.data
}

// ----- 朝堂 -----

export async function courtMonthlySettlement(params: {
  faction_id: string
  faction_name?: string
  monarch_style?: string
  turn?: number
  court_stability?: number
}): Promise<any> {
  const { data } = await api.post('/court/monthly-settlement', params)
  return data.data
}

export async function courtConflict(params: {
  event_type: string
  faction_id: string
  faction_name?: string
  turn?: number
  court_stability?: number
}): Promise<any> {
  const { data } = await api.post('/court/conflict', params)
  return data.data
}

// ----- 战斗 -----

export async function resolveBattle(params: {
  attacker_faction: string
  defender_faction: string
  tile_id: string
  attacker_troops: number
  defender_troops: number
  wall_level?: number
  season?: string
  terrain?: string
  is_siege?: boolean
}): Promise<BattleResult> {
  const { data } = await api.post('/battle/resolve', params)
  return data.data
}

// ----- 外交 -----

export async function diplomacyAction(params: {
  from_faction: string
  to_faction: string
  action_type: string
  terms?: Record<string, any>
  turn?: number
}): Promise<any> {
  const { data } = await api.post('/diplomacy/action', params)
  return data.data
}

// ----- 灾害 -----

export async function disasterForecast(params: {
  faction_id: string
  turn?: number
  season?: string
  active_disasters?: any[]
  disaster_index?: number
}): Promise<any> {
  const { data } = await api.post('/disaster/forecast', params)
  return data.data
}

// ----- 战略推演 -----

export async function strategyAnalyze(params: {
  faction_id: string
  faction_name?: string
  turn?: number
  season?: string
  tile_count?: number
  troops?: number
  treasury?: number
  reputation?: number
}): Promise<any> {
  const { data } = await api.post('/strategy/analyze', params)
  return data.data
}

// ----- AI 对话（链路4） -----

export async function agentChat(params: {
  faction_id: string
  message: string
  chat_mode?: string
  world_state?: any
}): Promise<any> {
  const { data } = await api.post('/agent/chat', params)
  return data.data
}

export async function strategicAdvice(params: {
  faction_id: string
  question: string
  world_state?: any
  round?: number
  npc_id?: string
  conversation_history?: any[]
}): Promise<any> {
  const { data } = await api.post('/agent/strategic-advice', params)
  return data.data
}

// ----- NPC 文臣对话（每个 NPC 对接腾讯云 AI） -----

export async function listNPCs(role?: string, factionId?: string): Promise<any> {
  const { data } = await api.get('/agent/npcs', { params: { role, faction_id: factionId } })
  return data.data
}

export async function getFactionAdvisers(factionId: string): Promise<any> {
  const { data } = await api.get(`/agent/faction-advisers/${factionId}`)
  return data.data
}

export async function getNPCDetail(npcId: string): Promise<any> {
  const { data } = await api.get(`/agent/npc/${npcId}`)
  return data.data
}

/** 获取可对话的武将 NPC 列表 */
export async function listGenerals(factionId?: string): Promise<any> {
  const params: any = { role: 'general' }
  if (factionId) params.faction_id = factionId
  const { data } = await api.get('/agent/npcs', { params })
  // 后端返回 { code:0, data:{npcs:[...]} }，data.data 才是载荷
  const payload = data?.data || data
  return { generals: payload?.npcs || payload || [] }
}

export async function npcChat(params: {
  npc_id: string
  faction_id: string
  message: string
  world_state?: any
  conversation_history?: any[]
}): Promise<any> {
  const { data } = await api.post('/agent/npc-chat', params)
  return data.data
}

export async function courtDebate(params: {
  topic: string
  faction_id: string
  npc_ids?: string[]
  world_state?: any
}): Promise<any> {
  const { data } = await api.post('/agent/court-debate', params)
  return data.data
}

export async function lawChat(params: {
  faction_id: string
  prisoner_name: string
  question: string
  world_state?: any
}): Promise<any> {
  const { data } = await api.post('/agent/law-chat', params)
  return data.data
}

export async function eventGenerate(params: {
  round: number
  season: string
  disaster_index: number
}): Promise<any> {
  const { data } = await api.post('/agent/event-generate', params)
  return data.data
}

export async function agentToolCall(params: {
  faction_id: string
  prompt: string
  world_state?: any
  tools?: string[]
}): Promise<any> {
  const { data } = await api.post('/agent/tool-call', params)
  return data.data
}

export async function listTools(category?: string): Promise<any> {
  const { data } = await api.get('/agent/tools', { params: { category } })
  return data.data
}

export async function agentAutoStep(params: { world_state: any }): Promise<any> {
  const { data } = await api.post('/agent/auto-step', params)
  return data.data
}

export async function agentStatus(): Promise<any> {
  const { data } = await api.get('/agent/status')
  return data.data
}

/** 全局AI智能体监控面板数据 */
export async function agentDashboard(): Promise<{
  ai_available: boolean
  architecture: string
  model_groups: Record<string, { function: string; agents: string }> | null
  global_stats: {
    total_calls: number
    avg_latency: number
    active_agents: number
    degraded_agents: number
  }
  agents: Array<{
    key: string
    name: string
    model_group: string
    trigger: string
    description: string
    player_only: boolean
    config: any
    circuit_state?: string
    call_count?: number
    avg_latency?: number
    alive?: boolean
    memories?: { short_term: number; mid_term: number; long_term: number }
  }>
  event_bus: { pending_events: number; archived_events: number; recent_round: number }
  edict_stats: { total_decrees: number; last_edicts: any[] }
  edict_action_count: number
}> {
  const { data } = await api.get('/agent/dashboard')
  return data.data
}

// ----- 存档（链路5） -----

export async function listSaves(): Promise<any> {
  const { data } = await api.get('/save/list')
  return data.data
}

export async function saveGame(slot: number, note?: string): Promise<any> {
  const { data } = await api.post('/save/save', { slot, note })
  if (data.msg && data.msg !== 'success') {
    showToast(data.msg, 'error')  // Bug F3修复
  }
  return data.data
}

export async function quickSave(note?: string): Promise<any> {
  const { data } = await api.post('/save/quick-save', { note })
  if (data.msg && data.msg !== 'success') {
    showToast(data.msg, 'error')  // Bug F3修复
  }
  return data.data
}

export async function loadGame(slot: number, filename?: string): Promise<any> {
  const { data } = await api.post('/save/load', { slot, filename })
  if (data.msg && data.msg !== 'success') {
    showToast(data.msg, 'error')  // Bug F3修复
  }
  return data.data
}

export async function deleteSave(filename: string): Promise<any> {
  const { data } = await api.delete('/save/delete', { data: { filename } })
  return data.data
}

export async function clearAllSaves(): Promise<any> {
  const { data } = await api.post('/save/clear-all')
  return data.data
}

export async function exportSaveFile(filename: string): Promise<any> {
  const { data } = await api.post('/save/export', { filename })
  return data.data
}

export async function importSaveFile(saveData: any, filename?: string): Promise<any> {
  const { data } = await api.post('/save/import', { save_data: saveData, filename })
  return data.data
}

export async function getReplaySnapshots(): Promise<any> {
  const { data } = await api.get('/save/replay-snapshots')
  return data.data
}

export async function getReplaySnapshot(roundNum: number): Promise<any> {
  const { data } = await api.get(`/save/replay-snapshot/${roundNum}`)
  return data.data
}

// ----- 地块 -----

export async function getTileDetail(tileId: string): Promise<any> {
  const { data } = await api.get(`/map/tile/${tileId}`)
  return data.data
}

export async function getAllTiles(): Promise<any> {
  const { data } = await api.get('/map/tiles')
  return data.data
}

export async function pathfindRoute(params: {
  from_tile: string
  to_tile: string
  faction_id?: string
}): Promise<any> {
  const { data } = await api.post('/map/pathfind', params)
  return data.data
}

// ----- 谍报细作（系统3） -----

export async function deploySpy(params: {
  owner_faction: string
  target_faction: string
}): Promise<any> {
  const { data } = await api.post('/spy/deploy', params)
  return data.data
}

export async function spyAction(params: {
  owner_faction: string
  target_faction: string
  action_type: string
}): Promise<any> {
  const { data } = await api.post('/spy/action', params)
  return data.data
}

export async function getSpyNetworks(factionId: string): Promise<any> {
  const { data } = await api.get(`/spy/networks/${factionId}`)
  return data.data
}

// ----- 外交（系统5） -----

export async function changeDiplomaticStance(params: {
  faction_a: string
  faction_b: string
  new_stance: string
  reason?: string
}): Promise<any> {
  const { data } = await api.post('/diplomacy/change-stance', params)
  return data.data
}

export async function openTradeRoute(params: {
  faction_a: string
  faction_b: string
}): Promise<any> {
  const { data } = await api.post('/diplomacy/trade', params)
  return data.data
}

export async function proposeMarriage(params: {
  from_faction: string
  to_faction: string
}): Promise<any> {
  const { data } = await api.post('/diplomacy/marriage', params)
  return data.data
}

export async function getFactionRelations(factionId: string): Promise<any> {
  const { data } = await api.get(`/diplomacy/relations/${factionId}`)
  return data.data
}

export async function getDiplomacySummary(factionId: string): Promise<any> {
  const { data } = await api.get(`/diplomacy/summary/${factionId}`)
  return data.data
}

// ----- 联邦/联盟 -----

export async function createCoalition(params: {
  name: string
  founder_faction: string
  description?: string
}): Promise<any> {
  const { data } = await api.post('/diplomacy/coalition/create', params)
  return data.data
}

export async function joinCoalition(params: {
  coalition_id: string
  faction_id: string
}): Promise<any> {
  const { data } = await api.post('/diplomacy/coalition/join', params)
  return data.data
}

export async function leaveCoalition(params: {
  coalition_id: string
  faction_id: string
}): Promise<any> {
  const { data } = await api.post('/diplomacy/coalition/leave', params)
  return data.data
}

export async function dissolveCoalition(params: {
  coalition_id: string
  faction_id: string
}): Promise<any> {
  const { data } = await api.post('/diplomacy/coalition/dissolve', params)
  return data.data
}

export async function listCoalitions(): Promise<any> {
  const { data } = await api.get('/diplomacy/coalitions')
  return data.data
}

// ----- 贸易/朝贡/附庸/停战 -----

export async function closeTradeRoute(params: {
  faction_a: string
  faction_b: string
}): Promise<any> {
  const { data } = await api.post('/diplomacy/trade/close', params)
  return data.data
}

export async function demandTribute(params: {
  suzerain_faction: string
  vassal_faction: string
  amount?: number
}): Promise<any> {
  const { data } = await api.post('/diplomacy/tribute', params)
  return data.data
}

export async function offerVassal(params: {
  suzerain_faction: string
  vassal_faction: string
  terms?: Record<string, any>
}): Promise<any> {
  const { data } = await api.post('/diplomacy/vassal/offer', params)
  return data.data
}

export async function cancelVassal(params: {
  suzerain_faction: string
  vassal_faction: string
}): Promise<any> {
  const { data } = await api.post('/diplomacy/vassal/cancel', params)
  return data.data
}

export async function signPeace(params: {
  faction_a: string
  faction_b: string
  terms?: Record<string, any>
}): Promise<any> {
  const { data } = await api.post('/diplomacy/peace', params)
  return data.data
}

// ----- 朝堂律法（系统2/4） -----

export async function appointOfficial(params: {
  faction_id: string
  name: string
  position: string
  ability?: number
  loyalty?: number
}): Promise<any> {
  const { data } = await api.post('/court/appoint', params)
  return data.data
}

export async function dismissOfficial(officialId: string): Promise<any> {
  const { data } = await api.post('/court/dismiss', { official_id: officialId })
  return data.data
}

export async function executeOfficial(officialId: string): Promise<any> {
  const { data } = await api.post('/court/execute', { official_id: officialId })
  return data.data
}

export async function handlePrisoner(params: {
  prisoner_id: string
  action: string
}): Promise<any> {
  const { data } = await api.post('/court/prisoner', params)
  return data.data
}

export async function getFactionOfficials(factionId: string): Promise<any> {
  const { data } = await api.get(`/court/officials/${factionId}`)
  return data.data
}

export async function getFactionPrisoners(factionId: string): Promise<any> {
  const { data } = await api.get(`/court/prisoners/${factionId}`)
  return data.data
}

export async function getCourtOverview(factionId: string): Promise<any> {
  const { data } = await api.get(`/court/overview/${factionId}`)
  return data.data
}

/**
 * 获取国策总览聚合数据（军事/外交/荒政/谍报/物资）
 * 一次请求聚合所有 PolicyPanel 所需数据，保证与全局一致
 */
export async function getPolicyOverview(factionId: string): Promise<any> {
  const { data } = await api.get(`/court/policy-overview/${factionId}`)
  return data.data
}

export async function applyDebateResult(params: {
  faction_id: string
  topic: string
  summary: string
  resolution: string
  override_text?: string
  debate_npcs?: Array<{ npc_id: string; npc_name: string; role_label: string }>
}): Promise<any> {
  const { data } = await api.post('/court/apply-debate-result', params)
  return data.data
}

export async function getDebateHistory(factionId: string): Promise<any> {
  const { data } = await api.get(`/court/debate-history/${factionId}`)
  return data.data
}

export async function getPolicies(): Promise<any> {
  const { data } = await api.get('/court/policies')
  return data.data
}

export async function unlockPolicy(params: {
  faction_id: string
  policy_id: string
  cost: number
}): Promise<any> {
  const { data } = await api.post('/court/unlock-policy', params)
  return data.data
}

export async function issueDecree(params: {
  faction_id: string
  text: string
}): Promise<any> {
  const { data } = await api.post('/court/decree', params)
  return data.data
}

// ----- 行军/战斗（系统1） -----

export async function resolveMarch(params: {
  from_tile: string
  to_tile: string
  troops: number
  attacker_faction: string
  grain?: number
}): Promise<any> {
  const { data } = await api.post('/march/resolve', params)
  return data.data
}

export async function getMarchPath(params: {
  from_tile: string
  to_tile: string
  troops?: number
}): Promise<any> {
  const { data } = await api.post('/march/path', params)
  return data.data
}

export async function getMarchNeighbors(tileId: string, factionId: string): Promise<any> {
  const params = factionId ? `?faction_id=${factionId}` : ''
  const { data } = await api.get(`/march/neighbors/${tileId}${params}`)
  return data.data
}

// ----- 静态地图基底（六边形地理数据） -----

export async function getStaticMap(): Promise<any> {
  const { data } = await api.get('/map/static')
  return data.data
}

// ----- 藩镇（系统9） -----

export async function checkVassalRebellion(factionId: string): Promise<any> {
  const { data } = await api.get(`/vassal/check/${factionId}`)
  return data.data
}

// ----- 工坊经济（系统6） -----

export async function getWorkshops(factionId: string): Promise<any> {
  const { data } = await api.get(`/economy/workshops/${factionId}`)
  return data.data
}

// ----- 游戏控制信息 -----

export async function getModeInfo(): Promise<any> {
  const { data } = await api.get('/game/mode-info')
  return data.data
}

export async function getOperationLocks(): Promise<any> {
  const { data } = await api.get('/game/operation-locks')
  return data.data
}

export async function getResponsibilityStats(): Promise<any> {
  const { data } = await api.get('/game/responsibility-stats')
  return data.data
}

// ----- 结局/统计（3.3 四大结局系统） -----

export async function getEnding(): Promise<any> {
  const { data } = await api.get('/game/ending')
  return data.data
}

/** 获取所有结局的配置数据（演出用） */
export async function getEndingsConfig(): Promise<any> {
  const { data } = await api.get('/game/endings/config')
  return data.data
}

/** 获取结局进度（各结局条件满足情况） */
export async function getEndingsProgress(): Promise<any> {
  const { data } = await api.get('/game/endings/progress')
  return data.data
}

/** 获取结局达成历史 */
export async function getEndingsHistory(): Promise<any> {
  const { data } = await api.get('/game/endings/history')
  return data.data
}

/** 获取传承数据（新周目可用） */
export async function getEndingsLegacy(): Promise<any> {
  const { data } = await api.get('/game/endings/legacy')
  return data.data
}

// ----- 征兵/军事 -----

export async function getRecruitInfo(tileId: string, factionId: string): Promise<any> {
  const params = factionId ? `?faction_id=${factionId}` : ''
  const { data } = await api.get(`/military/recruit-info/${tileId}${params}`)
  return data.data
}

// ----- 批量建造（3.2 新增） -----

export async function batchConstructBuildings(params: {
  tile_ids: string[]
  building_type: string
  faction_id: string
}): Promise<any> {
  const { data } = await api.post('/building/batch-construct', params)
  return data.data
}

// ----- 批量征兵（3.2 新增） -----

export async function batchRecruitTroops(params: {
  recruitments: Array<{ tile_id: string; amount: number }>
  faction_id: string
}): Promise<any> {
  const { data } = await api.post('/military/batch-recruit', params)
  return data.data
}

// ----- 势力地块摘要（3.2 新增） -----

export async function getOwnedTilesSummary(factionId: string): Promise<any> {
  const { data } = await api.get(`/tiles/owned/${factionId}`)
  return data.data
}

// ----- 地盘/领土 -----

export async function getTerritoryChanges(factionId: string, limit?: number): Promise<any> {
  const params = limit ? `?limit=${limit}` : ''
  const { data } = await api.get(`/territory/changes/${factionId}${params}`)
  return data.data
}

export async function getTerritorySummary(factionId: string): Promise<any> {
  const { data } = await api.get(`/territory/summary/${factionId}`)
  return data.data
}

export async function getGlobalTerritoryChanges(roundNum?: number, limit?: number): Promise<any> {
  const params = new URLSearchParams()
  if (roundNum) params.set('round_num', String(roundNum))
  if (limit) params.set('limit', String(limit))
  const { data } = await api.get(`/territory/global-changes?${params.toString()}`)
  return data.data
}

export async function getTileHistory(tileId: string): Promise<any> {
  const { data } = await api.get(`/territory/tile-history/${tileId}`)
  return data.data
}

/**
 * 获取全量图层数据（供14层渲染系统使用）
 * 单次返回：tiles/fog_visible/march_routes/supply_lines/diplomacy/claims/water_routes/buildings/disasters
 */
export async function getLayersData(factionId?: string): Promise<any> {
  const params = new URLSearchParams()
  if (factionId) params.set('faction_id', factionId)
  const { data } = await api.get(`/map/layers/data?${params.toString()}`)
  return data.data
}

// ----- 面板数据（皇家/医疗/海运/文化） -----

export async function getRoyalPanel(factionId: string): Promise<any> {
  const { data } = await api.get(`/panel/royal/${factionId}`)
  return data.data
}

export async function getMedicalPanel(factionId: string): Promise<any> {
  const { data } = await api.get(`/panel/medical/${factionId}`)
  return data.data
}

export async function getSeaPanel(factionId: string): Promise<any> {
  const { data } = await api.get(`/panel/sea/${factionId}`)
  return data.data
}

export async function getCulturePanel(factionId: string): Promise<any> {
  const { data } = await api.get(`/panel/culture/${factionId}`)
  return data.data
}

export async function getWeather(): Promise<any> {
  const { data } = await api.get('/panel/weather')
  return data.data
}

// ----- 高级功能（3.2 新增） -----

// 叛军系统
export async function listRebels(): Promise<any> {
  const { data } = await api.get('/rebel/list')
  return data.data
}

export async function suppressRebellion(factionId: string, rebelId: string, troops: number): Promise<any> {
  const { data } = await api.post('/rebel/suppress', { faction_id: factionId, rebel_id: rebelId, troops })
  return data.data
}

// 伏击/劫掠
export async function attemptAmbush(attackerFaction: string, targetFaction: string, tileId: string, troops: number): Promise<any> {
  const { data } = await api.post('/march/ambush', { attacker_faction: attackerFaction, target_faction: targetFaction, tile_id: tileId, troops })
  return data.data
}

export async function raidSupplyLine(raiderFaction: string, targetFaction: string, troops: number): Promise<any> {
  const { data } = await api.post('/march/raid', { raider_faction: raiderFaction, target_faction: targetFaction, troops })
  return data.data
}

export async function borderRaid(raiderFaction: string, targetFaction: string, troops: number): Promise<any> {
  const { data } = await api.post('/march/border_raid', { raider_faction: raiderFaction, target_faction: targetFaction, troops })
  return data.data
}

// 附庸吞并
export async function annexVassal(suzerainId: string, vassalId: string): Promise<any> {
  const { data } = await api.post('/diplomacy/vassal/annex', { suzerain_id: suzerainId, vassal_id: vassalId })
  return data.data
}

export async function checkVassalIndependence(suzerainId: string, vassalId: string): Promise<any> {
  const { data } = await api.get(`/diplomacy/vassal/check_independence/${suzerainId}/${vassalId}`)
  return data.data
}

// 高级谍报
export async function turnDoubleAgent(ownerFaction: string, targetFaction: string): Promise<any> {
  const { data } = await api.post('/spy/double_agent', { owner_faction: ownerFaction, target_faction: targetFaction })
  return data.data
}

export async function plantFalseIntel(planterFaction: string, targetFaction: string, intelType: string, fakeData: any): Promise<any> {
  const { data } = await api.post('/spy/false_intel', { planter_faction: planterFaction, target_faction: targetFaction, intel_type: intelType, fake_data: fakeData })
  return data.data
}

export async function counterSpy(ownerFaction: string, targetFaction: string): Promise<any> {
  const { data } = await api.post('/spy/counter', { owner_faction: ownerFaction, target_faction: targetFaction })
  return data.data
}

// 高级外交
export async function sendHostage(senderFaction: string, receiverFaction: string): Promise<any> {
  const { data } = await api.post('/diplomacy/hostage/send', { sender_faction: senderFaction, receiver_faction: receiverFaction })
  return data.data
}

export async function recallHostage(senderFaction: string, receiverFaction: string): Promise<any> {
  const { data } = await api.post('/diplomacy/hostage/recall', { sender_faction: senderFaction, receiver_faction: receiverFaction })
  return data.data
}

// 宗室高级功能
export async function moveCapital(factionId: string, newTileId: string): Promise<any> {
  const { data } = await api.post('/royal/move_capital', { faction_id: factionId, new_tile_id: newTileId })
  return data.data
}

export async function performSacrifice(factionId: string): Promise<any> {
  const { data } = await api.post('/royal/sacrifice', { faction_id: factionId })
  return data.data
}

// 迁都辅助
export async function getCapitalCandidates(factionId: string): Promise<any> {
  const { data } = await api.get(`/court/capital-candidates/${factionId}`)
  return data.data
}

export async function getCapitalHistory(factionId: string): Promise<any> {
  const { data } = await api.get(`/court/capital-history/${factionId}`)
  return data.data
}

// 官员系统
export async function recruitOfficials(factionId: string, count: number = 1): Promise<any> {
  const { data } = await api.post('/court/recruit_officials', { faction_id: factionId, count })
  return data.data
}

// 海战
export async function navalBattle(attackerFaction: string, defenderFaction: string, attackerTroops: number, defenderTroops: number, tileId: string): Promise<any> {
  const { data } = await api.post('/march/naval_battle', { attacker_faction: attackerFaction, defender_faction: defenderFaction, attacker_troops: attackerTroops, defender_troops: defenderTroops, tile_id: tileId })
  return data.data
}

// ============================================================
// 战争系统 v3.0：Casus Belli / 战争分数 / 和平谈判
// ============================================================

/** 获取对目标势力可用的宣战理由列表 */
export async function getAvailableCBList(factionId: string, targetFactionId: string): Promise<any> {
  const { data } = await api.get('/war/cb-list', { params: { faction_id: factionId, target_faction_id: targetFactionId } })
  return data.data
}

/** 获取所有活跃战争（含战争分数摘要） */
export async function getActiveWars(): Promise<any> {
  const { data } = await api.get('/war/active')
  return data.data
}

/** 获取指定战争的分数与事件 */
export async function getWarScore(warId: string, attacker?: string, defender?: string): Promise<any> {
  const params: any = { war_id: warId }
  if (attacker) params.attacker = attacker
  if (defender) params.defender = defender
  const { data } = await api.get('/war/score', { params })
  return data.data
}

/** 获取当前战争分数下可用的和平条款 */
export async function getAvailablePeaceTerms(warId: string): Promise<any> {
  const { data } = await api.post('/war/peace/available-terms', { war_id: warId })
  return data.data
}

/** 预评估和平提议是否会被接受 */
export async function evaluatePeaceProposal(params: {
  war_id: string
  terms: string[]
  is_from_attacker: boolean
  tile_ids?: string[]
  reparation_amount?: number
}): Promise<any> {
  const { data } = await api.post('/war/peace/evaluate', params)
  return data.data
}

/** 正式提出和平协议 */
export async function proposePeace(params: {
  war_id: string
  terms: string[]
  is_from_attacker: boolean
  tile_ids?: string[]
  reparation_amount?: number
}): Promise<any> {
  const { data } = await api.post('/war/peace/propose', params)
  return data.data
}

// ============================================================
// 武将系统（3.2 新增）
// ============================================================

export async function getFactionGenerals(factionId: string): Promise<any> {
  const { data } = await api.get(`/generals/${factionId}`)
  return data.data
}

// 人才市场
export async function getTalentMarket(): Promise<any> {
  const { data } = await api.get('/talent/market')
  return data.data
}

export async function recruitTalent(factionId: string, generalId: string): Promise<any> {
  const { data } = await api.post('/talent/recruit', { faction_id: factionId, general_id: generalId })
  return data.data
}

export async function getFactionLegions(factionId: string): Promise<any> {
  const { data } = await api.get(`/legions/${factionId}`)
  return data.data
}

export async function createLegion(params: {
  name: string; faction_id: string; commander_id: string;
  unit_composition: Record<string, number>; formation?: string;
}): Promise<any> {
  const { data } = await api.post('/legion/create', params)
  return data.data
}

export async function setLegionAutonomous(params: {
  legion_id: string; enabled: boolean; priority?: string;
}): Promise<any> {
  const { data } = await api.post('/legion/autonomous', params)
  return data.data
}

export async function assignGeneralToLegion(params: {
  general_id: string; legion_id: string;
}): Promise<any> {
  const { data } = await api.post('/general/assign', params)
  return data.data
}

export async function disbandLegion(params: {
  legion_id: string;
}): Promise<any> {
  const { data } = await api.post('/legion/disband', params)
  return data.data
}

export async function removeSubcommander(params: {
  legion_id: string; general_id: string;
}): Promise<any> {
  const { data } = await api.post('/legion/remove-subcommander', params)
  return data.data
}

// ============================================================
// 外交权谋（3.2 新增）
// ============================================================

export async function analyzeStrategicPosition(factionId: string): Promise<any> {
  const { data } = await api.post('/diplomacy/strategic-position', { faction_id: factionId })
  return data.data
}

export async function sowDiscord(params: {
  schemer_faction: string; target_a: string; target_b: string; discord_type: string;
}): Promise<any> {
  const { data } = await api.post('/diplomacy/discord', params)
  return data.data
}

export async function attemptCoopt(params: {
  coopter_faction: string; target_faction: string; coopt_type: string;
}): Promise<any> {
  const { data } = await api.post('/diplomacy/coopt', params)
  return data.data
}

export async function getDiplomaticRecommendations(factionId: string): Promise<any> {
  const { data } = await api.get(`/diplomacy/recommendations/${factionId}`)
  return data.data
}

// ============================================================
// 连通性测试（P1修复：统一诊断入口）
// ============================================================

/** 连通性测试单项目结果 */
export interface ConnectivityTestItem {
  name: string
  endpoint: string
  status: 'pending' | 'ok' | 'error' | 'timeout'
  latency_ms: number
  error?: string
  data?: any
}

/** 连通性测试完整报告 */
export interface ConnectivityReport {
  timestamp: string
  base_url: string
  overall: 'healthy' | 'degraded' | 'offline'
  network_ok: boolean
  items: ConnectivityTestItem[]
  summary: { total: number; passed: number; failed: number; avg_latency_ms: number }
}

/**
 * 连通性自动化诊断
 * 按顺序测试：基础网络 → 健康检查 → 配置加载 → 世界状态 → AI可用性
 * 返回完整诊断报告
 */
export async function runConnectivityTest(options?: {
  signal?: AbortSignal
  timeout?: number
}): Promise<ConnectivityReport> {
  const t0 = performance.now()
  const signal = options?.signal
  const timeout = options?.timeout || 10000
  const items: ConnectivityTestItem[] = []
  const timestamp = new Date().toISOString()

  const testEndpoints = [
    { name: '基础网络', endpoint: '/api/health', method: 'GET' as const },
    { name: '后端诊断', endpoint: '/api/health/connectivity', method: 'GET' as const },
    { name: '配置加载', endpoint: '/api/config/factions', method: 'GET' as const },
    { name: '游戏状态', endpoint: '/api/game/status', method: 'GET' as const },
    { name: 'LLM状态', endpoint: '/api/config/test-llm', method: 'POST' as const, body: { models: ['advisor'] }, longTimeout: true },
  ]

  for (const ep of testEndpoints) {
    if (signal?.aborted) break
    const item: ConnectivityTestItem = {
      name: ep.name,
      endpoint: ep.endpoint,
      status: 'pending',
      latency_ms: 0,
    }
    const t1 = performance.now()
    try {
      const config: any = {
        timeout: ep.longTimeout ? 30000 : timeout,
        signal,
      }
      let res: AxiosResponse
      if (ep.method === 'GET') {
        res = await apiClient.get(ep.endpoint, config)
      } else {
        res = await apiClient.post(ep.endpoint, ep.body || {}, config)
      }
      item.latency_ms = Math.round(performance.now() - t1)
      item.status = 'ok'
      item.data = res.data?.data || res.data
    } catch (err: any) {
      item.latency_ms = Math.round(performance.now() - t1)
      if (axios.isCancel(err) || err?.name === 'AbortError') {
        item.status = 'error'
        item.error = '请求已取消'
      } else if (err.code === 'ECONNABORTED') {
        item.status = 'timeout'
        item.error = `超时（${timeout}ms）`
      } else if (!err.response) {
        item.status = 'error'
        item.error = '无法连接服务器（后端未启动或端口错误）'
      } else {
        item.status = 'error'
        item.error = getApiErrorMessage(err)
      }
    }
    items.push(item)
  }

  const passed = items.filter(i => i.status === 'ok')
  const failed = items.filter(i => i.status !== 'ok')
  const avgLatency = passed.length > 0
    ? Math.round(passed.reduce((s, i) => s + i.latency_ms, 0) / passed.length)
    : 0

  // 基础网络检查通过 = health 端点可达
  const networkOk = items.length > 0 && items[0].status === 'ok'
  let overall: ConnectivityReport['overall'] = 'offline'
  if (networkOk && failed.length === 0) {
    overall = 'healthy'
  } else if (networkOk) {
    overall = 'degraded'
  }

  return {
    timestamp,
    base_url: apiClient.defaults.baseURL || '/api',
    overall,
    network_ok: networkOk,
    items,
    summary: { total: items.length, passed: passed.length, failed: failed.length, avg_latency_ms: avgLatency },
  }
}

/**
 * 快速连通性检查（仅基础网络 + 健康检查）
 */
export async function quickConnectivityCheck(timeout = 5000): Promise<boolean> {
  try {
    await apiClient.get('/api/health', { timeout })
    return true
  } catch {
    return false
  }
}

// ============================================================
// 历史剧情锚点（3.2 新增）
// ============================================================

export async function getHistoryAnchors(factionId: string): Promise<any> {
  const { data } = await api.get(`/history/anchors/${factionId}`)
  return data.data
}

export async function chooseHistoryBranch(params: {
  anchor_id: string; branch_id: string; faction_id: string;
}): Promise<any> {
  const { data } = await api.post('/history/choose-branch', params)
  return data.data
}

export async function getUnitTypes(): Promise<any> {
  const { data } = await api.get('/military/unit-types')
  return data.data
}

// ============================================================
// 全链路AI智能体（3.2 新增）
// ============================================================

export async function getAISnapshot(factionId: string): Promise<any> {
  const { data } = await api.get(`/ai/snapshot/${factionId}`)
  return data.data
}

export async function getFactionAIDetail(factionId: string): Promise<any> {
  const { data } = await api.get(`/ai/faction-detail/${factionId}`)
  return data.data
}

export async function civilAIAnalyze(factionId: string): Promise<any> {
  const { data } = await api.post('/ai/civil/analyze', { faction_id: factionId })
  return data.data
}

export async function civilAIBuildPlan(factionId: string, budget?: number): Promise<any> {
  const { data } = await api.post('/ai/civil/build-plan', { faction_id: factionId, budget })
  return data.data
}

export async function civilAIResourcePlan(factionId: string): Promise<any> {
  const { data } = await api.post('/ai/civil/resource-plan', { faction_id: factionId })
  return data.data
}

export async function civilAIAuto(factionId: string, delegationLevel: string): Promise<any> {
  const { data } = await api.post('/ai/civil/auto', { faction_id: factionId, delegation_level: delegationLevel })
  return data.data
}

export async function tacticalAIPath(from: string, to: string, factionId: string): Promise<any> {
  const { data } = await api.post('/ai/tactical/path', { from_tile: from, to_tile: to, faction_id: factionId })
  return data.data
}

export async function tacticalAIBattlePredict(from: string, tileId: string, troops: number, factionId: string): Promise<any> {
  const { data } = await api.post('/ai/tactical/battle-predict', { from_tile: from, tile_id: tileId, troops, faction_id: factionId })
  return data.data
}

export async function tacticalAIGarrison(factionId: string): Promise<any> {
  const { data } = await api.post('/ai/tactical/garrison', { faction_id: factionId })
  return data.data
}

export async function tacticalAIPlan(tileId: string, factionId: string): Promise<any> {
  const { data } = await api.post('/ai/tactical/plan', { tile_id: tileId, faction_id: factionId })
  return data.data
}

export async function factionAIDecisions(factionId: string, personality?: string): Promise<any> {
  const { data } = await api.post('/ai/faction/decisions', { faction_id: factionId, personality })
  return data.data
}

export async function nlCommand(text: string, factionId: string): Promise<any> {
  const { data } = await api.post('/ai/nl-command', { text, faction_id: factionId })
  return data.data
}

export async function getAgentsStatus(): Promise<any> {
  const { data } = await api.get('/ai/agents/status')
  return data.data
}

// ============================================================
// IOA 安全体系 API
// ============================================================

/** 获取 IOA 安全态势仪表盘 */
export async function getSecurityDashboard(): Promise<{
  ioa: any
  anomaly: any
  anonymizer: any
}> {
  const { data } = await api.get('/security/dashboard')
  return data.data
}

/** 获取安全事件列表 */
export async function getSecurityEvents(params?: {
  limit?: number
  severity?: string
  event_type?: string
}): Promise<{ total: number; events: any[] }> {
  const { data } = await api.get('/security/events', { params })
  return data.data
}

/** 获取异常告警列表 */
export async function getAnomalyAlerts(limit?: number): Promise<{ total: number; alerts: any[] }> {
  const { data } = await api.get('/security/alerts', { params: { limit } })
  return data.data
}

/** 获取指定势力的 Agent 行为风险报告 */
export async function getAgentBehaviorReport(factionId: string): Promise<{
  risk_report: any
  recent_actions: any[]
}> {
  const { data } = await api.get(`/security/agent/${factionId}`)
  return data.data
}

/** 获取指定势力的行为历史 */
export async function getAgentBehaviorHistory(
  factionId: string,
  limit?: number,
): Promise<any> {
  const { data } = await api.get(`/security/agent/${factionId}/history`, { params: { limit } })
  return data.data
}

/** 获取审计事件 */
export async function getAuditEvents(limit?: number): Promise<{ total: number; events: any[] }> {
  const { data } = await api.get('/security/audit/events', { params: { limit } })
  return data.data
}

/** 获取审计告警 */
export async function getAuditAlerts(limit?: number): Promise<{ total: number; alerts: any[] }> {
  const { data } = await api.get('/security/audit/alerts', { params: { limit } })
  return data.data
}

/** 获取安全体系统计总览 */
export async function getSecurityStats(): Promise<any> {
  const { data } = await api.get('/security/stats')
  return data.data
}

/** 获取封禁列表 */
export async function getBlockedEntities(): Promise<any> {
  const { data } = await api.get('/security/threats/blocked')
  return data.data
}

/** 获取 EdgeOne 安全策略 */
export async function getEdgeOnePolicy(): Promise<any> {
  const { data } = await api.get('/security/edgeone/policy')
  return data.data
}

/** 获取 WAF 规则 */
export async function getEdgeOneWAFRules(): Promise<any> {
  const { data } = await api.get('/security/edgeone/waf')
  return data.data
}

export default api
