<template>
  <!--
    回合过渡动画 · 水墨日历翻页
    回合推进完成后播放，展示新回合的时间信息
  -->
  <Teleport to="body">
    <Transition name="tt-fade">
      <div v-if="visible" class="turn-transition-overlay" @click="dismiss">
        <!-- 背景水墨洇染 -->
        <div class="tt-bg">
          <div class="tt-ink-wash"></div>
          <div class="tt-ink-rings">
            <div class="tt-ink-ring" v-for="i in 3" :key="i" :style="{ animationDelay: i * 0.15 + 's' }"></div>
          </div>
        </div>

        <!-- 主内容 -->
        <div class="tt-content">
          <!-- 旧历翻页 -->
          <div class="tt-calendar-flip" :class="{ 'flipped': phase >= 1 }">
            <div class="tt-old-page">
              <div class="tt-page-content">
                <div class="tt-old-round">第{{ prevRound }}回合</div>
                <div class="tt-old-date">至正{{ prevYear }}年·{{ prevMonth }}月</div>
                <div class="tt-old-season">{{ prevSeason }}季</div>
              </div>
            </div>
            <div class="tt-new-page">
              <!-- 水墨笔触书写 -->
              <div class="tt-brush-write" :class="{ 'writing': phase >= 1 }">
                <div class="tt-new-round">
                  <span v-for="(ch, i) in newRoundChars" :key="i"
                    class="tt-brush-char"
                    :style="{ animationDelay: 0.6 + i * 0.12 + 's' }"
                  >{{ ch }}</span>
                </div>
                <div class="tt-new-date">
                  <span class="tt-date-label">至正</span>
                  <span class="tt-date-year">{{ newYear }}</span>
                  <span class="tt-date-label">年 ·</span>
                  <span class="tt-date-month">{{ newMonth }}</span>
                  <span class="tt-date-label">月</span>
                </div>
                <div class="tt-new-season">{{ newSeason }}季</div>
              </div>
            </div>
          </div>

          <!-- 玉玺盖印 -->
          <div class="tt-seal-stamp" :class="{ 'stamped': phase >= 2 }">
            <div class="tt-seal-box">
              <div class="tt-seal-inner">
                <div class="tt-seal-text">受命于天</div>
                <div class="tt-seal-sub">既寿永昌</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部提示 -->
        <div class="tt-hint" :class="{ 'visible': phase >= 2 }">
          点击任意处继续
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * TurnTransition — 回合推进过渡动画
 *
 * 三阶段动画：
 *   Phase 0 (0-0.6s): 背景墨染展开
 *   Phase 1 (0.6-1.8s): 日历翻页 + 笔触书写新年月
 *   Phase 2 (1.8s+):   玉玺盖印 + 点击继续提示
 */
import { ref, computed, watch, onUnmounted } from 'vue'

// ==================== Props & Emits ====================
const props = defineProps<{
  visible: boolean
  prevRound: number
  prevYear: number
  prevMonth: number
  prevSeason: string
  newRound: number
  newYear: number
  newMonth: number
  newSeason: string
}>()

const emit = defineEmits<{
  done: []
}>()

// ==================== 动画阶段 ====================
const phase = ref(0)
let phaseTimers: ReturnType<typeof setTimeout>[] = []
let canDismiss = false

const newRoundChars = computed(() => {
  const text = `第${props.newRound}回合`
  return text.split('')
})

// ==================== 播放动画 ====================
function playAnimation() {
  phase.value = 0
  canDismiss = false

  phaseTimers.push(setTimeout(() => { phase.value = 1 }, 600))
  phaseTimers.push(setTimeout(() => { phase.value = 2 }, 1800))
  phaseTimers.push(setTimeout(() => { canDismiss = true }, 2500))
}

function dismiss() {
  if (!canDismiss) return
  clearTimers()
  emit('done')
}

function clearTimers() {
  phaseTimers.forEach(clearTimeout)
  phaseTimers = []
}

watch(() => props.visible, (val) => {
  if (val) {
    playAnimation()
  } else {
    clearTimers()
    phase.value = 0
  }
})

onUnmounted(clearTimers)
</script>

<style scoped>
/* ===== 遮罩层 ===== */
.turn-transition-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

/* 进出场 */
.tt-fade-enter-active { transition: opacity 0.5s ease; }
.tt-fade-leave-active { transition: opacity 0.6s ease; }
.tt-fade-enter-from,
.tt-fade-leave-to { opacity: 0; }

/* ===== 背景层 ===== */
.tt-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

/* 水墨洇染渐变 */
.tt-ink-wash {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 50% 45%, rgba(24, 18, 12, 0.92) 0%, rgba(10, 8, 4, 0.98) 65%, rgba(4, 3, 2, 1) 100%);
  animation: ttWashExpand 0.8s cubic-bezier(0.22, 0.61, 0.36, 1) both;
}
@keyframes ttWashExpand {
  0% {
    background:
      radial-gradient(ellipse at 50% 45%, rgba(24, 18, 12, 0.3) 0%, rgba(10, 8, 4, 0.6) 65%, rgba(4, 3, 2, 0.9) 100%);
    transform: scale(0.95);
  }
  100% {
    transform: scale(1);
  }
}

/* 墨晕纹 */
.tt-ink-rings {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}
.tt-ink-ring {
  position: absolute;
  border: 1px solid rgba(184, 150, 62, 0.08);
  border-radius: 50%;
  animation: ttRingExpand 2s ease-out both;
}
.tt-ink-ring:nth-child(1) {
  width: 100px; height: 100px;
  margin: -50px 0 0 -50px;
}
.tt-ink-ring:nth-child(2) {
  width: 200px; height: 200px;
  margin: -100px 0 0 -100px;
}
.tt-ink-ring:nth-child(3) {
  width: 350px; height: 350px;
  margin: -175px 0 0 -175px;
  border-color: rgba(184, 150, 62, 0.04);
}
@keyframes ttRingExpand {
  0% { opacity: 0.6; transform: scale(0.3); }
  100% { opacity: 0; transform: scale(2.5); }
}

