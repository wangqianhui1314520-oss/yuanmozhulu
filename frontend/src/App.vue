<template>
  <div id="yuanmo-app" class="yuanmo-app">
    <!-- 全局错误降级提示 -->
    <div v-if="globalError" class="global-error-banner">
      <span class="error-icon">⚠</span>
      <span class="error-msg">{{ globalError }}</span>
      <button class="error-dismiss" @click="dismissError">✕</button>
    </div>
    <router-view v-slot="{ Component }">
      <transition name="page-fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const globalError = ref('')
const errorTimer = ref<ReturnType<typeof setTimeout> | null>(null)

function dismissError() {
  globalError.value = ''
  if (errorTimer.value) { clearTimeout(errorTimer.value); errorTimer.value = null }
}

function handleGlobalError(e: ErrorEvent) {
  console.error('[YuanMo] Global error:', e.error || e)
  const msg = e.error?.message || e.message || '未知错误'
  // 显示更详细的错误信息帮助调试
  if (msg.includes('NetworkError') || msg.includes('fetch') || msg.includes('Failed to fetch')) {
    globalError.value = '网络连接异常，请检查后端服务是否运行。'
  } else if (msg.includes('timeout') || msg.includes('AbortError')) {
    globalError.value = '请求超时，AI服务可能繁忙，请稍后重试。'
  } else {
    globalError.value = `发生异常：${msg.slice(0, 200)}`
  }
  // 30秒后自动消失
  if (errorTimer.value) clearTimeout(errorTimer.value)
  errorTimer.value = setTimeout(() => { globalError.value = '' }, 30000)
}

function handleUnhandledRejection(e: PromiseRejectionEvent) {
  console.error('[YuanMo] Unhandled rejection:', e.reason)
  const msg = String(e.reason || '')
  if (msg.includes('NetworkError') || msg.includes('fetch')) {
    globalError.value = '网络连接异常，请检查后端服务是否运行。'
  } else if (msg.includes('timeout')) {
    globalError.value = '请求超时，请稍后重试。'
  }
  if (errorTimer.value) clearTimeout(errorTimer.value)
  errorTimer.value = setTimeout(() => { globalError.value = '' }, 10000)
}

onMounted(() => {
  window.addEventListener('error', handleGlobalError)
  window.addEventListener('unhandledrejection', handleUnhandledRejection)
})

onUnmounted(() => {
  window.removeEventListener('error', handleGlobalError)
  window.removeEventListener('unhandledrejection', handleUnhandledRejection)
  if (errorTimer.value) clearTimeout(errorTimer.value)
})
</script>

<style>
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.3s ease;
}
.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}

/* V4.1 全局错误邸报横幅 */
.global-error-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  background: linear-gradient(90deg, #8b2020, #c43a3a);
  color: #e0d5b8;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 13px;
  letter-spacing: 1px;
  font-family: "FangSong", "FangSong_GB2312", serif;
  animation: slideDown 0.3s ease-out;
  box-shadow: 0 2px 12px rgba(196, 58, 58, 0.3);
}

.global-error-banner .error-icon {
  font-size: 16px;
  color: #b8963e;
}

.global-error-banner .error-msg {
  flex: 1;
  text-align: center;
}

.global-error-banner .error-dismiss {
  background: none;
  border: 1px solid rgba(184, 150, 62, 0.4);
  color: #b8963e;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 2px;
  font-size: 14px;
  transition: all 0.2s;
}

.global-error-banner .error-dismiss:hover {
  background: rgba(184, 150, 62, 0.15);
}

@keyframes slideDown {
  from { transform: translateY(-100%); }
  to { transform: translateY(0); }
}
</style>
