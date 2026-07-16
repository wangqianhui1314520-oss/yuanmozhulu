<template>
  <Teleport to="body">
    <div class="policy-overlay" @click.self="$emit('close')" v-if="visible">
      <div class="policy-dialog animate-fade-in artifact-panel artifact-memorial">
        <!-- 标题栏 -->
        <div class="policy-header">
          <h2 class="policy-title">国策总览</h2>
          <span class="policy-subtitle">{{ overview?.faction_name || store.playerFaction?.name }} · 至正{{ store.currentYear }}年 · {{ store.currentSeason }} · 第{{ store.currentRound }}回合</span>
          <button class="refresh-btn" @click="fetchOverview" :disabled="loading" title="刷新">↻</button>
          <button class="panel-close-btn" @click="$emit('close')">✕</button>
        </div>

        <!-- 一级标签 -->
        <div class="policy-tabs">
          <button
            v-for="tab in primaryTabs"
            :key="tab.id"
            class="policy-tab"
            :class="{ active: activePrimary === tab.id }"
            @click="activePrimary = tab.id"
          >
            <span class="tab-icon">{{ tab.icon }}</span>
            <span class="tab-label">{{ tab.label }}</span>
          </button>
        </div>

        <!-- 二级标签 -->
        <div class="policy-subtabs" v-if="currentSubTabs.length > 0">
          <button
            v-for="sub in currentSubTabs"
            :key="sub.id"
            class="subtab-btn"
            :class="{ active: activeSecondary === sub.id }"
            @click="activeSecondary = sub.id"
          >
            {{ sub.label }}
          </button>
        </div>

        <!-- 内容区域 -->
        <div class="policy-content" v-if="!loading && overview">
          <!-- ═══════════ 军事 ═══════════ -->
          <div v-if="activePrimary === 'military'" class="policy-section">
            <!-- 兵力 -->
            <div v-if="activeSecondary === 'troops'" class="section-body">
              <div class="section-header-bar">
                <h4>兵力部署</h4>
                <span class="summary-badge">总兵力 {{ formatNum(mil.total_troops) }}</span>
              </div>
              <div class="data-grid" v-if="mil.troops_by_tile.length > 0">
                <div class="data-row" v-for="t in mil.troops_by_tile" :key="t.tile_id">
                  <span class="dr-name">{{ t.tile_name }}</span>
                  <span class="dr-troops">兵{{ formatNum(t.troops) }}</span>
                  <span class="dr-morale">士气{{ t.morale }}</span>
                  <span class="dr-fort">城防{{ t.fortification }}</span>
                  <span class="dr-elite" v-if="t.elite_ratio > 0">精{{ t.elite_ratio }}%</span>
                  <span class="dr-tag" v-if="t.garrison_resting">休整</span>
                </div>
              </div>
              <p class="empty-hint" v-else>所有城池暂无驻军。</p>
              <!-- 无兵力的城池 -->
              <div v-if="mil.tiles_without_troops.length > 0" class="empty-troops-section">
                <h5>无兵城池 <span class="count-badge">{{ mil.tiles_without_troops.length }}</span></h5>
                <div class="data-grid dim">
                  <div class="data-row" v-for="t in mil.tiles_without_troops" :key="t.tile_id">
                    <span class="dr-name">{{ t.tile_name }}</span>
                    <span class="dr-troops">兵0</span>
                    <span class="dr-fort">城防{{ t.fortification }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 围城 -->
            <div v-if="activeSecondary === 'siege'" class="section-body">
              <div class="section-header-bar">
                <h4>{{ mil.sieges_as_attacker.length ? '我方围攻' : '围城态势' }}</h4>
                <span class="summary-badge">{{ mil.sieges_as_attacker.length + mil.sieges_as_defender.length }}处</span>
              </div>
              <div v-if="mil.sieges_as_attacker.length > 0">
                <h5 class="sub-label">⚔ 我方围攻</h5>
                <div class="data-grid">
                  <div class="data-row siege-row" v-for="s in mil.sieges_as_attacker" :key="s.siege_id">
                    <span class="dr-name">{{ s.tile_name || s.tile_id }}</span>
                    <span class="dr-stance war">vs {{ s.defender_name }}</span>
                    <span class="dr-detail">兵{{ formatNum(s.attacker_troops) }} v {{ formatNum(s.defender_troops) }}</span>
                    <span class="dr-detail dim">城损{{ Math.round((s.wall_damage||0)*100) }}%</span>
                    <span class="dr-tag siege">第{{ s.siege_rounds }}回合</span>
                  </div>
                </div>
              </div>
              <div v-if="mil.sieges_as_defender.length > 0">
                <h5 class="sub-label">🛡 敌方围我</h5>
                <div class="data-grid">
                  <div class="data-row siege-row" v-for="s in mil.sieges_as_defender" :key="s.siege_id">
                    <span class="dr-name">{{ s.tile_name || s.tile_id }}</span>
                    <span class="dr-stance danger">犯{{ s.attacker_name }}</span>
                    <span class="dr-detail">兵{{ formatNum(s.defender_troops) }} v {{ formatNum(s.attacker_troops) }}</span>
                    <span class="dr-detail dim">城损{{ Math.round((s.wall_damage||0)*100) }}%</span>
                    <span class="dr-tag siege danger">第{{ s.siege_rounds }}回合</span>
                  </div>
                </div>
              </div>
              <p class="empty-hint" v-if="!mil.sieges_as_attacker.length && !mil.sieges_as_defender.length">当前无围城。</p>
            </div>

            <!-- 俘虏 -->
            <div v-if="activeSecondary === 'prisoner'" class="section-body">
              <div class="section-header-bar">
                <h4>俘虏名册</h4>
                <span class="summary-badge">{{ mil.prisoners_held.length + mil.prisoners_captured.length }}人</span>
              </div>
              <div v-if="mil.prisoners_held.length > 0">
                <h5 class="sub-label">🔒 我方关押</h5>
                <div class="data-grid">
                  <div class="data-row" v-for="p in mil.prisoners_held" :key="p.prisoner_id">
                    <span class="dr-name">{{ p.name || p.prisoner_id }}</span>
                    <span class="dr-detail">{{ p.rank === 'general' ? '将领' : p.rank }}</span>
                    <span class="dr-detail dim">自{{ p.captured_from }}</span>
                    <span class="dr-tag">第{{ p.captured_round }}回</span>
                  </div>
                </div>
              </div>
              <div v-if="mil.prisoners_captured.length > 0">
                <h5 class="sub-label">⚠ 我方被俘</h5>
                <div class="data-grid">
                  <div class="data-row" v-for="p in mil.prisoners_captured" :key="p.prisoner_id">
                    <span class="dr-name">{{ p.name || p.prisoner_id }}</span>
                    <span class="dr-detail">{{ p.rank === 'general' ? '将领' : p.rank }}</span>
                    <span class="dr-detail dim">陷于{{ p.held_by }}</span>
                  </div>
                </div>
              </div>
              <p class="empty-hint" v-if="!mil.prisoners_held.length && !mil.prisoners_captured.length">暂无俘虏记录。</p>
            </div>

            <!-- 瘟疫 -->
            <div v-if="activeSecondary === 'plague'" class="section-body">
              <h4>瘟疫监测</h4>
              <div v-if="mil.plague_tiles.length > 0" class="data-grid">
                <div class="data-row plague-row" v-for="pt in mil.plague_tiles" :key="pt.tile_id">
                  <span class="dr-name">{{ pt.tile_name }}</span>
                  <span class="dr-stance danger">瘟疫{{ pt.severity }}</span>
                </div>
              </div>
              <p class="empty-hint" v-else>治下无瘟疫，善。</p>
            </div>
          </div>

          <!-- ═══════════ 外交 ═══════════ -->
          <div v-if="activePrimary === 'diplomacy'" class="policy-section">
            <!-- 邦交 -->
            <div v-if="activeSecondary === 'relations'" class="section-body">
              <h4>势力邦交</h4>
              <div class="data-grid">
                <div class="data-row" v-for="r in dip.relations" :key="r.faction_id" :class="{ dead: !r.is_alive }">
                  <span class="dr-name" :style="{ color: r.color }">{{ r.faction_name }}</span>
                  <span class="dr-stance" :class="r.stance">{{ stanceLabel(r.stance) }}</span>
                  <span class="dr-attitude" :class="{ positive: r.attitude >= 60, negative: r.attitude <= 30 }">
                    好感 {{ r.attitude }}
                  </span>
                  <span class="dr-tag trade" v-if="r.trade_active">通商</span>
                  <span class="dr-tag" v-if="r.treaty_expiry > 0">约至{{ r.treaty_expiry }}回</span>
                </div>
              </div>
            </div>

            <!-- 条约 -->
            <div v-if="activeSecondary === 'treaty'" class="section-body">
              <h4>条约与联盟</h4>
              <!-- 同盟条约 -->
              <div v-if="dip.treaties.length > 0">
                <h5 class="sub-label">📜 条约</h5>
                <div class="data-grid">
                  <div class="data-row" v-for="t in dip.treaties" :key="t.treaty_id">
                    <span class="dr-name">{{ t.treaty_type || '同盟' }}</span>
                    <span class="dr-detail">与 {{ t.parties.join('、') }}</span>
                    <span class="dr-tag">第{{ t.signed_round }}-{{ t.expires_round }}回</span>
                  </div>
                </div>
              </div>
              <!-- 联盟 -->
              <div v-if="dip.coalitions.length > 0">
                <h5 class="sub-label">🏛 联盟</h5>
                <div class="data-grid">
                  <div class="data-row" v-for="c in dip.coalitions" :key="c.coalition_id">
                    <span class="dr-name">{{ c.coalition_id }}</span>
                    <span class="dr-detail">成员: {{ c.members.join('、') }}</span>
                  </div>
                </div>
              </div>
              <!-- 附庸 -->
              <div v-if="dip.vassals_of_mine.length > 0">
                <h5 class="sub-label">👑 我方附庸</h5>
                <div class="data-grid">
                  <div class="data-row" v-for="v in dip.vassals_of_mine" :key="v.faction_id">
                    <span class="dr-name">{{ v.name }}</span>
                    <span class="dr-stance vassal">附庸</span>
                  </div>
                </div>
              </div>
              <div v-if="dip.my_suzerain">
                <h5 class="sub-label">🔗 臣服于</h5>
                <div class="data-grid">
                  <div class="data-row">
                    <span class="dr-name">{{ dip.my_suzerain.name }}</span>
                    <span class="dr-stance vassal">宗主</span>
                  </div>
                </div>
              </div>
              <p class="empty-hint" v-if="!dip.treaties.length && !dip.coalitions.length && !dip.vassals_of_mine.length && !dip.my_suzerain">
                暂无条约与联盟。建议遣使通好。
              </p>
            </div>
          </div>

          <!-- ═══════════ 荒政 ═══════════ -->
          <div v-if="activePrimary === 'civil'" class="policy-section">
            <!-- 赈灾 -->
            <div v-if="activeSecondary === 'famine'" class="section-body">
              <div class="section-header-bar">
                <h4>赈灾民生</h4>
                <span class="summary-badge" :class="{ danger: civ.disaster_index > 50 }">
                  灾厄指数 {{ civ.disaster_index }}
                </span>
              </div>
              <div class="data-grid">
                <div class="data-row">
                  <span class="dr-name">总人口</span>
                  <span class="dr-value">{{ formatNum(civ.total_population) }}</span>
                </div>
                <div class="data-row">
                  <span class="dr-name">流民比例</span>
                  <span class="dr-value" :class="{ warning: civ.avg_refugee_ratio > 20 }">
                    {{ civ.avg_refugee_ratio }}%
                  </span>
                </div>
                <div class="data-row">
                  <span class="dr-name">发展度</span>
                  <span class="dr-value">{{ civ.development_level }}</span>
                </div>
                <div class="data-row">
                  <span class="dr-name">民心</span>
                  <span class="dr-value" :class="{ low: civ.realm_stability < 30 }">
                    {{ civ.realm_stability }}/100
                  </span>
                </div>
              </div>
              <!-- 全局灾害 -->
              <div v-if="civ.active_disasters.length > 0" class="disaster-block">
                <h5 class="sub-label">⚠ 当前灾害</h5>
                <div class="data-grid">
                  <div class="data-row disaster-row" v-for="d in civ.active_disasters" :key="d.type">
                    <span class="dr-name">{{ disasterName(d.type) }}</span>
                    <span class="dr-stance danger">严重度{{ d.severity || '?' }}</span>
                    <span class="dr-detail dim">{{ d.description }}</span>
                  </div>
                </div>
              </div>
              <!-- 地块灾害 -->
              <div v-if="civ.tile_disasters.length > 0" class="disaster-block">
                <h5 class="sub-label">📍 受灾城池</h5>
                <div class="data-grid">
                  <div class="data-row" v-for="(td, i) in civ.tile_disasters" :key="i">
                    <span class="dr-name">{{ td.tile_name }}</span>
                    <span class="dr-detail dim truncate">{{ disasterName(td.disaster_type) }}</span>
                    <span class="dr-detail">人口{{ formatNum(td.population) }}</span>
                  </div>
                </div>
              </div>
              <p class="empty-hint" v-if="!civ.active_disasters.length && !civ.tile_disasters.length && civ.disaster_index <= 0">
                境内安泰，暂无灾情。
              </p>
            </div>

            <!-- 天气 -->
            <div v-if="activeSecondary === 'weather'" class="section-body">
              <h4>天象观测</h4>
              <div v-if="hasWeather" class="data-grid">
                <div class="data-row" v-for="(val, key) in displayWeather" :key="key">
                  <span class="dr-name">{{ weatherLabel(key) }}</span>
                  <span class="dr-value">{{ val }}</span>
                </div>
              </div>
              <p class="empty-hint" v-else>暂无天象记录。<br/><small>四季更迭时司天监将会更新。</small></p>
            </div>
          </div>

          <!-- ═══════════ 谍报 ═══════════ -->
          <div v-if="activePrimary === 'spy'" class="policy-section">
            <!-- 谍网 -->
            <div v-if="activeSecondary === 'networks'" class="section-body">
              <h4>细作网络</h4>
              <div v-if="spyData.networks.length > 0" class="data-grid">
                <div class="data-row" v-for="net in spyData.networks" :key="net.network_id" :class="{ exposed: net.discovered }">
                  <span class="dr-name">{{ net.target_faction_name || net.target_faction_id }}</span>
                  <span class="dr-value">渗透{{ net.infiltration || 0 }}%</span>
                  <span class="dr-detail">细作{{ net.spies_count || 0 }}人</span>
                  <span class="dr-detail dim">行动点{{ net.action_points || 0 }}</span>
                  <span class="dr-tag danger" v-if="net.discovered">暴露</span>
                </div>
              </div>
              <!-- 回退到 store 数据 -->
              <div v-else-if="store.spyNetworks.length > 0" class="data-grid">
                <div class="data-row" v-for="net in store.spyNetworks" :key="net.network_id || net.target_faction_id">
                  <span class="dr-name">{{ net.target_faction || net.target_faction_id }}</span>
                  <span class="dr-value">渗透{{ net.infiltration || 0 }}%</span>
                </div>
              </div>
              <p class="empty-hint" v-else>暂无谍报活动记录。<br/><small>可在地图上右键敌方城池派遣细作。</small></p>
            </div>

            <!-- 情报 -->
            <div v-if="activeSecondary === 'intel'" class="section-body">
              <h4>情报汇总</h4>
              <div v-if="spyData.intel_reports.length > 0 || store.spyIntel.length > 0" class="data-grid">
                <div class="data-row intel-row" v-for="(intel, i) in (spyData.intel_reports.length ? spyData.intel_reports : store.spyIntel)" :key="i">
                  <span class="dr-name truncate">{{ intel.target_name || intel.title || '情报' }}</span>
                  <span class="dr-detail dim">{{ intel.content || intel.description || '' }}</span>
                  <span class="dr-tag" v-if="intel.reliability">可信{{ intel.reliability }}</span>
                  <span class="dr-tag dim" v-if="intel.round">第{{ intel.round }}回</span>
                </div>
              </div>
              <p class="empty-hint" v-else>暂无情报。<br/><small>派遣细作渗透目标势力后可获取情报。</small></p>
            </div>
          </div>

          <!-- ═══════════ 物资 ═══════════ -->
          <div v-if="activePrimary === 'resources'" class="policy-section">
            <!-- 国库 -->
            <div v-if="activeSecondary === 'treasury'" class="section-body">
              <h4>国库物资</h4>
              <div class="res-grid">
                <div class="res-card">
                  <span class="res-icon">💰</span>
                  <span class="res-label">银两</span>
                  <span class="res-value gold">{{ formatNum(res.treasury) }}</span>
                </div>
                <div class="res-card">
                  <span class="res-icon">🌾</span>
                  <span class="res-label">粮草</span>
                  <span class="res-value grain">{{ formatNum(res.grain) }}</span>
                </div>
                <div class="res-card">
                  <span class="res-icon">⚒</span>
                  <span class="res-label">军械</span>
                  <span class="res-value">{{ formatNum(res.arms) }}</span>
                </div>
                <div class="res-card">
                  <span class="res-icon">🐴</span>
                  <span class="res-label">战马</span>
                  <span class="res-value">{{ formatNum(res.horses) }}</span>
                </div>
                <div class="res-card">
                  <span class="res-icon">🏰</span>
                  <span class="res-label">领地</span>
                  <span class="res-value">{{ res.territory_count }}块</span>
                </div>
              </div>
              <div class="data-grid" style="margin-top:12px;">
                <div class="data-row">
                  <span class="dr-name">粮仓</span>
                  <span class="dr-value">{{ res.granaries.length || 0 }}座</span>
                </div>
              </div>
            </div>

            <!-- 工坊 -->
            <div v-if="activeSecondary === 'workshop'" class="section-body">
              <h4>工坊产业</h4>
              <div v-if="res.workshops.length > 0" class="data-grid">
                <div class="data-row" v-for="w in res.workshops" :key="w.building_id">
                  <span class="dr-name">{{ w.tile_name || w.tile_id }}</span>
                  <span class="dr-value">工坊 Lv.{{ w.level }}</span>
                </div>
              </div>
              <p class="empty-hint" v-else>境内暂无工坊。<br/><small>在城池中建造工坊可产出银两。</small></p>
            </div>

            <!-- 海策 -->
            <div v-if="activeSecondary === 'sea'" class="section-body">
              <h4>海策码头</h4>
              <div v-if="res.sea_related.length > 0" class="data-grid">
                <div class="data-row" v-for="s in res.sea_related" :key="s.tile_id + s.type">
                  <span class="dr-name">{{ s.tile_name || s.tile_id }}</span>
                  <span class="dr-value">{{ s.type === 'dock' ? `码头 Lv.${s.level}` : '未开发港口' }}</span>
                </div>
              </div>
              <p class="empty-hint" v-else>境内暂无海港/码头。<br/><small>占据沿海地块后可建造码头开展海上贸易。</small></p>
            </div>

            <!-- 通商 -->
            <div v-if="activeSecondary === 'trade'" class="section-body">
              <h4>通商路线</h4>
              <div v-if="activeTradeRoutes.length > 0" class="data-grid">
                <div class="data-row" v-for="tr in activeTradeRoutes" :key="tr.route_id || tr.partner">
                  <span class="dr-name">↔ {{ tr.partner }}</span>
                  <span class="dr-value gold" v-if="tr.income > 0">+{{ tr.income }}/回</span>
                  <span class="dr-tag trade" v-if="tr.active">运营中</span>
                  <span class="dr-tag dim" v-else>中断</span>
                </div>
              </div>
              <!-- 回退: 从外交邦交中提取通商 -->
              <div v-else-if="dip.relations.filter(r => r.trade_active).length > 0" class="data-grid">
                <div class="data-row" v-for="r in dip.relations.filter(r => r.trade_active)" :key="r.faction_id">
                  <span class="dr-name">↔ {{ r.faction_name }}</span>
                  <span class="dr-tag trade">通商中</span>
                </div>
              </div>
              <p class="empty-hint" v-else>暂无通商路线。<br/><small>与友好势力开通商路可增加国库收入。</small></p>
            </div>
          </div>
        </div>

        <!-- 加载中 -->
        <div class="policy-content loading-state" v-if="loading">
          <p class="empty-hint">🕰 奏报整理中……</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'

const props = defineProps<{ visible: boolean }>()
defineEmits<{ close: [] }>()

const store = useGameStore()

const activePrimary = ref('military')
const activeSecondary = ref('troops')
const loading = ref(false)
const overview = ref<any>(null)

// 从后端一次性加载聚合数据（每次面板打开时刷新）
async function fetchOverview() {
  if (!store.playerFactionId) return
  loading.value = true
  try {
    const result = await API.getPolicyOverview(store.playerFactionId)
    if (result) overview.value = result
  } catch (err) {
    console.warn('国策总览数据加载失败:', err)
    // 降级：使用 store 中的零散数据
    overview.value = null
  } finally {
    loading.value = false
  }
}

// 面板打开时加载
watch(() => store.isGameStarted, (started) => {
  if (started) fetchOverview()
}, { immediate: true })

// visible 变化时刷新（面板每次打开都拉最新数据）
watch(() => props.visible, (v: boolean) => {
  if (v) fetchOverview()
})

// ---- 计算属性：取 overview 数据或回退到 store ----
const mil = computed(() => overview.value?.military || {
  total_troops: store.totalTroops,
  troops_by_tile: store.playerTiles.map((t: any) => ({
    tile_id: t.tile_id, tile_name: t.tile_name, troops: t.troops,
    morale: t.morale, fortification: t.fortification, elite_ratio: 0, garrison_resting: false,
  })),
  tiles_without_troops: [],
  sieges_as_attacker: [],
  sieges_as_defender: [],
  prisoners_held: [],
  prisoners_captured: [],
  plague_tiles: [],
})

const dip = computed(() => overview.value?.diplomacy || {
  relations: store.livingFactions.map((f: any) => {
    const rel = store.relations
    const pid = store.playerFactionId
    const key1 = `${pid}|${f.faction_id}`
    const key2 = `${f.faction_id}|${pid}`
    const r = rel[key1] || rel[key2]
    let stance = 'neutral', attitude = 50
    if (r) { stance = r.stance; attitude = r.attitude || 50 }
    return {
      faction_id: f.faction_id, faction_name: f.name, color: f.color,
      stance, attitude, treaty_expiry: r?.treaty_expiry || 0, trade_active: r?.trade_active || false,
      coalition_id: r?.coalition_id || '', is_alive: f.is_alive !== false,
    }
  }),
  treaties: [], coalitions: [], vassals_of_mine: [], my_suzerain: null,
})

const civ = computed(() => overview.value?.civil || {
  disaster_index: store.disasterIndex,
  active_disasters: store.activeDisasters || [],
  total_population: store.totalPopulation,
  total_grain: store.playerFaction?.grain || 0,
  avg_refugee_ratio: '0.0',
  weather: {},
  development_level: store.playerFaction?.development_level || 0,
  realm_stability: store.realmStability,
  court_stability: store.courtStability,
  tile_disasters: [],
})

const spyData = computed(() => overview.value?.spy || {
  networks: store.spyNetworks || [],
  intel_reports: store.spyIntel || [],
})

const res = computed(() => overview.value?.resources || {
  treasury: store.playerFaction?.treasury || 0,
  grain: store.playerFaction?.grain || 0,
  arms: store.playerFaction?.arms || 0,
  horses: store.playerFaction?.horses || 0,
  territory_count: store.playerTiles.length,
  workshops: [], granaries: [], trade_routes: [], sea_related: [],
})

const hasWeather = computed(() => {
  const w = civ.value.weather
  return w && Object.keys(w).length > 0
})

const displayWeather = computed(() => {
  const w = civ.value.weather
  if (!w || Object.keys(w).length === 0) return {}
  // 只显示有意义的字段
  const result: Record<string, string> = {}
  for (const [k, v] of Object.entries(w)) {
    if (v === null || v === undefined || v === '') continue
    result[k] = String(v)
  }
  return result
})

const activeTradeRoutes = computed(() => {
  if (res.value.trade_routes.length > 0) return res.value.trade_routes
  // 回退：从外交面板找通商中的
  return dip.value.relations.filter((r: any) => r.trade_active)
    .map((r: any) => ({ partner: r.faction_name, active: true, income: 0, route_id: r.faction_id }))
})

// ---- 工具函数 ----
function formatNum(n: number | undefined): string {
  if (n === undefined || n === null) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function stanceLabel(s: string): string {
  const map: Record<string, string> = {
    war: '交战', neutral: '中立', truce: '停战', alliance: '同盟', vassal: '附庸',
  }
  return map[s] || s
}

function disasterName(type: string): string {
  const map: Record<string, string> = {
    flood: '洪水', drought: '干旱', locust: '蝗灾', plague: '瘟疫',
    war_devastation: '战火', refugee_wave: '流民潮', mutiny: '兵变',
    bandit_raid: '匪患', blizzard: '暴雪',
  }
  return map[type] || type
}

const weatherLabelMap: Record<string, string> = {
  current: '当前天气', condition: '天象', temperature: '气温',
  wind: '风向', rainfall: '降雨', season: '时令',
  forecast: '预报', effect: '影响', description: '描述',
  summary: '概览', type: '类型',
}

function weatherLabel(key: string): string {
  return weatherLabelMap[key] || key
}

// ---- 标签配置 ----
const primaryTabs = [
  { id: 'military', icon: '⚔', label: '军事' },
  { id: 'diplomacy', icon: '🤝', label: '外交' },
  { id: 'civil', icon: '🌾', label: '荒政' },
  { id: 'spy', icon: '🕵', label: '谍报' },
  { id: 'resources', icon: '📦', label: '物资' },
]

const subTabsMap: Record<string, { id: string; label: string }[]> = {
  military: [
    { id: 'troops', label: '兵力' },
    { id: 'siege', label: '围城' },
    { id: 'prisoner', label: '俘虏' },
    { id: 'plague', label: '瘟疫' },
  ],
  diplomacy: [
    { id: 'relations', label: '邦交' },
    { id: 'treaty', label: '条约' },
  ],
  civil: [
    { id: 'famine', label: '赈灾' },
    { id: 'weather', label: '天气' },
  ],
  spy: [
    { id: 'networks', label: '谍网' },
    { id: 'intel', label: '情报' },
  ],
  resources: [
    { id: 'treasury', label: '国库' },
    { id: 'workshop', label: '工坊' },
    { id: 'sea', label: '海策' },
    { id: 'trade', label: '通商' },
  ],
}

const currentSubTabs = computed(() => subTabsMap[activePrimary.value] || [])

// 切换一级标签时重置二级标签
watch(activePrimary, () => {
  const subs = subTabsMap[activePrimary.value]
  if (subs && subs.length > 0) activeSecondary.value = subs[0].id
})
</script>

<!-- 复用原有 CSS + 新增样式，详见下方 -->
<style scoped>
.policy-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
}

.policy-dialog {
  width: 90vw;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.4);
}

