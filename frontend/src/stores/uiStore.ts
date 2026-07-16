/**
 * UI 状态管理 Store · 元末逐鹿 3.0
 *
 * 管理所有面板的显示/隐藏状态，替代 gameStore 中散落的 showXxxPanel ref
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { PanelType, PanelVisibility, MapViewMode, AIThinkingState, AgentStatus } from '@/types/game';

export const useUiStore = defineStore('ui', () => {
  // ================================================================
  // 面板显示状态
  // ================================================================

  const panels = ref<PanelVisibility>({
    advisor: false,
    war: false,
    diplomacy: false,
    policy: false,
    recruit: false,
    march: false,
    general: false,
    spy: false,
    ending: false,
    replay: false,
    settings: false,
    security: false,
    talent: false,
    history: false,
    batch_build: false,
    batch_recruit: false,
  });

  // ================================================================
  // 地图视图状态
  // ================================================================

  const mapViewMode = ref<MapViewMode>('terrain');
  const selectedTile = ref<string | null>(null);
  const hoveredTile = ref<string | null>(null);
  const isMapDragging = ref(false);

  // ================================================================
  // AI 思考状态
  // ================================================================

  const aiThinking = ref<AIThinkingState>({
    round: 0,
    phase: 'idle',
    agents: [],
    overall_progress: 0,
  });

  const showAIThinking = ref(false);

  // ================================================================
  // 圣旨台状态
  // ================================================================

  const edictDrawerOpen = ref(false);
  const edictInput = ref('');
  const edictResult = ref<Record<string, unknown> | null>(null);
  const isEdictProcessing = ref(false);

  // ================================================================
  // 全局加载状态
  // ================================================================

  const isGlobalLoading = ref(false);
  const globalLoadingMessage = ref('');
  const toastMessage = ref('');
  const toastType = ref<'info' | 'success' | 'warning' | 'error'>('info');
  const toastVisible = ref(false);

  // ================================================================
  // 计算属性
  // ================================================================

  const anyPanelOpen = computed(() => {
    return Object.values(panels.value).some(v => v);
  });

  const openPanels = computed(() => {
    return Object.entries(panels.value)
      .filter(([, v]) => v)
      .map(([k]) => k as PanelType);
  });

  // ================================================================
  // 面板控制方法
  // ================================================================

  function togglePanel(panel: PanelType) {
    panels.value[panel] = !panels.value[panel];
  }

  function openPanel(panel: PanelType) {
    panels.value[panel] = true;
  }

  function closePanel(panel: PanelType) {
    panels.value[panel] = false;
  }

  function closeAllPanels() {
    for (const key of Object.keys(panels.value)) {
      panels.value[key] = false;
    }
  }

  function openOnlyPanel(panel: PanelType) {
    closeAllPanels();
    panels.value[panel] = true;
  }

  // ================================================================
  // 地图控制方法
  // ================================================================

  function setMapViewMode(mode: MapViewMode) {
    mapViewMode.value = mode;
  }

  function selectTile(tileId: string | null) {
    selectedTile.value = tileId;
  }

  function hoverTile(tileId: string | null) {
    hoveredTile.value = tileId;
  }

  // ================================================================
  // AI 思考状态方法
  // ================================================================

  function updateAIThinking(state: Partial<AIThinkingState>) {
    aiThinking.value = { ...aiThinking.value, ...state };
    showAIThinking.value = aiThinking.value.agents.some(
      a => a.status === 'thinking'
    );
  }

  function updateAgentStatus(agentId: string, update: Partial<AgentStatus>) {
    const agent = aiThinking.value.agents.find(a => a.agent_id === agentId);
    if (agent) {
      Object.assign(agent, update);
    }
    // 重新计算总进度
    const agents = aiThinking.value.agents;
    aiThinking.value.overall_progress = agents.length
      ? Math.round(agents.reduce((s, a) => s + a.progress, 0) / agents.length)
      : 0;
  }

  function clearAIThinking() {
    aiThinking.value = {
      round: 0,
      phase: 'idle',
      agents: [],
      overall_progress: 0,
    };
    showAIThinking.value = false;
  }

  // ================================================================
  // Toast 方法
  // ================================================================

  function showToast(message: string, type: 'info' | 'success' | 'warning' | 'error' = 'info', duration = 3000) {
    toastMessage.value = message;
    toastType.value = type;
    toastVisible.value = true;
    setTimeout(() => {
      toastVisible.value = false;
    }, duration);
  }

  // ================================================================
  // 圣旨台方法
  // ================================================================

  function openEdictDrawer() {
    edictDrawerOpen.value = true;
  }

  function closeEdictDrawer() {
    edictDrawerOpen.value = false;
    edictResult.value = null;
  }

  function setEdictProcessing(processing: boolean) {
    isEdictProcessing.value = processing;
  }

  // ================================================================
  // 全局加载方法
  // ================================================================

  function setGlobalLoading(loading: boolean, message = '') {
    isGlobalLoading.value = loading;
    globalLoadingMessage.value = message;
  }

  // ================================================================
  // 重置
  // ================================================================

  function resetAll() {
    closeAllPanels();
    mapViewMode.value = 'terrain';
    selectedTile.value = null;
    hoveredTile.value = null;
    clearAIThinking();
    edictDrawerOpen.value = false;
    edictInput.value = '';
    edictResult.value = null;
    isEdictProcessing.value = false;
    isGlobalLoading.value = false;
    globalLoadingMessage.value = '';
  }

  return {
    // 面板
    panels, anyPanelOpen, openPanels,
    togglePanel, openPanel, closePanel, closeAllPanels, openOnlyPanel,

    // 地图
    mapViewMode, selectedTile, hoveredTile, isMapDragging,
    setMapViewMode, selectTile, hoverTile,

    // AI
    aiThinking, showAIThinking,
    updateAIThinking, updateAgentStatus, clearAIThinking,

    // 圣旨台
    edictDrawerOpen, edictInput, edictResult, isEdictProcessing,
    openEdictDrawer, closeEdictDrawer, setEdictProcessing,

    // 加载 & Toast
    isGlobalLoading, globalLoadingMessage,
    toastMessage, toastType, toastVisible,
    showToast, setGlobalLoading,

    // 重置
    resetAll,
  };
});
