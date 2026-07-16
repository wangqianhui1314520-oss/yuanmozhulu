<template>
  <Teleport to="body">
    <Transition name="panel-slide">
      <div v-if="visible" class="achievement-overlay" @click.self="$emit('close')">
        <div class="achievement-panel artifact-panel artifact-codex">
          <!-- 头部 -->
          <div class="panel-header">
            <div class="header-left">
              <span class="header-icon">🏆</span>
              <span class="header-title">功勋录</span>
              <span class="header-subtitle">万古流芳</span>
            </div>
            <button class="btn-close" @click="$emit('close')">✕</button>
          </div>

          <!-- 统计行 -->
          <div class="stats-row">
            <div class="stat-item">
              <span class="stat-num">{{ progress.total }}</span>
              <span class="stat-label">已获成就</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-num">{{ progress.percent }}%</span>
              <span class="stat-label">完成度</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-num">{{ progress.legendary }}</span>
              <span class="stat-label">传奇成就</span>
            </div>
          </div>

          <!-- 进度条 -->
          <div class="progress-bar-wrap">
            <div class="progress-bar" :style="{ width: progress.percent + '%' }"></div>
          </div>

          <!-- 分类筛选 -->
          <div class="category-tabs">
            <button
              v-for="cat in categories"
              :key="cat.id"
              class="cat-btn"
              :class="{ active: activeCategory === cat.id }"
              @click="activeCategory = cat.id"
            >
              <span class="cat-icon">{{ cat.icon }}</span>
              <span class="cat-label">{{ cat.label }}</span>
              <span class="cat-count">{{ catCount(cat.id) }}</span>
            </button>
          </div>

          <!-- 成就列表 -->
          <div class="achievement-list">
            <div
              v-for="ach in filteredAchievements"
              :key="ach.id"
              class="achievement-card"
              :class="{
                unlocked: ach.unlocked,
                locked: !ach.unlocked,
                ['rarity-' + ach.rarity]: true,
                'newly-unlocked': ach.isNew,
              }"
            >
              <div class="ach-icon-wrap">
                <span class="ach-icon">{{ ach.icon }}</span>
                <span v-if="ach.rarity === 'legendary'" class="rarity-badge legendary">传</span>
                <span v-else-if="ach.rarity === 'epic'" class="rarity-badge epic">皇</span>
              </div>
              <div class="ach-info">
                <div class="ach-name">
                  {{ ach.name }}
                  <span v-if="ach.isNew" class="new-tag">新</span>
                </div>
                <div class="ach-desc">{{ ach.unlocked ? ach.description : '???' }}</div>
                <div v-if="ach.unlocked && ach.unlockedAt" class="ach-date">
                  解锁于 {{ ach.unlockedAt }}
                </div>
              </div>
              <div class="ach-status">
                <span v-if="ach.unlocked" class="status-unlocked">✓</span>
                <span v-else class="status-locked">🔒</span>
              </div>
            </div>

            <!-- 空状态 -->
            <div v-if="filteredAchievements.length === 0" class="empty-state">
              <span class="empty-icon">📭</span>
              <span class="empty-text">此分类暂无成就</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useAchievementStore } from '@/stores/achievementStore'
import type { AchievementInfo } from '@/stores/achievementStore'

const props = defineProps<{
  visible: boolean
  factionId?: string
}>()

defineEmits<{
  close: []
}>()

const store = useAchievementStore()
const activeCategory = ref('all')

// 分类定义
const categories = [
  { id: 'all', icon: '🏆', label: '全部' },
  { id: 'military', icon: '⚔️', label: '军事' },
  { id: 'economy', icon: '💰', label: '经济' },
  { id: 'diplomacy', icon: '🤝', label: '外交' },
  { id: 'internal', icon: '🏛️', label: '内政' },
  { id: 'exploration', icon: '🔭', label: '探索' },
  { id: 'special', icon: '⭐', label: '特殊' },
] as const

// 打开时加载
watch(() => props.visible, async (v) => {
  if (v && props.factionId) {
    await store.loadAchievements(props.factionId)
  }
})

onMounted(async () => {
  if (props.visible && props.factionId) {
    await store.loadAchievements(props.factionId)
  }
})

// 进度统计
const progress = computed(() => {
  const all = store.allAchievements
  const unlocked = all.filter(a => a.unlocked).length
  const legendary = all.filter(a => a.unlocked && a.rarity === 'legendary').length
  return {
    total: unlocked,
    totalAll: all.length,
    percent: all.length > 0 ? Math.round((unlocked / all.length) * 100) : 0,
    legendary,
  }
})

// 按分类筛选
const filteredAchievements = computed(() => {
  let list = store.allAchievements
  if (activeCategory.value !== 'all') {
    list = list.filter(a => a.category === activeCategory.value)
  }
  // 已解锁的排前面，新解锁的再优先
  return [...list].sort((a, b) => {
    if (a.isNew && !b.isNew) return -1
    if (!a.isNew && b.isNew) return 1
    if (a.unlocked && !b.unlocked) return -1
    if (!a.unlocked && b.unlocked) return 1
    return 0
  })
})

function catCount(catId: string): string {
  if (catId === 'all') return ''
  const total = store.allAchievements.filter(a => a.category === catId).length
  const unlocked = store.allAchievements.filter(a => a.category === catId && a.unlocked).length
  return `${unlocked}/${total}`
}
</script>

<style scoped>
.achievement-overlay {
  position: fixed;
  inset: 0;
  z-index: 900;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}

.achievement-panel {
  width: 560px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: inset 3px 0 0 var(--wuxing-metal);
  overflow: hidden;
  font-family: 'FangSong', 'FangSong_GB2312', serif;
}