.policy-header {
  display: flex;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(180deg, var(--bg-hover) 0%, var(--border-main) 100%);
}

.policy-title {
  font-size: 20px;
  font-weight: normal;
  color: var(--text-main);
  letter-spacing: 6px;
  margin-right: 16px;
}

.policy-subtitle {
  font-size: 12px;
  color: var(--text-dim);
  flex: 1;
  letter-spacing: 2px;
}

.refresh-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  font-size: 16px;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 2px;
  margin-right: 4px;
}

.refresh-btn:hover {
  color: #b8860b;
  background: rgba(184, 155, 104, 0.08);
}

.refresh-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.panel-close-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  font-size: 16px;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 2px;
}

.panel-close-btn:hover {
  color: #8b0000;
  background: rgba(139, 0, 0, 0.08);
}

/* 一级标签 */
.policy-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-card);
}

.policy-tab {
  flex: 1;
  padding: 10px 8px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  font-family: "SimSun", serif;
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s;
}

.policy-tab:hover {
  background: rgba(139, 115, 85, 0.08);
  color: var(--text-main);
}

.policy-tab.active {
  border-bottom-color: #8b0000;
  color: #8b0000;
  background: rgba(139, 0, 0, 0.04);
}

.tab-icon { font-size: 16px; }
.tab-label { letter-spacing: 2px; }

