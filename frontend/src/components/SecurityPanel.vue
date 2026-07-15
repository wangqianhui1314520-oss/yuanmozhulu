<template>
  <div class="security-panel" v-if="visible">
    <!-- 顶部标题栏 -->
    <div class="panel-header">
      <div class="header-left">
        <span class="header-icon">&#x56fe;</span>
        <span class="header-title">IOA 安全态势</span>
        <span :class="['risk-badge', riskLevel]">{{ riskLabel }}</span>
      </div>
      <div class="header-right">
        <span class="update-time" v-if="dashboard">更新于 {{ updateTime }}</span>
        <button class="btn-refresh" @click="refresh" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
        <button class="btn-close" @click="$emit('close')">&#x2715;</button>
      </div>
    </div>

    <!-- 加载中 -->
    <div class="loading" v-if="loading && !dashboard">
      <div class="spinner"></div>
      <span>正在采集安全态势数据...</span>
    </div>

    <!-- 仪表盘内容 -->
    <div class="panel-body" v-if="dashboard">
      <!-- 风险概览卡片 -->
      <section class="section">
        <h3 class="section-title">&#x25c9; 风险概览</h3>
        <div class="risk-cards">
          <div :class="['risk-card', riskCardClass(dashboard.ioa.risk_profile.overall_score)]">
            <div class="card-value">{{ dashboard.ioa.risk_profile.overall_score }}</div>
            <div class="card-label">综合风险分</div>
          </div>
          <div :class="['risk-card', riskCardClass(dashboard.ioa.risk_profile.behavior_risk)]">
            <div class="card-value">{{ dashboard.ioa.risk_profile.behavior_risk }}</div>
            <div class="card-label">行为风险</div>
          </div>
          <div :class="['risk-card', riskCardClass(dashboard.ioa.risk_profile.data_risk)]">
            <div class="card-value">{{ dashboard.ioa.risk_profile.data_risk }}</div>
            <div class="card-label">数据风险</div>
          </div>
          <div :class="['risk-card', riskCardClass(dashboard.ioa.risk_profile.ai_risk)]">
            <div class="card-value">{{ dashboard.ioa.risk_profile.ai_risk }}</div>
            <div class="card-label">AI风险</div>
          </div>
          <div :class="['risk-card', riskCardClass(dashboard.ioa.risk_profile.network_risk)]">
            <div class="card-value">{{ dashboard.ioa.risk_profile.network_risk }}</div>
            <div class="card-label">网络风险</div>
          </div>
        </div>
        <div class="risk-trend">
          趋势: <span :class="'trend-' + dashboard.ioa.risk_profile.trend">
            {{ trendLabel(dashboard.ioa.risk_profile.trend) }}
          </span>
          &nbsp;|&nbsp;
          活跃威胁: <span class="threat-count">{{ dashboard.ioa.risk_profile.active_threats }}</span>
          &nbsp;|&nbsp;
          24h事件: <span>{{ dashboard.ioa.risk_profile.events_24h }}</span>
        </div>
      </section>

      <!-- 实时指标 -->
      <section class="section">
        <h3 class="section-title">&#x25c9; 实时指标 (1h)</h3>
        <div class="metrics-grid">
          <div class="metric-item" v-for="m in metricsList" :key="m.key">
            <div :class="['metric-value', m.warn ? 'metric-warn' : '']">{{ m.value }}</div>
            <div class="metric-label">{{ m.label }}</div>
          </div>
        </div>
      </section>

      <!-- AI调用统计 -->
      <section class="section">
        <h3 class="section-title">&#x25c9; AI 调用统计</h3>
        <div class="ai-stats">
          <span>最近1小时: <strong>{{ dashboard.ioa.ai_call_stats.last_hour }}</strong></span>
          <span>累计: <strong>{{ dashboard.ioa.ai_call_stats.total }}</strong></span>
          <span>活跃会话: <strong>{{ dashboard.ioa.active_sessions }}</strong></span>
        </div>
      </section>

      <!-- 异常告警 -->
      <section class="section" v-if="dashboard.anomaly.top_alerts.length">
        <h3 class="section-title">&#x25c9; Top 异常告警</h3>
        <div class="alerts-list">
          <div
            v-for="(alert, i) in dashboard.anomaly.top_alerts"
            :key="i"
            :class="['alert-item', 'alert-' + alert.severity]"
          >
            <span class="alert-severity">{{ severityLabel(alert.severity) }}</span>
            <span class="alert-type">[{{ alert.type }}]</span>
            <span class="alert-source">{{ alert.source }}</span>
            <span class="alert-detail">{{ alert.detail }}</span>
          </div>
        </div>
      </section>

      <!-- 安全建议 -->
      <section class="section" v-if="dashboard.ioa.recommendations.length">
        <h3 class="section-title">&#x25c9; 安全建议</h3>
        <ul class="rec-list">
          <li v-for="(rec, i) in dashboard.ioa.recommendations" :key="i">{{ rec }}</li>
        </ul>
      </section>

      <!-- 数据脱敏统计 -->
      <section class="section">
        <h3 class="section-title">&#x25c9; 脱敏统计</h3>
        <div class="metrics-grid">
          <div class="metric-item">
            <div class="metric-value">{{ dashboard.anonymizer.total_masked }}</div>
            <div class="metric-label">已脱敏条数</div>
          </div>
          <div class="metric-item">
            <div class="metric-value">{{ dashboard.anonymizer.pii_detected }}</div>
            <div class="metric-label">PII检测</div>
          </div>
          <div class="metric-item">
            <div class="metric-value">{{ dashboard.anonymizer.keys_detected }}</div>
            <div class="metric-label">密钥检测</div>
          </div>
          <div class="metric-item">
            <div class="metric-value">{{ dashboard.anonymizer.enabled ? '运行中' : '已暂停' }}</div>
            <div class="metric-label">脱敏状态</div>
          </div>
        </div>
      </section>
    </div>

    <!-- 错误状态 -->
    <div class="error-state" v-if="error">
      <p>无法获取安全数据: {{ error }}</p>
      <button @click="refresh">重试</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { apiClient } from '@/services/api'

