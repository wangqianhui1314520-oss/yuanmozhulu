<template>
  <Teleport to="body">
    <div class="settings-overlay" @click.self="$emit('close')" v-if="visible">
      <div class="settings-dialog animate-fade-in">
        <div class="settings-header">
          <h2>⚙ 游戏设置</h2>
          <button v-audio class="settings-close" @click="$emit('close')">✕</button>
        </div>

        <!-- 标签页 -->
        <div class="settings-tabs">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            v-audio class="settings-tab"
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
          >
            {{ tab.icon }} {{ tab.label }}
          </button>
        </div>

        <!-- 内容区 -->
        <div class="settings-body">
          <!-- AI模型配置 -->
          <div v-if="activeTab === 'ai'" class="settings-section">
            <div class="config-card" v-for="model in aiModels" :key="model.id">
              <h4>{{ model.name }}</h4>
              <p class="config-desc">{{ model.desc }}</p>
              <div class="config-row">
                <label>API地址</label>
                <input type="text" v-model="model.apiBase" class="config-input" />
              </div>
              <div class="config-row">
                <label>模型名称</label>
                <input type="text" v-model="model.modelName" class="config-input" />
              </div>
              <div class="config-row">
                <label>温度 (0-2)</label>
                <input type="range" min="0" max="2" step="0.1" v-model.number="model.temperature" class="config-range" />
                <span class="range-val">{{ model.temperature }}</span>
              </div>
              <div class="config-row">
                <label>最大Token</label>
                <input type="number" v-model.number="model.maxTokens" class="config-input short" />
              </div>
            </div>
            <div class="config-actions">
              <button class="cfg-btn cfg-test" @click="testConnection" :disabled="testingModel">
                {{ testingModel ? '测试中...' : '连通性测试' }}
              </button>
              <button class="cfg-btn cfg-save" @click="saveConfig">保存配置</button>
              <button class="cfg-btn cfg-reset" @click="resetConfig">恢复默认</button>
            </div>
            <div class="config-status" v-if="statusMsg" :class="{ 'text-error': statusMsg.startsWith('✗') || statusMsg.startsWith('⏱') }">{{ statusMsg }}</div>
            <!-- 逐模型测试结果明细 -->
            <div v-if="Object.keys(modelTestResults).length > 0" class="test-results">
              <div
                v-for="(r, key) in modelTestResults"
                :key="key"
                class="test-result-item"
                :class="{ 'test-ok': r.status === 'ok', 'test-fail': r.status !== 'ok' }"
              >
                <span class="test-icon">{{ STATUS_ICONS[r.status] || '?' }}</span>
                <span class="test-model">{{ MODEL_LABELS[key] || key }}</span>
                <span class="test-name">{{ r.model_name }}</span>
                <span class="test-latency">{{ r.latency_ms }}ms</span>
                <span v-if="r.error" class="test-error">{{ r.error }}</span>
              </div>
            </div>
          </div>

          <!-- 圣旨AI模型配置 -->
          <div v-if="activeTab === 'edict'" class="settings-section">
            <div class="config-card">
              <h4>📜 圣旨AI解析模型</h4>
              <p class="config-desc">自然语言圣旨的意图识别与指令拆解模型。支持白话文、文言文、长篇战略叙事的智能解析。</p>
              <div class="config-row">
                <label>API地址</label>
                <input type="text" v-model="edictLLM.apiBase" class="config-input" />
              </div>
              <div class="config-row">
                <label>模型名称</label>
                <input type="text" v-model="edictLLM.modelName" class="config-input" />
              </div>
              <div class="config-row">
                <label>温度 (0-2)</label>
                <input type="range" min="0" max="2" step="0.1" v-model.number="edictLLM.temperature" class="config-range" />
                <span class="range-val">{{ edictLLM.temperature }}</span>
              </div>
              <div class="config-row">
                <label>最大Token</label>
                <input type="number" v-model.number="edictLLM.maxTokens" class="config-input short" />
              </div>
              <div class="config-row toggle-row">
                <label>AI解析开关</label>
                <button v-audio class="toggle-btn" :class="{ on: edictLLM.useAI }" @click="edictLLM.useAI = !edictLLM.useAI; saveEdictConfig()">
                  {{ edictLLM.useAI ? '启用' : '仅本地' }}
                </button>
              </div>
            </div>
            <div class="config-card">
              <h4>解析能力说明</h4>
              <div class="info-grid">
                <div class="info-item"><span>意图识别</span><span class="text-green">五大类细分</span></div>
                <div class="info-item"><span>实体提取</span><span class="text-green">势力/地块/数值/约束</span></div>
                <div class="info-item"><span>前置校验</span><span class="text-green">领地/资源/路径/去重</span></div>
                <div class="info-item"><span>批量解析</span><span class="text-green">支持多条连续圣旨</span></div>
                <div class="info-item"><span>战略拆解</span><span class="text-green">长篇规划多回合分步</span></div>
                <div class="info-item"><span>撤回指令</span><span class="text-green">识别作废/取消语义</span></div>
              </div>
            </div>
            <div class="config-actions">
              <button class="cfg-btn cfg-save" @click="saveEdictConfig">保存圣旨AI配置</button>
              <button class="cfg-btn cfg-reset" @click="resetEdictConfig">恢复默认</button>
            </div>
            <div class="config-status" v-if="edictStatusMsg" :class="{ 'text-error': edictStatusMsg.startsWith('✗') }">{{ edictStatusMsg }}</div>
          </div>

          <!-- 音频设置 -->
          <div v-if="activeTab === 'audio'" class="settings-section">
            <div class="config-card">
              <h4>音量控制</h4>
              <div class="config-row">
                <label>总音量</label>
                <input type="range" min="0" max="100" v-model.number="audioSettings.masterVolume" class="config-range" @change="saveAudioSettings" />
                <span class="range-val">{{ audioSettings.masterVolume }}%</span>
              </div>
              <div class="config-row">
                <label>UI音效</label>
                <input type="range" min="0" max="100" v-model.number="audioSettings.uiVolume" class="config-range" @change="saveAudioSettings" />
                <span class="range-val">{{ audioSettings.uiVolume }}%</span>
              </div>
              <div class="config-row">
                <label>战斗音效</label>
                <input type="range" min="0" max="100" v-model.number="audioSettings.battleVolume" class="config-range" @change="saveAudioSettings" />
                <span class="range-val">{{ audioSettings.battleVolume }}%</span>
              </div>
            </div>
            <div class="config-card">
              <h4>开关设置</h4>
              <div class="config-row toggle-row">
                <label>剧情旁白</label>
                <button v-audio class="toggle-btn" :class="{ on: audioSettings.narrationOn }" @click="audioSettings.narrationOn = !audioSettings.narrationOn; saveAudioSettings()">
                  {{ audioSettings.narrationOn ? '开' : '关' }}
                </button>
              </div>
              <div class="config-row toggle-row">
                <label>AI朗读</label>
                <button v-audio class="toggle-btn" :class="{ on: audioSettings.aiReadOn }" @click="audioSettings.aiReadOn = !audioSettings.aiReadOn; saveAudioSettings()">
                  {{ audioSettings.aiReadOn ? '开' : '关' }}
                </button>
              </div>
              <div class="config-row toggle-row">
                <label>全局静音</label>
                <button v-audio class="toggle-btn" :class="{ on: audioSettings.muted }" @click="audioSettings.muted = !audioSettings.muted; saveAudioSettings()">
                  {{ audioSettings.muted ? '静音' : '正常' }}
                </button>
              </div>
            </div>
          </div>

          <!-- 画面设置 -->
          <div v-if="activeTab === 'display'" class="settings-section">
            <div class="config-card">
              <h4>画面选项</h4>
              <div class="config-row">
                <label>缩放比例</label>
                <select v-model="displaySettings.scale" class="config-select" @change="saveDisplaySettings">
                  <option value="0.75">75%</option>
                  <option value="0.9">90%</option>
                  <option value="1">100%</option>
                  <option value="1.1">110%</option>
                  <option value="1.25">125%</option>
                </select>
              </div>
              <div class="config-row">
                <label>提示延迟(ms)</label>
                <input type="number" v-model.number="displaySettings.tooltipDelay" class="config-input short" @change="saveDisplaySettings" />
              </div>
              <div class="config-row toggle-row">
                <label>动画效果</label>
                <button v-audio class="toggle-btn" :class="{ on: displaySettings.animationsOn }" @click="displaySettings.animationsOn = !displaySettings.animationsOn; saveDisplaySettings()">
                  {{ displaySettings.animationsOn ? '开' : '关' }}
                </button>
              </div>
              <div class="config-row toggle-row">
                <label>主题</label>
                <button class="toggle-btn theme-btn" @click="displaySettings.darkMode = !displaySettings.darkMode; saveDisplaySettings()">
                  {{ displaySettings.darkMode ? '🌙 深色对局' : '☀ 浅色阅览' }}
                </button>
              </div>
              <div class="config-row toggle-row">
                <label>侧边栏自动收起</label>
                <button v-audio class="toggle-btn" :class="{ on: displaySettings.autoCollapseSidebar }" @click="displaySettings.autoCollapseSidebar = !displaySettings.autoCollapseSidebar; saveDisplaySettings()">
                  {{ displaySettings.autoCollapseSidebar ? '开' : '关' }}
                </button>
              </div>
            </div>
          </div>

          <!-- 存档管理 -->
          <div v-if="activeTab === 'save'" class="settings-section">
            <div class="config-card">
              <h4>存档管理</h4>
              <div class="config-row">
                <label>自动存档间隔</label>
                <select v-model="saveSettings.autoSaveInterval" class="config-select" @change="saveSaveSettings">
                  <option :value="1">每回合</option>
                  <option :value="3">每3回合</option>
                  <option :value="5">每5回合</option>
                  <option :value="10">每10回合</option>
                  <option :value="0">关闭</option>
                </select>
              </div>
            </div>
            <div class="config-actions">
              <button class="cfg-btn" @click="exportSave">导出存档</button>
              <button class="cfg-btn" @click="importSave">导入存档</button>
              <button class="cfg-btn cfg-danger" @click="clearAllSaves">清空存档</button>
              <input ref="importFileInput" type="file" accept=".json" style="display:none" @change="handleImportFile" />
              <p class="status-msg" v-if="statusMsg">{{ statusMsg }}</p>
            </div>
          </div>

          <!-- 系统 -->
          <div v-if="activeTab === 'system'" class="settings-section">
            <div class="config-card">
              <h4>系统信息</h4>
              <div class="info-row"><span>前端版本</span><span>3.0.0</span></div>
              <div class="info-row"><span>后端版本</span><span>{{ backendVersion }}</span></div>
              <div class="info-row"><span>AI状态</span><span :class="aiAvailable ? 'text-green' : 'text-red'">{{ aiAvailable ? '在线' : '离线' }}</span></div>
            </div>
            <div class="config-actions">
              <button v-if="!isOnHomePage" class="cfg-btn cfg-danger" @click="resetGame">重置本局</button>
              <button v-if="!isOnHomePage" class="cfg-btn" @click="goHome">返回首页</button>
              <button v-else class="cfg-btn" @click="emit('close')">关闭设置</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/gameStore'