/* 二级标签 */
.policy-subtabs {
  display: flex;
  gap: 2px;
  padding: 6px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-light);
}

.subtab-btn {
  padding: 4px 14px;
  font-size: 12px;
  font-family: "SimSun", serif;
  background: none;
  border: 1px solid transparent;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 2px;
  letter-spacing: 1px;
  transition: all 0.2s;
}

.subtab-btn:hover {
  background: rgba(139, 115, 85, 0.1);
}

.subtab-btn.active {
  background: rgba(139, 0, 0, 0.1);
  border-color: rgba(139, 0, 0, 0.3);
  color: #8b0000;
}

/* 内容区域 */
.policy-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.section-body h4 {
  font-size: 15px;
  font-weight: normal;
  color: var(--text-main);
  margin-bottom: 12px;
  letter-spacing: 2px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-light);
}

.section-body h5 {
  font-size: 13px;
  color: var(--text-secondary);
  letter-spacing: 1px;
  margin: 12px 0 6px;
}

.section-header-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-light);
}

.section-header-bar h4 {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.summary-badge {
  font-size: 11px;
  color: var(--text-dim);
  background: rgba(139, 115, 85, 0.08);
  padding: 2px 8px;
  border-radius: 2px;
  letter-spacing: 1px;
}

.summary-badge.danger { color: #8b0000; background: rgba(139, 0, 0, 0.08); }

.count-badge {
  font-size: 11px;
  color: var(--text-dim);
  background: rgba(139, 115, 85, 0.06);
  padding: 1px 6px;
  border-radius: 2px;
  margin-left: 6px;
}

.sub-label {
  font-size: 13px;
  color: var(--text-secondary);
  letter-spacing: 1px;
  margin: 12px 0 6px;
}

.data-grid {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.data-grid.dim { opacity: 0.75; }

.data-row {
  display: flex;
  align-items: center;
  padding: 7px 10px;
  font-size: 13px;
  border-bottom: 1px dotted var(--border-light);
  gap: 12px;
}

.data-row.dead { opacity: 0.35; }

.dr-name {
  flex: 1;
  color: var(--text-main);
  font-weight: bold;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dr-troops { color: #c44b3c; white-space: nowrap; }
.dr-morale { color: #5b8c5a; white-space: nowrap; }
.dr-fort { color: var(--text-dim); white-space: nowrap; }
.dr-elite { color: #b8860b; font-size: 11px; white-space: nowrap; }
.dr-stance { color: var(--text-secondary); white-space: nowrap; }
.dr-stance.war { color: #c44b3c; }
.dr-stance.vassal { color: #8b6914; }
.dr-stance.danger { color: #c44b3c; }
.dr-attitude { color: var(--text-dim); white-space: nowrap; }
.dr-attitude.positive { color: #5b8c5a; }
.dr-attitude.negative { color: #c44b3c; }
.dr-detail { color: var(--text-secondary); font-size: 12px; white-space: nowrap; }
.dr-detail.dim { color: var(--text-dim); }
.dr-value { color: var(--text-main); font-weight: bold; white-space: nowrap; }
.dr-value.warning { color: #b8860b; }
.dr-value.low { color: #c44b3c; }

.dr-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 2px;
  background: rgba(139, 115, 85, 0.08);
  color: var(--text-dim);
  white-space: nowrap;
}

.dr-tag.trade { background: rgba(91, 140, 90, 0.12); color: #5b8c5a; }
.dr-tag.siege { background: rgba(196, 75, 60, 0.08); color: #c44b3c; }
.dr-tag.danger { background: rgba(139, 0, 0, 0.1); color: #8b0000; }
.dr-tag.dim { opacity: 0.6; }

.truncate {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gold-text, .gold { color: #b8860b; }
.grain-text, .grain { color: #5b8c5a; }
.gold { color: #b8860b; }
.grain { color: #5b8c5a; }

.empty-hint {
  text-align: center;
  padding: 32px 16px;
  color: var(--text-dim);
  font-size: 13px;
  letter-spacing: 2px;
  line-height: 1.8;
}

.empty-hint small {
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}

/* 物资卡片网格 */
.res-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}

.res-card {
  background: rgba(139, 115, 85, 0.04);
  border: 1px solid var(--border-light);
  border-radius: 3px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.res-icon { font-size: 22px; }
.res-label { font-size: 12px; color: var(--text-dim); letter-spacing: 2px; }
.res-value { font-size: 18px; font-weight: bold; color: var(--text-main); }

/* 特殊行样式 */
.siege-row { background: rgba(196, 75, 60, 0.03); }
.plague-row { background: rgba(139, 0, 0, 0.03); }
.disaster-row { background: rgba(184, 155, 104, 0.03); }
.intel-row { background: rgba(184, 155, 104, 0.02); }
.exposed { border-left: 2px solid #8b0000; }

.empty-troops-section {
  margin-top: 16px;
}

.disaster-block {
  margin-top: 12px;
}

.animate-fade-in {
  animation: fadeIn 0.25s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}
</style>
