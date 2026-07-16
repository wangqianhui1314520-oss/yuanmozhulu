<template>
  <!-- 科技树面板 — 四大分支可视化 -->
  <Transition name="panel-slide">
    <div v-if="visible" class="tech-tree-panel artifact-panel artifact-codex">
      <!-- 头部 -->
      <div class="panel-header">
        <div class="header-left">
          <span class="header-icon">📜</span>
          <span class="header-title">变法图强</span>
        </div>
        <div class="header-right">
          <span class="treasury-badge">💰 {{ store.treasury.toLocaleString() }} 两</span>
          <span class="stat-badge">已研究 {{ store.totalUnlocked }} 项</span>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>
      </div>

      <!-- 分类标签 -->
      <div class="category-tabs">
        <button
          v-for="cat in store.categories"
          :key="cat.id"
          class="cat-tab"
          :class="{ active: activeCategory === cat.id }"
          @click="activeCategory = cat.id"
        >
          <span class="cat-icon">{{ cat.icon }}</span>
          <span class="cat-name">{{ cat.name }}</span>
        </button>
      </div>

      <!-- 科技树主体 -->
      <div class="tech-content">
        <div v-if="store.isLoading" class="loading-state">
          <div class="loading-spinner" />
          <span>加载科技树...</span>
        </div>

        <div v-else-if="store.errorMessage" class="error-state">
          <span class="error-icon">⚠️</span>
          <span>{{ store.errorMessage }}</span>
          <button class="retry-btn" @click="store.loadTechTree(props.factionId)">重试</button>
        </div>

        <template v-else>
          <!-- 分支列表 -->
          <div
            v-for="branch in activeBranches"
            :key="branch.id"
            class="tech-branch"
          >
            <div class="branch-header">
              <span class="branch-name">{{ branch.name }}</span>
              <span class="branch-desc">{{ branch.description }}</span>
            </div>

            <!-- 科技节点（三层级联） -->
            <div class="tech-nodes">
              <div
                v-for="node in branch.nodes"
                :key="node.id"
                class="tech-node"
                :class="{
                  unlocked: node.unlocked,
                  available: node.available && !node.unlocked,
                  locked: !node.unlocked && !node.available,
                }"
                @click="tryResearch(node)"
              >
                <!-- 节点图标 -->
                <div class="node-icon">
                  <span v-if="node.unlocked">✅</span>
                  <span v-else-if="node.available">🔓</span>
                  <span v-else>🔒</span>
                </div>

                <!-- 节点信息 -->
                <div class="node-info">
                  <div class="node-name">
                    <span class="tier-badge">T{{ node.tier }}</span>
                    {{ node.name }}
                  </div>
                  <div class="node-desc">{{ node.description }}</div>

                  <!-- 效果列表 -->
                  <div v-if="node.effects && Object.keys(node.effects).length" class="node-effects">
                    <span
                      v-for="(val, key) in node.effects"
                      :key="key"
                      class="effect-tag"
                      :class="{ positive: val > 0, negative: val < 0 }"
                    >
                      {{ formatEffect(key, val) }}
                    </span>
                  </div>

                  <!-- 操作区 -->
                  <div v-if="node.available && !node.unlocked" class="node-actions">
                    <button
                      class="research-btn"
                      :class="{ affordable: store.canAffordResearch(node.cost) }"
                      :disabled="!store.canAffordResearch(node.cost)"
                      @click.stop="tryResearch(node)"
                    >
                      💰 {{ node.cost }} 两 研究
                    </button>
                    <span v-if="!store.canAffordResearch(node.cost)" class="cost-hint">银两不足</span>
                  </div>
                </div>

                <!-- 连接线 -->
                <div v-if="node.tier > 1" class="node-connector" />
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="!activeBranches.length && !store.isLoading" class="empty-state">
            暂无科技树数据
          </div>
        </template>
      </div>

      <!-- 研究结果提示 -->
      <Transition name="toast-fade">
        <div v-if="store.showResearchResult && store.researchResult" class="research-toast" :class="{ error: !store.researchResult.success }">
          {{ store.researchResult.message }}
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useTechTreeStore } from '@/stores/techTreeStore'
import type { PolicyNode } from '@/stores/techTreeStore'

const props = defineProps<{
  visible: boolean
  factionId: string
}>()

const emit = defineEmits<{
  close: []
}>()

const store = useTechTreeStore()
const activeCategory = ref('civil')

// 监听打开状态和势力ID变化
watch([() => props.visible, () => props.factionId], ([v, fid]) => {
  if (v && fid) {
    store.loadTechTree(fid)
  }
})