import { healthCheck, getRuntimeConfig, updateRuntimeConfig, getDefaultConfig, testLLMConnection, exportSaveFile, importSaveFile, clearAllSaves as apiClearAll, listSaves, getEdictLLMConfig, updateEdictLLMConfig } from '@/services/api'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

const router = useRouter()
const store = useGameStore()

/** 当前是否已在首页（路由为 / 或 /:pathMatch） */
const isOnHomePage = computed(() => {
  const name = router.currentRoute.value.name
  return name === 'home' || name === 'not-found'
})

const activeTab = ref('ai')
const statusMsg = ref('')
const testingModel = ref(false)
const modelTestResults = ref<Record<string, { status: string; model_name: string; latency_ms: number; error?: string }>>({})
const backendVersion = ref('—')
const aiAvailable = ref(false)

const tabs = [
  { id: 'ai', icon: '🧠', label: 'AI模型' },
  { id: 'edict', icon: '📜', label: '圣旨AI' },
  { id: 'audio', icon: '🔊', label: '音频' },
  { id: 'display', icon: '🖥', label: '画面' },
  { id: 'save', icon: '💾', label: '存档' },
  { id: 'system', icon: 'ℹ', label: '系统' },
]

const aiModels = reactive([
  { id: 'advisor', name: '主谋臣模型', desc: '用于君主对话、谋臣献策、廷议辩论', apiBase: 'https://api.lkeap.cloud.tencent.com/v3', modelName: 'hunyuan-role', temperature: 0.7, maxTokens: 4096 },
  { id: 'law', name: '战略推演模型', desc: '用于年度战略推演、合纵连横判定', apiBase: 'https://api.lkeap.cloud.tencent.com/v3', modelName: 'hunyuan-standard-256k', temperature: 0.6, maxTokens: 8192 },
  { id: 'enemy', name: '敌方AI模型', desc: '用于灾害判定、战斗结算、贪腐检查', apiBase: 'https://api.lkeap.cloud.tencent.com/v3', modelName: 'hunyuan-turbo', temperature: 0.65, maxTokens: 2048 },
])

