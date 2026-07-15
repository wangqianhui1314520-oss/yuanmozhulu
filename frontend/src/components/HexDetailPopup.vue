<template>
  <div
    v-if="visible && tile"
    class="hex-detail-popup parchment-panel"
    :style="{ left: position.x + 'px', top: position.y + 'px' }"
    @click.stop
  >
    <!-- 头部 -->
    <div class="hdp-header">
      <span class="hdp-name" :style="{ color: factionColor || '#c9a94e' }">
        {{ tile.tile_name }}
      </span>
      <button class="hdp-close" @click="$emit('close')">✕</button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="hdp-loading">加载中...</div>

    <!-- 详情内容 -->
    <div v-else-if="data" class="hdp-body">
      <div class="hdp-row">
        <span class="hdp-label">坐标</span>
        <span class="hdp-value">({{ tile.q }}, {{ tile.r }})</span>
      </div>
      <div class="hdp-row">
        <span class="hdp-label">类型</span>
        <span class="hdp-value">{{ tileTypeName(tile.tile_type) }}</span>
      </div>
      <div class="hdp-row">
        <span class="hdp-label">人口</span>
        <span class="hdp-value">{{ formatNum(tile.population) }}</span>
      </div>
      <div class="hdp-row">
        <span class="hdp-label">驻军</span>
        <span class="hdp-value">{{ formatNum(tile.troops) }}</span>
      </div>
      <div class="hdp-row">
        <span class="hdp-label">民心</span>
        <span class="hdp-value">{{ tile.morale }}</span>
      </div>
      <div class="hdp-row" v-if="tile.faction_id">
        <span class="hdp-label">归属</span>
        <span class="hdp-value" :style="{ color: factionColor || '#c9a94e' }">
          {{ factionName }}
        </span>
      </div>
      <div class="hdp-row" v-if="tile.is_capital">
        <span class="hdp-label">都城</span>
        <span class="hdp-value">★ 是</span>
      </div>

      <!-- 建筑信息 -->
      <div class="hdp-divider" v-if="buildings.length > 0"></div>
      <div v-if="buildings.length > 0" class="hdp-buildings">
        <span class="hdp-section-title">🏗 本地建筑</span>
        <div class="hdp-bld-row" v-for="b in buildings" :key="b.key">
          <span class="hdp-bld-icon">{{ b.icon }}</span>
          <span class="hdp-bld-name">{{ b.name }}</span>
          <span class="hdp-bld-level">Lv.{{ b.level }}</span>
          <span class="hdp-bld-effect">{{ b.effectShort }}</span>
        </div>
      </div>
      <div v-else class="hdp-row hdp-dim">
        <span class="hdp-label">建筑</span>
        <span class="hdp-value">无</span>
      </div>

      <!-- 可用操作 -->
      <div class="hdp-row" v-if="data.available_actions?.length">
        <span class="hdp-label">可用操作</span>
        <span class="hdp-value">{{ data.available_actions.join('、') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HexTile } from '@/utils/hexUtils'

const props = defineProps<{
  visible: boolean
  tile: HexTile | null
  data: any
  loading: boolean
  position: { x: number; y: number }
  factionColor: string
  factionName: string
}>()

defineEmits<{
  close: []
}>()

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

interface BuildingInfo { key: string; name: string; icon: string; level: number; effectShort: string }

const buildingInfoMap: Record<string, { name: string; icon: string; effectShort: string }> = {
  water_works: { name: '水利', icon: '🌊', effectShort: '人口增长+0.15%/级' },
  granary: { name: '粮仓', icon: '🌾', effectShort: '储粮上限+500/级' },
  clinic: { name: '医馆', icon: '🏥', effectShort: '人口增长+0.30%/级·降瘟疫' },
  fortification: { name: '城防', icon: '🏰', effectShort: '防御+20%/级·驻军上限+2000' },
  armory: { name: '军械所', icon: '⚒', effectShort: '精锐比例+0.10/级' },
  stable: { name: '马场', icon: '🐴', effectShort: '解锁战马购买' },
  port: { name: '港口', icon: '⚓', effectShort: '海上贸易+80银/回合' },
}

const buildings = computed<BuildingInfo[]>(() => {
  if (!props.tile) return []
  const t = props.tile
  const result: BuildingInfo[] = []
  if (t.water_works > 0) result.push({ key: 'water_works', level: t.water_works, ...buildingInfoMap.water_works })
  if (t.granary > 0) result.push({ key: 'granary', level: t.granary, ...buildingInfoMap.granary })
  if (t.clinic > 0) result.push({ key: 'clinic', level: t.clinic, ...buildingInfoMap.clinic })
  if (t.fortification > 0) result.push({ key: 'fortification', level: t.fortification, ...buildingInfoMap.fortification })
  if (t.armory > 0) result.push({ key: 'armory', level: t.armory, ...buildingInfoMap.armory })
  if (t.stable > 0) result.push({ key: 'stable', level: t.stable, ...buildingInfoMap.stable })
  if (t.is_port) result.push({ key: 'port', level: 1, ...buildingInfoMap.port })
  return result
})
</script>

<style scoped>
.hex-detail-popup {
  position: fixed;
  z-index: 5000;
  min-width: 210px;
  max-width: 290px;
}

.parchment-panel {
  background: linear-gradient(180deg, #f5eed8 0%, #e8dcc8 50%, #dcc8a0 100%);
  border: 2px solid #b8a080;
  border-radius: 4px;
  box-shadow:
    0 4px 24px rgba(0, 0, 0, 0.35),
    inset 0 0 30px rgba(139, 115, 85, 0.08);
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
}

.hdp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(139, 115, 85, 0.3);
  background: linear-gradient(180deg, rgba(139, 115, 85, 0.08) 0%, transparent 100%);
}

.hdp-name {
  font-size: 16px;
  font-weight: bold;
  letter-spacing: 1px;
}

.hdp-close {
  background: none;
  border: none;
  color: #8a7a6a;
  cursor: pointer;
  font-size: 16px;
  padding: 2px 6px;
  border-radius: 2px;
  font-family: serif;
  transition: all 0.15s;
}

.hdp-close:hover {
  color: #3a2a1a;
  background: rgba(139, 115, 85, 0.12);
}

.hdp-loading {
  padding: 16px;
  text-align: center;
  color: #8a7a6a;
  font-size: 12px;
}

.hdp-body {
  padding: 10px 14px;
}

.hdp-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
  border-bottom: 1px dotted rgba(139, 115, 85, 0.2);
}

.hdp-label {
  color: #5a4a3a;
}

.hdp-value {
  color: #3a2a1a;
  font-weight: bold;
}

.hdp-dim .hdp-value {
  color: #8a7a6a;
  font-weight: normal;
}

.hdp-divider {
  height: 1px;
  background: rgba(139, 115, 85, 0.2);
  margin: 6px 0;
}

.hdp-section-title {
  font-size: 11px;
  color: #8b6508;
  display: block;
  margin-bottom: 4px;
  letter-spacing: 1px;
}

.hdp-buildings {
  margin-top: 2px;
}

.hdp-bld-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 0;
  font-size: 11px;
  border-bottom: 1px dotted rgba(139, 115, 85, 0.15);
}

.hdp-bld-icon {
  font-size: 13px;
  width: 18px;
  text-align: center;
}

.hdp-bld-name {
  color: #3a2a1a;
  font-weight: bold;
  min-width: 40px;
}

.hdp-bld-level {
  color: #2e7d32;
  font-size: 10px;
  background: rgba(46, 125, 50, 0.1);
  padding: 1px 5px;
  border-radius: 2px;
}

.hdp-bld-effect {
  color: #8a7a6a;
  font-size: 10px;
  margin-left: auto;
}
</style>
