<template>
  <Teleport to="body">
    <Transition name="panel-slide">
      <div v-if="visible" class="aicp-overlay">
        <div class="aicp-panel artifact-panel artifact-secret">
          <!-- 头部 -->
          <div class="aicp-header">
            <h2>🤖 AI 中控台</h2>
            <button class="aicp-close" @click="$emit('close')">✕</button>
          </div>

          <!-- 状态栏 -->
          <div class="aicp-status-bar">
            <div class="status-item" :class="{ active: aiStatus.connected }">
              <span class="status-dot"></span>
              <span>AI {{ aiStatus.connected ? '在线' : '离线' }}</span>
            </div>
            <div class="status-item">
              <span>模型: {{ aiStatus.model || '--' }}</span>
            </div>
            <div class="status-item">
              <span>活跃: {{ dashboardStats?.active_agents ?? aiStatus.activeAgents ?? 0 }}/10</span>
            </div>
            <div class="status-item" v-if="dashboardStats">
              <span>总调用: {{ dashboardStats.total_calls || 0 }}</span>
            </div>
          </div>

          <!-- 标签页 -->
          <div class="aicp-tabs">
            <button v-for="tab in tabs" :key="tab.id"
              :class="{ active: activeTab === tab.id }"
              @click="activeTab = tab.id">
              {{ tab.label }}
            </button>
          </div>

          <!-- Tab: 委任配置 -->
          <div v-if="activeTab === 'delegation'" class="aicp-content">
            <h3>🏛️ 委任权限配置</h3>
            <p class="aicp-desc">设置各领域的AI委任等级。全委任=AI全权代理，半委任=自动执行低风险操作，建议=AI推荐需手动确认。</p>

            <div class="delegation-list">
              <div v-for="d in delegationDomains" :key="d.key" class="delegation-item">
                <div class="delegation-info">
                  <span class="delegation-icon">{{ d.icon }}</span>
                  <div>
                    <strong>{{ d.label }}</strong>
                    <p class="aicp-desc">{{ d.desc }}</p>
                  </div>
                </div>
                <div class="delegation-controls">
                  <select v-model="delegationLevels[d.key]"
                    :disabled="loading"
                    @change="updateDelegation(d.key)">
                    <option value="full_manual">🖐️ 手动</option>
                    <option value="advisory">💡 建议</option>
                    <option value="semi_auto">⚡ 半委任</option>
                    <option value="full_auto">🤖 全委任</option>
                  </select>
                </div>
              </div>
            </div>

            <div class="quick-actions">
              <button class="btn-action" @click="setAll('full_auto')">全部全委任</button>
              <button class="btn-action secondary" @click="setAll('semi_auto')">全部半委任</button>
              <button class="btn-action secondary" @click="setAll('advisory')">全部建议</button>
              <button class="btn-action danger" @click="setAll('full_manual')">全部手动</button>
            </div>

            <div v-if="delegationSaved" class="delegation-saved-hint">✓ 委任配置已保存（本地存储，随圣旨系统生效）</div>
            <div v-if="delegationError" class="delegation-error-hint">{{ delegationError }}</div>
          </div>

          <!-- Tab: 内政AI -->
          <div v-if="activeTab === 'civil'" class="aicp-content">
            <h3>🏗️ 文官内政AI</h3>
            <div class="analysis-section" v-if="civilAnalysis">
              <h4>📊 资源评估</h4>
              <div class="resource-grid">
                <div v-for="(r, key) in civilAnalysis.resource_assessment" :key="key" class="resource-card">
                  <div class="resource-name">{{ keyLabels[key] || key }}</div>
                  <div class="resource-value">{{ formatNum(r.value) }}</div>
                  <div class="resource-status" :class="r.status">{{ statusLabels[r.status] || r.status }}</div>
                </div>
              </div>

              <div v-if="civilAnalysis.building_recommendations?.length" class="rec-section">
                <h4>🔨 建造推荐</h4>
                <div v-for="b in civilAnalysis.building_recommendations" :key="b.building" class="rec-item">
                  <span>{{ b.building }} ({{ b.cost }}两)</span>
                  <span class="rec-score">优先级 {{ b.priority_score }}</span>
                  <span class="rec-reason">{{ b.reason }}</span>
                </div>
              </div>

              <div v-if="civilAnalysis.policy_recommendations?.length" class="rec-section">
                <h4>📜 国策推荐</h4>
                <div v-for="p in civilAnalysis.policy_recommendations" :key="p.policy" class="rec-item">
                  <span>{{ p.policy }}</span>
                  <span class="rec-reason">{{ p.reason }}</span>
                </div>
              </div>

              <div v-if="civilAnalysis.risk_alerts?.length" class="rec-section danger">
                <h4>⚠️ 风险警示</h4>
                <div v-for="r in civilAnalysis.risk_alerts" :key="r" class="rec-item">
                  <span>{{ r }}</span>
                </div>
              </div>
            </div>

            <button class="btn-action" @click="refreshCivil" :disabled="loading">
              {{ loading ? (civilPhase || '分析中...') : '刷新内政分析' }}
            </button>
            <button class="btn-action secondary" @click="resourcePlanCivil" :disabled="loading">
              {{ loading && civilPhase ? civilPhase : '资源调配方案' }}
            </button>
            <button class="btn-action secondary" @click="executeCivilPlan" :disabled="loading">
              {{ loading ? '执行中...' : '执行城建计划' }}
            </button>
          </div>

          <!-- Tab: 战术AI -->
          <div v-if="activeTab === 'tactical'" class="aicp-content">
            <h3>⚔️ 战术AI分析</h3>

            <div class="section-row">
              <div class="input-group">
                <label>起始地块</label>
                <input v-model="tactical.from" placeholder="输入地块ID" />
              </div>
              <div class="input-group">
                <label>目标地块</label>
                <input v-model="tactical.to" placeholder="输入地块ID" />
              </div>
            </div>
            <div class="section-row">
              <div class="input-group">
                <label>出征兵力</label>
                <input type="number" v-model.number="tactical.troops" min="100" max="10000" step="100" />
              </div>
            </div>

            <!-- 战术查询历史 -->
            <div v-if="tacticalHistory.length" class="tactical-history">
              <span class="history-label">最近查询:</span>
              <button v-for="(h, i) in tacticalHistory" :key="i" class="history-chip"
                @click="loadTacticalHistory(h)" :title="`${h.from} → ${h.to} (${h.troops}兵)`">
                {{ h.from }}→{{ h.to }}
              </button>
            </div>

            <div class="btn-row">
              <button class="btn-action" @click="findPath" :disabled="loading">🗺️ 路径</button>
              <button class="btn-action" @click="predictBattle" :disabled="loading">⚔️ 推演</button>
              <button class="btn-action" @click="planTactics" :disabled="loading">🎯 规划</button>
              <button class="btn-action secondary" @click="garrisonPriorities" :disabled="loading">🛡️ 驻防</button>
            </div>

            <div v-if="loading && activeTab === 'tactical'" class="tactical-loading">🔮 天机推演中…</div>

            <div v-if="tacticalResult" class="result-section">
              <!-- 路径结果 -->
              <div v-if="tacticalResult.path || tacticalResult.steps !== undefined" class="tactical-card">
                <div class="tactical-card-title">🗺️ 最优路径</div>
                <div class="tactical-card-body">
                  <span class="tactical-stat">步数: {{ tacticalResult.path?.length || tacticalResult.steps }}</span>
                  <span class="tactical-stat" v-if="tacticalResult.cost !== undefined">耗粮: {{ tacticalResult.cost }}</span>
                  <span class="tactical-stat" v-if="tacticalResult.time !== undefined">耗时: {{ tacticalResult.time }}天</span>
                </div>
              </div>
              <!-- 战损推演 -->
              <div v-if="tacticalResult.win_probability !== undefined || tacticalResult.win_rate !== undefined" class="tactical-card">
                <div class="tactical-card-title">⚔️ 战损推演</div>
                <div class="tactical-card-body">
                  <span class="tactical-stat">胜率: {{ ((tacticalResult.win_probability ?? tacticalResult.win_rate) * 100).toFixed(0) }}%</span>
                  <span class="tactical-stat" v-if="tacticalResult.expected_losses !== undefined">预计伤亡: {{ tacticalResult.expected_losses }}</span>
                  <span class="tactical-stat" v-if="tacticalResult.advantage">优势: {{ tacticalResult.advantage }}</span>
                </div>
              </div>
              <!-- 驻防 -->
              <div v-if="tacticalResult.priorities?.length" class="tactical-card">
                <div class="tactical-card-title">🛡️ 驻防优先级</div>
                <div class="tactical-card-body">
                  <div v-for="(p, i) in tacticalResult.priorities.slice(0, 5)" :key="i" class="tactical-priority-row">
                    <span>{{ i + 1 }}. {{ p.tile || p.tile_id || (typeof p === 'string' ? p : '') }}</span>
                    <span v-if="p.score" class="rec-score">威胁 {{ p.score }}</span>
                  </div>
                </div>
              </div>
              <!-- 战术规划 -->
              <div v-if="tacticalResult.plan || tacticalResult.strategy" class="tactical-card">
                <div class="tactical-card-title">🎯 战术规划</div>
                <div class="tactical-card-body">{{ tacticalResult.plan || tacticalResult.strategy }}</div>
              </div>
              <!-- 兜底：无法识别的结构→折叠原始数据 -->
              <details v-if="isRawResult()" class="result-raw-details">
                <summary class="result-raw-toggle">📄 查看原始数据</summary>
                <pre class="result-json">{{ JSON.stringify(tacticalResult, null, 2) }}</pre>
              </details>
            </div>
          </div>

          <!-- Tab: 决策日志 -->
          <div v-if="activeTab === 'log'" class="aicp-content">
            <h3>📋 AI决策日志</h3>
            <div class="btn-row" style="margin-bottom:10px;">
              <button class="btn-action secondary" @click="refreshDecisionLogs" :disabled="dashboardLoading">
                {{ dashboardLoading ? '加载中...' : '🔄 刷新日志' }}
              </button>
              <button class="btn-action secondary" @click="exportLogsCSV" :disabled="!decisionLogs.length">📥 导出CSV</button>
              <button class="btn-action secondary" @click="decisionLogs = []" :disabled="!decisionLogs.length">清空</button>
            </div>

            <!-- 日志筛选行 -->
            <div class="log-filter-row" v-if="decisionLogs.length > 3">
              <input v-model="logFilterAgent" placeholder="筛选Agent…" class="log-filter-input" />
              <select v-model="logFilterRisk" class="log-filter-select">
                <option value="">全部风险</option>
                <option value="low">🟢 低</option>
                <option value="medium">🟡 中</option>
                <option value="high">🔴 高</option>
              </select>
              <span class="log-filter-count">{{ filteredLogs.length }}/{{ decisionLogs.length }}</span>
            </div>

            <div v-if="dashboardData?.event_bus" class="aicp-event-bus-info">
              <span>📨 待处理事件: {{ dashboardData.event_bus.pending_events }}</span>
              <span>📦 已归档: {{ dashboardData.event_bus.archived_events }}</span>
              <span>🔄 当前回合: {{ dashboardData.event_bus.recent_round }}</span>
            </div>

            <div class="log-list">
              <div v-for="(log, i) in filteredLogs" :key="i" class="log-item">
                <span class="log-time">回合{{ log.turn }}</span>
                <span class="log-agent">[{{ log.agent }}]</span>
                <span class="log-faction">{{ log.faction }}</span>
                <span class="log-summary">{{ log.summary }}</span>
                <span class="log-risk" :class="log.risk">{{ log.risk }}</span>
              </div>
              <div v-if="!filteredLogs.length" class="empty-state">
                {{ decisionLogs.length ? '无匹配的日志记录' : '暂无决策日志，点击"刷新日志"从后端同步' }}
              </div>
            </div>
          </div>

          <!-- Tab: 智能体状态 -->
          <div v-if="activeTab === 'agents'" class="aicp-content">
            <h3>🧠 AI智能体集群 <span v-if="_pollActive" class="polling-badge">⟳ 自动刷新</span></h3>

            <!-- 全局统计摘要 -->
            <div v-if="dashboardStats" class="dashboard-summary">
              <div class="ds-card">
                <div class="ds-value">{{ dashboardStats.total_calls || 0 }}</div>
                <div class="ds-label">总调用次数</div>
              </div>
              <div class="ds-card">
                <div class="ds-value">{{ dashboardStats.avg_latency || 0 }}ms</div>
                <div class="ds-label">平均延迟</div>
              </div>
              <div class="ds-card">
                <div class="ds-value" :class="{ warn: dashboardStats.degraded_agents > 0 }">{{ dashboardStats.active_agents || 0 }}</div>
                <div class="ds-label">活跃/{{ dashboardStats.total_agents || 10 }}智能体</div>
              </div>
              <div class="ds-card">
                <div class="ds-value">{{ dashboardData?.event_bus?.pending_events ?? 0 }}</div>
                <div class="ds-label">待处理事件</div>
              </div>
            </div>

            <div class="btn-row" style="margin-bottom:12px;">
              <button class="btn-action secondary" @click="refreshDashboard" :disabled="dashboardLoading">
                {{ dashboardLoading ? '加载中...' : '🔄 刷新' }}
              </button>
              <button class="btn-action" @click="triggerAutoStep" :disabled="store.isProcessing || !aiStatus.connected">
                {{ store.isProcessing ? '执行中...' : '⚡ 一键推演' }}
              </button>
            </div>

            <!-- 模型分组 -->
            <div v-if="dashboardData?.model_groups" class="model-groups-info">
              <span v-for="(g, key) in dashboardData.model_groups" :key="key" class="model-group-tag">
                {{ key }}: {{ g.function }} ({{ g.agents }})
              </span>
            </div>

            <div class="agent-grid">
              <div v-for="agent in liveAgents" :key="agent.key" class="agent-card" :class="agentCardClass(agent)"
                @click="toggleAgentExpand(agent.key)">
                <div class="agent-header">
                  <span class="agent-icon">{{ agentIcon(agent.key) }}</span>
                  <strong>{{ agent.name }}</strong>
                  <span class="agent-status" :class="agentStatusClass(agent)">{{ agentStatusLabel(agent) }}</span>
                </div>
                <p class="agent-desc">{{ agent.description }}</p>
                <div class="agent-model">
                  <span>模型: {{ agent.model_group || agent.config?.model || '--' }}</span>
                  <span>触发: {{ agent.trigger === 'both' ? '手动+自动' : agent.trigger === 'manual' ? '手动' : '自动' }}</span>
                </div>
                <div v-if="agent.circuit_state" class="agent-stats-row">
                  <span>熔断: {{ agent.circuit_state }}</span>
                  <span v-if="agent.call_count">调用: {{ agent.call_count }}次</span>
                  <span v-if="agent.avg_latency">延迟: {{ agent.avg_latency }}ms</span>
                </div>
                <div v-if="agent.memories" class="agent-memories">
                  记忆: 短{{ agent.memories.short_term || 0 }} / 中{{ agent.memories.mid_term || 0 }} / 长{{ agent.memories.long_term || 0 }}
                </div>
                <!-- 展开详情 -->
                <div v-if="expandedAgent === agent.key" class="agent-expand">
                  <div v-if="agent.config" class="agent-expand-section">
                    <div class="expand-label">配置</div>
                    <div class="expand-json">{{ JSON.stringify(agent.config, null, 1) }}</div>
                  </div>
                  <div v-if="agent.recent_outputs?.length" class="agent-expand-section">
                    <div class="expand-label">最近产出 ({{ agent.recent_outputs.length }})</div>
                    <div v-for="(ro, ri) in agent.recent_outputs.slice(0, 3)" :key="ri" class="expand-item">{{ ro }}</div>
                  </div>
                  <div v-if="agent.circuit_history?.length" class="agent-expand-section">
                    <div class="expand-label">熔断历史</div>
                    <div v-for="(ch, ci) in agent.circuit_history.slice(0, 3)" :key="ci" class="expand-item circuit-item">
                      {{ ch.time || '?' }} — {{ ch.state || ch }}
                    </div>
                  </div>
                  <div v-if="!agent.config && !agent.recent_outputs?.length" class="expand-hint">点击刷新获取详情…</div>
                </div>
              </div>
            </div>

            <!-- 降级智能体警告 -->
            <div v-if="dashboardStats?.degraded_agents > 0" class="degraded-warning">
              ⚠️ {{ dashboardStats.degraded_agents }}个智能体已降级（熔断/回退模式）
            </div>
          </div>

          <!-- 快捷键提示 -->
          <div class="aicp-shortcut-bar">
            <span>Ctrl+1~5 切换Tab</span>
            <span>Esc 关闭面板</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import api, {
  agentDashboard,
} from '@/services/api'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: any }>()

