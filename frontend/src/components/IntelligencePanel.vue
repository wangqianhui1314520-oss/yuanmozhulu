<template>
  <div class="intel-panel" :class="{ collapsed: isCollapsed }">
    <!-- 标题栏 -->
    <div class="intel-header">
      <span class="intel-title">四方谍报</span>
      <span class="intel-badge" v-if="newIntelCount > 0">{{ newIntelCount }}条新报</span>
      <div class="intel-actions">
        <button class="intel-action-btn" @click="filterMode = filterMode === 'all' ? 'important' : filterMode === 'important' ? 'all' : 'all'" :title="filterMode === 'all' ? '仅看要闻' : '全部显示'">
          {{ filterMode === 'all' ? '📋' : '⭐' }}
        </button>
        <button class="intel-action-btn" @click="isCollapsed = !isCollapsed" :title="isCollapsed ? '展开' : '收起'">
          {{ isCollapsed ? '◀' : '▶' }}
        </button>
      </div>
    </div>

    <div class="intel-body" v-if="!isCollapsed">
      <!-- 快速摘要栏 -->
      <div class="intel-summary">
        <div class="summary-item" v-for="s in summaryCards" :key="s.key" :class="s.className">
          <span class="summary-icon">{{ s.icon }}</span>
          <span class="summary-val">{{ s.value }}</span>
          <span class="summary-label">{{ s.label }}</span>
        </div>
      </div>

      <!-- 过滤标签 -->
      <div class="intel-filters" v-if="filterMode === 'all'">
        <button v-for="f in filterCategories" :key="f.key" class="filter-tag" :class="{ active: activeCategory === f.key }" @click="activeCategory = activeCategory === f.key ? '' : f.key">
          {{ f.label }}
        </button>
      </div>

      <!-- 谍报条目列表 -->
      <div class="intel-list" ref="intelListRef">
        <div class="intel-empty" v-if="filteredIntel.length === 0">
          <span>暂无相关谍报</span>
        </div>
        <div v-for="item in filteredIntel" :key="item.id" class="intel-item" :class="'severity-' + item.severity" @click="onIntelClick(item)">
          <div class="intel-item-header">
            <span class="intel-item-icon">{{ categoryIcon(item.category) }}</span>
            <span class="intel-item-category">{{ item.categoryLabel }}</span>
            <span class="intel-item-time">{{ item.time }}</span>
            <span v-if="item.factionName" class="intel-item-faction" :style="{ color: item.factionColor }">【{{ item.factionName }}】</span>
          </div>
          <div class="intel-item-title">{{ item.title }}</div>
          <div class="intel-item-detail" v-if="item.detail">{{ item.detail }}</div>
          <div class="intel-item-resources" v-if="item.resourceChanges">
            <span v-for="rc in item.resourceChanges" :key="rc.key" :class="'res-change ' + (rc.change > 0 ? 'positive' : 'negative')">
              {{ rc.icon }} {{ rc.change > 0 ? '+' : '' }}{{ rc.changeStr }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 谍报详情弹窗 -->
    <div v-if="selectedIntel" class="intel-detail-overlay" @click.self="selectedIntel = null">
      <div class="intel-detail-card">
        <div class="idc-header">
          <span class="idc-category" :style="{ borderColor: selectedIntel.factionColor || '#b89b68' }">
            {{ categoryIcon(selectedIntel.category) }} {{ selectedIntel.categoryLabel }}
          </span>
          <button class="idc-close" @click="selectedIntel = null">✕</button>
        </div>
        <h3 class="idc-title">{{ selectedIntel.title }}</h3>
        <div class="idc-meta" v-if="selectedIntel.factionName">
          <span class="idc-faction" :style="{ color: selectedIntel.factionColor }">【{{ selectedIntel.factionName }}】</span>
          <span class="idc-time">{{ selectedIntel.time }}</span>
        </div>
        <div class="idc-detail" v-if="selectedIntel.fullDetail">{{ selectedIntel.fullDetail }}</div>
        <div class="idc-effects" v-if="selectedIntel.effects">
          <div class="idc-effect-title">影响评估</div>
          <div v-for="(eff, key) in selectedIntel.effects" :key="key" class="idc-effect-row">
            <span class="idc-effect-key">{{ key }}</span>
            <span class="idc-effect-val" :class="eff.change > 0 ? 'positive' : eff.change < 0 ? 'negative' : ''">
              {{ eff.change > 0 ? '+' : '' }}{{ eff.changeStr || eff.change }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useGameStore } from '@/stores/gameStore'

const store = useGameStore()

const isCollapsed = ref(false)
const filterMode = ref<'all' | 'important'>('all')
const activeCategory = ref('')
const selectedIntel = ref<any>(null)
const intelListRef = ref<HTMLElement>()
const lastRoundIntelCount = ref(0)

// 过滤分类
const filterCategories = [
  { key: 'military', label: '军情' },
  { key: 'diplomacy', label: '外交' },
  { key: 'economy', label: '钱粮' },
  { key: 'disaster', label: '灾异' },
  { key: 'court', label: '朝堂' },
  { key: 'territory', label: '疆土' },
]

function categoryIcon(cat: string): string {
  const m: Record<string, string> = {
    military: '⚔️', diplomacy: '🤝', economy: '💰', disaster: '🌪️',
    court: '🏛️', territory: '🗺️', event: '📜', spy: '🕵️',
    rebel: '🔥', building: '🏗️', policy: '📋', supply: '🎯',
  }
  return m[cat] || '•'
}

// 从store数据实时生成谍报条目
const intelligenceItems = computed(() => {
  const items: any[] = []
  const now = `第${store.currentRound}回合`

  // 1. 最近事件
  for (const evt of store.events.slice(0, 30)) {
    const cat = mapEventType(evt.event_type)
    const faction = evt.faction_id ? store.factions[evt.faction_id] : null
    items.push({
      id: evt.event_id || `evt_${Math.random()}`,
      category: cat,
      categoryLabel: categoryName(cat),
      title: evt.title || evt.description?.slice(0, 40) || '',
      detail: evt.description?.slice(0, 100) || '',
      fullDetail: evt.narrative || evt.description || '',
      time: `第${evt.round || store.currentRound}回合`,
      factionName: faction?.name || '',
      factionColor: faction?.color || '',
      severity: cat === 'military' ? 'major' : cat === 'disaster' ? 'critical' : evt.severity || 'minor',
      effects: evt.effects,
    })
  }

  // 2. 势力动向
  for (const [fid, faction] of Object.entries(store.factions)) {
    if (!faction.is_alive || fid === store.playerFactionId) continue
    const f = faction as any
    // 势力基本信息摘要
    items.push({
      id: `faction_${fid}_${store.currentRound}`,
      category: 'territory',
      categoryLabel: '疆土',
      title: `${faction.name}：领地${f.tile_count || '?'}城·兵${f.total_troops ? formatNum(f.total_troops) : '?'}`,
      detail: `声望${f.reputation || '?'}·民心${f.realm_stability || '?'}`,
      time: now,
      factionName: faction.name,
      factionColor: faction.color || '#8a7a6a',
      severity: 'minor',
      resourceChanges: [],
    })
  }

  // 3. 地块变更
  for (const change of store.tileChangesThisRound || []) {
    const tile = change?.tile_id ? store.tiles[change.tile_id] : null
    items.push({
      id: `tchange_${change?.tile_id || Math.random()}`,
      category: 'territory',
      categoryLabel: '疆土',
      title: `${tile?.tile_name || change?.tile_id || '某地'}易主`,
      detail: `${change?.from_faction || '未知'} → ${change?.to_faction || '未知'}`,
      time: now,
      factionName: change?.to_faction ? store.factions[change.to_faction]?.name : '',
      severity: 'major',
    })
  }

  // 4. 灾害信息
  for (const disaster of store.activeDisasters || []) {
    items.push({
      id: `dis_${disaster?.type || Math.random()}`,
      category: 'disaster',
      categoryLabel: '灾异',
      title: `${disasterName(disaster?.type || '')}${disaster?.location ? '·' + disaster.location : ''}`,
      detail: disaster?.description || `严重程度: ${disaster?.severity || '?'}`,
      time: now,
      severity: disaster?.severity >= 0.7 ? 'critical' : 'major',
    })
  }

  // 5. 叛军
  for (const rebel of store.rebelArmies || []) {
    const tile = rebel?.tile_id ? store.tiles[rebel.tile_id] : null
    items.push({
      id: `rebel_${rebel?.rebel_id || Math.random()}`,
      category: 'rebel',
      categoryLabel: '叛军',
      title: `叛军${tile?.tile_name ? '占据' + tile.tile_name : '流窜'}`,
      detail: `兵力${rebel?.troops || '?'}·首领${rebel?.leader || '不明'}`,
      time: now,
      severity: 'critical',
    })
  }

  // 6. 补给线状态
  for (const supply of store.activeSupplyLines || []) {
    if (supply.broken) {
      items.push({
        id: `supply_${supply.id}`,
        category: 'supply',
        categoryLabel: '补给',
        title: '补给线中断！',
        detail: `补给线${supply.id}已被切断，部队面临逃散风险`,
        time: now,
        severity: 'critical',
      })
    }
  }

  // 7. 建筑变更（如有新增）
  for (const [tid, blds] of Object.entries(store.tileBuildingData || {})) {
    const tile = store.tiles[tid]
    if (tile && blds?.length) {
      items.push({
        id: `bld_${tid}_${store.currentRound}`,
        category: 'building',
        categoryLabel: '营造',
        title: `${tile.tile_name}基建`,
        detail: blds.map((b: any) => `${b.name || b.type}Lv.${b.level}`).join('·'),
        time: now,
        factionName: tile.faction_id ? store.factions[tile.faction_id]?.name : '',
        severity: 'minor',
      })
    }
  }

  return items
})

// 过滤后的谍报
const filteredIntel = computed(() => {
  let items = intelligenceItems.value
  if (filterMode.value === 'important') {
    items = items.filter(i => i.severity === 'major' || i.severity === 'critical')
  }
  if (activeCategory.value) {
    items = items.filter(i => i.category === activeCategory.value)
  }
  return items.slice(0, 50)
})

// 新报数
const newIntelCount = computed(() => {
  return Math.max(0, intelligenceItems.value.length - lastRoundIntelCount.value)
})

// 摘要卡片
const summaryCards = computed(() => {
  const others = Object.values(store.factions).filter(f => f.is_alive && f.faction_id !== store.playerFactionId)
  const wars = others.filter(f => {
    const key = [store.playerFactionId, f.faction_id].sort().join('|')
    const rel = (store.relations as any)[key]
    return rel?.stance === 'war'
  }).length
  const allies = others.filter(f => {
    const key = [store.playerFactionId, f.faction_id].sort().join('|')
    const rel = (store.relations as any)[key]
    return rel?.stance === 'alliance'
  }).length
  const disasters = store.activeDisasters?.length || 0
  const rebels = store.rebelArmies?.length || 0

  return [
    { key: 'wars', icon: '⚔️', value: wars, label: '交战', className: wars > 0 ? 'danger' : '' },
    { key: 'allies', icon: '🤝', value: allies, label: '盟邦', className: allies > 0 ? 'good' : '' },
    { key: 'disasters', icon: '🌪️', value: disasters, label: '灾异', className: disasters > 0 ? 'warn' : '' },
    { key: 'rebels', icon: '🔥', value: rebels, label: '乱军', className: rebels > 0 ? 'danger' : '' },
  ]
})

function onIntelClick(item: any) {
  selectedIntel.value = item
}

function mapEventType(type: string): string {
  const m: Record<string, string> = {
    battle: 'military', diplomacy: 'diplomacy', disaster: 'disaster',
    court: 'court', economy: 'economy', spy: 'spy', civil: 'event',
    royal: 'court', random: 'event', ending: 'event', policy: 'policy',
    decree: 'court',
  }
  return m[type] || 'event'
}

function categoryName(cat: string): string {
  const m: Record<string, string> = {
    military: '军情', diplomacy: '外交', economy: '钱粮', disaster: '灾异',
    court: '朝堂', territory: '疆土', event: '邸报', spy: '谍报',
    rebel: '叛军', building: '营造', policy: '国策', supply: '补给',
  }
  return m[cat] || cat
}

function disasterName(type: string): string {
  const m: Record<string, string> = {
    flood: '洪水', drought: '旱灾', locust: '蝗灾', plague: '瘟疫',
    war_devastation: '兵灾', refugee_wave: '流民潮', mutiny: '兵变',
    bandit_raid: '匪患', blizzard: '暴雪',
  }
  return m[type] || type
}

function formatNum(n: number | undefined): string {
  if (n === undefined) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return String(Math.floor(n))
}

// 监听回合变化，更新新报计数
watch(() => store.currentRound, () => {
  lastRoundIntelCount.value = intelligenceItems.value.length
  nextTick(() => {
    if (intelListRef.value) intelListRef.value.scrollTop = 0
  })
})

onMounted(() => {
  lastRoundIntelCount.value = intelligenceItems.value.length
})
</script>

<style scoped>
.intel-panel {
  position: fixed;
  right: 0;
  top: 64px;
  bottom: 0;
  width: 260px;
  background: linear-gradient(180deg, #1e1912 0%, #140f0a 100%);
  border-left: 1px solid #2a2418;
  display: flex;
  flex-direction: column;
  z-index: 50;
  transition: width 0.25s ease;
  overflow: hidden;
}

.intel-panel.collapsed {
  width: 40px;
}

.intel-header {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(184, 155, 104, 0.2);
  gap: 6px;
  flex-shrink: 0;
}

.intel-title {
  font-size: 13px;
  font-family: "STKaiti", "KaiTi", serif;
  color: var(--gold);
  letter-spacing: 2px;
  flex: 1;
}

.intel-badge {
  font-size: 9px;
  padding: 1px 6px;
  background: rgba(200, 60, 40, 0.2);
  border: 1px solid rgba(200, 60, 40, 0.4);
  border-radius: 2px;
  color: #D07070;
  letter-spacing: 1px;
  white-space: nowrap;
}

.intel-actions {
  display: flex;
  gap: 2px;
}

.intel-action-btn {
  background: none;
  border: 1px solid rgba(184, 155, 104, 0.2);
  color: var(--text-dim);
  font-size: 11px;
  padding: 2px 6px;
  cursor: pointer;
  border-radius: 2px;
}

.intel-action-btn:hover {
  border-color: var(--gold);
  color: var(--gold);
}

.intel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 摘要栏 */
.intel-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
  padding: 6px;
  border-bottom: 1px solid rgba(139, 115, 85, 0.15);
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 6px;
  border-radius: 2px;
  background: rgba(139, 115, 85, 0.06);
}

.summary-item.danger { background: rgba(200, 60, 40, 0.08); }
.summary-item.warn { background: rgba(200, 160, 40, 0.08); }
.summary-item.good { background: rgba(90, 160, 90, 0.08); }

.summary-icon { font-size: 13px; }
.summary-val { font-size: 15px; font-weight: bold; color: var(--gold); letter-spacing: 1px; }
.summary-label { font-size: 9px; color: var(--text-dim); letter-spacing: 1px; }
.danger .summary-val { color: #D07070; }
.good .summary-val { color: #7AB87A; }

/* 过滤标签 */
.intel-filters {
  display: flex;
  gap: 3px;
  padding: 4px 6px;
  flex-wrap: wrap;
  border-bottom: 1px solid rgba(139, 115, 85, 0.1);
}

.filter-tag {
  padding: 2px 8px;
  font-size: 9px;
  font-family: "SimSun", serif;
  background: rgba(139, 115, 85, 0.08);
  border: 1px solid rgba(139, 115, 85, 0.2);
  color: var(--text-dim);
  border-radius: 2px;
  cursor: pointer;
  letter-spacing: 1px;
}

.filter-tag:hover, .filter-tag.active {
  background: rgba(184, 155, 104, 0.12);
  border-color: var(--gold);
  color: var(--gold);
}

/* 谍报列表 */
.intel-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.intel-list::-webkit-scrollbar { width: 3px; }
.intel-list::-webkit-scrollbar-thumb { background: rgba(184, 155, 104, 0.2); border-radius: 2px; }

.intel-empty {
  text-align: center;
  padding: 30px 10px;
  font-size: 12px;
  color: var(--text-dim);
}

.intel-item {
  padding: 6px 10px;
  border-bottom: 1px solid rgba(139, 115, 85, 0.08);
  cursor: pointer;
  transition: background 0.15s;
  border-left: 2px solid transparent;
}

.intel-item:hover {
  background: rgba(184, 155, 104, 0.06);
}

.intel-item.severity-critical { border-left-color: #C03030; }
.intel-item.severity-major { border-left-color: #C08030; }
.intel-item.severity-minor { border-left-color: #6A8A6A; }
.intel-item.severity-trivial { border-left-color: #5A5A5A; }

.intel-item-header {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 2px;
}

.intel-item-icon { font-size: 10px; }
.intel-item-category {
  font-size: 9px;
  color: var(--text-dim);
  letter-spacing: 1px;
  background: rgba(139, 115, 85, 0.12);
  padding: 0 4px;
  border-radius: 1px;
}

.intel-item-time {
  font-size: 8px;
  color: var(--text-dim);
  margin-left: auto;
}

.intel-item-faction {
  font-size: 9px;
  font-weight: bold;
}

.intel-item-title {
  font-size: 11px;
  color: var(--text-main);
  line-height: 1.4;
}

.intel-item-detail {
  font-size: 10px;
  color: var(--text-dim);
  margin-top: 2px;
  line-height: 1.3;
}

.intel-item-resources {
  display: flex;
  gap: 6px;
  margin-top: 3px;
}

.res-change {
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 1px;
}

.res-change.positive {
  background: rgba(90, 160, 90, 0.12);
  color: #7AB87A;
}

.res-change.negative {
  background: rgba(200, 60, 40, 0.12);
  color: #D07070;
}

/* 详情弹窗 */
.intel-detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
}

.intel-detail-card {
  background: linear-gradient(180deg, #2a2418 0%, #1a1510 100%);
  border: 2px solid var(--gold);
  border-radius: 4px;
  padding: 20px 24px;
  max-width: 480px;
  width: 90%;
  max-height: 70vh;
  overflow-y: auto;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
}

.idc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.idc-category {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 2px;
  border-bottom: 2px solid;
  padding-bottom: 2px;
}

.idc-close {
  background: none;
  border: 1px solid var(--text-dim);
  color: var(--text-dim);
  font-size: 14px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.idc-close:hover {
  color: var(--danger);
  border-color: var(--danger);
}

.idc-title {
  font-size: 16px;
  font-family: "STKaiti", "KaiTi", serif;
  color: var(--gold);
  letter-spacing: 2px;
  margin-bottom: 8px;
}

.idc-meta {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 11px;
}

.idc-faction {
  font-weight: bold;
}

.idc-time {
  color: var(--text-dim);
}

.idc-detail {
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.8;
  margin-bottom: 12px;
}

.idc-effects {
  border-top: 1px solid rgba(184, 155, 104, 0.2);
  padding-top: 10px;
}

.idc-effect-title {
  font-size: 11px;
  color: var(--gold);
  letter-spacing: 2px;
  margin-bottom: 6px;
}

.idc-effect-row {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 12px;
}

.idc-effect-key {
  color: var(--text-dim);
}

.idc-effect-val {
  font-weight: bold;
}

.idc-effect-val.positive { color: #7AB87A; }
.idc-effect-val.negative { color: #D07070; }
</style>
