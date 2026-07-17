<template>
  <!-- V5.0 统一Toast组件 — 竹简便签风格，由 props + emit 驱动 -->
  <Transition name="toast" @after-leave="onLeaveEnd">
    <div
      v-if="visible"
      class="app-toast"
      :class="[`toast-${type}`, { 'toast-leaving': isLeaving }]"
      @mouseenter="pauseTimer"
      @mouseleave="resumeTimer"
    >
      <!-- 类型图标 -->
      <span class="toast-icon">
        <span v-if="type === 'success'" class="icon-jade">&#9670;</span>
        <span v-else-if="type === 'error'" class="icon-danger">&#10005;</span>
        <span v-else-if="type === 'warning'" class="icon-gold">&#9888;</span>
        <span v-else class="icon-info">&#9432;</span>
      </span>
      <!-- 消息内容 -->
      <span class="toast-text">{{ message }}</span>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  message: string
  type?: 'info' | 'success' | 'warning' | 'error'
  duration?: number
  visible: boolean
}>(), {
  type: 'info',
  duration: 3000,
})

const emit = defineEmits<{
  (e: 'close'): void
}>()

const isLeaving = ref(false)
let timerId: ReturnType<typeof setTimeout> | null = null
let remainingTime = props.duration

function startTimer() {
  if (timerId) clearTimeout(timerId)
  timerId = setTimeout(() => {
    isLeaving.value = true
  }, remainingTime)
}

function pauseTimer() {
  if (timerId) {
    clearTimeout(timerId)
    timerId = null
  }
}

function resumeTimer() {
  remainingTime = Math.max(remainingTime - 100, 500)
  startTimer()
}

function onLeaveEnd() {
  emit('close')
  isLeaving.value = false
}

watch(() => props.visible, (v) => {
  if (v) {
    isLeaving.value = false
    remainingTime = props.duration
    startTimer()
  }
}, { immediate: true })

onUnmounted(() => {
  if (timerId) clearTimeout(timerId)
})
</script>

<style scoped>
.app-toast {
  position: fixed;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 99999;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  background: var(--bg-panel);
  border: 1px solid var(--gold);
  border-radius: var(--radius-sm);
  color: var(--text-main);
  font-family: var(--font-annotation);
  font-size: var(--fs-sm);
  letter-spacing: 2px;
  box-shadow:
    0 4px 24px rgba(0, 0, 0, 0.55),
    inset 0 1px 0 rgba(184, 150, 62, 0.06);
  user-select: none;
  cursor: default;
  max-width: 80vw;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 类型变体 */
.toast-info {
  border-color: var(--gold-dim);
}
.toast-success {
  border-color: var(--jade);
}
.toast-warning {
  border-color: var(--color-zhang);
}
.toast-error {
  border-color: var(--danger);
}

/* 图标 */
.toast-icon {
  flex-shrink: 0;
  font-size: 14px;
  line-height: 1;
}
.icon-gold { color: var(--gold); }
.icon-danger { color: var(--danger); }
.icon-jade { color: var(--jade); }
.icon-info { color: var(--text-dim); }

.toast-text {
  color: var(--text-main);
}

/* Vue Transition */
.toast-enter-active {
  animation: toastSlideIn 0.35s var(--ease-squash);
}
.toast-leave-active {
  animation: toastSlideOut 0.2s var(--ease-in);
}

/* 手动触发离开动画（暂停恢复后） */
.toast-leaving {
  animation: toastSlideOut 0.2s var(--ease-in) forwards;
}

@keyframes toastSlideIn {
  0% {
    opacity: 0;
    transform: translateX(-50%) translateY(-20px) scale(0.9);
  }
  60% {
    opacity: 1;
    transform: translateX(-50%) translateY(4px) scale(1.03);
  }
  80% {
    transform: translateX(-50%) translateY(-2px) scale(0.99);
  }
  100% {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
}

@keyframes toastSlideOut {
  0% {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateX(-50%) translateY(-12px) scale(0.9);
  }
}
</style>