const store = useGameStore()

const activeTab = ref('delegation')
const loading = ref(false)
const delegationSaved = ref(false)  // 委任保存提示
const delegationError = ref('')     // 委任保存错误提示

const tabs = [
  { id: 'delegation', label: '🏛️ 委任' },
  { id: 'civil', label: '🏗️ 内政' },
  { id: 'tactical', label: '⚔️ 战术' },
  { id: 'log', label: '📋 日志' },
  { id: 'agents', label: '🧠 集群' },
]

// 委任配置
const delegationDomains = [
  { key: 'civil', icon: '🏗️', label: '内政建设', desc: '城建、资源调配、民心维稳、国策推荐' },
  { key: 'military', icon: '⚔️', label: '军事征伐', desc: '征兵、行军、战斗、驻防、训练' },
  { key: 'diplomacy', icon: '🕊️', label: '外交纵横', desc: '结盟、宣战、求和、贸易、联姻' },
  { key: 'espionage', icon: '🕵️', label: '谍报密探', desc: '渗透、破坏、情报、谣言、策反' },
  { key: 'economy', icon: '💰', label: '经济财政', desc: '税收、贸易、徭役、开支' },
]

// 从 localStorage 加载委任配置
function loadDelegationConfig(): Record<string, string> {
  try {
    const saved = localStorage.getItem('yuanmo_delegation_config')
    if (saved) return JSON.parse(saved)
  } catch (_) { console.warn('加载委任配置失败:', _) }
  return { civil: 'advisory', military: 'advisory', diplomacy: 'advisory', espionage: 'advisory', economy: 'advisory' }
}

