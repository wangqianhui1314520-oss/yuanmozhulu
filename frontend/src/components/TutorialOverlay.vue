<template>
  <!-- 教程引导覆盖层 — 步骤式高亮引导 -->
  <Teleport to="body">
    <Transition name="tutorial-fade">
      <div v-if="store.isVisible && store.currentStep" class="tutorial-overlay">
        <!-- 半透明遮罩（挖洞效果） -->
        <div class="tutorial-backdrop" @click.self.prevent />

        <!-- 步骤卡片 -->
        <div
          class="tutorial-card"
          :class="'position-' + (store.currentStep.position || 'bottom')"
          :style="cardStyle"
        >
          <!-- 进度条 -->
          <div class="tutorial-progress-bar">
            <div class="tutorial-progress-fill" :style="{ width: store.progress + '%' }" />
          </div>

          <!-- 标题 -->
          <div class="tutorial-header">
            <span class="tutorial-step-badge">{{ store.currentStep.step_index + 1 }}/{{ store.currentStep.total_steps }}</span>
            <span class="tutorial-title">{{ store.currentStep.title }}</span>
          </div>

          <!-- 描述 -->
          <div class="tutorial-body">{{ store.currentStep.description }}</div>

          <!-- 提示 -->
          <div v-if="store.currentStep.hint" class="tutorial-hint">
            💡 {{ store.currentStep.hint }}
          </div>

          <!-- 操作按钮 -->
          <div class="tutorial-actions">
            <button class="tutorial-btn skip" @click="store.skip()">跳过教程</button>
            <button
              v-if="store.currentStep.id !== 'complete'"
              class="tutorial-btn next"
              @click="store.nextStep()"
            >
              下一步 →
            </button>
            <button
              v-else
              class="tutorial-btn next finish"
              @click="store.complete()"
            >
              开始征程 ✦
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTutorialStore } from '@/stores/tutorialStore'

const store = useTutorialStore()

const cardStyle = computed(() => {
  const rect = store.highlightRect
  if (!rect) {
    // 居中显示
    return {
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
    }
  }

  const pos = store.currentStep?.position || 'bottom'
  const gap = 16

  switch (pos) {
    case 'bottom':
      return {
        top: (rect.bottom + gap) + 'px',
        left: (rect.left + rect.width / 2) + 'px',
        transform: 'translateX(-50%)',
      }
    case 'top':
      return {
        bottom: (window.innerHeight - rect.top + gap) + 'px',
        left: (rect.left + rect.width / 2) + 'px',
        transform: 'translateX(-50%)',
      }
    case 'left':
      return {
        top: (rect.top + rect.height / 2) + 'px',
        right: (window.innerWidth - rect.left + gap) + 'px',
        transform: 'translateY(-50%)',
      }
    case 'right':
      return {
        top: (rect.top + rect.height / 2) + 'px',
        left: (rect.right + gap) + 'px',
        transform: 'translateY(-50%)',
      }
    default:
      return {
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
      }
  }
})
</script>

<style scoped>
.tutorial-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  pointer-events: none;
}
.tutorial-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  pointer-events: auto;
}

/* ===== 卡片 ===== */
.tutorial-card {
  position: absolute;
  pointer-events: auto;
  width: 360px;
  max-width: 90vw;
  background: linear-gradient(135deg, #2a1f14 0%, #1a1208 100%);
  border: 1.5px solid #b8963e;
  border-radius: 8px;
  padding: 0;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.6),
    0 0 0 1px rgba(184, 150, 62, 0.2) inset,
    0 0 40px rgba(184, 150, 62, 0.1);
  font-family: 'FangSong', 'FangSong_GB2312', 'SimSun', serif;
  overflow: hidden;
  animation: tutorialSlideIn 0.4s cubic-bezier(0.22, 0.61, 0.36, 1);
}

@keyframes tutorialSlideIn {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* 进度条 */
.tutorial-progress-bar {
  height: 3px;
  background: rgba(184, 150, 62, 0.15);
}
.tutorial-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #b8963e, #d4b65e);
  transition: width 0.4s ease;
}

/* 头部 */
.tutorial-header {
  padding: 16px 20px 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.tutorial-step-badge {
  font-size: 12px;
  color: #8b7355;
  background: rgba(184, 150, 62, 0.1);
  border: 1px solid rgba(184, 150, 62, 0.25);
  padding: 1px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.tutorial-title {
  font-size: 18px;
  font-weight: bold;
  color: #d4b65e;
  letter-spacing: 2px;
}

/* 正文 */
.tutorial-body {
  padding: 4px 20px 12px;
  font-size: 14px;
  color: #c0b090;
  line-height: 1.8;
}

/* 提示 */
.tutorial-hint {
  margin: 0 20px 12px;
  padding: 8px 12px;
  background: rgba(184, 150, 62, 0.08);
  border-left: 3px solid #b8963e;
  border-radius: 0 4px 4px 0;
  font-size: 13px;
  color: #a09070;
}

/* 操作按钮 */
.tutorial-actions {
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid rgba(184, 150, 62, 0.12);
}
.tutorial-btn {
  padding: 8px 20px;
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 1px;
}
.tutorial-btn.skip {
  background: transparent;
  border: 1px solid rgba(139, 115, 85, 0.4);
  color: #8b7355;
}
.tutorial-btn.skip:hover {
  border-color: #8b7355;
  color: #a09070;
}
.tutorial-btn.next {
  background: linear-gradient(135deg, #b8963e, #8b6f2e);
  border: 1px solid #b8963e;
  color: #1a1208;
  font-weight: bold;
}
.tutorial-btn.next:hover {
  background: linear-gradient(135deg, #d4b65e, #a0803e);
  box-shadow: 0 0 12px rgba(184, 150, 62, 0.3);
}
.tutorial-btn.finish {
  background: linear-gradient(135deg, #c43a3a, #8b2020);
  border-color: #c43a3a;
  color: #e0d5b8;
}
.tutorial-btn.finish:hover {
  background: linear-gradient(135deg, #e05050, #a03030);
  box-shadow: 0 0 16px rgba(196, 58, 58, 0.4);
}

/* ===== 过渡动画 ===== */
.tutorial-fade-enter-active,
.tutorial-fade-leave-active {
  transition: all 0.35s ease;
}
.tutorial-fade-enter-from,
.tutorial-fade-leave-to {
  opacity: 0;
}
</style>
