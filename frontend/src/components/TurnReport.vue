<template>
  <!--
    上回合总结报告 · 奏折
    回合推进后弹出，以古风奏折样式展示上回合完整总结
  -->
  <Teleport to="body">
    <Transition name="tr-fade">
      <div v-if="visible" class="turn-report-overlay" @click.self="onClose">
        <div class="tr-memorial artifact-memorial">
          <!-- 奏折封皮 -->
          <div class="tr-cover">
            <div class="tr-cover-line tr-cover-line-top"></div>
            <div class="tr-cover-content">
              <div class="tr-cover-title">天下事状</div>
              <div class="tr-cover-subtitle">
                至正{{ year }}年·{{ month }}月·{{ seasonName }}季
              </div>
              <div class="tr-cover-round">第{{ round }}回合</div>
            </div>
            <div class="tr-cover-line tr-cover-line-bot"></div>
          </div>

          <!-- 奏折正文（可滚动） -->
          <div class="tr-body" ref="bodyEl">
            <!-- ===== 一、政务总览 ===== -->
            <section class="tr-section" v-if="factionSummary.length > 0">
              <div class="tr-section-header">
                <span class="tr-section-deco">◆</span>
                <h4>一、政务总览</h4>
                <span class="tr-section-deco">◆</span>
              </div>
              <div class="tr-faction-grid">
                <div
                  v-for="f in factionSummary"
                  :key="f.id"
                  class="tr-faction-card"
                  :class="{ 'is-player': f.isPlayer }"
                >
                  <div class="tr-faction-name" :style="{ color: f.color || '#c8a84a' }">
                    {{ f.name }}
                    <span v-if="f.isPlayer" class="tr-faction-tag">御</span>
                  </div>
                  <div class="tr-faction-stats">
                    <div class="tr-stat-row">
                      <span class="tr-stat-label">库银</span>
                      <span class="tr-stat-value gold">{{ fmtNum(f.treasury) }}</span>
                    </div>
                    <div class="tr-stat-row">
                      <span class="tr-stat-label">粮草</span>
                      <span class="tr-stat-value grain">{{ fmtNum(f.grain) }}</span>
                    </div>
                    <div class="tr-stat-row">
                      <span class="tr-stat-label">兵力</span>
                      <span class="tr-stat-value troops">{{ fmtNum(f.troops) }}</span>
                    </div>
                    <div class="tr-stat-row">
                      <span class="tr-stat-label">人口</span>
                      <span class="tr-stat-value pop">{{ fmtNum(f.population) }}</span>
                    </div>
                    <div class="tr-stat-row">
                      <span class="tr-stat-label">城池</span>
                      <span class="tr-stat-value">{{ f.tileCount }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <!-- ===== 二、军务简报 ===== -->
            <section class="tr-section" v-if="battleEvents.length > 0 || tileChanges.length > 0">
              <div class="tr-section-header">
                <span class="tr-section-deco">◆</span>
                <h4>二、军务简报</h4>
                <span class="tr-section-deco">◆</span>
              </div>

              <!-- 战事 -->
              <div v-if="battleEvents.length > 0" class="tr-subsection">
                <div class="tr-subtitle">—— 本回合战事 ——</div>
                <div v-for="(evt, i) in battleEvents" :key="i" class="tr-battle-item">
                  <div class="tr-battle-header">
                    <span class="tr-battle-icon">⚔</span>
                    <span class="tr-battle-title">{{ evt.title || '未名之战' }}</span>
                    <span class="tr-battle-severity" :class="evt.severity">
                      {{ severityLabel(evt.severity) }}
                    </span>
                  </div>
                  <div class="tr-battle-desc">{{ evt.description }}</div>
                </div>
              </div>

              <!-- 版图变更 -->
              <div v-if="tileChanges.length > 0" class="tr-subsection">
                <div class="tr-subtitle">—— 版图变更 ——</div>
                <div class="tr-tile-changes">
                  <div v-for="(tc, i) in tileChanges" :key="i" class="tr-tc-item">
                    <span class="tr-tc-tile">{{ getTileName(tc.tile_id) }}</span>
                    <span class="tr-tc-arrow">→</span>
                    <span class="tr-tc-faction" :style="{ color: getFactionColor(tc) }">
                      {{ getFactionName(tc) }}
                    </span>
                  </div>
                </div>
              </div>

              <div v-if="battleEvents.length === 0 && tileChanges.length === 0" class="tr-empty">
                本月无战事，诸镇相安。
              </div>
            </section>

            <!-- ===== 三、天下大事 ===== -->
            <section class="tr-section">
              <div class="tr-section-header">
                <span class="tr-section-deco">◆</span>
                <h4>三、天下大事</h4>
                <span class="tr-section-deco">◆</span>
              </div>

              <!-- 加载态 -->
              <div v-if="loadingNarrative" class="tr-loading">
                <span class="tr-loading-icon">⏳</span>
                <span>{{ narrativeMinister ? `臣${narrativeMinister}正在誊写邸报…` : '正在誊写邸报…' }}</span>
              </div>

              <!-- AI 叙事 -->
              <div v-else-if="narrative" class="tr-narrative" v-html="renderedNarrative"></div>

              <!-- 降级文本 -->
              <div v-else class="tr-narrative tr-narrative-fallback">
                启奏陛下。本月天下大事已录于起居注。臣谨奏。
              </div>

              <!-- 关键事件 -->
              <div v-if="otherEvents.length > 0" class="tr-subsection">
                <div class="tr-subtitle">—— 其余要事 ——</div>
                <div v-for="(evt, i) in otherEvents" :key="i" class="tr-event-item">
                  <span class="tr-event-dot">·</span>
                  <span class="tr-event-title">{{ evt.title || evt.description?.slice(0, 60) }}</span>
                  <span class="tr-event-type">{{ evt.event_type || evt.type }}</span>
                </div>
              </div>
            </section>

            <!-- 四、臣子署名 -->
            <div class="tr-signature">
              <span class="tr-sign-line">──────────────</span>
              <span v-if="narrativeMinister">
                臣 <strong>{{ narrativeMinister }}</strong>
                <span v-if="narrativeTitle"> {{ narrativeTitle }}</span>
              </span>
              <span v-else>臣 中书省</span>
              <span>谨奏</span>
            </div>
          </div>

          <!-- 关闭按钮 -->
          <button class="tr-close-btn" @click="onClose" :disabled="loadingNarrative && !canSkipNarrative">
            {{ loadingNarrative && !hasNarrative ? '誊写中…' : '朕已阅' }}
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * TurnReport — 上回合总结报告（奏折）
 *
 * 展示内容：
 *   一、政务总览 — 各势力库银/粮草/兵力/人口/城池
 *   二、军务简报 — 本回合战事 + 版图变更
 *   三、天下大事 — AI 生成的文言叙事 + 其余要事
 */
import { ref, computed, watch, onUnmounted } from 'vue'

// ==================== Props & Emits ====================
const props = defineProps<{
  visible: boolean
  round: number
  year: number
  month: number
  season: string
  /** 势力快照（各势力当前数据） */
  snapshot?: Record<string, {
    name: string
    treasury: number
    grain: number
    total_troops: number
    total_population: number
    tile_count: number
    is_alive: boolean
  }>
  /** 战事事件 */
  battleEvents?: any[]
  /** 版图变更 */
  tileChanges?: any[]
  /** 其余事件 */
  otherEvents?: any[]
  /** 势力配置（用于颜色、名称） */
  factionConfigs?: Record<string, { name: string; color: string }>
  /** 玩家势力ID */
  playerFactionId?: string
  /** AI 叙事文本 */
  narrative?: string
  /** 叙事臣子名 */
  narrativeMinister?: string
  /** 叙事臣子官职 */
  narrativeTitle?: string
  /** 叙事加载中 */
  loadingNarrative?: boolean
  /** 地块名称映射 */
  tileNames?: Record<string, string>
}>()

const emit = defineEmits<{
  close: []
}>()

// ==================== 本地状态 ====================
const bodyEl = ref<HTMLElement | null>(null)
const canSkipNarrative = ref(false)
let skipTimer: ReturnType<typeof setTimeout> | null = null

// ==================== 计算属性 ====================
const seasonName = computed(() => {
  const s = String(props.season)
  return { '春': '春', '夏': '夏', '秋': '秋', '冬': '冬' }[s] || s
})

const hasNarrative = computed(() => !!props.narrative)

/** 势力摘要（按 tile_count 降序排列） */
const factionSummary = computed(() => {
  if (!props.snapshot) return []
  return Object.entries(props.snapshot)
    .filter(([_, f]) => f.is_alive)
    .map(([id, f]) => ({
      id,
      name: f.name || id,
      treasury: f.treasury || 0,
      grain: f.grain || 0,
      troops: f.total_troops || 0,
      population: f.total_population || 0,
      tileCount: f.tile_count || 0,
      isPlayer: id === props.playerFactionId,
      color: props.factionConfigs?.[id]?.color || '#c8a84a',
    }))
    .sort((a, b) => b.tileCount - a.tileCount)
})

const renderedNarrative = computed(() => {
  const text = props.narrative || ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
})

// ==================== 超时跳过 ====================
watch(
  () => props.loadingNarrative,
  (val) => {
    if (val) {
      canSkipNarrative.value = false
      skipTimer = setTimeout(() => { canSkipNarrative.value = true }, 8000)
    } else {
      canSkipNarrative.value = true
      if (skipTimer) { clearTimeout(skipTimer); skipTimer = null }
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  if (skipTimer) clearTimeout(skipTimer)
})

// ==================== 辅助方法 ====================
function fmtNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(2) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + '千'
  return String(Math.round(n))
}

function severityLabel(s: string): string {
  const m: Record<string, string> = {
    major: '重大', minor: '一般', routine: '常事',
    high: '重大', medium: '一般', low: '轻微', critical: '危急',
  }
  return m[s] || s
}

function getTileName(tileId: string): string {
  return props.tileNames?.[tileId] || tileId
}

function getFactionName(tc: any): string {
  const fid = tc.new_faction_id || tc.faction_id || tc.to_faction_id || ''
  return props.factionConfigs?.[fid]?.name || fid
}

function getFactionColor(tc: any): string {
  const fid = tc.new_faction_id || tc.faction_id || tc.to_faction_id || ''
  return props.factionConfigs?.[fid]?.color || '#c8a84a'
}

// ==================== 关闭 ====================
function onClose() {
  if (props.loadingNarrative && !canSkipNarrative.value) return
  emit('close')
}
</script>

<style scoped>
/* ===== 遮罩 ===== */
.turn-report-overlay {
  position: fixed;
  inset: 0;
  z-index: 1001;
  background: rgba(0, 0, 0, 0.82);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.tr-fade-enter-active { transition: opacity 0.35s ease; }
.tr-fade-leave-active { transition: opacity 0.45s ease; }
.tr-fade-enter-from,
.tr-fade-leave-to { opacity: 0; }

/* ===== 奏折主体 ===== */
.tr-memorial {
  display: flex;
  flex-direction: column;
  max-width: 680px;
  width: 94%;
  max-height: 88vh;
  animation: trUnfurl 0.6s cubic-bezier(0.22, 0.61, 0.36, 1) both;
}
@keyframes trUnfurl {
  0% { opacity: 0; transform: scaleY(0.5) translateY(-3%); }
  100% { opacity: 1; transform: scaleY(1) translateY(0); }
}

/* ===== 封皮 ===== */
.tr-cover {
  background: linear-gradient(
    180deg,
    rgba(30, 20, 10, 0.95) 0%,
    rgba(22, 15, 8, 0.98) 100%
  );
  border: 2px solid rgba(184, 150, 62, 0.3);
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  padding: 20px 28px 16px;
}
.tr-cover-line {
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(184, 150, 62, 0.3) 20%,
    rgba(200, 168, 74, 0.5) 50%,
    rgba(184, 150, 62, 0.3) 80%,
    transparent 100%
  );
}
.tr-cover-line-top { margin-bottom: 14px; }
.tr-cover-line-bot { margin-top: 14px; }
.tr-cover-content {
  text-align: center;
}
.tr-cover-title {
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  font-size: 24px;
  color: #c8a84a;
  letter-spacing: 10px;
  text-shadow: 0 0 16px rgba(200, 168, 74, 0.2);
}
.tr-cover-subtitle {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 14px;
  color: #8a7040;
  letter-spacing: 4px;
  margin-top: 8px;
}
.tr-cover-round {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 12px;
  color: #5a4030;
  letter-spacing: 3px;
  margin-top: 4px;
}

/* ===== 正文 ===== */
.tr-body {
  background:
    linear-gradient(90deg, rgba(50, 35, 15, 0.08) 0%, transparent 8%, transparent 92%, rgba(50, 35, 15, 0.08) 100%),
    linear-gradient(180deg, #252018 0%, #1e1a10 100%);
  border-left: 3px solid rgba(184, 150, 62, 0.2);
  border-right: 3px solid rgba(184, 150, 62, 0.2);
  padding: 18px 28px 8px;
  max-height: 52vh;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(184, 150, 62, 0.15) transparent;
  position: relative;
}
.tr-body::-webkit-scrollbar { width: 4px; }
.tr-body::-webkit-scrollbar-thumb {
  background: rgba(184, 150, 62, 0.15);
  border-radius: 2px;
}
/* 纸纹 */
.tr-body::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 28px,
    rgba(184, 150, 62, 0.01) 28px,
    rgba(184, 150, 62, 0.01) 29px
  );
  z-index: 0;
}
.tr-body > * { position: relative; z-index: 1; }