const audioSettings = reactive({
  masterVolume: 80,
  uiVolume: 60,
  battleVolume: 70,
  narrationOn: true,
  aiReadOn: false,
  muted: false,
})

const displaySettings = reactive({
  scale: '1',
  tooltipDelay: 300,
  animationsOn: true,
  darkMode: true,
  autoCollapseSidebar: false,
})

const saveSettings = reactive({
  autoSaveInterval: 5,
})

// 圣旨AI专用模型配置
const edictLLM = reactive({
  apiBase: 'https://api.lkeap.cloud.tencent.com/v3',
  modelName: 'hunyuan-role',
  temperature: 0.4,
  maxTokens: 4096,
  useAI: true,
})
const edictStatusMsg = ref('')

onMounted(async () => {
  try {
    const health = await healthCheck()
    backendVersion.value = health.version
    aiAvailable.value = health.ai_available
  } catch {
    console.warn('健康检查失败')
    backendVersion.value = '未连接'
  }

  // 加载运行时配置
  try {
    const rt = await getRuntimeConfig()
    if (rt && Object.keys(rt).length > 0) {
      for (const model of aiModels) {
        if (rt[model.id]) {
          model.apiBase = rt[model.id].api_base || model.apiBase
          model.modelName = rt[model.id].model_name || model.modelName
          model.temperature = rt[model.id].temperature ?? model.temperature
          model.maxTokens = rt[model.id].max_tokens ?? model.maxTokens
        }
      }
    }
  } catch {
    console.warn('加载运行时配置失败，使用本地存储')
    // 后端不可用时使用本地存储
    const saved = localStorage.getItem('yuanmo_ai_config')
    if (saved) {
      try {
        const configs = JSON.parse(saved)
        for (const c of configs) {
          const model = aiModels.find(m => m.id === c.id)
          if (model) {
            model.apiBase = c.apiBase || model.apiBase
            model.modelName = c.modelName || model.modelName
            model.temperature = c.temperature ?? model.temperature
            model.maxTokens = c.maxTokens ?? model.maxTokens
          }
        }
      } catch { console.warn('Agent配置加载失败') }
    }
  }

  // 加载音频设置（本地持久化）
  const savedAudio = localStorage.getItem('yuanmo_audio')
  if (savedAudio) {
    try { Object.assign(audioSettings, JSON.parse(savedAudio)) } catch { console.warn('音频设置解析失败') }
  }

  // 加载画面设置（本地持久化）
  const savedDisplay = localStorage.getItem('yuanmo_display')
  if (savedDisplay) {
    try { Object.assign(displaySettings, JSON.parse(savedDisplay)) } catch { console.warn('画面设置解析失败') }
  }

  // 加载存档设置（本地持久化）
  const savedSaveSettings = localStorage.getItem('yuanmo_save_settings')
  if (savedSaveSettings) {
    try { Object.assign(saveSettings, JSON.parse(savedSaveSettings)) } catch { console.warn('存档设置解析失败') }
  }

  // 加载圣旨AI配置
  try {
    const ec = await getEdictLLMConfig()
    if (ec && ec.api_base) {
      edictLLM.apiBase = ec.api_base
      edictLLM.modelName = ec.model_name
      edictLLM.temperature = ec.temperature
      edictLLM.maxTokens = ec.max_tokens
      edictLLM.useAI = ec.available
    }
  } catch {
    // 降级到本地存储
    const saved = localStorage.getItem('yuanmo_edict_llm')
    if (saved) {
      try { Object.assign(edictLLM, JSON.parse(saved)) } catch { /* ignore */ }
    }
  }
})