defineProps<{ visible: boolean }>()
defineEmits<{ close: [] }>()

const loading = ref(false)
const error = ref('')
const dashboard = ref<any>(null)
let _timer: ReturnType<typeof setInterval> | null = null

const updateTime = computed(() => {
  if (!dashboard.value) return ''
  const ts = dashboard.value.ioa.risk_profile.timestamp
    || dashboard.value.ioa.risk_profile.overall_score ? Date.now() : 0
  if (!ts) return ''
  return new Date(ts * 1000 || Date.now()).toLocaleTimeString('zh-CN')
})

const riskLevel = computed(() => {
  const score = dashboard.value?.ioa?.risk_profile?.overall_score ?? 0
  if (score >= 70) return 'critical'
  if (score >= 40) return 'high'
  if (score >= 15) return 'medium'
  return 'low'
})

const riskLabel = computed(() => {
  const map: Record<string, string> = { critical: '严重', high: '高危', medium: '中等', low: '正常' }
  return map[riskLevel.value] ?? '正常'
})

const metricsList = computed(() => {
  const d = dashboard.value
  if (!d) return []
  return [
    { key: 'anomaly', label: '异常行为', value: d.ioa.anomaly_count_1h, warn: d.ioa.anomaly_count_1h > 5 },
    { key: 'validation', label: '校验失败', value: d.ioa.validation_fail_count_1h, warn: d.ioa.validation_fail_count_1h > 3 },
    { key: 'suspicious', label: '可疑Agent', value: d.ioa.agent_suspicious_count_1h, warn: d.ioa.agent_suspicious_count_1h > 2 },
    { key: 'rate_limit', label: '限流命中', value: d.ioa.rate_limit_hits_1h, warn: d.ioa.rate_limit_hits_1h > 5 },
  ]
})

function riskCardClass(score: number): string {
  if (score >= 70) return 'critical'
  if (score >= 40) return 'high'
  if (score >= 15) return 'medium'
  return 'low'
}

function trendLabel(t: string): string {
  const map: Record<string, string> = { rising: '&#x2191; 上升', falling: '&#x2193; 下降', stable: '&#x2194; 稳定' }
  return map[t] ?? t
}

function severityLabel(s: string): string {
  const map: Record<string, string> = { critical: '严重', high: '高危', medium: '中危', low: '低危' }
  return map[s] ?? s
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await apiClient.get('/security/dashboard')
    if (data.code === 200) {
      dashboard.value = data.data
    } else {
      error.value = data.msg || '未知错误'
    }
  } catch (e: any) {
    error.value = e.message || '请求失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refresh()
  _timer = setInterval(refresh, 15000) // 15秒自动刷新
})

onUnmounted(() => {
  if (_timer) clearInterval(_timer)
})
</script>

<style scoped>
.security-panel {
  position: fixed;
  top: 10%;
  left: 50%;
  transform: translateX(-50%);
  width: 720px;
  max-height: 80vh;
  background: linear-gradient(135deg, #1a1614 0%, #24201c 100%);
  border: 1px solid #443F38;
  border-radius: 6px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.6);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  font-family: "STKaiti", "KaiTi", serif;
  color: #EAE3D6;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  border-bottom: 1px solid #443F38;
  background: rgba(0,0,0,0.3);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  font-size: 18px;
}

.header-title {
  font-size: 16px;
  letter-spacing: 2px;
  color: #B89B68;
}

.risk-badge {
  padding: 2px 10px;
  border-radius: 3px;
  font-size: 11px;
  letter-spacing: 1px;
}

