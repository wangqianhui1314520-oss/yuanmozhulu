<template>
  <!--
    PanelManager - 面板显示/隐藏管理器
    替代 FloatPanels.vue 的渐进式重构入口
    
    用法：
    - 新面板直接在此注册
    - 旧面板暂时引用 FloatPanels.vue 保持兼容
    - 逐步将 FloatPanels.vue 中的面板迁移到此组件
  -->
  <div class="panel-manager" :class="managerClass">
    <!-- ===== 已迁移到独立组件的面板 ===== -->

    <!-- AI智能体思考状态 -->
    <AIThinkingIndicator
      v-if="showThinkingIndicator"
      :states="thinkingStates"
      :compact="false"
      class="pm-thinking-indicator"
    />

    <!-- ===== 保留 FloatPanels 作为向后兼容层 ===== -->
    <!-- 当面板不属于新架构时，回退到旧 FloatPanels -->
    <FloatPanels
      v-if="useLegacyFallback"
      :panelSide="panelSide"
      @openDiplomacyDeep="$emit('openDiplomacyDeep')"
      @openTalentMarket="$emit('openTalentMarket')"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import type { AIThinkingState } from '@/types/game'
import AIThinkingIndicator from '@/components/AIThinkingIndicator.vue'
// 向后兼容：保留原 FloatPanels
import FloatPanels from '@/components/FloatPanels.vue'

const props = defineProps<{
  panelSide?: string
}>()

const emit = defineEmits<{
  (e: 'openDiplomacyDeep'): void
  (e: 'openTalentMarket'): void
}>()

const store = useGameStore()

const managerClass = computed(() => {
  const side = props.panelSide || 'left'
  return `pm-side-${side}`
})

// ===== AI 思考状态 =====
const thinkingStates = ref<AIThinkingState[]>([])
const showThinkingIndicator = computed(() =>
  thinkingStates.value.some(s => s.status !== 'idle')
)

// 监听 store 处理状态变化
watch(() => store.isProcessing, (processing) => {
  if (processing) {
    thinkingStates.value = [
      {
        agent_id: 'strategist',
        agent_name: '军师谋主',
        agent_role: '战略分析',
        status: 'thinking',
        progress: 30,
        current_action: '分析天下形势...',
      },
      {
        agent_id: 'general',
        agent_name: '大将统帅',
        agent_role: '军事调度',
        status: 'thinking',
        progress: 15,
        current_action: '评估兵力部署...',
      },
    ]
  } else {
    // 处理完成
    thinkingStates.value = thinkingStates.value.map(s => ({
      ...s,
      status: 'done' as const,
      progress: 100,
    }))
    // 3秒后隐藏
    setTimeout(() => {
      thinkingStates.value = []
    }, 3000)
  }
})

/**
 * 当所有活跃面板都不在新架构中时，使用旧 FloatPanels 作为回退
 * 随着面板逐步迁移，此条件会逐渐缩小
 */
const useLegacyFallback = computed(() => {
  // 目前所有面板仍在 FloatPanels 中，所以始终使用旧版
  // 后续迁移面板时逐步减少此条件
  return true
})
</script>

<style scoped>
.panel-manager {
  position: relative;
  pointer-events: none;
}

.panel-manager > * {
  pointer-events: auto;
}

.pm-thinking-indicator {
  position: fixed;
  bottom: 100px;
  right: 20px;
  z-index: 200;
}
</style>