/* ===== 段落 ===== */
.tr-section {
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(184, 150, 62, 0.08);
}
.tr-section:last-of-type { border-bottom: none; }

.tr-section-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 12px;
}
.tr-section-deco {
  font-size: 10px;
  color: rgba(184, 150, 62, 0.3);
}
.tr-section-header h4 {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 17px;
  color: #c8a84a;
  letter-spacing: 4px;
  margin: 0;
  font-weight: normal;
}

/* ===== 势力卡片 ===== */
.tr-faction-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
  padding: 0 4px;
}
.tr-faction-card {
  background: rgba(30, 20, 10, 0.5);
  border: 1px solid rgba(184, 150, 62, 0.1);
  border-radius: 4px;
  padding: 10px 12px;
}
.tr-faction-card.is-player {
  border-color: rgba(200, 168, 74, 0.3);
  background: rgba(40, 28, 14, 0.6);
  box-shadow: 0 0 12px rgba(200, 168, 74, 0.06);
}
.tr-faction-name {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 14px;
  letter-spacing: 2px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.tr-faction-tag {
  font-size: 10px;
  padding: 1px 5px;
  border: 1px solid currentColor;
  border-radius: 2px;
  opacity: 0.7;
}
.tr-faction-stats {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.tr-stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tr-stat-label {
  font-size: 11px;
  color: #6a5a40;
  letter-spacing: 1px;
}
.tr-stat-value {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 13px;
  color: #b8a080;
}
.tr-stat-value.gold { color: #d4b86a; }
.tr-stat-value.grain { color: #8ab86a; }
.tr-stat-value.troops { color: #d4786a; }
.tr-stat-value.pop { color: #8ab8d4; }

/* ===== 战事 ===== */
.tr-subsection { margin-top: 8px; }
.tr-subtitle {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 13px;
  color: #7a6040;
  letter-spacing: 3px;
  padding: 6px 0;
}
.tr-battle-item {
  background: rgba(180, 50, 40, 0.06);
  border-left: 2px solid rgba(200, 100, 80, 0.3);
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 0 4px 4px 0;
}
.tr-battle-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tr-battle-icon { color: #c86450; font-size: 14px; }
.tr-battle-title {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 14px;
  color: #d4c5a0;
  letter-spacing: 2px;
}
.tr-battle-severity {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 2px;
  margin-left: auto;
}
.tr-battle-severity.major,
.tr-battle-severity.high,
.tr-battle-severity.critical {
  background: rgba(200, 50, 30, 0.2);
  color: #d46450;
}
.tr-battle-severity.minor,
.tr-battle-severity.medium {
  background: rgba(180, 130, 50, 0.2);
  color: #c8a050;
}
.tr-battle-severity.routine,
.tr-battle-severity.low {
  background: rgba(100, 100, 100, 0.15);
  color: #8a8070;
}
.tr-battle-desc {
  font-size: 12px;
  color: #8a7860;
  margin-top: 4px;
  line-height: 1.6;
}
.tr-empty {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 13px;
  color: #5a4a30;
  text-align: center;
  padding: 8px 0;
}

/* 版图变更 */
.tr-tile-changes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tr-tc-item {
  font-size: 12px;
  color: #8a7860;
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(30, 20, 10, 0.4);
  padding: 3px 8px;
  border-radius: 3px;
  border: 1px solid rgba(184, 150, 62, 0.08);
}
.tr-tc-tile { color: #a09070; }
.tr-tc-arrow { color: #5a4a30; }
.tr-tc-faction {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 12px;
}

/* ===== 叙事 ===== */
.tr-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 20px 0;
  font-size: 14px;
  color: #8a7040;
  font-family: 'STKaiti', 'KaiTi', serif;
}
.tr-loading-icon {
  display: inline-block;
  animation: trSpin 2s linear infinite;
}
@keyframes trSpin {
  to { transform: rotate(360deg); }
}

.tr-narrative {
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  font-size: 15px;
  line-height: 2;
  color: #d4c5a0;
  text-align: justify;
  letter-spacing: 1px;
  white-space: pre-wrap;
}
.tr-narrative-fallback {
  color: #6a5a40;
  text-align: center;
  font-style: italic;
}

/* 其余要事 */
.tr-event-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 4px 0;
  font-size: 13px;
  color: #9a8a70;
}
.tr-event-dot { color: rgba(184, 150, 62, 0.4); flex-shrink: 0; }
.tr-event-title {
  flex: 1;
  line-height: 1.5;
}
.tr-event-type {
  font-size: 10px;
  color: #5a4a30;
  background: rgba(60, 40, 20, 0.3);
  padding: 1px 6px;
  border-radius: 2px;
  flex-shrink: 0;
}

/* ===== 署名 ===== */
.tr-signature {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(184, 150, 62, 0.1);
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 14px;
  color: #b89b68;
  letter-spacing: 2px;
}
.tr-sign-line {
  color: rgba(184, 150, 62, 0.2);
  font-size: 9px;
  letter-spacing: 0;
  margin-bottom: 2px;
}
.tr-signature strong {
  color: #c8a84a;
  font-weight: normal;
  letter-spacing: 3px;
}

/* ===== 关闭按钮 ===== */
.tr-close-btn {
  background: linear-gradient(
    180deg,
    rgba(30, 20, 10, 0.95) 0%,
    rgba(22, 15, 8, 0.98) 100%
  );
  border: 2px solid rgba(184, 150, 62, 0.3);
  border-top: none;
  border-radius: 0 0 6px 6px;
  padding: 12px 40px;
  color: #c8a84a;
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 16px;
  letter-spacing: 6px;
  cursor: pointer;
  transition: all 0.25s;
}
.tr-close-btn:hover:not(:disabled) {
  background: linear-gradient(180deg, rgba(40, 28, 14, 0.95) 0%, rgba(30, 20, 10, 0.98) 100%);
  border-color: rgba(200, 168, 74, 0.5);
  box-shadow: 0 0 20px rgba(200, 168, 74, 0.1);
}
.tr-close-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ===== 响应式 ===== */
@media (max-width: 600px) {
  .tr-memorial { max-width: 98vw; max-height: 92vh; }
  .tr-cover { padding: 14px 16px 12px; }
  .tr-cover-title { font-size: 20px; letter-spacing: 6px; }
  .tr-body { padding: 12px 14px 6px; max-height: 48vh; }
  .tr-faction-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
  .tr-narrative { font-size: 14px; line-height: 1.9; }
  .tr-close-btn { font-size: 14px; letter-spacing: 4px; padding: 10px 30px; }
}
</style>
