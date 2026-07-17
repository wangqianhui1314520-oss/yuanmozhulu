<template>
  <Teleport to="body">
    <div class="settings-overlay" @click.self="$emit('close')" v-if="visible">
      <div class="settings-dialog animate-fade-in artifact-panel artifact-memorial">
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
            <!-- 预设方案：一键切换 -->
            <div class="config-card preset-card">
              <h4>⚡ 预设方案</h4>
              <p class="config-desc">一键切换模型配置，点击即应用。越快的模型圣旨/回合等待时间越短。</p>
              <div class="preset-grid">
                <button
                  v-for="p in speedPresets"
                  :key="p.id"
                  class="preset-btn"
                  :class="{ active: activePreset === p.id }"
                  @click="applyPreset(p.id)"
                >
                  <span class="preset-icon">{{ p.icon }}</span>
                  <span class="preset-name">{{ p.name }}</span>
                  <span class="preset-speed">{{ p.speed }}</span>
                  <span class="preset-desc">{{ p.desc }}</span>
                </button>
              </div>
            </div>

            <!-- API 提供商切换 -->
            <div class="config-card provider-card">
              <h4>🔌 API 提供商</h4>
              <p class="config-desc">切换 API 服务商将自动更新地址和推荐模型。使用自己的 API Key 可绕过代理延迟。</p>
              <div class="provider-row">
                <button
                  v-for="prov in providers"
                  :key="prov.id"
                  class="provider-btn"
                  :class="{ active: activeProvider === prov.id }"
                  @click="switchProvider(prov.id)"
                >
                  <span class="prov-name">{{ prov.name }}</span>
                  <span class="prov-speed">{{ prov.speed }}</span>
                </button>
              </div>
            </div>

            <!-- 三个模型组的详细配置 -->
            <div class="config-card" v-for="model in aiModels" :key="model.id">
              <h4>{{ model.name }}</h4>
              <p class="config-desc">{{ model.desc }}</p>
              <div class="config-row">
                <label>API地址</label>
                <input type="text" v-model="model.apiBase" class="config-input" />
              </div>
              <div class="config-row">
                <label>模型名称</label>
                <div class="model-select-group">
                  <select v-model="model.modelName" class="config-select model-select" @change="onModelSelect(model)">
                    <option v-for="opt in getModelOptions(model.id)" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                    <option value="__custom__">自定义...</option>
                  </select>
                  <input
                    v-if="model.modelName === '__custom__' || !getModelOptions(model.id).some(o => o.value === model.modelName)"
                    type="text"
                    v-model="model.modelName"
                    class="config-input model-input"
                    placeholder="输入模型名称..."
                    @focus="model.modelName = model.modelName === '__custom__' ? '' : model.modelName"
                  />
                </div>
              </div>
              <div class="config-row">
                <label>API Key</label>
                <div class="key-input-group">
                  <input
                    :type="model.showKey ? 'text' : 'password'"
                    v-model="model.apiKey"
                    class="config-input"
                    :placeholder="model.apiKey ? maskApiKey(model.apiKey) : (activeProvider === 'codebuddy' ? '使用服务器默认Key（留空）' : '输入你的 API Key')"
                  />
                  <button class="key-toggle" @click="model.showKey = !model.showKey" :title="model.showKey ? '隐藏' : '显示'">
                    {{ model.showKey ? '🙈' : '👁' }}
                  </button>
                </div>
              </div>
              <div class="config-row">
                <label>温度 (0-2)</label>
                <input type="range" min="0" max="2" step="0.1" v-model.number="model.temperature" class="config-range" />
                <span class="range-val">{{ model.temperature }}</span>
              </div>
              <div class="config-row">
                <label>最大Token</label>
                <input type="number" v-model.number="model.maxTokens" class="config-input short" />
                <span class="token-hint" v-if="model.maxTokens <= 1024">⚡快</span>
                <span class="token-hint" v-else-if="model.maxTokens <= 4096">— 中</span>
                <span class="token-hint" v-else>🐢 慢</span>
              </div>
            </div>
            <div class="config-card painter-card">
              <h4>🎨 AI画师 · 文生图</h4>
              <p class="config-desc">
                调用混元文生图 API 生成元末历史题材水墨画。在史馆→画师页面输入描述词即可生成。
                需自备腾讯云混元 API Key（或使用服务端已配置的全局密钥）。
              </p>
              <div class="config-row">
                <label>API Key</label>
                <div class="key-input-group">
                  <input
                    :type="painterKeyVisible ? 'text' : 'password'"
                    v-model="painterApiKey"
                    class="config-input"
                    :placeholder="painterApiKey ? maskApiKey(painterApiKey) : '输入混元 API Key（留空使用服务端默认）'"
                  />
                  <button class="key-toggle" @click="painterKeyVisible = !painterKeyVisible" :title="painterKeyVisible ? '隐藏' : '显示'">
                    {{ painterKeyVisible ? '🙈' : '👁' }}
                  </button>
                </div>
              </div>
              <div class="config-row">
                <label>API地址</label>
                <input type="text" v-model="painterApiBase" class="config-input" placeholder="留空使用服务端默认地址" />
              </div>
              <div class="config-actions">
                <button class="cfg-btn cfg-save" @click="savePainterConfig">保存画师配置</button>
                <button class="cfg-btn cfg-reset" @click="clearPainterConfig">清除</button>
              </div>
              <p class="status-msg" v-if="painterStatusMsg">{{ painterStatusMsg }}</p>
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
                <div class="model-select-group">
                  <select v-model="edictLLM.modelName" class="config-select model-select">
                    <option v-for="opt in getModelOptions('edict')" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                    <option value="__custom__">自定义...</option>
                  </select>
                  <input
                    v-if="edictLLM.modelName === '__custom__' || !getModelOptions('edict').some(o => o.value === edictLLM.modelName)"
                    type="text"
                    v-model="edictLLM.modelName"
                    class="config-input model-input"
                    placeholder="输入模型名称..."
                    @focus="edictLLM.modelName = edictLLM.modelName === '__custom__' ? '' : edictLLM.modelName"
                  />
                </div>
              </div>
              <div class="config-row">
                <label>API Key</label>
                <div class="key-input-group">
                  <input
                    :type="edictLLM.showKey ? 'text' : 'password'"
                    v-model="edictLLM.apiKey"
                    class="config-input"
                    :placeholder="edictLLM.apiKey ? maskApiKey(edictLLM.apiKey) : '输入你的 API Key（留空使用服务器默认）'"
                  />
                  <button class="key-toggle" @click="edictLLM.showKey = !edictLLM.showKey" :title="edictLLM.showKey ? '隐藏' : '显示'">
                    {{ edictLLM.showKey ? '🙈' : '👁' }}
                  </button>
                </div>
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
                <button v-audio class="toggle-btn" :class="{ on: edictLLM.useAI }" @click="edictLLM.useAI = !edictLLM.useAI; debouncedSaveEdictConfig()">
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
                <input type="range" min="0" max="100" v-model.number="audioSettings.masterVolume" class="config-range" @change="onAudioChange" />
                <span class="range-val">{{ audioSettings.masterVolume }}%</span>
              </div>
              <div class="config-row">
                <label>背景音乐</label>
                <input type="range" min="0" max="100" v-model.number="audioSettings.bgmVolume" class="config-range" @change="onAudioChange" />
                <span class="range-val">{{ audioSettings.bgmVolume }}%</span>
              </div>
              <div class="config-row">
                <label>音效</label>
                <input type="range" min="0" max="100" v-model.number="audioSettings.sfxVolume" class="config-range" @change="onAudioChange" />
                <span class="range-val">{{ audioSettings.sfxVolume }}%</span>
              </div>
              <div class="config-row">
                <label>语音</label>
                <input type="range" min="0" max="100" v-model.number="audioSettings.voiceVolume" class="config-range" @change="onAudioChange" />
                <span class="range-val">{{ audioSettings.voiceVolume }}%</span>
              </div>
            </div>
            <div class="config-card">
              <h4>开关设置</h4>
              <div class="config-row toggle-row">
                <label>背景音乐</label>
                <button v-audio class="toggle-btn" :class="{ on: audioSettings.bgmOn }" @click="audioSettings.bgmOn = !audioSettings.bgmOn; onAudioChange()">
                  {{ audioSettings.bgmOn ? '开' : '关' }}
                </button>
              </div>
              <div class="config-row toggle-row">
                <label>全局静音</label>
                <button v-audio class="toggle-btn" :class="{ on: audioSettings.muted }" @click="audioSettings.muted = !audioSettings.muted; onAudioChange()">
                  {{ audioSettings.muted ? '静音' : '正常' }}
                </button>
              </div>
            </div>

            <!-- TTS 语音提供商 -->
            <div class="config-card">
              <h4>🎙 语音合成引擎</h4>
              <p class="config-desc">选择角色配音的 TTS 提供商。ElevenLabs 音质更佳，需自备 API Key。</p>
              <div class="provider-row">
                <button
                  class="provider-btn"
                  :class="{ active: ttsProvider === 'edge' }"
                  @click="ttsProvider = 'edge'; persistTtsSettings()"
                >
                  <span class="prov-name">Edge TTS</span>
                  <span class="prov-speed">免费</span>
                </button>
                <button
                  class="provider-btn"
                  :class="{ active: ttsProvider === 'elevenlabs' }"
                  @click="ttsProvider = 'elevenlabs'; persistTtsSettings()"
                >
                  <span class="prov-name">ElevenLabs</span>
                  <span class="prov-speed">高品质</span>
                </button>
              </div>
            </div>

            <!-- ElevenLabs API Key 配置 -->
            <div class="config-card" v-if="ttsProvider === 'elevenlabs'">
              <h4>🔑 ElevenLabs API Key</h4>
              <p class="config-desc">
                前往 <a href="https://elevenlabs.io/app/settings/api-keys" target="_blank" class="link">elevenlabs.io → API Keys</a> 创建 Key 后填入。
                免费账户每月 10,000 字符额度。
              </p>
              <div class="config-row">
                <label>API Key</label>
                <div class="key-input-group">
                  <input
                    :type="elevenKeyVisible ? 'text' : 'password'"
                    v-model="elevenLabsKey"
                    class="config-input"
                    :placeholder="elevenLabsKey ? maskApiKey(elevenLabsKey) : '输入 ElevenLabs API Key（sk_...）'"
                  />
                  <button class="key-toggle" @click="elevenKeyVisible = !elevenKeyVisible" :title="elevenKeyVisible ? '隐藏' : '显示'">
                    {{ elevenKeyVisible ? '🙈' : '👁' }}
                  </button>
                </div>
              </div>
              <div class="config-actions">
                <button class="cfg-btn cfg-save" @click="saveElevenLabsKey">保存 Key</button>
                <button class="cfg-btn cfg-reset" @click="clearElevenLabsKey">清除</button>
              </div>
              <p class="status-msg" v-if="ttsStatusMsg">{{ ttsStatusMsg }}</p>
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
import { audioManager } from '@/utils/audioManager'

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
  { id: 'advisor', name: '主谋臣模型', desc: '用于君主对话、谋臣献策、廷议辩论', apiBase: 'https://copilot.tencent.com/v2', modelName: 'deepseek-v3', temperature: 0.7, maxTokens: 4096, apiKey: '', showKey: false },
  { id: 'law', name: '战略推演模型', desc: '用于年度战略推演、合纵连横判定', apiBase: 'https://copilot.tencent.com/v2', modelName: 'deepseek-v3', temperature: 0.6, maxTokens: 8192, apiKey: '', showKey: false },
  { id: 'enemy', name: '敌方AI模型', desc: '用于灾害判定、战斗结算、贪腐检查', apiBase: 'https://copilot.tencent.com/v2', modelName: 'deepseek-v3', temperature: 0.65, maxTokens: 2048, apiKey: '', showKey: false },
])