const delegationLevels = reactive<Record<string, string>>(loadDelegationConfig())

// AI状态
const aiStatus = reactive({
  connected: false,
  model: '',
  activeAgents: 0,
})

// 内政分析
const civilAnalysis = ref<any>(null)
const civilPhase = ref('')  // 分析阶段提示: analyzing / generating / validating
const tactical = reactive({ from: '', to: '', troops: 500 })
const tacticalResult = ref<any>(null)
// 决策日志
const decisionLogs = ref<any[]>([])
const logFilterAgent = ref('')
const logFilterRisk = ref('')
const filteredLogs = computed(() => {
  let logs = decisionLogs.value
  if (logFilterAgent.value) {
    const kw = logFilterAgent.value.toLowerCase()
    logs = logs.filter(l => l.agent?.toLowerCase().includes(kw))
  }
  if (logFilterRisk.value) {
    logs = logs.filter(l => l.risk === logFilterRisk.value)
  }
  return logs
})

// ===== Dashboard 数据 =====
const dashboardData = ref<any>(null)
const dashboardLoading = ref(false)

// 智能体信息计算属性
const dashboardStats = computed(() => dashboardData.value?.global_stats || null)

const liveAgents = computed(() => {
  if (dashboardData.value?.agents?.length) {
    return dashboardData.value.agents
  }
  // 降级：使用硬编码列表（从后端未获取数据时）— 十大智能体 A1~A10
  return [
    { key: 'A1', name: '谋策阁', model_group: 'advisor', trigger: 'both', description: '谋臣献策、廷议辩论、战略分析（每回合自动为玩家献策）', player_only: true },
    { key: 'A2', name: '群雄殿', model_group: 'advisor', trigger: 'auto', description: '君主NPC自主推演、势力决策（玩家势力强制休眠）', player_only: false },
    { key: 'A3', name: '律法堂', model_group: 'advisor', trigger: 'manual', description: '案件审理、律法判决、朝堂审讯（仅玩家手动触发）', player_only: true },
    { key: 'A4', name: '谍报司', model_group: 'enemy', trigger: 'both', description: '细作网络、情报搜集、渗透破坏（玩家势力仅手动触发）', player_only: false },
    { key: 'A5', name: '司天台', model_group: 'enemy', trigger: 'both', description: '天灾人祸、祥瑞异象、随机事件生成', player_only: false },
    { key: 'A6', name: '外交署', model_group: 'law', trigger: 'both', description: '合纵连横、盟约谈判、贸易联姻', player_only: false },
    { key: 'A7', name: '宗室府', model_group: 'advisor', trigger: 'auto', description: '继承顺位、宗室管理、皇子培养', player_only: false },
    { key: 'A8', name: '国史馆', model_group: 'law', trigger: 'auto', description: '史书修撰、结局传记、事件归档', player_only: false },
    { key: 'A9', name: '军机处', model_group: 'enemy', trigger: 'auto', description: '战斗后自动生成古风战报、军情分析（无玩家交互）', player_only: false },
    { key: 'A10', name: '度支司', model_group: 'law', trigger: 'auto', description: '税收粮储调配、国策经济影响评估（后台自动运行）', player_only: false },
  ]
})

