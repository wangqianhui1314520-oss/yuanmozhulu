/**
 * 外交状态管理 Store · 元末逐鹿 3.0
 *
 * 管理外交关系：同盟、战争、附庸、贸易、关系值
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { AllianceLine, WarLine, WarState, CasusBelli } from '@/types/game';

export const useDiplomacyStore = defineStore('diplomacy', () => {
  // ================================================================
  // 状态
  // ================================================================

  const alliances = ref<AllianceLine[]>([]);
  const wars = ref<WarLine[]>([]);
  const activeWars = ref<WarState[]>([]);
  const relations = ref<Record<string, number>>({});
  const vassals = ref<string[]>([]);
  const tradeRoutes = ref<string[]>([]);

  // ================================================================
  // 计算属性
  // ================================================================

  const isAtWar = computed(() => activeWars.value.length > 0);

  const warCount = computed(() => activeWars.value.length);

  const allianceCount = computed(() => alliances.value.length);

  const hasVassals = computed(() => vassals.value.length > 0);

  /** 获取与指定势力的关系值 */
  function getRelation(factionId: string): number {
    return relations.value[factionId] || 0;
  }

  /** 是否与指定势力结盟 */
  function isAlliedWith(factionId: string): boolean {
    return alliances.value.some(
      a => (a.from_faction === factionId || a.to_faction === factionId)
    );
  }

  /** 是否与指定势力交战 */
  function isAtWarWith(factionId: string): boolean {
    return activeWars.value.some(
      w => w.attacker === factionId || w.defender === factionId
    );
  }

  /** 从 WorldState 中提取外交数据 */
  function extractFromWorldState(worldState: Record<string, unknown>) {
    const ws = worldState as Record<string, unknown>;

    if (ws.diplomacy) {
      const diplo = ws.diplomacy as Record<string, unknown>;
      alliances.value = (diplo.alliances as AllianceLine[]) || [];
      wars.value = (diplo.wars as WarLine[]) || [];
    }

    if (ws.active_wars) {
      activeWars.value = (ws.active_wars as WarState[]) || [];
    }

    if (ws.relations) {
      relations.value = (ws.relations as Record<string, number>) || {};
    }

    if (ws.vassals) {
      vassals.value = (ws.vassals as string[]) || [];
    }

    if (ws.trade_routes) {
      tradeRoutes.value = (ws.trade_routes as string[]) || [];
    }
  }

  /** 重置外交状态 */
  function resetAll() {
    alliances.value = [];
    wars.value = [];
    activeWars.value = [];
    relations.value = {};
    vassals.value = [];
    tradeRoutes.value = [];
  }

  return {
    alliances, wars, activeWars, relations, vassals, tradeRoutes,
    isAtWar, warCount, allianceCount, hasVassals,
    getRelation, isAlliedWith, isAtWarWith,
    extractFromWorldState, resetAll,
  };
});