// ========== 预设方案 ==========
const activePreset = ref('standard')
const speedPresets = [
  { id: 'fast', icon: '⚡', name: '极速模式', speed: '~5-15秒/操作', desc: '回合推进最快，适合快速游玩。模型输出较短，AI叙事可能稍简。' },
  { id: 'standard', icon: '⚖', name: '标准模式', speed: '~10-35秒/操作', desc: '平衡速度与质量，推荐日常使用。' },
  { id: 'quality', icon: '🎨', name: '沉浸模式', speed: '~20-60秒/操作', desc: '最大化 AI 叙事质量和策略深度，回合最慢但体验最佳。' },
]

// ========== API 提供商 ==========
const activeProvider = ref('codebuddy')
const providers = [
  { id: 'codebuddy', name: 'CodeBuddy 代理', speed: '中等', apiBase: 'https://copilot.tencent.com/v2' },
  { id: 'deepseek', name: 'DeepSeek 官方', speed: '较快', apiBase: 'https://api.deepseek.com/v1' },
  { id: 'openai', name: 'OpenAI 官方', speed: '较快', apiBase: 'https://api.openai.com/v1' },
]

// 每个提供商的默认模型名（用于切换时回退）
const PROVIDER_DEFAULT_MODEL: Record<string, string> = {
  codebuddy: 'deepseek-v3',
  deepseek: 'deepseek-chat',
  openai: 'gpt-4o-mini',
}

