<template>
  <div
    v-if="visible && tile"
    class="hex-tooltip parchment-panel"
    :style="{ left: position.x + 'px', top: position.y + 'px' }"
  >
    <!-- 地块名 -->
    <div class="tt-name" :style="{ color: factionColor || '#c9a94e' }">
      {{ tile.tile_name }}
    </div>
    <div class="tt-id">[{{ tile.tile_id }}] ({{ tile.q }},{{ tile.r }})</div>

    <!-- 基本信息 -->
    <div class="tt-row">
      <span class="tt-label">人口</span>
      <span class="tt-value">{{ formatNum(tile.population) }}</span>
    </div>
    <div class="tt-row">
      <span class="tt-label">驻军</span>
      <span class="tt-value">{{ formatNum(tile.troops) }}</span>
    </div>
    <div class="tt-row">
      <span class="tt-label">民心</span>
      <span class="tt-value">{{ tile.morale }}</span>
    </div>
    <div class="tt-row">
      <span class="tt-label">城防</span>
      <span class="tt-value">Lv.{{ tile.fortification || 0 }}</span>
    </div>

    <!-- 建筑图标行 -->
    <div class="tt-buildings" v-if="tileBuildings.length > 0">
      <span v-for="b in tileBuildings" :key="b.key" class="tt-bld-icon" :title="b.name + ' Lv.' + b.level">
        {{ b.icon }}
      </span>
    </div>

    <!-- 归属势力 -->
    <div class="tt-row" v-if="tile.faction_id">
      <span class="tt-label">归属</span>
      <span class="tt-value" :style="{ color: factionColor || '#c9a94e' }">
        {{ factionName }}
      </span>
    </div>

    <!-- 冷却状态 -->
    <div class="tt-row tt-cooling" v-if="coolingActions.length > 0">
      <span class="tt-label">本回合已操作</span>
      <span class="tt-value tt-cooling-text">
        {{ coolingActions.map((c: any) => actionNameMap[c.action] || c.action).join('、') }}
      </span>
    </div>

    <!-- 灾害状态 -->
    <div class="tt-row tt-disaster" v-if="tile.disasters && tile.disasters.length > 0">
      <span class="tt-label">灾害</span>
      <span class="tt-value tt-disaster-text">
        {{ tile.disasters.map((d: any) => disasterNameMap[typeof d === 'string' ? d : d.value] || d).join('、') }}
      </span>
    </div>

    <!-- 地块类型 -->
    <div class="tt-type">{{ tileTypeName(tile.tile_type) }}</div>
  </div>
</template>

<script setup lang="ts">
import type { HexTile } from '@/utils/hexUtils'

defineProps<{
  visible: boolean
  tile: HexTile | null
  position: { x: number; y: number }
  factionColor: string
  factionName: string
  coolingActions: any[]
  tileBuildings: { key: string; name: string; icon: string; level: number }[]
}>()

const actionNameMap: Record<string, string> = {
  march: '行军', develop: '开发', recruit: '征兵',
  fortify: '城防', relief: '赈灾', build: '建造',
  tax: '税政', diplomacy: '外交', enfeoff: '分封',
  spy: '细作', law: '律法',
}

const disasterNameMap: Record<string, string> = {
  flood: '洪水', drought: '旱灾', locust: '蝗灾',
  plague: '瘟疫', war_devastation: '兵灾',
}

const TILE_TYPE_NAMES: Record<string, string> = {
  farmland: '农田', mountain: '山地', water: '水域',
  coast: '海岸', city: '城池', pass: '关隘',
  port: '港口', desert: '漠地', grassland: '草原',
}

function tileTypeName(type: string): string {
  return TILE_TYPE_NAMES[type] || type
}

function formatNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}
</script>

<style scoped>
.hex-tooltip {
  position: fixed;
  z-index: 5000;
  pointer-events: none;
  min-width: 170px;
  max-width: 220px;
}

.parchment-panel {
  background: linear-gradient(180deg, #f5eed8 0%, #e8dcc8 50%, #dcc8a0 100%);
  border: 2px solid #b8a080;
  border-radius: 4px;
  padding: 10px 14px;
  box-shadow:
    0 4px 24px rgba(0, 0, 0, 0.35),
    inset 0 0 30px rgba(139, 115, 85, 0.08);
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
}

.tt-name {
  font-size: 17px;
  font-weight: bold;
  margin-bottom: 2px;
  letter-spacing: 1px;
}

.tt-id {
  font-size: 10px;
  color: #8a7a6a;
  margin-bottom: 6px;
}

.tt-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 0;
  border-bottom: 1px dotted rgba(139, 115, 85, 0.25);
}

.tt-label {
  color: #5a4a3a;
}

.tt-value {
  color: #3a2a1a;
  font-weight: bold;
}

.tt-buildings {
  display: flex;
  gap: 3px;
  padding: 2px 0;
  border-bottom: 1px dotted rgba(139, 115, 85, 0.2);
}

.tt-bld-icon {
  font-size: 13px;
  cursor: default;
}

.tt-cooling {
  border-bottom-color: rgba(128, 128, 128, 0.25) !important;
}

.tt-cooling-text {
  color: #888 !important;
  font-size: 10px !important;
}

.tt-disaster {
  border-bottom-color: rgba(220, 50, 50, 0.25) !important;
}

.tt-disaster-text {
  color: #b83030 !important;
  font-size: 10px !important;
}

.tt-type {
  font-size: 10px;
  color: #8a7a6a;
  text-align: right;
  margin-top: 4px;
}
</style>
