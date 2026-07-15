import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 统一全屏切换 composable
 * 自动处理 fullscreenchange 事件注册/注销
 * 用法:
 *   const { isFullscreen, toggleFullscreen, fullscreenIcon } = useFullscreen()
 * 模板:
 *   <button class="icon-btn" :title="isFullscreen ? '退出全屏' : '切换全屏'" @click="toggleFullscreen">
 *     <span class="icon">{{ fullscreenIcon }}</span>
 *   </button>
 */
export function useFullscreen() {
  const isFullscreen = ref(false)

  function syncState() {
    isFullscreen.value = !!document.fullscreenElement
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().then(syncState).catch(() => {})
    } else {
      document.exitFullscreen().then(syncState).catch(() => {})
    }
  }

  onMounted(() => {
    document.addEventListener('fullscreenchange', syncState)
    // 初始同步（处理页面刷新后仍在全屏的情况）
    syncState()
  })

  onUnmounted(() => {
    document.removeEventListener('fullscreenchange', syncState)
  })

  return { isFullscreen, toggleFullscreen }
}
