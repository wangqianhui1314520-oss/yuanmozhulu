<template>
  <!-- 回合大事录 · 圣旨卷轴弹窗 -->
  <Teleport to="body">
    <div v-if="visible" class="turn-summary-overlay" @click.self="onClose">
      <div class="ts-scroll-wrapper artifact-edict">
        <!-- 卷轴顶部轴杆 -->
        <div class="ts-scroll-rod ts-scroll-rod-top">
          <div class="ts-rod-knob"></div>
          <div class="ts-rod-bar"></div>
          <div class="ts-rod-knob"></div>
        </div>

        <!-- 卷轴纸面 -->
        <div class="ts-scroll-paper animate-ts-unfurl">
          <!-- 抬头 -->
          <div class="ts-header">
            <div class="ts-header-deco">&#x269C;</div>
            <h3>天下大事录</h3>
            <div class="ts-header-deco">&#x269C;</div>
          </div>

          <div class="ts-subtitle">
            至正{{ year }}年·{{ month }}月·{{ seasonName }}季 · 第{{ round }}回合
          </div>

          <!-- 正文区域 -->
          <div class="ts-body" ref="bodyEl">
            <!-- 加载态 -->
            <div v-if="loading" class="ts-loading">
              <span class="ts-loading-icon">⏳</span>
              <span v-if="ministerName">臣{{ ministerName }}正在誊写邸报…</span>
              <span v-else>正在誊写邸报…</span>
            </div>

            <!-- 正文 -->
            <div v-else class="ts-narrative" v-html="renderedNarrative"></div>

            <!-- 臣子署名 -->
            <div v-if="!loading && ministerName" class="ts-signature">
              <span class="ts-sign-line">────────────────</span>
              <span>臣 <strong>{{ ministerName }}</strong></span>
              <span v-if="ministerTitle">{{ ministerTitle }}</span>
              <span>谨奏</span>
            </div>
          </div>

          <!-- 关闭按钮 -->
          <button class="ts-close-btn" @click="onClose" :disabled="loading && !canSkip">
            {{ loading && !hasContent ? '誊写中…' : '朕已知晓' }}
          </button>
        </div>

        <!-- 卷轴底部轴杆 -->
        <div class="ts-scroll-rod ts-scroll-rod-bot">
          <div class="ts-rod-knob"></div>
          <div class="ts-rod-bar"></div>
          <div class="ts-rod-knob"></div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * TurnSummaryScroll - 回合大事录圣旨弹窗
 *
 * 回合推进后弹出，以随机臣子身份用文言文汇报上回合天下大事。
 * 优先调用后端 AI 生成文言叙事，超时/失败后降级为模板文本。
 */
import { ref, computed, watch, onUnmounted } from 'vue'

// ==================== Props & Emits ====================
const props = defineProps<{
  visible: boolean
  year: number
  month: number
  round: number
  season: string
  /** 后端返回的叙事文本 */
  narrative: string
  /** 臣子姓名 */
  ministerName: string
  /** 臣子官职 */
  ministerTitle: string
  /** 是否正在加载 AI 叙事 */
  loading: boolean
  /** 是否 AI 生成 */
  aiGenerated: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

// ==================== 本地状态 ====================
const bodyEl = ref<HTMLElement | null>(null)
/** 超时后允许跳过加载 */
const canSkip = ref(false)
let skipTimer: ReturnType<typeof setTimeout> | null = null

// ==================== 计算属性 ====================
const seasonName = computed(() => {
  const s = String(props.season)
  return { '春': '春', '夏': '夏', '秋': '秋', '冬': '冬' }[s] || s
})

const hasContent = computed(() => !!props.narrative)

const renderedNarrative = computed(() => {
  const text = props.narrative || '本月天下太平，诸事如常。'
  // 保留换行，简单转义
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
})

// ==================== 超时允许强制关闭 ====================
watch(
  () => props.loading,
  (val) => {
    if (val) {
      canSkip.value = false
      skipTimer = setTimeout(() => {
        canSkip.value = true
      }, 8000) // 8 秒后允许跳过加载
    } else {
      canSkip.value = true
      if (skipTimer) {
        clearTimeout(skipTimer)
        skipTimer = null
      }
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  if (skipTimer) clearTimeout(skipTimer)
})

// ==================== 方法 ====================
function onClose() {
  if (props.loading && !canSkip.value) return
  emit('close')
}
</script>

<style scoped>
/* ===== 遮罩层 ===== */
.turn-summary-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.78);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: tsFadeIn 0.3s ease;
}
@keyframes tsFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ===== 卷轴包装层 ===== */
.ts-scroll-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 620px;
  width: 90%;
  max-height: 85vh;
}

