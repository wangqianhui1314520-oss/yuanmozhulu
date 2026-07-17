<template>
  <!--
    AI思考状态指示器 · 元末逐鹿 3.0
    古风设计：竹简底色 + 墨迹动画 + 鎏金点缀
    显示十大AI智能体的当前思考进度
  -->
  <div class="ai-thinking-indicator" v-if="visible">
    <!-- 标题栏 -->
    <div class="thinking-header" @click="collapsed = !collapsed">
      <span class="header-icon">📜</span>
      <span class="header-title">天机推演</span>
      <span class="header-progress">{{ overallProgress }}%</span>
      <span class="collapse-arrow" :class="{ collapsed: collapsed }">▾</span>
    </div>

    <!-- 智能体列表 -->
    <Transition name="slide">
      <div class="agents-list" v-if="!collapsed">
        <div
          v-for="agent in agents"
          :key="agent.agent_id"
          class="agent-row"
          :class="agent.status"
        >
          <!-- 智能体图标 -->
          <span class="agent-icon">{{ getAgentIcon(agent.agent_id) }}</span>

          <!-- 名称 -->
          <span class="agent-name">{{ agent.agent_name }}</span>

          <!-- 状态指示 -->
          <span class="agent-status-label">{{ getStatusLabel(agent.status) }}</span>

          <!-- 进度条 -->
          <div class="progress-bar-wrapper">
            <div
              class="progress-bar-fill"
              :class="agent.status"
              :style="{ width: agent.progress + '%' }"
            >
              <span class="ink-trail" v-if="agent.status === 'thinking'"></span>
            </div>
          </div>

          <!-- 消息 -->
          <span class="agent-message" v-if="agent.message" :title="agent.message">
            {{ truncate(agent.message, 12) }}
          </span>
        </div>
      </div>
    </Transition>

    <!-- 底部墨迹装饰 -->
    <div class="ink-decoration" v-if="!collapsed"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { AgentStatus } from '@/types/game';

const props = defineProps<{
  agents: AgentStatus[];
  visible: boolean;
}>();

const collapsed = ref(false);

const overallProgress = computed(() => {
  if (!props.agents.length) return 0;
  const sum = props.agents.reduce((acc, a) => acc + a.progress, 0);
  return Math.round(sum / props.agents.length);
});

function getAgentIcon(agentId: string): string {
  const icons: Record<string, string> = {
    A1: '🎯', A2: '⚔️', A3: '⚖️', A4: '🕵️',
    A5: '🌤️', A6: '🤝', A7: '👑', A8: '📖',
  };
  return icons[agentId] || '🔮';
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    idle: '待命',
    thinking: '推演中',
    done: '已毕',
    error: '有失',
    timeout: '逾时',
  };
  return labels[status] || status;
}

function truncate(text: string, maxLen: number): string {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
}
</script>

<style scoped>
/* ================================================================
   古风 AI 思考状态指示器样式
   配色：竹简底 + 鎏金 + 朱批 + 墨色
   ================================================================ */

.ai-thinking-indicator {
  position: fixed;
  top: 80px;
  right: 16px;
  z-index: 1000;
  width: 260px;
  background: linear-gradient(135deg, #1a1510 0%, #221c14 100%);
  border: 1px solid #8b7355;
  border-radius: 6px;
  box-shadow:
    0 4px 24px rgba(0, 0, 0, 0.5),
    inset 0 1px 0 rgba(139, 115, 85, 0.15);
  font-family: 'STKaiti', 'KaiTi', '楷体', serif;
  overflow: hidden;
  user-select: none;
}

/* 标题栏 */
.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(180deg, rgba(139, 115, 85, 0.2) 0%, transparent 100%);
  border-bottom: 1px solid rgba(139, 115, 85, 0.3);
  cursor: pointer;
  transition: background 0.2s;
}

.thinking-header:hover {
  background: linear-gradient(180deg, rgba(139, 115, 85, 0.3) 0%, transparent 100%);
}

.header-icon {
  font-size: 14px;
}