const activeBranches = computed(() => {
  const cat = store.categories.find(c => c.id === activeCategory.value)
  return cat?.branches || []
})

/** 尝试研究 */
async function tryResearch(node: PolicyNode) {
  if (!node.available || node.unlocked) return
  if (store.treasury < node.cost) return
  await store.research(props.factionId, node.id)
}

/** 格式化效果 */
function formatEffect(key: string, val: number): string {
  const names: Record<string, string> = {
    grain_production: '粮产',
    population_growth: '人口',
    realm_stability: '民心',
    court_stability: '朝堂',
    reputation: '声望',
    troop_power: '战力',
    morale_bonus: '士气',
    siege_bonus: '攻城',
    fortification_bonus: '城防',
    tax_efficiency: '税收',
    treasury_income: '国库',
    trade_income: '贸易',
    arms_production: '军械',
    construction_speed: '建造',
    garrison_cost_reduction: '驻军消耗',
    march_speed: '行军',
    naval_power: '水师',
    famine_resistance: '抗灾',
    plague_reduction: '防疫',
    flood_reduction: '防洪',
    land_fertility: '肥力',
    corruption_reduction: '反腐',
    spy_success_rate: '谍报',
    alliance_strength: '同盟',
    grain_storage: '储粮',
    border_defense: '边防',
    elite_troops_ratio: '精锐',
    march_cost_reduction: '军耗',
    reinforce_speed: '援军',
    trade_protection: '商路',
    rare_goods: '奇珍',
    naval_range: '航程',
    intel_gathering: '情报',
    culture_bonus: '文教',
    puppet_control: '傀儡',
    vassal_acceptance: '附庸',
    coalitions_leadership: '盟主',
    ally_morale: '盟军士气',
    interest_income: '利息',
    trade_goods: '商品',
    trade_speed: '流通',
    development_speed: '发展',
    official_ability_bonus: '官员',
  }
  const name = names[key] || key
  const sign = val > 0 ? '+' : ''
  return `${name} ${sign}${val}${val < 1 && val > -1 ? '%' : ''}`
}
</script>

<style scoped>
.tech-tree-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 480px;
  max-width: 92vw;
  z-index: 9000;
  display: flex;
  flex-direction: column;
  font-family: 'FangSong', 'FangSong_GB2312', 'SimSun', serif;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.5);
}