/* 头部 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: linear-gradient(90deg, rgba(184, 150, 62, 0.15), transparent 60%);
  border-bottom: 1px solid rgba(184, 150, 62, 0.25);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  font-size: 24px;
}

.header-title {
  font-size: 20px;
  color: #e0d5b8;
  font-weight: bold;
  letter-spacing: 2px;
}

.header-subtitle {
  font-size: 12px;
  color: #8a7550;
  margin-left: 4px;
}

.btn-close {
  width: 32px;
  height: 32px;
  background: rgba(184, 150, 62, 0.1);
  border: 1px solid rgba(184, 150, 62, 0.3);
  color: #b8963e;
  font-size: 16px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-close:hover {
  background: rgba(184, 150, 62, 0.25);
  color: #e0d5b8;
}

/* 统计行 */
.stats-row {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px 20px 10px;
  gap: 24px;
  flex-shrink: 0;
}

.stat-item {
  text-align: center;
}

.stat-num {
  display: block;
  font-size: 22px;
  color: #e0d5b8;
  font-weight: bold;
}

.stat-label {
  font-size: 11px;
  color: #8a7550;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background: rgba(184, 150, 62, 0.2);
}

/* 进度条 */
.progress-bar-wrap {
  margin: 0 20px 12px;
  height: 4px;
  background: rgba(184, 150, 62, 0.15);
  border-radius: 2px;
  overflow: hidden;
  flex-shrink: 0;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #b8963e, #d4af37);
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.22, 0.61, 0.36, 1);
}

/* 分类筛选 */
.category-tabs {
  display: flex;
  gap: 4px;
  padding: 0 16px 12px;
  overflow-x: auto;
  flex-shrink: 0;
  scrollbar-width: none;
}

.category-tabs::-webkit-scrollbar { display: none; }

.cat-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  background: rgba(184, 150, 62, 0.06);
  border: 1px solid transparent;
  color: #8a7550;
  font-size: 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  font-family: inherit;
}

.cat-btn:hover {
  background: rgba(184, 150, 62, 0.12);
  color: #c0a060;
}

.cat-btn.active {
  background: rgba(184, 150, 62, 0.18);
  border-color: rgba(184, 150, 62, 0.4);
  color: #e0d5b8;
}

.cat-icon {
  font-size: 14px;
}

.cat-label {
  font-size: 12px;
}

.cat-count {
  font-size: 10px;
  opacity: 0.6;
  margin-left: 2px;
}

/* 成就列表 */
.achievement-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.achievement-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  transition: all 0.3s;
  border: 1px solid transparent;
}

.achievement-card.unlocked {
  background: rgba(184, 150, 62, 0.06);
  border-color: rgba(184, 150, 62, 0.15);
}

.achievement-card.locked {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.04);
  opacity: 0.55;
}

.achievement-card.newly-unlocked {
  animation: unlockGlow 2s ease-out;
  border-color: rgba(184, 150, 62, 0.4);
  background: rgba(184, 150, 62, 0.1);
}

.achievement-card.rarity-legendary.unlocked {
  border-color: rgba(212, 175, 55, 0.4);
  background: rgba(212, 175, 55, 0.08);
}

.achievement-card.rarity-epic.unlocked {
  border-color: rgba(160, 100, 220, 0.3);
}

/* 图标 */
.ach-icon-wrap {
  position: relative;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: rgba(184, 150, 62, 0.1);
  flex-shrink: 0;
}

.achievement-card.locked .ach-icon-wrap {
  background: rgba(255, 255, 255, 0.03);
}

.ach-icon {
  font-size: 22px;
}

.rarity-badge {
  position: absolute;
  top: -4px;
  right: -8px;
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: bold;
  line-height: 1.2;
}

.rarity-badge.legendary {
  background: linear-gradient(135deg, #d4af37, #ffd700);
  color: #3a2000;
}

.rarity-badge.epic {
  background: linear-gradient(135deg, #a064dc, #c084fc);
  color: #fff;
}

/* 信息 */
.ach-info {
  flex: 1;
  min-width: 0;
}

.ach-name {
  font-size: 14px;
  color: #e0d5b8;
  margin-bottom: 3px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.new-tag {
  font-size: 10px;
  background: #d4af37;
  color: #1a1410;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: bold;
  animation: pulse 1.5s ease-in-out infinite;
}

.ach-desc {
  font-size: 12px;
  color: #8a7550;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ach-date {
  font-size: 10px;
  color: #5a4a30;
  margin-top: 2px;
}

.ach-status {
  flex-shrink: 0;
  font-size: 18px;
}

.status-unlocked {
  color: #b8963e;
}

.status-locked {
  color: #3a2a10;
  font-size: 14px;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 40px 0;
  color: #5a4a30;
}

.empty-icon {
  font-size: 32px;
  display: block;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 13px;
}

/* 动画 */
@keyframes unlockGlow {
  0% { box-shadow: 0 0 20px rgba(184, 150, 62, 0.5); }
  100% { box-shadow: 0 0 0px rgba(184, 150, 62, 0); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* 面板滑入 */
.panel-slide-enter-active {
  transition: all 0.35s cubic-bezier(0.22, 0.61, 0.36, 1);
}
.panel-slide-leave-active {
  transition: all 0.25s ease-in;
}
.panel-slide-enter-from {
  opacity: 0;
}
.panel-slide-enter-from .achievement-panel {
  transform: scale(0.95) translateY(10px);
}
.panel-slide-leave-to {
  opacity: 0;
}
</style>