// 持久化音频设置
function saveAudioSettings() {
  localStorage.setItem('yuanmo_audio', JSON.stringify({
    masterVolume: audioSettings.masterVolume,
    uiVolume: audioSettings.uiVolume,
    battleVolume: audioSettings.battleVolume,
    narrationOn: audioSettings.narrationOn,
    aiReadOn: audioSettings.aiReadOn,
    muted: audioSettings.muted,
  }))
}

// 持久化画面设置
function saveDisplaySettings() {
  localStorage.setItem('yuanmo_display', JSON.stringify({
    scale: displaySettings.scale,
    tooltipDelay: displaySettings.tooltipDelay,
    animationsOn: displaySettings.animationsOn,
    darkMode: displaySettings.darkMode,
    autoCollapseSidebar: displaySettings.autoCollapseSidebar,
  }))
  // 应用缩放
  if (displaySettings.darkMode) {
    document.documentElement.classList.add('dark-theme')
  } else {
    document.documentElement.classList.remove('dark-theme')
  }
}

// 持久化存档设置
function saveSaveSettings() {
  localStorage.setItem('yuanmo_save_settings', JSON.stringify({
    autoSaveInterval: saveSettings.autoSaveInterval,
  }))
}

/** 模型角色中文名映射 */
const MODEL_LABELS: Record<string, string> = {
  advisor: '主谋臣',
  law: '战略推演',
  enemy: '敌方AI',
}