// ========== 模型选项（按提供商+分组分级） ==========
const MODEL_CATALOG: Record<string, Array<{ value: string; label: string; speed: string }>> = {
  codebuddy: [
    { value: 'deepseek-v3', label: 'DeepSeek-V3 — 标准', speed: '中' },
    { value: 'deepseek-v3-flash', label: 'DeepSeek-V3 Flash — 快速', speed: '快' },
    { value: 'deepseek-v3.2', label: 'DeepSeek-V3.2 — 新版', speed: '中' },
    { value: 'deepseek-v4-flash', label: 'DeepSeek-V4 Flash — 最新', speed: '快' },
    { value: 'hunyuan-turbo', label: '混元 Turbo — 腾讯快速', speed: '快' },
    { value: 'hunyuan-2.0-instruct', label: '混元 2.0 — 腾讯增强', speed: '中' },
    { value: 'hunyuan-2.0-instruct-20251111', label: '混元 2.0 Instruct — 长版', speed: '中' },
    { value: 'glm-5', label: 'GLM-5 — 智谱', speed: '中' },
    { value: 'kimi-k2.6', label: 'Kimi K2.6 — 月之暗面', speed: '中' },
  ],
  deepseek: [
    { value: 'deepseek-chat', label: 'DeepSeek-Chat (V3) — 推荐', speed: '快' },
    { value: 'deepseek-reasoner', label: 'DeepSeek-R1 — 深度推理', speed: '慢' },
    { value: 'deepseek-v3', label: 'DeepSeek-V3 — 经典', speed: '中' },
  ],
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o — 多模态', speed: '中' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini — 快速', speed: '快' },
    { value: 'gpt-4.1', label: 'GPT-4.1 — 强力', speed: '慢' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini — 平衡', speed: '中' },
    { value: 'o4-mini', label: 'o4-mini — 推理', speed: '中' },
  ],
}

