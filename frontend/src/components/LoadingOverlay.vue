<template>
  <!--
    全局加载覆盖层 · 元末逐鹿 3.0
    古风墨韵加载动画，用于回合推进、读档、初始化等需要等待的操作
  -->
  <Teleport to="body">
    <Transition name="loading-fade">
      <div v-if="visible" class="loading-overlay">
        <!-- 背景墨染 -->
        <div class="loading-bg"></div>

        <!-- 中央内容 -->
        <div class="loading-content">
          <!-- 旋转龙纹徽章 -->
          <div class="loading-seal">
            <div class="seal-ring"></div>
            <div class="seal-dragon">龍</div>
          </div>

          <!-- 加载消息 -->
          <div class="loading-title" v-if="title">{{ title }}</div>
          <div class="loading-message" v-if="message">{{ message }}</div>

          <!-- 进度条 -->
          <div class="loading-progress" v-if="showProgress">
            <div class="progress-track">
              <div
                class="progress-fill"
                :style="{ width: progress + '%' }"
              ></div>
            </div>
            <div class="progress-text">{{ progress }}%</div>
          </div>

          <!-- 墨点脉动指示器 -->
          <div class="ink-dots" v-if="!showProgress">
            <span class="ink-dot" v-for="i in 3" :key="i" :style="{ animationDelay: (i - 1) * 0.2 + 's' }"></span>
          </div>
        </div>

        <!-- 底部篆刻 -->
        <div class="loading-footer">元末逐鹿 · 天机推演</div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  title?: string
  message?: string
  progress?: number
  showProgress?: boolean
}>()

defineEmits<{
  cancel: []
}>()
</script>

<style scoped>
.loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}

/* 背景墨染 — V3.1 水墨洇开渐变 */
.loading-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 50% 45%, rgba(24, 18, 12, 0.88) 0%, rgba(14, 10, 6, 0.96) 60%, rgba(8, 6, 4, 0.99) 100%);
  backdrop-filter: blur(8px);
}
/* V3.1 墨滴晕染层 — 缓慢呼吸，模拟砚台水墨 */
.loading-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 50% 40%, rgba(184, 150, 62, 0.04) 0%, transparent 50%);
  animation: inkWash 4s ease-in-out infinite;
}
@keyframes inkWash {
  0%, 100% { opacity: 0.3; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.05); }
}

/* 中央内容 */
.loading-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

/* 龙纹徽章旋转 */
.loading-seal {
  position: relative;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.seal-ring {
  position: absolute;
  width: 72px;
  height: 72px;
  border: 2px solid rgba(184, 150, 62, 0.3);
  border-top-color: rgba(184, 150, 62, 0.9);
  border-right-color: rgba(184, 150, 62, 0.6);
  border-radius: 50%;
  animation: seal-spin 2s linear infinite;
}
/* V3.1 外圈光环 — 反向旋转，增加层次 */
.seal-ring::before {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 1px solid rgba(184, 150, 62, 0.12);
  border-bottom-color: rgba(184, 150, 62, 0.3);
  animation: seal-spin-reverse 4s linear infinite;
}

@keyframes seal-spin {
  to { transform: rotate(360deg); }
}
@keyframes seal-spin-reverse {
  to { transform: rotate(-360deg); }
}

.seal-dragon {
  font-size: 32px;
  color: #b8963e;
  font-family: 'STKaiti', 'KaiTi', serif;
  text-shadow: 0 0 12px rgba(184, 150, 62, 0.4);
  animation: sealGlow 2s ease-in-out infinite;
}
@keyframes sealGlow {
  0%, 100% { text-shadow: 0 0 8px rgba(184, 150, 62, 0.3); }
  50% { text-shadow: 0 0 20px rgba(184, 150, 62, 0.6); }
}

/* 标题 */
.loading-title {
  font-size: 20px;
  color: #eae3d6;
  font-family: 'STKaiti', 'KaiTi', serif;
  letter-spacing: 6px;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
}

.loading-message {
  font-size: 13px;
  color: #a09880;
  font-family: 'STKaiti', 'KaiTi', serif;
  letter-spacing: 2px;
  max-width: 320px;
  text-align: center;
  line-height: 1.6;
}

/* 进度条 */
.loading-progress {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-track {
  width: 200px;
  height: 3px;
  background: rgba(184, 150, 62, 0.15);
  border-radius: 1.5px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #b8963e 0%, #d4b86a 50%, #b8963e 100%);
  background-size: 200% 100%;
  animation: progress-shimmer 2s linear infinite;
  border-radius: 1.5px;
  transition: width 0.5s ease;
}

@keyframes progress-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.progress-text {
  font-size: 12px;
  color: #b8963e;
  font-family: 'STKaiti', 'KaiTi', serif;
  min-width: 36px;
  text-align: right;
}

/* 墨点脉动 */
.ink-dots {
  display: flex;
  gap: 8px;
}

.ink-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #b8963e;
  animation: ink-pulse 1.2s ease-in-out infinite;
  opacity: 0.3;
}

@keyframes ink-pulse {
  0%, 100% { opacity: 0.3; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.5); }
}

/* 底部 */
.loading-footer {
  position: absolute;
  bottom: 30px;
  font-size: 11px;
  color: #4a4438;
  font-family: 'STKaiti', 'KaiTi', serif;
  letter-spacing: 4px;
  z-index: 1;
}

/* 进出场动画 */
.loading-fade-enter-active {
  transition: opacity 0.4s ease;
}
.loading-fade-leave-active {
  transition: opacity 0.5s ease;
}
.loading-fade-enter-from,
.loading-fade-leave-to {
  opacity: 0;
}
</style>