/* 头部 */
.panel-header {
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(184, 150, 62, 0.2);
  background: rgba(184, 150, 62, 0.05);
}
.header-left { display: flex; align-items: center; gap: 8px; }
.header-icon { font-size: 22px; }
.header-title { font-size: 18px; font-weight: bold; color: #d4b65e; letter-spacing: 2px; }
.header-right { display: flex; align-items: center; gap: 10px; }
.treasury-badge {
  font-size: 12px; color: #b8963e; background: rgba(184, 150, 62, 0.1);
  padding: 2px 8px; border-radius: 10px; border: 1px solid rgba(184, 150, 62, 0.2);
}
.stat-badge { font-size: 12px; color: #8b7355; }
.close-btn {
  background: none; border: 1px solid rgba(139, 115, 85, 0.3); color: #8b7355;
  width: 26px; height: 26px; border-radius: 4px; cursor: pointer;
  font-size: 14px; display: flex; align-items: center; justify-content: center;
}
.close-btn:hover { border-color: #b8963e; color: #b8963e; }

/* 分类标签 */
.category-tabs {
  display: flex; padding: 8px 12px; gap: 6px;
  border-bottom: 1px solid rgba(184, 150, 62, 0.1);
  background: rgba(0, 0, 0, 0.15);
  overflow-x: auto;
}
.cat-tab {
  padding: 6px 14px; border-radius: 4px; border: 1px solid rgba(139, 115, 85, 0.2);
  background: transparent; color: #8b7355; cursor: pointer; font-family: inherit;
  font-size: 13px; display: flex; align-items: center; gap: 5px; white-space: nowrap;
  transition: all 0.2s;
}
.cat-tab:hover { border-color: #b8963e; }
.cat-tab.active {
  background: rgba(184, 150, 62, 0.12); border-color: #b8963e; color: #d4b65e;
}
.cat-icon { font-size: 16px; }
.cat-name { letter-spacing: 1px; }

/* 科技内容 */
.tech-content {
  flex: 1; overflow-y: auto; padding: 12px;
}
.tech-content::-webkit-scrollbar { width: 4px; }
.tech-content::-webkit-scrollbar-thumb { background: rgba(184, 150, 62, 0.2); border-radius: 2px; }

/* 分支 */
.tech-branch {
  margin-bottom: 16px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(184, 150, 62, 0.08);
  border-radius: 6px;
  overflow: hidden;
}
.branch-header {
  padding: 10px 14px;
  background: rgba(184, 150, 62, 0.06);
  border-bottom: 1px solid rgba(184, 150, 62, 0.08);
  display: flex; align-items: center; gap: 10px;
}
.branch-name { font-size: 14px; font-weight: bold; color: #c0a860; }
.branch-desc { font-size: 12px; color: #6b5a40; }

/* 科技节点 */
.tech-nodes { padding: 8px 12px; }
.tech-node {
  display: flex; gap: 10px; padding: 10px;
  border-radius: 6px; margin-bottom: 6px; position: relative;
  transition: all 0.2s;
}
.tech-node.available { background: rgba(100, 180, 80, 0.06); cursor: pointer; }
.tech-node.available:hover { background: rgba(100, 180, 80, 0.12); }
.tech-node.unlocked { background: rgba(184, 150, 62, 0.08); }
.tech-node.locked { background: rgba(0, 0, 0, 0.1); opacity: 0.6; }

.node-icon { font-size: 20px; min-width: 28px; text-align: center; padding-top: 2px; }

.node-info { flex: 1; min-width: 0; }
.node-name {
  font-size: 14px; font-weight: bold; color: #c0b090;
  display: flex; align-items: center; gap: 6px;
}
.tier-badge {
  font-size: 10px; color: #8b7355; background: rgba(139, 115, 85, 0.15);
  padding: 0px 5px; border-radius: 8px;
}
.node-desc { font-size: 12px; color: #7a6a50; margin-top: 3px; line-height: 1.5; }

.node-effects { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.effect-tag {
  font-size: 11px; padding: 1px 7px; border-radius: 10px; white-space: nowrap;
}
.effect-tag.positive { background: rgba(80, 160, 60, 0.12); color: #6ab04c; }
.effect-tag.negative { background: rgba(200, 60, 60, 0.12); color: #c06060; }

.node-actions { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.research-btn {
  padding: 5px 14px; border-radius: 4px; border: 1px solid rgba(139, 115, 85, 0.3);
  background: transparent; color: #8b7355; cursor: pointer;
  font-family: inherit; font-size: 12px; transition: all 0.2s;
}
.research-btn.affordable { border-color: #b8963e; color: #d4b65e; }
.research-btn.affordable:hover { background: rgba(184, 150, 62, 0.15); }
.research-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.cost-hint { font-size: 11px; color: #a04040; }

/* 连接线 */
.node-connector {
  position: absolute; left: 34px; top: -8px; width: 2px; height: 12px;
  background: rgba(184, 150, 62, 0.2);
}

/* 结果提示 */
.research-toast {
  position: absolute; bottom: 16px; left: 16px; right: 16px;
  padding: 10px 16px; background: rgba(80, 160, 60, 0.15);
  border: 1px solid rgba(106, 176, 76, 0.4); border-radius: 6px;
  color: #6ab04c; font-size: 13px; text-align: center;
}
.research-toast.error {
  background: rgba(200, 60, 60, 0.15); border-color: rgba(200, 60, 60, 0.4); color: #c06060;
}

/* 加载 */
.loading-state {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 40px; color: #8b7355;
}
.loading-spinner {
  width: 32px; height: 32px; border: 3px solid rgba(184, 150, 62, 0.2);
  border-top-color: #b8963e; border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state { text-align: center; padding: 40px; color: #6b5a40; }

.error-state {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 40px; color: #c06060;
}
.error-icon { font-size: 28px; }
.retry-btn {
  padding: 6px 20px; border-radius: 4px; border: 1px solid #b8963e;
  background: rgba(184, 150, 62, 0.1); color: #d4b65e;
  cursor: pointer; font-family: inherit; font-size: 13px;
}
.retry-btn:hover { background: rgba(184, 150, 62, 0.2); }

/* 动画 */
.panel-slide-enter-active { transition: all 0.35s cubic-bezier(0.22, 0.61, 0.36, 1); }
.panel-slide-leave-active { transition: all 0.25s ease-in; }
.panel-slide-enter-from { transform: translateX(100%); opacity: 0; }
.panel-slide-leave-to { transform: translateX(60px); opacity: 0; }

.toast-fade-enter-active { transition: all 0.3s ease; }
.toast-fade-leave-active { transition: all 0.2s ease; }
.toast-fade-enter-from,
.toast-fade-leave-to { opacity: 0; transform: translateY(10px); }
</style>
