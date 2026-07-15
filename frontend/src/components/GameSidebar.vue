<template>
  <nav class="game-sidebar" :class="{ collapsed: isCollapsed }">
    <button
      v-for="tool in sidebarTools"
      :key="tool.id"
      class="sidebar-btn"
      :class="{ active: store.activePanel === tool.id }"
      :title="tool.label"
      @click="store.togglePanel(tool.id as any)"
    >
      <span class="sidebar-icon">{{ tool.icon }}</span>
      <span class="sidebar-label">{{ tool.label }}</span>
    </button>

    <button class="sidebar-btn sidebar-toggle" @click="isCollapsed = !isCollapsed" title="收起/展开">
      <span class="sidebar-icon">{{ isCollapsed ? '▶' : '◀' }}</span>
      <span class="sidebar-label">{{ isCollapsed ? '展开' : '收起' }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useGameStore } from '@/stores/gameStore'

const store = useGameStore()
const isCollapsed = ref(false)

const sidebarTools = [
  { id: 'treasury', icon: '💰', label: '国库' },
  { id: 'territory', icon: '🗺', label: '领土' },
  { id: 'court', icon: '🏛', label: '朝堂' },
  { id: 'military', icon: '⚔', label: '军事' },
  { id: 'ambush', icon: '🌲', label: '伏击' },
  { id: 'diplomacy', icon: '🤝', label: '外交' },
  { id: 'law', icon: '⚖', label: '律法' },
  { id: 'law-interrogate', icon: '🔍', label: '审讯' },
  { id: 'spy', icon: '🕵', label: '驿站' },
  { id: 'royal', icon: '👑', label: '皇子' },
  { id: 'medical', icon: '🏥', label: '疲病' },
  { id: 'sea', icon: '⛵', label: '海策' },
  { id: 'vassal', icon: '🏰', label: '藩镇' },
  { id: 'workshop', icon: '🔨', label: '工坊' },
  { id: 'rebel', icon: '🔥', label: '叛军' },
  { id: 'prisoner', icon: '🔗', label: '招安' },
  { id: 'personnel', icon: '👤', label: '人物' },
  { id: 'culture', icon: '📖', label: '民俗' },
  { id: 'events', icon: '📋', label: '邸报' },
  { id: 'faction_network', icon: '🕸', label: '天下势' },
]
</script>

<style scoped>
.game-sidebar {
  width: 54px;
  background: linear-gradient(180deg, #3a2e1e 0%, #2a1f14 100%);
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 4px;
  border-right: 1px solid #8a7348;
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.2s;
}

.game-sidebar.collapsed {
  width: 36px;
}

.sidebar-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 3px;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-dim);
  font-family: "SimSun", serif;
  font-size: 9px;
  transition: all var(--duration-fast) var(--ease-out);
  white-space: nowrap;
}

.sidebar-btn:hover {
  background: rgba(184, 155, 104, 0.08);
  color: var(--text-secondary);
  border-color: rgba(184, 155, 104, 0.2);
}

.sidebar-btn.active {
  background: rgba(184, 155, 104, 0.15);
  border-color: var(--gold);
  color: var(--gold);
}

.sidebar-btn:active {
  transform: translateY(1px);
}

.sidebar-icon {
  font-size: 20px;
  line-height: 1;
}

.sidebar-label {
  font-size: 9px;
  letter-spacing: 1px;
}

.collapsed .sidebar-label {
  display: none;
}

.sidebar-toggle {
  margin-top: auto;
  opacity: 0.5;
}
.sidebar-toggle:hover {
  opacity: 0.8;
}
</style>