// 各模型组在不同预设下的推荐参数
const PRESET_CONFIGS: Record<string, Record<string, { modelName: string; maxTokens: number; temperature: number }>> = {
  fast: {
    advisor: { modelName: 'deepseek-chat', maxTokens: 2048, temperature: 0.5 },
    law: { modelName: 'deepseek-chat', maxTokens: 2048, temperature: 0.4 },
    enemy: { modelName: 'deepseek-chat', maxTokens: 1024, temperature: 0.5 },
  },
  standard: {
    advisor: { modelName: 'deepseek-v3', maxTokens: 4096, temperature: 0.7 },
    law: { modelName: 'deepseek-v3', maxTokens: 4096, temperature: 0.6 },
    enemy: { modelName: 'deepseek-v3', maxTokens: 2048, temperature: 0.65 },
  },
  quality: {
    advisor: { modelName: 'deepseek-v3', maxTokens: 8192, temperature: 0.8 },
    law: { modelName: 'deepseek-v3', maxTokens: 8192, temperature: 0.7 },
    enemy: { modelName: 'deepseek-v3', maxTokens: 4096, temperature: 0.7 },
  },
}

function getModelOptions(modelId: string) {
  const providerModels = MODEL_CATALOG[activeProvider.value] || MODEL_CATALOG['codebuddy']
  // 合并当前模型的实际值，确保已选模型始终在列表中
  const current = modelId === 'edict' ? edictLLM : aiModels.find(m => m.id === modelId)
  const currentName = modelId === 'edict' ? edictLLM.modelName : (current as any)?.modelName
  const hasCurrent = providerModels.some(o => o.value === currentName)
  if (currentName && !hasCurrent) {
    return [...providerModels, { value: currentName, label: `${currentName} (当前)`, speed: '?' }]
  }
  return providerModels
}

function onModelSelect(model: typeof aiModels[number]) {
  // select 变更时不做额外处理，v-model 已绑定
}

