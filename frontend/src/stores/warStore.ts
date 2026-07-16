/**
 * 战争状态管理 Store · 元末逐鹿 3.0
 *
 * 管理战争相关状态：活跃战争、战斗历史、战争分数
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { WarState, WarEvent, CasusBelli, CasusBelliType } from '@/types/game';

export const useWarStore = defineStore('war', () => {
  // ================================================================
  // 状态
  // ================================================================

  const activeWars = ref<WarState[]>([]);
  const warHistory = ref<WarEvent[]>([]);
  const availableCasusBelli = ref<CasusBelli[]>([]);

  // ================================================================
  // 计算属性
  // ================================================================

  const isAtWar = computed(() => activeWars.value.length > 0);

  const totalWarScore = computed(() => {
    if (!activeWars.value.length) return 0;
    return activeWars.value.reduce((sum, w) => sum + w.war_score, 0);
  });

  /** 获取与指定势力的战争 */
  function getWarWith(factionId: string): WarState | undefined {
    return activeWars.value.find(
      w => w.attacker === factionId || w.defender === factionId
    );
  }

  /** 检查是否与指定势力交战 */
  function isAtWarWith(factionId: string): boolean {
    return activeWars.value.some(
      w => w.attacker === factionId || w.defender === factionId
    );
  }

  /** 获取可用的宣战理由 */
  function getCasusBelliFor(factionId: string): CasusBelli[] {
    return availableCasusBelli.value.filter(cb => {
      // 根据目标势力过滤可用的CB
      return true;  // 简化处理，实际逻辑由后端控制
    });
  }

  /** 从 WorldState 中提取战争数据 */
  function extractFromWorldState(worldState: Record<string, unknown>) {
    const ws = worldState as Record<string, unknown>;

    if (ws.active_wars) {
      activeWars.value = (ws.active_wars as WarState[]) || [];
    }

    if (ws.war_history) {
      warHistory.value = (ws.war_history as WarEvent[]) || [];
    }

    if (ws.available_cb) {
      availableCasusBelli.value = (ws.available_cb as CasusBelli[]) || [];
    }
  }

  /** 重置战争状态 */
  function resetAll() {
    activeWars.value = [];
    warHistory.value = [];
    availableCasusBelli.value = [];
  }

  return {
    activeWars, warHistory, availableCasusBelli,
    isAtWar, totalWarScore,
    getWarWith, isAtWarWith, getCasusBelliFor,
    extractFromWorldState, resetAll,
  };
});