/** 状态图标映射 */
const STATUS_ICONS: Record<string, string> = {
  ok: '✓',
  timeout: '⏱',
  error: '✗',
  not_configured: '⚙',
  warning: '⚠',
  no_response: '✗',
  unexpected_response: '⚠',
  skipped: '⊘',
}

async function testConnection() {
  statusMsg.value = ''
  modelTestResults.value = {}
  testingModel.value = true

  try {
    const result = await testLLMConnection()
    modelTestResults.value = result.results || {}
    if (result.configured && result.passed) {
      statusMsg.value = '✓ 全部模型连通正常'
    } else if (!result.configured) {
      statusMsg.value = '⚙ 请先配置 API Key 后再测试'
    } else {
      statusMsg.value = result.message
    }
  } catch (e: any) {
    console.warn('AI连通性测试失败:', e)
    statusMsg.value = '✗ 后端连接失败，请检查后端服务是否启动'
  } finally {
    testingModel.value = false
  }
}

async function saveConfig() {
  statusMsg.value = '正在保存...'
  try {
    const payload: Record<string, any> = {}
    for (const m of aiModels) {
      payload[m.id] = {
        api_base: m.apiBase,
        model_name: m.modelName,
        temperature: m.temperature,
        max_tokens: m.maxTokens,
      }
    }
    await updateRuntimeConfig(payload)
    statusMsg.value = '✓ 配置已保存并热更新（无需重启）'
  } catch {
    console.warn('运行时配置保存失败，降级到本地存储')
    // 降级：保存到本地存储
    localStorage.setItem('yuanmo_ai_config', JSON.stringify(aiModels.map(m => ({
      id: m.id, apiBase: m.apiBase, modelName: m.modelName, temperature: m.temperature, maxTokens: m.maxTokens,
    }))))
    statusMsg.value = '✓ 配置已保存到本地（后端不可用）'
  }
}

async function resetConfig() {
  try {
    const defaults = await getDefaultConfig()
    for (const model of aiModels) {
      if (defaults[model.id]) {
        model.apiBase = defaults[model.id].api_base
        model.modelName = defaults[model.id].model_name
        model.temperature = defaults[model.id].temperature
        model.maxTokens = defaults[model.id].max_tokens
      }
    }
    statusMsg.value = '已恢复默认配置'
  } catch {
    console.warn('加载默认配置失败，使用硬编码默认值')
    aiModels.forEach(m => {
      m.apiBase = 'https://api.lkeap.cloud.tencent.com/v3'
      m.temperature = m.id === 'advisor' ? 0.7 : m.id === 'law' ? 0.6 : 0.65
      m.maxTokens = m.id === 'advisor' ? 4096 : m.id === 'law' ? 8192 : 2048
    })
    statusMsg.value = '已恢复默认配置（本地）'
  }
}

// 圣旨AI配置保存/重置
async function saveEdictConfig() {
  edictStatusMsg.value = '正在保存...'
  try {
    await updateEdictLLMConfig({
      api_base: edictLLM.apiBase,
      model_name: edictLLM.modelName,
      temperature: edictLLM.temperature,
      max_tokens: edictLLM.maxTokens,
    })
    edictStatusMsg.value = '✓ 圣旨AI配置已保存并即时热生效'
    localStorage.setItem('yuanmo_edict_llm', JSON.stringify({
      apiBase: edictLLM.apiBase, modelName: edictLLM.modelName,
      temperature: edictLLM.temperature, maxTokens: edictLLM.maxTokens,
      useAI: edictLLM.useAI,
    }))
  } catch {
    localStorage.setItem('yuanmo_edict_llm', JSON.stringify({
      apiBase: edictLLM.apiBase, modelName: edictLLM.modelName,
      temperature: edictLLM.temperature, maxTokens: edictLLM.maxTokens,
      useAI: edictLLM.useAI,
    }))
    edictStatusMsg.value = '✓ 已保存到本地（后端不可用时降级）'
  }
}