function applyPreset(presetId: string) {
  activePreset.value = presetId
  const configs = PRESET_CONFIGS[presetId]
  if (!configs) return
  for (const model of aiModels) {
    const cfg = configs[model.id]
    if (cfg) {
      model.modelName = cfg.modelName
      model.maxTokens = cfg.maxTokens
      model.temperature = cfg.temperature
    }
  }
  // 极速模式默认推荐 DeepSeek 官方 API
  if (presetId === 'fast' && activeProvider.value === 'codebuddy') {
    switchProvider('deepseek')
  }
}

function switchProvider(providerId: string) {
  activeProvider.value = providerId
  const prov = providers.find(p => p.id === providerId)
  if (!prov) return
  const defaultModel = PROVIDER_DEFAULT_MODEL[providerId] || 'deepseek-v3'
  for (const model of aiModels) {
    model.apiBase = prov.apiBase
    // 如果当前模型不在新提供商的目录里，切换到默认模型
    const catalogModels = (MODEL_CATALOG[providerId] || []).map(o => o.value)
    if (!catalogModels.includes(model.modelName)) {
      model.modelName = defaultModel
    }
  }
}

const audioSettings = reactive({
  muted: false,
  masterVolume: 70,
  bgmVolume: 50,
  sfxVolume: 60,
  voiceVolume: 80,
  bgmOn: true,
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
  apiKey: '',
  showKey: false,
})
const edictStatusMsg = ref('')

// ========== TTS 语音提供商 & ElevenLabs Key ==========
const ttsProvider = ref<'edge' | 'elevenlabs'>('edge')
const elevenLabsKey = ref('')
const elevenKeyVisible = ref(false)
const ttsStatusMsg = ref('')

function loadTtsSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem('yuanmo_tts_settings') || '{}')
    ttsProvider.value = saved.provider || 'edge'
    // 从统一 Key 存储读取 elevenlabs key
    const savedKeys = JSON.parse(localStorage.getItem('yuanmo_llm_api_keys') || '{}')
    elevenLabsKey.value = savedKeys?.elevenlabs || ''
  } catch { /* ignore */ }
}

function persistTtsSettings() {
  try {
    localStorage.setItem('yuanmo_tts_settings', JSON.stringify({ provider: ttsProvider.value }))
  } catch { /* ignore */ }
}

function saveElevenLabsKey() {
  if (!elevenLabsKey.value.trim()) {
    ttsStatusMsg.value = '✗ API Key 不能为空'
    return
  }
  if (!elevenLabsKey.value.startsWith('sk_')) {
    ttsStatusMsg.value = '⚠ Key 格式似乎不正确（应以 sk_ 开头），但仍会保存'
  }
  try {
    const savedKeys = JSON.parse(localStorage.getItem('yuanmo_llm_api_keys') || '{}')
    savedKeys['elevenlabs'] = elevenLabsKey.value.trim()
    localStorage.setItem('yuanmo_llm_api_keys', JSON.stringify(savedKeys))
    persistTtsSettings()
    ttsStatusMsg.value = '✓ ElevenLabs API Key 已保存（仅存本地浏览器，不会上传服务器）'
  } catch {
    ttsStatusMsg.value = '✗ 保存失败，请检查浏览器存储空间'
  }
}

function clearElevenLabsKey() {
  elevenLabsKey.value = ''
  try {
    const savedKeys = JSON.parse(localStorage.getItem('yuanmo_llm_api_keys') || '{}')
    delete savedKeys['elevenlabs']
    localStorage.setItem('yuanmo_llm_api_keys', JSON.stringify(savedKeys))
    ttsStatusMsg.value = '✓ API Key 已清除'
  } catch { /* ignore */ }
}

// ========== AI画师 API Key ==========
const painterApiKey = ref('')
const painterApiBase = ref('')
const painterKeyVisible = ref(false)
const painterStatusMsg = ref('')

function loadPainterConfig() {
  try {
    const savedKeys = JSON.parse(localStorage.getItem('yuanmo_llm_api_keys') || '{}')
    painterApiKey.value = savedKeys?.painter || ''
    painterApiBase.value = savedKeys?.painterApiBase || ''
  } catch { /* ignore */ }
}