// 智能体图标映射
function agentIcon(key: string): string {
  const icons: Record<string, string> = {
    'A1': '🎓', 'A2': '👑', 'A3': '⚖️', 'A4': '🕵️',
    'A5': '🌤️', 'A6': '🤝', 'A7': '🏰', 'A8': '📜',
    'A9': '⚔️', 'A10': '🪙',
  }
  return icons[key] || '🤖'
}

function agentStatusClass(agent: any): string {
  // dashboard 数据未加载 → 待同步
  if (!dashboardData.value) return 'standby'
  // 已停止的 agent 优先级最高
  if (agent.alive === false) return 'dead'
  // 熔断态
  if (agent.circuit_state === 'OPEN') return 'degraded'
  // 恢复中
  if (agent.circuit_state === 'HALF_OPEN') return 'standby'
  // 正常运行的 agent（不依赖 LLM 可用性判断，dashboard 已返回即视为在线）
  return 'active'
}

function agentCardClass(agent: any): string {
  if (!dashboardData.value) return ''
  if (agent.alive === false) return 'dead'
  if (agent.circuit_state === 'OPEN') return 'degraded'
  return 'active'
}

function agentStatusLabel(agent: any): string {
  // dashboard 数据未加载 → 提示用户需要刷新
  if (!dashboardData.value) return '未同步'
  // 已停止的 agent
  if (agent.alive === false) return '已停止'
  // 熔断态
  if (agent.circuit_state === 'OPEN') return '已熔断'
  // 恢复中
  if (agent.circuit_state === 'HALF_OPEN') return '恢复中'
  // 正常运行的 agent（dashboard 已成功返回即视为在线）
  return '运行中'
}

