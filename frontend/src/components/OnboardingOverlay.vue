<script setup lang="ts">
/**
 * 新手引导浮层 — 非侵入式提示系统
 * 首次访问显示5条引导，localStorage 记录已读状态。
 * 不影响游戏操作，可随时跳过/关闭。
 * 零后端依赖，纯前端组件。
 */
import { ref, onMounted } from 'vue'

const STORAGE_KEY = 'yuanmo_onboarding_seen'

const tips = [
  {
    title: '颁布圣旨',
    text: '在下方圆角圣旨栏中输入自然语言命令——「命徐达率三万精兵攻取集庆」——AI 将解析圣旨并执行推演。右击沙盘格位可快速下达行军、建设、募兵等预制命令。',
    icon: '📜',
  },
  {
    title: '沙盘舆图',
    text: '中央六边形沙盘为元末天下全图。点击格位查看详情，滚轮缩放，拖拽平移。左侧工具栏为军政大事，右侧为内政谋略，点击按钮即可打开对应面板。',
    icon: '🗺️',
  },
  {
    title: '天下大势',
    text: '顶部「战」「策」「谋」「势」「史」为快速入口——「战」观兵戈、「策」变法图强、「谋」朝堂问计、「势」天下格局、「史」青史札记。点击「下一回合」推进天下时局。',
    icon: '⚔️',
  },
  {
    title: '青史札记',
    text: '史馆中收录了 AI 驱动的天下大事、势力列传与元末掌故。每回合 AI 自动修史，无需额外操作即可纵览群雄兴衰。',
    icon: '🏛',
  },
  {
    title: '存档管理',
    text: '点击顶部「存」可快速存档，「档」进入存档管理页面。AI 自动存档保护进度，突发事件前亦有自动快照。祝君逐鹿天下，早定乾坤！',
    icon: '💾',
  },
]

const currentTip = ref(0)
const visible = ref(false)

onMounted(() => {
  const seen = localStorage.getItem(STORAGE_KEY)
  if (!seen) {
    visible.value = true
  }
})

function next() {
  if (currentTip.value < tips.length - 1) {
    currentTip.value++
  } else {
    dismiss()
  }
}

function dismiss() {
  localStorage.setItem(STORAGE_KEY, 'true')
  visible.value = false
}

function skip() {
  localStorage.setItem(STORAGE_KEY, 'true')
  visible.value = false
}
</script>

<template>
  <div v-if="visible" class="onboarding-overlay">
    <!-- 半透明遮罩 -->
    <div class="onboarding-backdrop" @click="skip"></div>

    <!-- 提示卡片 -->
    <div class="onboarding-card animate-onboard">
      <!-- 步骤指示器 -->
      <div class="onboarding-steps">
        <span
          v-for="(_, i) in tips" :key="i"
          class="step-dot"
          :class="{ active: i === currentTip, done: i < currentTip }"
        ></span>
      </div>

      <!-- 图标 -->
      <div class="onboarding-icon">{{ tips[currentTip].icon }}</div>

      <!-- 标题 -->
      <h3 class="onboarding-title">{{ tips[currentTip].title }}</h3>

      <!-- 正文 -->
      <p class="onboarding-text">{{ tips[currentTip].text }}</p>

      <!-- 按钮 -->
      <div class="onboarding-actions">
        <button class="onboarding-btn skip-btn" @click="skip">跳过引导</button>
        <button class="onboarding-btn next-btn" @click="next">
          {{ currentTip < tips.length - 1 ? '下一步' : '开始逐鹿' }}
        </button>
      </div>

      <!-- 进度 -->
      <div class="onboarding-progress">{{ currentTip + 1 }} / {{ tips.length }}</div>
    </div>
  </div>
</template>

<style scoped>
.onboarding-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.onboarding-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
}

.onboarding-card {
  position: relative;
  width: min(480px, 90vw);
  background: linear-gradient(180deg, #2a1f14 0%, #1a1208 100%);
  border: 2px solid #b89b68;
  border-radius: 16px;
  padding: 36px 32px 28px;
  text-align: center;
  box-shadow: 0 0 80px rgba(180, 140, 80, 0.2), 0 12px 40px rgba(0,0,0,0.6);
}

.onboarding-steps {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 20px;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(184, 155, 104, 0.2);
  transition: all 0.3s;
}
.step-dot.active { background: #b89b68; box-shadow: 0 0 8px rgba(184, 155, 104, 0.4); }
.step-dot.done { background: rgba(184, 155, 104, 0.5); }

.onboarding-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.onboarding-title {
  margin: 0 0 14px;
  font-size: 22px;
  color: #d4c098;
  font-family: 'STKaiti', 'KaiTi', serif;
  letter-spacing: 3px;
}

.onboarding-text {
  margin: 0 0 28px;
  font-size: 14px;
  color: #a09078;
  line-height: 1.9;
}

.onboarding-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.onboarding-btn {
  padding: 10px 24px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-family: 'STKaiti', 'KaiTi', serif;
  transition: all 0.2s;
}

.skip-btn {
  background: transparent;
  border: 1px solid rgba(184, 155, 104, 0.3);
  color: #887755;
}
.skip-btn:hover { background: rgba(184, 155, 104, 0.1); color: #c8b080; }

.next-btn {
  background: linear-gradient(180deg, #b89b68, #8b6f3f);
  border: 1px solid #c8a84a;
  color: #1a1208;
  font-weight: bold;
}
.next-btn:hover { background: linear-gradient(180deg, #c8a84a, #9b7f4f); }

.onboarding-progress {
  margin-top: 18px;
  font-size: 11px;
  color: #554433;
}

.animate-onboard {
  animation: onboardIn 0.35s ease-out;
}
@keyframes onboardIn {
  from { opacity: 0; transform: translateY(20px) scale(0.95); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
</style>