function savePainterConfig() {
  if (!painterApiKey.value.trim()) {
    painterStatusMsg.value = '⚠ 未输入 Key，将使用服务端默认密钥（可能不可用）'
  }
  try {
    const savedKeys = JSON.parse(localStorage.getItem('yuanmo_llm_api_keys') || '{}')
    savedKeys['painter'] = painterApiKey.value.trim()
    savedKeys['painterApiBase'] = painterApiBase.value.trim()
    localStorage.setItem('yuanmo_llm_api_keys', JSON.stringify(savedKeys))
    painterStatusMsg.value = painterApiKey.value.trim()
      ? '✓ 画师 API Key 已保存（仅存本地浏览器，不会上传服务器）'
      : '✓ 设置已保存，将使用服务端默认密钥'
  } catch {
    painterStatusMsg.value = '✗ 保存失败，请检查浏览器存储空间'
  }
}

function clearPainterConfig() {
  painterApiKey.value = ''
  painterApiBase.value = ''
  try {
    const savedKeys = JSON.parse(localStorage.getItem('yuanmo_llm_api_keys') || '{}')
    delete savedKeys['painter']
    delete savedKeys['painterApiBase']
    localStorage.setItem('yuanmo_llm_api_keys', JSON.stringify(savedKeys))
    painterStatusMsg.value = '✓ 画师配置已清除'
  } catch { /* ignore */ }
}

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

  // 加载本地存储的API Key（仅客户端，安全考虑不存服务端）
  const savedApiKeys = localStorage.getItem('yuanmo_llm_api_keys')
  if (savedApiKeys) {
    try {
      const keys = JSON.parse(savedApiKeys)
      for (const model of aiModels) {
        if (keys[model.id]) model.apiKey = keys[model.id]
      }
      if (keys['edict']) edictLLM.apiKey = keys['edict'] || ''
    } catch { console.warn('API Key加载失败') }
  }

  // 加载音频设置（统一存储，与 FloatPanels 兼容）
  loadAudioSettings()
  // 加载 TTS 提供商设置
  loadTtsSettings()

  // 加载 AI画师配置
  loadPainterConfig()

  // 加载画面设置（本地持久化）
  const savedDisplay = localStorage.getItem('yuanmo_display')
  if (savedDisplay) {
    try { Object.assign(displaySettings, JSON.parse(savedDisplay)) } catch { console.warn('画面设置解析失败') }
  }
  // 立即应用画面设置
  applyDisplaySettings()

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

// 持久化音频设置（统一使用 yuanmo_audio_panel，与 FloatPanels 兼容）
const AUDIO_STORAGE_KEY = 'yuanmo_audio_panel'

function loadAudioSettings() {
  try {
    // 兼容旧版 yuanmo_audio key
    const oldSaved = localStorage.getItem('yuanmo_audio')
    if (oldSaved) {
      const old = JSON.parse(oldSaved)
      Object.assign(audioSettings, {
        masterVolume: old.masterVolume ?? 70,
        muted: old.muted ?? false,
      })
      localStorage.removeItem('yuanmo_audio')  // 迁移后删除旧 key
    }
    const saved = localStorage.getItem(AUDIO_STORAGE_KEY)
    if (saved) {
      Object.assign(audioSettings, JSON.parse(saved))
    }
  } catch { /* ignore */ }
}

function saveAudioSettings() {
  localStorage.setItem(AUDIO_STORAGE_KEY, JSON.stringify({
    muted: audioSettings.muted,
    masterVolume: audioSettings.masterVolume,
    bgmVolume: audioSettings.bgmVolume,
    sfxVolume: audioSettings.sfxVolume,
    voiceVolume: audioSettings.voiceVolume,
    bgmOn: audioSettings.bgmOn,
  }))
}

function onAudioChange() {
  saveAudioSettings()
  // 立即应用到 audioManager
  audioManager.setMuted(audioSettings.muted)
  audioManager.setMasterVolume(audioSettings.masterVolume / 100)
  audioManager.setBgmVolume(audioSettings.bgmVolume / 100)
  audioManager.setSfxVolume(audioSettings.sfxVolume / 100)
  audioManager.setVoiceVolume(audioSettings.voiceVolume / 100)
  if (audioSettings.bgmOn) {
    audioManager.resumeBgm()
  } else {
    audioManager.pauseBgm()
  }
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
  applyDisplaySettings()
}