/* ===== 主内容 ===== */
.tt-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
}

/* ===== 日历翻页 ===== */
.tt-calendar-flip {
  position: relative;
  width: 480px;
  height: 240px;
  perspective: 1200px;
}

/* 旧页 */
.tt-old-page {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    rgba(40, 30, 18, 0.95) 0%,
    rgba(30, 22, 12, 0.98) 50%,
    rgba(20, 14, 8, 0.95) 100%
  );
  border: 2px solid rgba(184, 150, 62, 0.25);
  border-radius: 8px;
  transform-origin: left center;
  transition: transform 0.8s cubic-bezier(0.4, 0, 0.2, 1);
  backface-visibility: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    inset 0 0 80px rgba(0, 0, 0, 0.4),
    0 8px 48px rgba(0, 0, 0, 0.6);
}
.tt-calendar-flip.flipped .tt-old-page {
  transform: rotateY(-95deg);
  opacity: 0;
  transition: transform 0.7s cubic-bezier(0.55, 0, 1, 0.45), opacity 0.3s ease 0.4s;
}

.tt-page-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}
.tt-old-round {
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  font-size: 28px;
  color: #c8a84a;
  letter-spacing: 8px;
  text-shadow: 0 0 16px rgba(200, 168, 74, 0.3);
}
.tt-old-date {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 18px;
  color: #8a7040;
  letter-spacing: 4px;
}
.tt-old-season {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 22px;
  color: #6a5030;
  letter-spacing: 6px;
  margin-top: 4px;
}

/* 新页 */
.tt-new-page {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    rgba(35, 28, 18, 0.97) 0%,
    rgba(25, 19, 10, 0.99) 50%,
    rgba(18, 13, 7, 0.97) 100%
  );
  border: 2px solid rgba(184, 150, 62, 0.35);
  border-radius: 8px;
  box-shadow:
    inset 0 0 80px rgba(0, 0, 0, 0.4),
    0 8px 48px rgba(0, 0, 0, 0.6),
    0 0 60px rgba(184, 150, 62, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 水墨笔触书写 */
.tt-brush-write {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.tt-new-round {
  display: flex;
  gap: 0;
}
.tt-brush-char {
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  font-size: 30px;
  color: #d4c5a0;
  letter-spacing: 4px;
  text-shadow: 0 0 12px rgba(200, 168, 74, 0.35);
  opacity: 0;
  animation: ttBrushAppear 0.6s ease-out both;
}
@keyframes ttBrushAppear {
  0% {
    opacity: 0;
    transform: translateY(-8px);
    filter: blur(4px);
  }
  40% {
    opacity: 0.5;
    filter: blur(1px);
  }
  70% {
    opacity: 0.9;
    transform: translateY(0);
    filter: blur(0);
  }
  100% {
    opacity: 1;
  }
}

.tt-new-date {
  display: flex;
  align-items: baseline;
  gap: 2px;
  margin-top: 4px;
}
.tt-date-label {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 16px;
  color: #8a7040;
  letter-spacing: 2px;
}
.tt-date-year,
.tt-date-month {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 24px;
  color: #b8963e;
  letter-spacing: 3px;
}

.tt-new-season {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 22px;
  color: #c8a84a;
  letter-spacing: 8px;
  margin-top: 6px;
  text-shadow: 0 0 20px rgba(200, 168, 74, 0.4);
}

/* ===== 玉玺盖印 ===== */
.tt-seal-stamp {
  opacity: 0;
  transform: scale(0.3) rotate(-15deg);
  transition: all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.tt-seal-stamp.stamped {
  opacity: 1;
  transform: scale(1) rotate(0deg);
}

.tt-seal-box {
  width: 110px;
  height: 110px;
  border: 3px solid #8a2010;
  padding: 4px;
  transform: rotate(3deg);
  box-shadow: 0 4px 24px rgba(180, 30, 20, 0.3);
}
.tt-seal-inner {
  width: 100%;
  height: 100%;
  border: 1.5px solid #8a2010;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 4px;
}
.tt-seal-text {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 19px;
  color: #8a2010;
  letter-spacing: 3px;
  white-space: nowrap;
  line-height: 1.2;
}
.tt-seal-sub {
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 19px;
  color: #8a2010;
  letter-spacing: 3px;
  white-space: nowrap;
  line-height: 1.2;
}

/* ===== 底部提示 ===== */
.tt-hint {
  position: absolute;
  bottom: 40px;
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 14px;
  color: rgba(184, 150, 62, 0.4);
  letter-spacing: 4px;
  opacity: 0;
  transition: opacity 0.6s ease;
  animation: ttHintPulse 2s ease-in-out infinite;
  z-index: 1;
}
.tt-hint.visible {
  opacity: 1;
}
@keyframes ttHintPulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}

/* ===== 响应式 ===== */
@media (max-width: 600px) {
  .tt-calendar-flip {
    width: 320px;
    height: 200px;
  }
  .tt-old-round { font-size: 22px; }
  .tt-old-date { font-size: 15px; }
  .tt-old-season { font-size: 18px; }
  .tt-brush-char { font-size: 24px; }
  .tt-date-year, .tt-date-month { font-size: 20px; }
  .tt-new-season { font-size: 18px; }
  .tt-seal-box { width: 90px; height: 90px; }
  .tt-seal-text { font-size: 16px; letter-spacing: 2px; }
  .tt-seal-sub { font-size: 16px; letter-spacing: 2px; }
}
</style>
