<template>
  <!--
    游戏事件通知叠加层 · 元末逐鹿 3.0
    古风卷轴式事件弹窗，用于战斗/领土/外交等关键事件反馈
    V3.1: 交错入场 + 类型专属微动效 (game-feel enhanced)
  -->
  <Teleport to="body">
    <TransitionGroup name="event-item" tag="div" class="event-container">
      <div
        v-for="(evt, idx) in visibleEvents"
        :key="evt.id"
        class="event-toast"
        :class="['event-' + evt.type, { 'event-critical': evt.type === 'battle_lose' || evt.type === 'rebellion' || evt.type === 'disaster' }]"
        :style="{ animationDelay: idx * 0.08 + 's' }"
      >
        <!-- 左侧墨迹装饰条 -->
        <div class="event-accent-stripe"></div>

        <!-- 事件图标（含微动效） -->
        <div class="event-icon" :class="'icon-' + evt.type">
          <span class="icon-glyph" v-if="evt.type === 'battle_win'">🏆</span>
          <span class="icon-glyph shake-once" v-else-if="evt.type === 'battle_lose'">💀</span>
          <span class="icon-glyph" v-else-if="evt.type === 'territory_gain'">🏴</span>
          <span class="icon-glyph pulse-slow" v-else-if="evt.type === 'territory_lose'">🚩</span>
          <span class="icon-glyph" v-else-if="evt.type === 'diplomacy'">🤝</span>
          <span class="icon-glyph wobble-slow" v-else-if="evt.type === 'disaster'">🌪️</span>
          <span class="icon-glyph flicker" v-else-if="evt.type === 'rebellion'">🔥</span>
          <span class="icon-glyph pop-in" v-else-if="evt.type === 'economy'">💰</span>
          <span class="icon-glyph" v-else-if="evt.type === 'event'">📜</span>
          <span class="icon-glyph" v-else>📌</span>
        </div>

        <!-- 事件内容 -->
        <div class="event-body">
          <div class="event-title">{{ evt.title }}</div>
          <div class="event-detail" v-if="evt.detail">{{ evt.detail }}</div>
        </div>

        <!-- 关闭按钮 -->
        <button class="event-close" @click="dismiss(evt.id)">✕</button>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

export interface GameEvent {
  id: string
  type: 'battle_win' | 'battle_lose' | 'territory_gain' | 'territory_lose'
    | 'diplomacy' | 'disaster' | 'rebellion' | 'economy' | 'event' | 'info'
  title: string
  detail?: string
  duration?: number  // 自动消失时间，默认 5000ms
}

const events = ref<GameEvent[]>([])
const visibleEvents = ref<GameEvent[]>([])
let _idCounter = 0

/** 推送一个新事件通知 */
function push(evt: Omit<GameEvent, 'id'>) {
  const id = `evt_${Date.now()}_${++_idCounter}`
  const full: GameEvent = { ...evt, id }
  events.value.push(full)
  visibleEvents.value.push(full)

  const duration = evt.duration ?? 5000
  setTimeout(() => dismiss(id), duration)
}

/** 手动关闭事件 */
function dismiss(id: string) {
  visibleEvents.value = visibleEvents.value.filter(e => e.id !== id)
}

/** 清除所有事件 */
function clearAll() {
  visibleEvents.value = []
  events.value = []
}

defineExpose({ push, dismiss, clearAll })
</script>

<style scoped>
.event-container {
  position: fixed;
  top: 80px;
  right: 20px;
  z-index: 6000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
  max-width: 360px;
}

.event-toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 3px;
  pointer-events: auto;
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  font-family: 'STKaiti', 'KaiTi', serif;
  min-width: 280px;
  transition: all 0.3s ease;
}

/* 不同类型配色 */
.event-battle_win {
  background: linear-gradient(135deg, rgba(44, 51, 32, 0.95), rgba(24, 28, 18, 0.95));
  border: 1px solid rgba(184, 155, 104, 0.5);
  border-left: 3px solid #b89b68;
}
.event-battle_lose {
  background: linear-gradient(135deg, rgba(92, 26, 21, 0.95), rgba(50, 16, 14, 0.95));
  border: 1px solid rgba(158, 43, 37, 0.5);
  border-left: 3px solid #9e2b25;
}
.event-territory_gain {
  background: linear-gradient(135deg, rgba(32, 51, 42, 0.95), rgba(18, 30, 24, 0.95));
  border: 1px solid rgba(80, 160, 80, 0.5);
  border-left: 3px solid #50a050;
}
.event-territory_lose {
  background: linear-gradient(135deg, rgba(60, 40, 20, 0.95), rgba(40, 25, 12, 0.95));
  border: 1px solid rgba(204, 136, 0, 0.5);
  border-left: 3px solid #cc8800;
}
.event-diplomacy {
  background: linear-gradient(135deg, rgba(30, 40, 60, 0.95), rgba(18, 25, 38, 0.95));
  border: 1px solid rgba(100, 149, 237, 0.5);
  border-left: 3px solid #6495ed;
}
.event-disaster {
  background: linear-gradient(135deg, rgba(60, 30, 60, 0.95), rgba(40, 18, 40, 0.95));
  border: 1px solid rgba(180, 80, 180, 0.5);
  border-left: 3px solid #b450b4;
}
.event-rebellion {
  background: linear-gradient(135deg, rgba(80, 30, 20, 0.95), rgba(50, 18, 12, 0.95));
  border: 1px solid rgba(255, 80, 40, 0.5);
  border-left: 3px solid #ff5028;
}
.event-economy {
  background: linear-gradient(135deg, rgba(40, 45, 30, 0.95), rgba(25, 30, 18, 0.95));
  border: 1px solid rgba(200, 180, 60, 0.5);
  border-left: 3px solid #c8b43c;
}
.event-event, .event-info {
  background: linear-gradient(135deg, rgba(44, 40, 36, 0.95), rgba(28, 24, 20, 0.95));
  border: 1px solid rgba(184, 150, 62, 0.35);
  border-left: 3px solid #b8963e;
}