const keyLabels: Record<string, string> = {
  treasury: '库银', grain: '粮草', troops: '兵力', arms: '军械',
}
const statusLabels: Record<string, string> = {
  healthy: '充裕', warning: '紧张', critical: '危急', ok: '正常',
}

function formatNum(n: number) {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + '千'
  return String(n)
}

function isRawResult(): boolean {
  const r = tacticalResult.value
  if (!r) return false
  return !(r.path || r.steps !== undefined || r.win_probability !== undefined || r.win_rate !== undefined || r.priorities?.length || r.plan || r.strategy)
}

function setAll(level: string) {
  Object.keys(delegationLevels).forEach(k => { delegationLevels[k] = level })
  updateDelegation('all')
}

function updateDelegation(_domain: string) {
  // 保存到 localStorage（前端本地存储，影响前端 AI 控制面板行为）
  delegationError.value = ''
  try {
    localStorage.setItem('yuanmo_delegation_config', JSON.stringify({ ...delegationLevels }))
    delegationSaved.value = true
    setTimeout(() => { delegationSaved.value = false }, 3000)
  } catch (e) {
    console.warn('委任配置保存失败:', e)
    delegationError.value = '保存失败，请检查浏览器存储空间'
    setTimeout(() => { delegationError.value = '' }, 5000)
  }
}

// 内政分析
async function refreshCivil() {
  if (!store.playerFactionId) return
  loading.value = true
  try {
    const resp = await api.post('/ai/civil/analyze', {
      faction_id: store.playerFactionId,
    })
    civilAnalysis.value = resp.data?.data || resp.data
  } catch (e) {
    console.error('内政分析失败:', e)
  } finally {
    loading.value = false
  }
}

async function executeCivilPlan() {
  if (!store.playerFactionId) return
  loading.value = true
  try {
    const resp = await api.post('/ai/civil/build-plan', {
      faction_id: store.playerFactionId,
    })
    if (resp.data?.data?.commands) {
      decisionLogs.value.unshift({
        turn: store.currentRound,
        agent: '文官内政AI',
        faction: store.playerFactionId,
        summary: `城建计划: ${resp.data.data.commands.length}项`,
        risk: resp.data.data.risk_assessment || 'low',
      })
      if (decisionLogs.value.length > 50) decisionLogs.value.pop()
    }
  } catch (e) {
    console.error('城建执行失败:', e)
  } finally {
    loading.value = false
  }
}

async function resourcePlanCivil() {
  if (!store.playerFactionId) return
  loading.value = true
  civilPhase.value = 'analyzing'
  try {
    const resp = await api.post('/ai/civil/resource-plan', {
      faction_id: store.playerFactionId,
    })
    if (resp.data?.data) {
      civilAnalysis.value = { ...civilAnalysis.value, ...resp.data.data }
    }
  } catch (e) {
    console.error('资源调配分析失败:', e)
  } finally {
    loading.value = false
    civilPhase.value = ''
  }
}