function resetEdictConfig() {
  edictLLM.apiBase = 'https://api.lkeap.cloud.tencent.com/v3'
  edictLLM.modelName = 'hunyuan-role'
  edictLLM.temperature = 0.4
  edictLLM.maxTokens = 4096
  edictLLM.useAI = true
  edictStatusMsg.value = '已恢复圣旨AI默认配置'
  saveEdictConfig()
}

const importFileInput = ref<HTMLInputElement | null>(null)

async function exportSave() {
  statusMsg.value = '正在获取存档列表...'
  try {
    const { saves } = await listSaves()
    const manual = saves.filter((s: any) => !s.is_auto)
    if (manual.length === 0) {
      statusMsg.value = '没有可导出的手动存档，请先在存档管理中保存'
      return
    }
    // 导出最近的一个手动存档
    const latest = manual[0]
    const result = await exportSaveFile(latest.filename)
    const blob = new Blob([JSON.stringify(result.save_data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = latest.filename
    a.click()
    URL.revokeObjectURL(url)
    statusMsg.value = `已导出: ${latest.filename}`
  } catch (e: any) {
    statusMsg.value = '导出失败: ' + (e?.response?.data?.msg || e?.message || '未知错误')
  }
}

async function importSave() {
  importFileInput.value?.click()
}

async function handleImportFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  statusMsg.value = '正在导入...'
  try {
    const text = await file.text()
    const saveData = JSON.parse(text)
    if (!saveData.world_state && !saveData.round) {
      statusMsg.value = '无效的存档文件'
      return
    }
    const result = await importSaveFile(saveData, file.name)
    statusMsg.value = `导入成功: ${result.filename}`
  } catch (e: any) {
    statusMsg.value = '导入失败: ' + (e?.response?.data?.msg || e?.message || '文件格式错误')
  }
  if (importFileInput.value) importFileInput.value.value = ''
}

async function clearAllSaves() {
  if (!confirm('确认清空全部本地存档（含自动存档）？此操作不可撤销。')) return
  statusMsg.value = '正在清空...'
  try {
    const result = await apiClearAll()
    statusMsg.value = `已清空 ${result.deleted_count || 0} 个存档`
  } catch (e: any) {
    statusMsg.value = '清空失败: ' + (e?.response?.data?.msg || e?.message || '未知错误')
  }
}

async function resetGame() {
  if (confirm('确认重置当前对局？未存档的进度将丢失。')) {
    await store.resetGame()
    router.push({ name: 'home' }).catch(() => {})
    emit('close')
  }
}

function goHome() {
  // 已在首页：关闭设置面板即可
  if (isOnHomePage.value) {
    emit('close')
    return
  }
  // 游戏中：提示进度丢失
  if (store.currentRound > 1 && !confirm('返回首页将丢失当前进度，是否继续？')) return
  // 先导航到首页（组件存活时执行），再关闭设置面板
  router.push({ name: 'home' }).catch(() => {
    // NavigationDuplicated 等已由 Vue Router 内部处理
  })
  emit('close')
}
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4000;
}

.settings-dialog {
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-panel) 100%);
  border: 2px solid var(--text-dim);
  border-radius: 3px;
  width: 90vw;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.4);
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(180deg, var(--bg-hover) 0%, var(--border-main) 100%);
}

.settings-header h2 {
  font-size: 18px;
  font-weight: normal;
  letter-spacing: 4px;
}

.settings-close {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  font-size: 16px;
  cursor: pointer;
  color: var(--text-secondary);
}

.settings-close:hover { color: #8b0000; }

.settings-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-light);
}

.settings-tab {
  flex: 1;
  padding: 10px 8px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  font-family: "SimSun", serif;
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 2px;
  transition: all 0.2s;
}