function applyDisplaySettings() {
  // 应用缩放
  const scale = parseFloat(displaySettings.scale) || 1
  const appEl = document.getElementById('app')
  if (appEl) {
    appEl.style.transform = scale !== 1 ? `scale(${scale})` : ''
    appEl.style.transformOrigin = 'top left'
  }
  // 应用暗色/浅色主题（与 main.css 中 .theme-light 类名对齐）
  if (displaySettings.darkMode) {
    document.documentElement.classList.add('dark-theme')
    document.documentElement.classList.remove('theme-light')
  } else {
    document.documentElement.classList.remove('dark-theme')
    document.documentElement.classList.add('theme-light')
  }
  // 应用动画开关
  if (!displaySettings.animationsOn) {
    document.documentElement.classList.add('no-anim')
  } else {
    document.documentElement.classList.remove('no-anim')
  }
  // 应用 tooltip 延迟
  document.documentElement.style.setProperty('--tooltip-delay', `${displaySettings.tooltipDelay}ms`)
}

// 持久化存档设置
function saveSaveSettings() {
  localStorage.setItem('yuanmo_save_settings', JSON.stringify({
    autoSaveInterval: saveSettings.autoSaveInterval,
  }))
  // 同步到后端
  import('@/services/api').then((api) => {
    api.default.post('/config/runtime', { auto_save_interval: saveSettings.autoSaveInterval }).catch(() => {})
  })
}

/** 模型角色中文名映射 */
const MODEL_LABELS: Record<string, string> = {
  advisor: '主谋臣',
  law: '战略推演',
  enemy: '敌方AI',
}

/** 脱敏显示 API Key（仅显示前4+后4字符） */
function maskApiKey(key: string): string {
  if (!key || key.length <= 8) return key ? '****' : ''
  return key.slice(0, 4) + '****' + key.slice(-4)
}