.risk-badge.critical { background: #5C1A15; color: #E07060; border: 1px solid #9E2B25; }
.risk-badge.high { background: #5C3A15; color: #E0A060; border: 1px solid #9E6B25; }
.risk-badge.medium { background: #3A3A15; color: #C0C060; border: 1px solid #6B6B25; }
.risk-badge.low { background: #1A3A1A; color: #60C060; border: 1px solid #256B25; }

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.update-time {
  font-size: 11px;
  color: #8A8276;
}

.btn-refresh {
  padding: 4px 12px;
  border: 1px solid #443F38;
  background: transparent;
  color: #B89B68;
  cursor: pointer;
  border-radius: 3px;
  font-family: inherit;
  font-size: 12px;
}

.btn-refresh:hover { background: rgba(184,155,104,0.1); }
.btn-refresh:disabled { opacity: 0.5; cursor: default; }

.btn-close {
  border: none;
  background: none;
  color: #8A8276;
  cursor: pointer;
  font-size: 16px;
  padding: 4px;
}

.btn-close:hover { color: #E07060; }

/* 加载 */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 16px;
  color: #8A8276;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid #443F38;
  border-top-color: #B89B68;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* 主体 */
.panel-body {
  overflow-y: auto;
  padding: 16px 18px;
  flex: 1;
}

.section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 13px;
  color: #B89B68;
  margin: 0 0 10px 0;
  letter-spacing: 2px;
  border-bottom: 1px solid #332F2A;
  padding-bottom: 6px;
}

/* 风险卡片 */
.risk-cards {
  display: flex;
  gap: 10px;
}

.risk-card {
  flex: 1;
  text-align: center;
  padding: 10px 6px;
  border-radius: 4px;
  border: 1px solid;
}

.risk-card .card-value {
  font-size: 24px;
  font-weight: bold;
}

.risk-card .card-label {
  font-size: 11px;
  margin-top: 4px;
  opacity: 0.8;
}

.risk-card.low { border-color: #256B25; background: rgba(37,107,37,0.15); color: #60C060; }
.risk-card.medium { border-color: #6B6B25; background: rgba(107,107,37,0.15); color: #C0C060; }
.risk-card.high { border-color: #9E6B25; background: rgba(158,107,37,0.15); color: #E0A060; }
.risk-card.critical { border-color: #9E2B25; background: rgba(158,43,37,0.15); color: #E07060; }

.risk-trend {
  margin-top: 10px;
  font-size: 12px;
  color: #8A8276;
}

.trend-rising { color: #E07060; }
.trend-falling { color: #60C060; }
.trend-stable { color: #8A8276; }
.threat-count { color: #E07060; }

/* 指标网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.metric-item {
  text-align: center;
  padding: 10px;
  background: rgba(0,0,0,0.2);
  border-radius: 4px;
}

.metric-value {
  font-size: 22px;
  font-weight: bold;
  color: #EAE3D6;
}

.metric-value.metric-warn { color: #E07060; }

.metric-label {
  font-size: 11px;
  color: #8A8276;
  margin-top: 4px;
}

/* AI统计 */
.ai-stats {
  display: flex;
  gap: 24px;
  font-size: 13px;
  color: #8A8276;
}

.ai-stats strong { color: #EAE3D6; }

/* 告警列表 */
.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.alert-item {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 6px 10px;
  border-radius: 3px;
  font-size: 12px;
  border-left: 3px solid;
}

.alert-critical { background: rgba(158,43,37,0.15); border-color: #9E2B25; }
.alert-high { background: rgba(158,107,37,0.15); border-color: #9E6B25; }
.alert-medium { background: rgba(107,107,37,0.15); border-color: #6B6B25; }
.alert-low { background: rgba(37,107,37,0.1); border-color: #256B25; }

.alert-severity { color: #E07060; min-width: 32px; }
.alert-type { color: #B89B68; }
.alert-source { color: #8A8276; }
.alert-detail { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 建议列表 */
.rec-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.rec-list li {
  padding: 4px 0;
  font-size: 12px;
  color: #8A8276;
  padding-left: 16px;
  position: relative;
}

.rec-list li::before {
  content: '\25b8';
  position: absolute;
  left: 0;
  color: #B89B68;
}

/* 错误状态 */
.error-state {
  padding: 30px;
  text-align: center;
  color: #E07060;
}

.error-state button {
  margin-top: 10px;
  padding: 6px 16px;
  background: transparent;
  border: 1px solid #9E2B25;
  color: #E07060;
  cursor: pointer;
  border-radius: 3px;
  font-family: inherit;
}

/* 滚动条 */
.panel-body::-webkit-scrollbar { width: 4px; }
.panel-body::-webkit-scrollbar-track { background: transparent; }
.panel-body::-webkit-scrollbar-thumb { background: #443F38; border-radius: 2px; }
</style>