// 战术AI
async function findPath() {
  if (!tactical.from || !tactical.to || !store.playerFactionId) return
  recordTacticalQuery()
  loading.value = true
  try {
    const resp = await api.post('/ai/tactical/path', {
      from_tile: tactical.from,
      to_tile: tactical.to,
      faction_id: store.playerFactionId,
    })
    tacticalResult.value = resp.data?.data || resp.data
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

async function predictBattle() {
  if (!tactical.to || !store.playerFactionId) return
  recordTacticalQuery()
  loading.value = true
  try {
    const resp = await api.post('/ai/tactical/battle-predict', {
      tile_id: tactical.to,
      faction_id: store.playerFactionId,
      troops: tactical.troops,
      from_tile: tactical.from || undefined,
    })
    tacticalResult.value = resp.data?.data || resp.data
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

async function planTactics() {
  if (!tactical.to || !store.playerFactionId) return
  recordTacticalQuery()
  loading.value = true
  try {
    const resp = await api.post('/ai/tactical/plan', {
      tile_id: tactical.to,
      faction_id: store.playerFactionId,
    })
    tacticalResult.value = resp.data?.data || resp.data
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

async function garrisonPriorities() {
  if (!store.playerFactionId) return
  loading.value = true
  try {
    const resp = await api.post('/ai/tactical/garrison', {
      faction_id: store.playerFactionId,
    })
    tacticalResult.value = resp.data?.data || resp.data
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

// ===== Dashboard 刷新 =====
async function refreshDashboard() {
  dashboardLoading.value = true
  try {
    const data = await agentDashboard()
    dashboardData.value = data
    if (data) {
      aiStatus.connected = data.ai_available
      aiStatus.activeAgents = data.global_stats?.active_agents || 0
    }
  } catch (e) {
    console.warn('Agent Dashboard 加载失败:', e)
  } finally {
    dashboardLoading.value = false
  }
}

async function refreshDecisionLogs() {
  dashboardLoading.value = true
  try {
    // 从 dashboard 获取事件总线数据生成决策日志
    const data = await agentDashboard()
    dashboardData.value = data
    if (data) {
      const newLogs: any[] = []

      // 从圣旨统计生成日志
      if (data.edict_stats?.last_edicts) {
        for (const e of data.edict_stats.last_edicts) {
          newLogs.push({
            turn: e.round || '?',
            agent: '圣旨台',
            faction: store.playerFactionId || '?',
            summary: `执行${e.executed || 0}项/失败${e.failed || 0}项: ${e.text || ''}`,
            risk: e.failed > 0 ? 'medium' : 'low',
          })
        }
      }

      // 从事件总线添加摘要
      if (data.event_bus) {
        newLogs.unshift({
          turn: data.event_bus.recent_round,
          agent: '事件总线',
          faction: '全局',
          summary: `待处理${data.event_bus.pending_events}事件 / 已归档${data.event_bus.archived_events}事件`,
          risk: data.event_bus.pending_events > 10 ? 'high' : data.event_bus.pending_events > 5 ? 'medium' : 'low',
        })
      }

      // 从智能体统计生成日志
      if (data.agents) {
        for (const agent of data.agents) {
          if (agent.call_count > 0) {
            newLogs.push({
              turn: store.currentRound,
              agent: `${agent.key} ${agent.name}`,
              faction: agent.player_only ? store.playerFactionId || '玩家' : '全局',
              summary: `已调用${agent.call_count}次 / 延迟${agent.avg_latency || 0}ms / 熔断${agent.circuit_state || 'CLOSED'}`,
              risk: agent.circuit_state === 'OPEN' ? 'high' : 'low',
            })
          }
        }
      }

      // 合并到现有日志，去重
      const merged = [...decisionLogs.value]
      for (const log of newLogs) {
        const dup = merged.find(l => l.agent === log.agent && l.summary === log.summary && l.turn === log.turn)
        if (!dup) merged.unshift(log)
      }
      if (merged.length > 100) merged.length = 100
      decisionLogs.value = merged
    }
  } catch (e) {
    console.warn('决策日志刷新失败:', e)
  } finally {
    dashboardLoading.value = false
  }
}

async function triggerAutoStep() {
  if (store.isProcessing) return
  try {
    const result = await store.autoStepAI()
    if (result) {
      decisionLogs.value.unshift({
        turn: store.currentRound,
        agent: 'Orchestrator',
        faction: '全局',
        summary: `一键推演完成: ${typeof result === 'string' ? result.slice(0, 100) : JSON.stringify(result).slice(0, 100)}`,
        risk: 'low',
      })
      if (decisionLogs.value.length > 100) decisionLogs.value.pop()
    }
  } catch (e) {
    console.warn('自动推演失败:', e)
  }
}

// 连接状态检查（使用 /api/agent/status 获取AI在线状态和模型信息）
// + 集群Tab自动轮询（带防抖）
let _pollTimer: ReturnType<typeof setInterval> | null = null
const _pollActive = ref(false)
let _lastPollTime = 0

function safePollDashboard() {
  const now = Date.now()
  if (dashboardLoading.value || now - _lastPollTime < 3000) return
  _lastPollTime = now
  refreshDashboard()
}

function startPolling() {
  stopPolling()
  _pollActive.value = true
  _pollTimer = setInterval(safePollDashboard, 5000)
}
function stopPolling() {
  _pollActive.value = false
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null }
}

watch([() => props.visible, () => activeTab.value], ([v, tab]) => {
  if (v) {
    // 并行请求状态和 dashboard
    try {
      api.get('/api/agent/status').then(resp => {
        const d = resp.data?.data || resp.data
        aiStatus.connected = d?.ai_available || false
        aiStatus.model = d?.models?.advisor || '--'
        aiStatus.activeAgents = d?.agents?.length || 10
      }).catch(e => { console.warn('获取AI状态失败:', e); aiStatus.connected = false })
    } catch (_) {}

    // 非阻塞加载 dashboard
    refreshDashboard()

    // 集群Tab自动轮询
    if (tab === 'agents') startPolling()
    else stopPolling()
  } else {
    stopPolling()
  }
})

// ===== 以下为新增工具函数 =====

// Agent 卡片展开/折叠
const expandedAgent = ref('')  // 当前展开的 Agent key

function toggleAgentExpand(key: string) {
  expandedAgent.value = expandedAgent.value === key ? '' : key
}

// 战术查询历史（最近5次）
const tacticalHistory = ref<Array<{ from: string; to: string; troops: number }>>([])

function recordTacticalQuery() {
  if (!tactical.from || !tactical.to) return
  const entry = { from: tactical.from, to: tactical.to, troops: tactical.troops }
  tacticalHistory.value.unshift(entry)
  if (tacticalHistory.value.length > 5) tacticalHistory.value.pop()
  // 去重
  tacticalHistory.value = tacticalHistory.value.filter(
    (h, i, arr) => arr.findIndex(x => x.from === h.from && x.to === h.to) === i
  )
}

function loadTacticalHistory(entry: { from: string; to: string; troops: number }) {
  tactical.from = entry.from
  tactical.to = entry.to
  tactical.troops = entry.troops
}

// 日志导出 CSV
function exportLogsCSV() {
  if (!decisionLogs.value.length) return
  const header = '回合,Agent,势力,摘要,风险\n'
  const rows = decisionLogs.value.map(l =>
    `${l.turn || ''},${(l.agent || '').replace(/,/g, ' ')},${l.faction || ''},${(l.summary || '').replace(/,/g, ' ')},${l.risk || ''}`
  ).join('\n')
  const blob = new Blob(['\uFEFF' + header + rows], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `AI决策日志_回合${store.currentRound}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// 键盘快捷键 Ctrl+1~5 切换Tab | Escape 关闭
function handleKeydown(e: KeyboardEvent) {
  if (!props.visible) return
  if (e.ctrlKey && e.key >= '1' && e.key <= '5') {
    e.preventDefault()
    activeTab.value = tabs[parseInt(e.key) - 1].id
  }
  if (e.key === 'Escape') {
    e.preventDefault()
    emit('close')
  }
}

onMounted(() => { window.addEventListener('keydown', handleKeydown) })
onUnmounted(() => { window.removeEventListener('keydown', handleKeydown); stopPolling() })
</script>

<style scoped>
.aicp-overlay {
  position: fixed; inset: 0; z-index: 1000; background: rgba(0,0,0,0.5);
  display: flex; justify-content: flex-end;
}
.aicp-panel {
  width: 520px; height: 100vh; color: #e0d5c1;
  display: flex; flex-direction: column;
  font-family: 'Noto Serif SC', 'SimSun', serif;
}
.aicp-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; background: #16213e; border-bottom: 1px solid #c9a45c;
}
.aicp-header h2 { margin: 0; font-size: 18px; color: #c9a45c; }
.aicp-close { background: none; border: none; color: #e0d5c1; font-size: 20px; cursor: pointer; }
.aicp-status-bar { display: flex; gap: 16px; padding: 8px 20px; background: #0f3460; font-size: 12px; }
.status-item { display: flex; align-items: center; gap: 4px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #666; }
.status-item.active .status-dot { background: #4caf50; }
.aicp-tabs { display: flex; background: #16213e; border-bottom: 1px solid #333; }
.aicp-tabs button {
  flex: 1; padding: 10px 8px; background: none; border: none; color: #888;
  font-size: 13px; cursor: pointer; font-family: inherit;
  border-bottom: 2px solid transparent;
}
.aicp-tabs button.active { color: #c9a45c; border-bottom-color: #c9a45c; }
.aicp-content { flex: 1; overflow-y: auto; padding: 16px 20px; }
.aicp-content h3 { color: #c9a45c; font-size: 16px; margin: 0 0 12px; }
.aicp-content h4 { color: #e0d5c1; font-size: 14px; margin: 16px 0 8px; }
.aicp-desc { font-size: 12px; color: #888; margin: 4px 0; }
.delegation-list { display: flex; flex-direction: column; gap: 8px; }
.delegation-item { display: flex; justify-content: space-between; align-items: center;
  background: #16213e; padding: 10px 14px; border-radius: 6px; }
.delegation-info { display: flex; align-items: center; gap: 10px; }
.delegation-icon { font-size: 20px; }
.delegation-controls select {
  background: #1a1a2e; color: #c9a45c; border: 1px solid #333; padding: 6px 12px;
  border-radius: 4px; font-family: inherit; font-size: 13px;
}
.quick-actions { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.btn-action {
  background: #c9a45c; color: #1a1a2e; border: none; padding: 8px 16px;
  border-radius: 4px; cursor: pointer; font-family: inherit; font-size: 13px;
  transition: opacity 0.2s;
}
.btn-action:disabled { opacity: 0.5; }
.btn-action.secondary { background: #333; color: #e0d5c1; }
.btn-action.danger { background: #6b3030; color: #e0d5c1; }
.section-row { display: flex; gap: 8px; margin-bottom: 12px; }
.input-group { flex: 1; }
.input-group label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.input-group input {
  width: 100%; background: #16213e; color: #e0d5c1; border: 1px solid #333;
  padding: 8px 12px; border-radius: 4px; font-family: inherit; box-sizing: border-box;
}
.btn-row { display: flex; gap: 8px; margin-bottom: 16px; }
.resource-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.resource-card { background: #16213e; padding: 8px 12px; border-radius: 4px; }
.resource-name { font-size: 12px; color: #888; }
.resource-value { font-size: 18px; font-weight: bold; color: #c9a45c; }
.resource-status { font-size: 11px; }
.resource-status.healthy { color: #4caf50; }
.resource-status.warning { color: #ff9800; }
.resource-status.critical { color: #f44336; }
.rec-section { margin-top: 12px; }
.rec-section.danger { background: rgba(244,67,54,0.1); padding: 8px 12px; border-radius: 4px; }
.rec-item { display: flex; gap: 12px; padding: 4px 0; font-size: 13px; border-bottom: 1px solid #222; }
.rec-score { color: #c9a45c; }
.rec-reason { color: #888; font-size: 12px; }
.result-section { margin-top: 12px; background: #0d1b2a; padding: 12px; border-radius: 4px; max-height: 300px; overflow-y: auto; }
.result-json { margin: 0; font-size: 11px; color: #4caf50; white-space: pre-wrap; font-family: monospace; }
.log-list { display: flex; flex-direction: column; gap: 4px; }
.log-item { display: flex; gap: 8px; padding: 6px 0; border-bottom: 1px solid #222; font-size: 12px; align-items: center; flex-wrap: wrap; }
.log-time { color: #888; min-width: 50px; }
.log-agent { color: #c9a45c; font-weight: bold; min-width: 80px; }
.log-faction { color: #4caf50; }
.log-summary { color: #e0d5c1; flex: 1; }
.log-risk { padding: 2px 6px; border-radius: 3px; font-size: 10px; }
.log-risk.low { background: rgba(76,175,80,0.2); color: #4caf50; }
.log-risk.medium { background: rgba(255,152,0,0.2); color: #ff9800; }
.log-risk.high { background: rgba(244,67,54,0.2); color: #f44336; }
.empty-state { color: #666; text-align: center; padding: 40px; font-size: 14px; }
.agent-grid { display: flex; flex-direction: column; gap: 8px; }
.agent-card { background: #16213e; padding: 10px 14px; border-radius: 6px; opacity: 0.6; }
.agent-card.active { opacity: 1; border: 1px solid #c9a45c; }
.agent-card.degraded { opacity: 0.8; border: 1px solid #ff9800; }
.agent-card.dead { opacity: 0.4; border: 1px solid #666; }
.agent-header { display: flex; align-items: center; gap: 8px; }
.agent-icon { font-size: 18px; }
.agent-status { font-size: 11px; padding: 2px 6px; border-radius: 3px; margin-left: auto; }
.agent-status.active { background: rgba(76,175,80,0.2); color: #4caf50; }
.agent-status.standby { background: rgba(136,136,136,0.2); color: #888; }
.agent-status.degraded { background: rgba(255,152,0,0.2); color: #ff9800; }
.agent-status.dead { background: rgba(136,136,136,0.2); color: #666; }
.agent-desc { font-size: 12px; color: #888; margin: 4px 0; }
.agent-model { font-size: 11px; color: #666; display: flex; gap: 12px; }
.agent-stats-row { font-size: 10px; color: #777; display: flex; gap: 10px; margin-top: 4px; }
.agent-memories { font-size: 10px; color: #5a7a9a; margin-top: 2px; }

/* ===== Dashboard 摘要卡片 ===== */
.dashboard-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.ds-card { background: #16213e; padding: 8px 12px; border-radius: 4px; text-align: center; }
.ds-value { font-size: 20px; font-weight: bold; color: #c9a45c; }
.ds-value.warn { color: #ff9800; }
.ds-label { font-size: 10px; color: #888; margin-top: 2px; }

/* ===== 模型分组标签 ===== */
.model-groups-info { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
.model-group-tag { font-size: 10px; color: #94a3b8; background: rgba(100,116,139,0.15); padding: 2px 6px; border-radius: 3px; }

/* ===== 降级警告 ===== */
.degraded-warning { margin-top: 10px; padding: 8px 12px; background: rgba(255,152,0,0.15); color: #ff9800; border-radius: 4px; font-size: 12px; }

/* ===== 事件总线摘要 ===== */
.aicp-event-bus-info { display: flex; flex-wrap: wrap; gap: 10px; font-size: 11px; color: #94a3b8; margin-bottom: 10px; background: rgba(45,40,32,0.4); padding: 6px 10px; border-radius: 4px; }

/* ===== 委任保存提示 ===== */
.delegation-saved-hint { margin-top: 12px; font-size: 11px; color: #4caf50; text-align: center; }
.delegation-error-hint { margin-top: 12px; font-size: 11px; color: #f44336; text-align: center; }

/* ===== 战术卡片 ===== */
.tactical-loading { text-align: center; color: #c9a45c; padding: 12px; font-size: 13px; animation: pulse-text 1.5s ease-in-out infinite; }
.tactical-card { background: #16213e; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; border-left: 3px solid #c9a45c; }
.tactical-card-title { font-size: 13px; color: #c9a45c; font-weight: bold; margin-bottom: 6px; }
.tactical-card-body { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; color: #e0d5c1; }
.tactical-stat { background: rgba(201,164,92,0.1); padding: 2px 8px; border-radius: 3px; font-size: 11px; }
.tactical-priority-row { display: flex; gap: 8px; padding: 2px 0; width: 100%; font-size: 12px; border-bottom: 1px solid #222; }
.result-raw-details { margin-top: 4px; }
.result-raw-toggle { font-size: 11px; color: #888; cursor: pointer; user-select: none; }

/* ===== 日志筛选 ===== */
.log-filter-row { display: flex; gap: 6px; margin-bottom: 8px; align-items: center; }
.log-filter-input { flex: 1; background: #16213e; color: #e0d5c1; border: 1px solid #333; padding: 4px 8px; border-radius: 4px; font-family: inherit; font-size: 11px; }
.log-filter-select { background: #16213e; color: #c9a45c; border: 1px solid #333; padding: 4px 6px; border-radius: 4px; font-family: inherit; font-size: 11px; }
.log-filter-count { font-size: 10px; color: #666; white-space: nowrap; }

/* ===== 集群轮询标记 ===== */
.polling-badge { font-size: 10px; color: #4caf50; font-weight: normal; margin-left: 6px; opacity: 0.8; animation: pulse-text 2s ease-in-out infinite; }

/* ===== Agent 展开详情 ===== */
.agent-card { cursor: pointer; transition: all 0.2s; }
.agent-card:hover { filter: brightness(1.05); }
.agent-expand { margin-top: 8px; padding-top: 8px; border-top: 1px solid #333; }
.agent-expand-section { margin-bottom: 6px; }
.expand-label { font-size: 10px; color: #5a7a9a; text-transform: uppercase; margin-bottom: 2px; }
.expand-json { font-size: 10px; color: #777; white-space: pre-wrap; font-family: monospace; max-height: 80px; overflow-y: auto; }
.expand-item { font-size: 10px; color: #94a3b8; padding: 1px 0; }
.circuit-item { color: #ff9800; }
.expand-hint { font-size: 10px; color: #555; font-style: italic; }

/* ===== 战术历史 ===== */
.tactical-history { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-bottom: 8px; }
.history-label { font-size: 10px; color: #666; }
.history-chip {
  background: rgba(201,164,92,0.1); color: #c9a45c; border: 1px solid rgba(201,164,92,0.2);
  padding: 2px 8px; border-radius: 3px; font-size: 10px; cursor: pointer; font-family: monospace;
  transition: background 0.15s;
}
.history-chip:hover { background: rgba(201,164,92,0.2); }

/* ===== 快捷键栏 ===== */
.aicp-shortcut-bar {
  display: flex; gap: 16px; justify-content: center; padding: 6px 12px;
  background: #0d1b2a; border-top: 1px solid #1a1a2e; font-size: 10px; color: #555;
}

/* ===== 通用动画 ===== */
@keyframes pulse-text { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