/** 持久化 API Key 到本地存储 */
function persistApiKeys() {
  let keys: Record<string, string> = {}
  // 先读取已有 keys（保留 elevenlabs 等非 LLM 的 key）
  try {
    keys = JSON.parse(localStorage.getItem('yuanmo_llm_api_keys') || '{}')
  } catch { /* ignore */ }
  for (const m of aiModels) {
    if (m.apiKey) keys[m.id] = m.apiKey
    else delete keys[m.id]
  }
  if (edictLLM.apiKey) keys['edict'] = edictLLM.apiKey
  else delete keys['edict']
  localStorage.setItem('yuanmo_llm_api_keys', JSON.stringify(keys))
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
    // 将用户在 UI 填写的完整模型配置一起发送给后端（模型名/api地址/apiKey/温度/maxTokens）
    const apiKeys: Record<string, string> = {}
    const modelConfigs: Record<string, any> = {}
    for (const m of aiModels) {
      if (m.apiKey) apiKeys[m.id] = m.apiKey
      modelConfigs[m.id] = {
        model_name: m.modelName,
        api_base: m.apiBase,
        temperature: m.temperature,
        max_tokens: m.maxTokens,
      }
    }
    const result = await testLLMConnection(undefined, apiKeys, modelConfigs)
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
  persistApiKeys()
  try {
    const payload: Record<string, any> = {}
    for (const m of aiModels) {
      payload[m.id] = {
        api_base: m.apiBase,
        model_name: m.modelName,
        temperature: m.temperature,
        max_tokens: m.maxTokens,
      }
      if (m.apiKey) {
        payload[m.id].api_key = m.apiKey
      }
    }
    await updateRuntimeConfig(payload)

    // 同时同步每个模型的 API Key 到后端（支持不同提供商使用不同 Key）
    for (const m of aiModels) {
      if (m.apiKey) {
        try {
          const { default: api } = await import('@/services/api')
          await api.post('/config/player-api-key', { api_key: m.apiKey, model_role: m.id })
        } catch { /* 非阻塞 */ }
      }
    }

    statusMsg.value = '✓ 配置已保存并热更新（无需重启）'
  } catch {
    console.warn('运行时配置保存失败，降级到本地存储')
    localStorage.setItem('yuanmo_ai_config', JSON.stringify(aiModels.map(m => ({
      id: m.id, apiBase: m.apiBase, modelName: m.modelName, temperature: m.temperature, maxTokens: m.maxTokens,
    }))))
    statusMsg.value = '✓ 配置已保存到本地（后端不可用，API Key 已本地存储）'
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

// debounce 工具：圣旨AI开关切换防抖（避免每次点击立即触发 API 保存）
let _edictDebounceTimer: ReturnType<typeof setTimeout> | null = null
function debouncedSaveEdictConfig() {
  if (_edictDebounceTimer) clearTimeout(_edictDebounceTimer)
  _edictDebounceTimer = setTimeout(() => saveEdictConfig(), 800)
}

// 圣旨AI配置保存/重置
async function saveEdictConfig() {
  edictStatusMsg.value = '正在保存...'
  persistApiKeys()
  try {
    const payload: Record<string, any> = {
      api_base: edictLLM.apiBase,
      model_name: edictLLM.modelName,
      temperature: edictLLM.temperature,
      max_tokens: edictLLM.maxTokens,
    }
    if (edictLLM.apiKey) payload.api_key = edictLLM.apiKey
    await updateEdictLLMConfig(payload)
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
    edictStatusMsg.value = '✓ 已保存到本地（后端不可用时降级，API Key 已本地存储）'
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
  router.push({ name: 'home' }).catch((err: any) => {
    // NavigationDuplicated：已在首页，正常忽略
    if (err?.name !== 'NavigationDuplicated') {
      console.error('返回首页导航失败:', err)
    }
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
  width: 90vw;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
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

/* ========== 预设方案卡片 ========== */
.preset-card {
  background: linear-gradient(135deg, rgba(139, 0, 0, 0.06) 0%, rgba(240, 228, 204, 0.6) 100%);
  border-color: rgba(139, 0, 0, 0.15);
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 8px;
}

.preset-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 6px;
  background: rgba(240, 228, 204, 0.4);
  border: 1px solid var(--text-dim);
  border-radius: 2px;
  cursor: pointer;
  font-family: "SimSun", serif;
  transition: all 0.2s;
  text-align: center;
}

.preset-btn:hover {
  background: rgba(139, 0, 0, 0.08);
  border-color: rgba(139, 0, 0, 0.3);
}

.preset-btn.active {
  background: rgba(139, 0, 0, 0.12);
  border-color: #8b0000;
  box-shadow: 0 0 8px rgba(139, 0, 0, 0.15);
}

.preset-icon {
  font-size: 20px;
}

.preset-name {
  font-size: 13px;
  font-weight: bold;
  color: var(--text-main);
  letter-spacing: 2px;
}

.preset-speed {
  font-size: 10px;
  color: #5b8c5a;
  font-family: "Courier New", monospace;
}

.preset-desc {
  font-size: 10px;
  color: var(--text-dim);
  line-height: 1.3;
  margin-top: 2px;
}

/* ========== 提供商卡片 ========== */
.provider-card {
  background: linear-gradient(135deg, rgba(26, 58, 92, 0.06) 0%, rgba(240, 228, 204, 0.6) 100%);
  border-color: rgba(74, 138, 176, 0.15);
}

.provider-row {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}

.provider-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 10px;
  background: rgba(240, 228, 204, 0.4);
  border: 1px solid var(--text-dim);
  border-radius: 2px;
  cursor: pointer;
  font-family: "SimSun", serif;
  transition: all 0.2s;
}

.provider-btn:hover {
  background: rgba(74, 138, 176, 0.08);
  border-color: rgba(74, 138, 176, 0.3);
}

.provider-btn.active {
  background: rgba(74, 138, 176, 0.12);
  border-color: #4a8ab0;
  box-shadow: 0 0 6px rgba(74, 138, 176, 0.15);
}

.prov-name {
  font-size: 13px;
  font-weight: bold;
  color: var(--text-main);
  letter-spacing: 1px;
}

.prov-speed {
  font-size: 10px;
  color: #5b8c5a;
  font-family: "Courier New", monospace;
}

/* ========== 模型选择器 ========== */
.model-select-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-select {
  padding: 4px 8px;
  background: var(--bg-card);
  border: 1px solid var(--text-dim);
  border-radius: 2px;
  font-family: "SimSun", serif;
  font-size: 12px;
  color: var(--text-main);
  cursor: pointer;
}

.model-select:focus {
  border-color: #8b0000;
  outline: none;
}

.model-input {
  margin-top: 0;
}

.token-hint {
  font-size: 10px;
  font-family: "Courier New", monospace;
  color: var(--text-dim);
  min-width: 32px;
  text-align: center;
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

.key-input-group {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 4px;
}

.key-input-group .config-input {
  flex: 1;
}

.key-toggle {
  width: 32px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--text-dim);
  border-radius: 2px;
  background: var(--bg-card);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.key-toggle:hover {
  background: var(--bg-hover);
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