.settings-tab:hover { background: rgba(139, 115, 85, 0.06); }
.settings-tab.active { border-bottom-color: #8b0000; color: #8b0000; }

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.config-card {
  background: rgba(240, 228, 204, 0.6);
  border: 1px solid var(--border-light);
  border-radius: 2px;
  padding: 12px 16px;
  margin-bottom: 12px;
}

.config-card h4 {
  font-size: 14px;
  font-weight: normal;
  color: var(--text-main);
  margin-bottom: 8px;
  letter-spacing: 2px;
}

.config-desc {
  font-size: 11px;
  color: var(--text-dim);
  margin-bottom: 10px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
}

.config-row label {
  width: 80px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.config-input {
  flex: 1;
  padding: 4px 8px;
  background: var(--bg-card);
  border: 1px solid var(--text-dim);
  border-radius: 2px;
  font-family: "SimSun", serif;
  font-size: 12px;
  color: var(--text-main);
}

.config-input.short {
  flex: 0;
  width: 80px;
}

.config-range {
  flex: 1;
  accent-color: #8b0000;
}

.range-val {
  width: 40px;
  text-align: right;
  color: var(--text-main);
}

.config-select {
  padding: 4px 8px;
  background: var(--bg-card);
  border: 1px solid var(--text-dim);
  border-radius: 2px;
  font-family: "SimSun", serif;
  font-size: 12px;
  color: var(--text-main);
}

.toggle-row {
  justify-content: space-between;
}

.toggle-btn {
  padding: 3px 16px;
  font-size: 11px;
  font-family: "SimSun", serif;
  background: rgba(139, 115, 85, 0.1);
  border: 1px solid var(--text-dim);
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 2px;
  letter-spacing: 2px;
}

.toggle-btn.on {
  background: rgba(91, 140, 90, 0.15);
  border-color: #5b8c5a;
  color: #5b8c5a;
}

.theme-btn {
  width: 140px;
}

.config-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.cfg-btn {
  padding: 8px 16px;
  font-size: 12px;
  font-family: "SimSun", serif;
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-card) 100%);
  border: 1px solid #c9a94e;
  color: var(--text-main);
  cursor: pointer;
  border-radius: 2px;
  letter-spacing: 2px;
  transition: all 0.2s;
}

.cfg-btn:hover {
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-hover) 100%);
}

.cfg-save {
  background: linear-gradient(180deg, #8b0000 0%, #6b0000 100%);
  color: var(--bg-card);
  border-color: #a00000;
}

.cfg-save:hover {
  background: linear-gradient(180deg, #a00000 0%, #800000 100%);
}

.cfg-danger {
  color: #8b0000;
  border-color: rgba(139, 0, 0, 0.4);
}

.cfg-danger:hover {
  background: rgba(139, 0, 0, 0.1);
}

.config-status {
  margin-top: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: #5b8c5a;
  background: rgba(91, 140, 90, 0.08);
  border-radius: 2px;
  letter-spacing: 1px;
}

.config-status.text-error {
  color: #c44b3c;
  background: rgba(196, 75, 60, 0.08);
}

/* 连通性测试按钮 */
.cfg-test {
  background: linear-gradient(180deg, #1a3a5c 0%, #15304a 100%);
  border-color: #4a8ab0;
  color: #8cc8e8;
}

.cfg-test:hover:not(:disabled) {
  background: linear-gradient(180deg, #224c74 0%, #1a3a5c 100%);
  border-color: #5a9ac0;
}

.cfg-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 逐模型测试结果 */
.test-results {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.test-result-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 2px;
  letter-spacing: 1px;
}

.test-ok {
  background: rgba(91, 140, 90, 0.08);
  color: #5b8c5a;
}

.test-fail {
  background: rgba(196, 75, 60, 0.06);
  color: #c44b3c;
}

.test-icon {
  width: 16px;
  text-align: center;
  font-weight: bold;
}

.test-model {
  font-weight: bold;
  min-width: 56px;
}

.test-name {
  color: var(--text-secondary);
  flex: 1;
}

.test-latency {
  color: var(--text-dim);
  min-width: 52px;
  text-align: right;
}

.test-error {
  color: #c44b3c;
  font-size: 10px;
  word-break: break-all;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px dotted var(--border-light);
}

.info-row span:first-child { color: var(--text-secondary); }
.info-row span:last-child { color: var(--text-main); font-weight: bold; }

.text-green { color: #5b8c5a; }
.text-red { color: #c44b3c; }

.animate-fade-in {
  animation: fadeIn 0.25s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}
</style>