/* ===== 卷轴轴杆 ===== */
.ts-scroll-rod {
  display: flex;
  align-items: center;
  gap: 0;
  width: 88%;
  height: 18px;
}
.ts-rod-knob {
  width: 18px;
  height: 18px;
  background: radial-gradient(circle at 40% 40%, #5a4830, #2a1e10);
  border-radius: 50%;
  border: 1px solid #3a2818;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
  flex-shrink: 0;
}
.ts-rod-bar {
  flex: 1;
  height: 8px;
  background: linear-gradient(180deg, #4a3820 0%, #3a2818 50%, #4a3820 100%);
  border-radius: 2px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
}

/* ===== 卷轴纸面 ===== */
.ts-scroll-paper {
  background:
    linear-gradient(90deg, rgba(50, 35, 15, 0.1) 0%, transparent 6%, transparent 94%, rgba(50, 35, 15, 0.1) 100%),
    linear-gradient(180deg, #2a2218 0%, #1f1a10 100%);
  border-left: 3px solid rgba(184, 150, 62, 0.25);
  border-right: 3px solid rgba(184, 150, 62, 0.25);
  width: 100%;
  max-height: 65vh;
  overflow-y: auto;
  box-shadow:
    inset 0 0 40px rgba(0, 0, 0, 0.3),
    0 8px 48px rgba(0, 0, 0, 0.7);
  position: relative;
  padding: 24px 28px 20px;
}
/* 纸面纹理 */
.ts-scroll-paper::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 28px,
    rgba(184, 150, 62, 0.012) 28px,
    rgba(184, 150, 62, 0.012) 29px
  );
  z-index: 0;
}
.ts-scroll-paper > * {
  position: relative;
  z-index: 1;
}

/* ===== 展开动画 ===== */
.animate-ts-unfurl {
  animation: tsUnfurl 0.7s cubic-bezier(0.22, 0.61, 0.36, 1) both;
  transform-origin: top center;
}
@keyframes tsUnfurl {
  0% {
    opacity: 0;
    transform: scaleY(0.1) translateY(-5%);
    max-height: 0;
  }
  20% {
    opacity: 1;
  }
  100% {
    transform: scaleY(1) translateY(0);
    max-height: 68vh;
  }
}

/* ===== 抬头 ===== */
.ts-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(184, 150, 62, 0.18);
  margin-bottom: 6px;
}
.ts-header-deco {
  font-size: 20px;
  color: #8a7040;
  flex-shrink: 0;
}
.ts-header h3 {
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  font-size: 20px;
  color: #c8a84a;
  letter-spacing: 10px;
  text-shadow: 0 0 20px rgba(200, 168, 74, 0.25);
  margin: 0;
  font-weight: normal;
}
.ts-subtitle {
  text-align: center;
  font-size: 13px;
  color: #8a7040;
  letter-spacing: 3px;
  padding: 6px 0 14px;
  border-bottom: 1px solid rgba(184, 150, 62, 0.1);
  margin-bottom: 14px;
}

/* ===== 正文区域 ===== */
.ts-body {
  min-height: 80px;
  max-height: 42vh;
  overflow-y: auto;
  padding: 0 4px;
  scrollbar-width: thin;
  scrollbar-color: rgba(184, 150, 62, 0.2) transparent;
}
.ts-body::-webkit-scrollbar {
  width: 4px;
}
.ts-body::-webkit-scrollbar-thumb {
  background: rgba(184, 150, 62, 0.2);
  border-radius: 2px;
}

/* 加载态 */
.ts-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 30px 0;
  font-size: 15px;
  color: #8a7040;
  font-family: 'STKaiti', 'KaiTi', serif;
}
.ts-loading-icon {
  display: inline-block;
  animation: inkGrindingSpin 2s linear infinite;
  font-size: 20px;
}
@keyframes inkGrindingSpin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 叙事正文 */
.ts-narrative {
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  font-size: 16px;
  line-height: 2;
  color: #d4c5a0;
  text-align: justify;
  letter-spacing: 1px;
  white-space: pre-wrap;
}

/* 臣子署名 */
.ts-signature {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  margin-top: 20px;
  padding-top: 12px;
  border-top: 1px solid rgba(184, 150, 62, 0.1);
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 15px;
  color: #b89b68;
  letter-spacing: 2px;
}
.ts-sign-line {
  color: rgba(184, 150, 62, 0.25);
  font-size: 10px;
  letter-spacing: 0;
  margin-bottom: 2px;
}
.ts-signature strong {
  color: #c8a84a;
  font-weight: normal;
  letter-spacing: 3px;
}

/* ===== 关闭按钮 ===== */
.ts-close-btn {
  display: block;
  margin: 18px auto 0;
  padding: 10px 40px;
  background: linear-gradient(180deg, rgba(184, 150, 62, 0.12) 0%, rgba(100, 70, 30, 0.15) 100%);
  border: 1px solid rgba(184, 150, 62, 0.35);
  border-radius: 4px;
  color: #c8a84a;
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 16px;
  letter-spacing: 6px;
  cursor: pointer;
  transition: all 0.25s;
}
.ts-close-btn:hover:not(:disabled) {
  background: linear-gradient(180deg, rgba(200, 168, 74, 0.2) 0%, rgba(120, 90, 40, 0.2) 100%);
  border-color: rgba(200, 168, 74, 0.55);
  box-shadow: 0 0 16px rgba(200, 168, 74, 0.12);
}
.ts-close-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ===== 响应式 ===== */
@media (max-width: 600px) {
  .ts-scroll-wrapper {
    max-width: 95vw;
  }
  .ts-scroll-paper {
    padding: 16px 14px 14px;
    max-height: 58vh;
  }
  .ts-header h3 {
    font-size: 18px;
    letter-spacing: 6px;
  }
  .ts-narrative {
    font-size: 14px;
    line-height: 1.9;
  }
}
</style>