.event-icon {
  font-size: 20px;
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.event-body {
  flex: 1;
  min-width: 0;
}

.event-title {
  font-size: 14px;
  color: #eae3d6;
  letter-spacing: 1px;
  line-height: 1.4;
}

.event-detail {
  font-size: 12px;
  color: #a09880;
  margin-top: 3px;
  letter-spacing: 0.5px;
}

.event-close {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: #6a6458;
  cursor: pointer;
  font-size: 12px;
  border-radius: 2px;
  transition: all 0.2s;
  margin-top: 2px;
}
.event-close:hover {
  color: #eae3d6;
  background: rgba(255, 255, 255, 0.08);
}

/* V3.1 左侧墨迹装饰条 — 强化器物感 */
.event-accent-stripe {
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 2px;
  border-radius: 1px;
  opacity: 0;
  transition: opacity 0.5s var(--ease-ink);
}
.event-toast:hover .event-accent-stripe {
  opacity: 0.6;
}
.event-battle_win .event-accent-stripe  { background: #b89b68; }
.event-battle_lose .event-accent-stripe { background: #9e2b25; }
.event-territory_gain .event-accent-stripe { background: #50a050; }
.event-territory_lose .event-accent-stripe { background: #cc8800; }
.event-diplomacy .event-accent-stripe    { background: #6495ed; }
.event-disaster .event-accent-stripe     { background: #b450b4; }
.event-rebellion .event-accent-stripe    { background: #ff5028; }
.event-economy .event-accent-stripe      { background: #c8b43c; }
.event-event .event-accent-stripe,
.event-info .event-accent-stripe         { background: #b8963e; }

/* V3.1 图标微动效 — 12原则动画 */
.icon-glyph {
  display: inline-block;
}
/* 战败抖动（单次） */
.shake-once {
  animation: evtShake 0.5s ease-out;
}
@keyframes evtShake {
  0%, 100% { transform: translateX(0); }
  15% { transform: translateX(-5px); }
  30% { transform: translateX(5px); }
  45% { transform: translateX(-4px); }
  60% { transform: translateX(3px); }
  75% { transform: translateX(-2px); }
}
/* 失地脉动 */
.pulse-slow {
  animation: evtPulse 2s ease-in-out infinite;
}
@keyframes evtPulse {
  0%, 100% { opacity: 0.7; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.15); }
}
/* 灾难摇晃（缓慢） */
.wobble-slow {
  animation: evtWobble 3s ease-in-out infinite;
}
@keyframes evtWobble {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(3deg); }
  75% { transform: rotate(-3deg); }
}
/* 叛乱闪烁 */
.flicker {
  animation: evtFlicker 0.8s ease-in-out infinite;
}
@keyframes evtFlicker {
  0%, 100% { opacity: 1; }
  30% { opacity: 0.5; }
  35% { opacity: 1; }
  60% { opacity: 0.6; }
  65% { opacity: 1; }
}
/* 经济弹入 */
.pop-in {
  animation: evtPopIn 0.4s var(--ease-squash);
}
@keyframes evtPopIn {
  0% { transform: scale(0); opacity: 0; }
  60% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}

/* V3.1 关键事件（战败/叛乱/灾难）额外震感光晕 */
.event-critical {
  animation: criticalGlow 2s ease-in-out infinite;
}
@keyframes criticalGlow {
  0%, 100% { box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
  50% { box-shadow: 0 4px 28px rgba(0,0,0,0.6), 0 0 12px rgba(200,40,40,0.12); }
}

/* V3.1 交错入场增强 */
.event-item-enter-active {
  transition: all 0.45s cubic-bezier(0.22, 0.61, 0.36, 1);
}
.event-item-leave-active {
  transition: all 0.3s ease-in;
  position: absolute; /* 离开时脱离流，避免跳跃 */
}
.event-item-enter-from {
  opacity: 0;
  transform: translateX(80px) scale(0.85);
  filter: blur(2px);
}
.event-item-leave-to {
  opacity: 0;
  transform: translateX(50px) scale(0.9);
  filter: blur(1px);
}

/* V3.1 hover 放大（微交互） */
.event-toast:hover {
  transform: scale(1.02) translateX(-2px);
  transition: transform 0.2s var(--ease-squash);
}
</style>
