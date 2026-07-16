/**
 * 地图状态管理 Store · 元末逐鹿 3.0
 *
 * 管理地图图层数据：迷雾、驻防、行军、灾害、建筑、外交连线
 * 从 gameStore 中拆分出来，降低单一 store 的复杂度
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  FogLayer, GarrisonLayer, MarchLayer, DisasterLayer,
  BuildingLayer, DiplomacyLayer, LayerData, HexCoord,
  MarchRoute, Disaster, TileBuilding, AllianceLine, WarLine,
} from '@/types/game';
import * as API from '@/services/api';

export const useMapStore = defineStore('map', () => {
  // ================================================================
  // 状态
  // ================================================================

  const fogLayer = ref<FogLayer>({ visible_tiles: [], explored_tiles: [] });
  const garrisonLayer = ref<GarrisonLayer>({ tiles: {} });
  const marchLayer = ref<MarchLayer>({ routes: [] });
  const disasterLayer = ref<DisasterLayer>({ disasters: [] });
  const buildingLayer = ref<BuildingLayer>({ tiles: {} });
  const diplomacyLayer = ref<DiplomacyLayer>({ alliances: [], wars: [] });

  const isLoading = ref(false);
  const lastFetchRound = ref(0);

  // ================================================================
  // 计算属性
  // ================================================================

  /** 是否有活跃的行军 */
  const hasActiveMarches = computed(() => marchLayer.value.routes.length > 0);

  /** 是否有活跃的灾害 */
  const hasActiveDisasters = computed(() => disasterLayer.value.disasters.length > 0);

  /** 活跃战争数量 */
  const activeWarCount = computed(() => diplomacyLayer.value.wars.length);

  /** 所有图层数据 */
  const allLayers = computed<LayerData>(() => ({
    fog: fogLayer.value,
    garrison: garrisonLayer.value,
    march: marchLayer.value,
    disaster: disasterLayer.value,
    building: buildingLayer.value,
    diplomacy: diplomacyLayer.value,
  }));

  // ================================================================
  // 方法
  // ================================================================

  /** 从 WorldState 中提取图层数据 */
  function extractFromWorldState(worldState: Record<string, unknown>) {
    const ws = worldState as Record<string, unknown>;

    // 迷雾
    if (ws.fog_of_war) {
      const fog = ws.fog_of_war as Record<string, unknown>;
      fogLayer.value = {
        visible_tiles: (fog.visible_tiles as string[]) || [],
        explored_tiles: (fog.explored_tiles as string[]) || [],
      };
    }

    // 驻防
    if (ws.garrisons) {
      garrisonLayer.value = {
        tiles: (ws.garrisons as Record<string, { troops: number; faction_id: string }>) || {},
      };
    }

    // 行军
    if (ws.marches) {
      marchLayer.value = { routes: (ws.marches as MarchRoute[]) || [] };
    }

    // 灾害
    if (ws.disasters) {
      disasterLayer.value = { disasters: (ws.disasters as Disaster[]) || [] };
    }

    // 建筑
    if (ws.buildings) {
      buildingLayer.value = { tiles: (ws.buildings as Record<string, TileBuilding>) || {} };
    }

    // 外交
    if (ws.diplomacy) {
      const diplo = ws.diplomacy as Record<string, unknown>;
      diplomacyLayer.value = {
        alliances: (diplo.alliances as AllianceLine[]) || [],
        wars: (diplo.wars as WarLine[]) || [],
      };
    }
  }

  /** 从后端API刷新图层数据 */
  async function fetchLayerData(factionId: string) {
    isLoading.value = true;
    try {
      const data = await API.getLayersData(factionId);
      if (data) {
        extractFromWorldState(data);
      }
      lastFetchRound.value = Date.now();
    } catch (_err) {
      // 静默降级：图层加载失败不阻塞游戏
    } finally {
      isLoading.value = false;
    }
  }

  /** 重置所有图层数据 */
  function resetAll() {
    fogLayer.value = { visible_tiles: [], explored_tiles: [] };
    garrisonLayer.value = { tiles: {} };
    marchLayer.value = { routes: [] };
    disasterLayer.value = { disasters: [] };
    buildingLayer.value = { tiles: {} };
    diplomacyLayer.value = { alliances: [], wars: [] };
    isLoading.value = false;
    lastFetchRound.value = 0;
  }

  /** 检查地块是否可见 */
  function isTileVisible(tileId: string): boolean {
    return fogLayer.value.visible_tiles.includes(tileId);
  }

  /** 检查地块是否已探索 */
  function isTileExplored(tileId: string): boolean {
    return fogLayer.value.explored_tiles.includes(tileId);
  }

  /** 获取地块驻防信息 */
  function getTileGarrison(tileId: string): { troops: number; faction_id: string } | null {
    return garrisonLayer.value.tiles[tileId] || null;
  }

  return {
    // 状态
    fogLayer, garrisonLayer, marchLayer, disasterLayer,
    buildingLayer, diplomacyLayer, isLoading, lastFetchRound,

    // 计算属性
    hasActiveMarches, hasActiveDisasters, activeWarCount, allLayers,

    // 方法
    extractFromWorldState, fetchLayerData, resetAll,
    isTileVisible, isTileExplored, getTileGarrison,
  };
});
