/**
 * 教程状态管理 Store
 * 管理新手引导的步骤进度与UI状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getTutorialState,
  advanceTutorial,
  skipTutorial,
  resetTutorial,
} from '@/services/api'

export interface TutorialStepDetail {
  id: string
  title: string
  description: string
  target_selector: string
  position: 'top' | 'bottom' | 'left' | 'right' | 'center'
  required_action: string
  hint: string
  step_index: number
  total_steps: number
}

export type TutorialStatus = 'idle' | 'active' | 'completed' | 'skipped'

export const useTutorialStore = defineStore('tutorial', () => {
  // ===== 状态 =====
  const status = ref<TutorialStatus>('idle')
  const currentStep = ref<TutorialStepDetail | null>(null)
  const isVisible = ref(false)
  const highlightRect = ref<DOMRect | null>(null)
  const targetElement = ref<Element | null>(null)
  const factionId = ref('')

  // ===== 计算属性 =====
  const progress = computed(() => {
    if (!currentStep.value) return 0
    return Math.round(((currentStep.value.step_index + 1) / currentStep.value.total_steps) * 100)
  })

  const isActive = computed(() => status.value === 'active')

  // ===== 方法 =====

  /** 初始化教程（进入游戏后调用） */
  async function init(fid: string) {
    factionId.value = fid
    try {
      const data = await getTutorialState(fid)
      if (!data) {
        status.value = 'idle'
        return
      }

      const stateData = data.state
      if (stateData?.completed || stateData?.skipped) {
        status.value = stateData.skipped ? 'skipped' : 'completed'
        isVisible.value = false
        return
      }

      // current_step 已经在 /api/tutorial/state 响应中
      if (data.current_step) {
        currentStep.value = data.current_step as TutorialStepDetail
        status.value = 'active'
        isVisible.value = true
        // 延迟高亮（等DOM渲染）
        setTimeout(() => highlightTarget(), 400)
      } else {
        status.value = 'completed'
        isVisible.value = false
      }
    } catch {
      status.value = 'idle'
    }
  }

  /** 高亮目标元素 */
  function highlightTarget() {
    if (!currentStep.value?.target_selector) {
      highlightRect.value = null
      targetElement.value = null
      return
    }
    try {
      const el = document.querySelector(currentStep.value.target_selector)
      if (el) {
        targetElement.value = el
        highlightRect.value = el.getBoundingClientRect()
        // 滚动到可见区域
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    } catch {
      highlightRect.value = null
    }
  }

  /** 推进到下一步 */
  async function nextStep() {
    try {
      const data = await advanceTutorial(factionId.value)

      if (data?.state?.completed || data?.state?.skipped) {
        complete()
        return
      }

      if (data.current_step) {
        currentStep.value = data.current_step as TutorialStepDetail
        isVisible.value = true
        setTimeout(() => highlightTarget(), 300)
      } else {
        complete()
      }
    } catch {
      // 降级：本地推进
      if (currentStep.value) {
        const nextIdx = currentStep.value.step_index + 1
        if (nextIdx >= (currentStep.value.total_steps || 8)) {
          complete()
          return
        }
      }
    }
  }

  /** 跳过教程 */
  async function skip() {
    try {
      await skipTutorial(factionId.value)
    } catch { console.warn('[Tutorial] 跳过教程请求失败') }
    status.value = 'skipped'
    isVisible.value = false
    currentStep.value = null
    highlightRect.value = null
  }

  /** 完成教程 */
  function complete() {
    status.value = 'completed'
    isVisible.value = false
    currentStep.value = null
    highlightRect.value = null
    targetElement.value = null
  }

  /** 重置教程 */
  async function reset() {
    try {
      await resetTutorial(factionId.value)
    } catch { console.warn('[Tutorial] 重置教程请求失败') }
    status.value = 'idle'
    currentStep.value = null
    isVisible.value = false
    highlightRect.value = null
    targetElement.value = null
  }

  /** 关闭面板（不推进步骤） */
  function dismiss() {
    isVisible.value = false
  }

  function show() {
    isVisible.value = true
    setTimeout(() => highlightTarget(), 200)
  }

  return {
    status, currentStep, isVisible, highlightRect, targetElement, factionId,
    progress, isActive,
    init, nextStep, skip, complete, reset, dismiss, show, highlightTarget,
  }
})