.header-title {
  flex: 1;
  font-size: 13px;
  color: #d4a853;
  letter-spacing: 2px;
}

.header-progress {
  font-size: 12px;
  color: #c0a060;
  font-weight: bold;
}

.collapse-arrow {
  font-size: 12px;
  color: #8b7355;
  transition: transform 0.3s ease;
}

.collapse-arrow.collapsed {
  transform: rotate(-90deg);
}

/* 智能体列表 */
.agents-list {
  padding: 6px 10px 10px;
}

.agent-row {
  display: grid;
  grid-template-columns: 20px 1fr auto;
  grid-template-rows: auto auto;
  gap: 2px 6px;
  align-items: center;
  padding: 4px 6px;
  border-radius: 3px;
  transition: background 0.2s;
}

.agent-row:hover {
  background: rgba(139, 115, 85, 0.1);
}

.agent-row + .agent-row {
  margin-top: 2px;
  border-top: 1px solid rgba(139, 115, 85, 0.1);
}

.agent-icon {
  font-size: 12px;
  grid-row: span 2;
  display: flex;
  align-items: center;
  justify-content: center;
}

.agent-name {
  font-size: 11px;
  color: #d0c8b0;
  letter-spacing: 1px;
}

.agent-status-label {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 2px;
  text-align: center;
}

/* 状态颜色 */
.agent-row.idle .agent-status-label { color: #6b5b3a; }
.agent-row.thinking .agent-status-label {
  color: #d4a853;
  animation: pulse-text 2s ease-in-out infinite;
}
.agent-row.done .agent-status-label { color: #5a8a4a; }
.agent-row.done .agent-icon {
  animation: doneBounce 0.4s var(--ease-squash);
}
@keyframes doneBounce {
  0% { transform: scale(1); }
  40% { transform: scale(1.3); }
  100% { transform: scale(1); }
}
.agent-row.error .agent-status-label { color: #c04040; }
.agent-row.timeout .agent-status-label { color: #b08040; }

/* 进度条 */
.progress-bar-wrapper {
  grid-column: 2 / -1;
  height: 3px;
  background: rgba(139, 115, 85, 0.15);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.22, 0.61, 0.36, 1);
  position: relative;
}

.progress-bar-fill.thinking {
  background: linear-gradient(90deg, #8b7355, #d4a853);
  animation: progressShimmer 2s ease-in-out infinite;
  background-size: 200% 100%;
}
@keyframes progressShimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}

.progress-bar-fill.done {
  background: #5a8a4a;
  animation: donePulse 0.5s var(--ease-squash);
}
@keyframes donePulse {
  0% { filter: brightness(1); }
  50% { filter: brightness(1.6); box-shadow: 0 0 6px rgba(90,138,74,0.5); }
  100% { filter: brightness(1); }
}

.progress-bar-fill.error {
  background: #c04040;
}

.progress-bar-fill.timeout {
  background: #b08040;
}

.progress-bar-fill.idle {
  background: rgba(139, 115, 85, 0.3);
  width: 100% !important;
}

/* 墨迹动画 */
.ink-trail {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 20px;
  background: linear-gradient(90deg, transparent, rgba(212, 168, 83, 0.4));
  animation: ink-flow 1.5s ease-in-out infinite;
}

@keyframes ink-flow {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.8; }
}

/* 消息文字 */
.agent-message {
  display: none;
  grid-column: 2 / -1;
  font-size: 9px;
  color: #8b7355;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-row.thinking .agent-message,
.agent-row.done .agent-message {
  display: block;
}

/* 底部墨迹装饰 */
.ink-decoration {
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(139, 115, 85, 0.5) 20%,
    rgba(139, 115, 85, 0.8) 50%,
    rgba(139, 115, 85, 0.5) 80%,
    transparent 100%
  );
}

/* 折叠动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
  max-height: 400px;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  max-height: 0;
  opacity: 0;
}

/* 脉冲文字动画 */
@keyframes pulse-text {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}
</style>
