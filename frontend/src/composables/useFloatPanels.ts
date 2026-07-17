/**
 * useFloatPanels - 浮动面板管理 Composable
 * 
 * 将 FloatPanels.vue 中的面板逻辑提取为独立的 composable
 * 每个面板的逻辑集中在对应的 composable 中，减少组件复杂度
 * 
 * 当前是渐进式重构：新代码使用此 composable，旧 FloatPanels.vue 保持兼容
 */
import { ref, computed, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import { useFormat } from '@/composables/useFormat'
import * as API from '@/services/api'

export function useFloatPanels() {
  const store = useGameStore()
  const { formatNum } = useFormat()

  // ===== 通用面板状态 =====
  const playerFaction = computed(() => store.playerFaction)

  // ===== 国库面板 =====
  const treasuryTab = ref<'overview' | 'income' | 'expense'>('overview')

  function estimateTaxIncome(): number {
    const pop = store.totalPopulation
    const tiles = store.playerTiles.length
    return Math.floor(pop * 0.05 + tiles * 30 + (playerFaction.value?.development_level || 20) * 5)
  }

  function estimateGrainOutput(): number {
    const farmCount = store.playerTiles.filter(t => t.tile_type === 'farmland').length
    return Math.floor(farmCount * 120 + store.totalPopulation * 0.03)
  }

  function estimateTradeIncome(): number {
    const portCount = store.playerTiles.filter(t => t.is_port).length
    const tradeCount = (store as any).tradeRoutes?.length || 0
    return portCount * 50 + tradeCount * 100
  }

  function estimateWorkshopOutput(): number {
    return Math.floor(store.playerTiles.filter(t => (t as any).armory > 0 || (t as any).stable > 0).length * 40)
  }

  function estimateMilitaryCost(): number {
    return Math.floor(store.totalTroops * 2 + store.playerTiles.length * 20)
  }

  function estimateNetIncome(): number {
    const income = estimateTaxIncome() + estimateTradeIncome()
    const expense = estimateMilitaryCost() + (store.officials.length * 50) + Math.max(100, store.playerTiles.length * 25) + Math.max(50, Object.keys(store.relations || {}).length * 100)
    return income - expense
  }

  function countTileType(type: string): number {
    return store.playerTiles.filter(t => t.tile_type === type).length
  }

  // ===== 外交面板 =====
  const diploFeedback = ref<{ text: string; type: string }>({ text: '', type: '' })
  const diploTimer = ref<number | null>(null)
  const diploRecommendations = ref<any[]>([])
  const diploRecLoading = ref(false)

  function getStance(targetFactionId: string): string {
    const rels = store.relations
    for (const [key, rel] of Object.entries(rels)) {
      const parts = key.split('|')
      if (parts.includes(targetFactionId)) {
        return (rel as any).stance || 'neutral'
      }
    }
    return 'neutral'
  }

  function getStanceLabel(targetFactionId: string): string {
    const labels: Record<string, string> = {
      war: '⚔ 交战', neutral: '⊘ 中立', truce: '☮ 停战',
      alliance: '🤝 同盟', vassal: '🏰 藩属',
    }
    return labels[getStance(targetFactionId)] || '⊘ 中立'
  }

  function getAttitude(targetFactionId: string): number {
    const rels = store.relations
    for (const [key, rel] of Object.entries(rels)) {
      const parts = key.split('|')
      if (parts.includes(targetFactionId)) {
        return (rel as any).attitude ?? 50
      }
    }
    return 50
  }

  async function doDiplomacy(targetFaction: string, action: string) {
    const faction = store.factions[targetFaction]
    const name = faction?.name || targetFaction
    diploFeedback.value = { text: `正在向${name}${action === 'war' ? '宣战' : '进行外交'}...`, type: 'info' }

    try {
      let result: any
      switch (action) {
        case 'tribute':
          result = await store.submitCommand('diplomacy', { target_faction: targetFaction, diplomacy_type: 'tribute' })
          break
        case 'alliance':
          result = await store.changeDiplomacy(targetFaction, 'alliance')
          break
        case 'trade':
          result = await store.openTrade(targetFaction)
          break
        case 'marriage':
          result = await store.marryTo(targetFaction)
          break
        case 'truce':
          result = await store.changeDiplomacy(targetFaction, 'truce')
          break
        case 'war':
          result = await store.changeDiplomacy(targetFaction, 'war')
          break
        default:
          result = await store.submitCommand('diplomacy', { target_faction: targetFaction, diplomacy_type: action })
      }

      const msg = result?.message || result?.msg || '外交行动已提交'
      diploFeedback.value = { text: msg, type: 'success' }
    } catch (err: any) {
      diploFeedback.value = { text: err?.message || '外交行动失败', type: 'error' }
    }

    if (diploTimer.value) clearTimeout(diploTimer.value)
    diploTimer.value = setTimeout(() => { diploFeedback.value = { text: '', type: '' } }, 4000)
  }

  async function loadDiplomacyRecommendations() {
    if (!store.playerFactionId) return
    diploRecLoading.value = true
    try {
      const result = await API.getDiplomaticRecommendations(store.playerFactionId)
      diploRecommendations.value = result?.recommendations || result || []
    } catch {
      diploRecommendations.value = []
    } finally {
      diploRecLoading.value = false
    }
  }

  // ===== 朝堂面板 =====
  const courtTab = ref<'overview' | 'policies' | 'officials' | 'decrees'>('overview')
  const activePolicyCat = ref('civil')
  const officialsData = ref<any[]>([])
  const policyData = ref<any>(null)
  const decreeText = ref('')
  const newOfficialName = ref('')
  const newOfficialPosition = ref('')
  const newOfficialAbility = ref(50)
  const newOfficialLoyalty = ref(60)
  const courtOverviewData = ref<any>(null)
  const debateHistory = ref<any[]>([])
  const courtOverviewLoading = ref(false)

  const policyCategories = [
    { key: 'civil', icon: '🏛', name: '内政' },
    { key: 'military', icon: '⚔', name: '军事' },
    { key: 'diplomacy', icon: '🤝', name: '外交' },
    { key: 'economy', icon: '💰', name: '经济' },
  ]

  const quickDecrees = [
    '大赦天下，减免赋税三成',
    '全国征兵，整军备战',
    '开科取士，选拔贤能',
    '兴修水利，劝课农桑',
    '遣使通好，改善邦交',
  ]

  const currentPolicyBranches = computed(() => {
    if (!policyData.value) return []
    const cat = policyData.value[activePolicyCat.value]
    return cat?.branches || []
  })

  function isPolicyUnlocked(policyId: string): boolean {
    return (playerFaction.value?.unlocked_policies || []).includes(policyId)
  }

  function canUnlockPolicy(tier: any): boolean {
    if (isPolicyUnlocked(tier.id)) return false
    if ((playerFaction.value?.treasury || 0) < tier.cost) return false
    if (tier.prerequisites?.length) {
      return tier.prerequisites.every((p: string) => isPolicyUnlocked(p))
    }
    return true
  }

  function getLockReason(tier: any): string {
    if ((playerFaction.value?.treasury || 0) < tier.cost) return '银两不足'
    if (tier.prerequisites?.length && !tier.prerequisites.every((p: string) => isPolicyUnlocked(p))) return '前置未解锁'
    return '条件不足'
  }

  function effectLabel(key: string): string {
    const labels: Record<string, string> = {
      treasury: '国库', grain: '粮草', troops: '兵力', morale: '士气',
      court_stability: '朝纲', realm_stability: '民心', reputation: '声望',
      development: '发展', arms: '军械', horses: '战马',
    }
    return labels[key] || key
  }

  function getStatClass(val: number): string {
    if (val >= 70) return 'stat-good'
    if (val >= 40) return 'stat-warn'
    return 'stat-danger'
  }

  function loyaltyColor(val: number): string {
    if (val >= 70) return '#8EB89B'
    if (val >= 40) return '#C9AC78'
    return '#E07060'
  }

  async function loadCourtData() {
    if (!store.playerFactionId) return
    try {
      const [officials, policies] = await Promise.all([
        API.getFactionOfficials(store.playerFactionId).catch(() => null),
        API.getPolicies().catch(() => null),
      ])
      if (officials) officialsData.value = officials?.officials || officials || []
      if (policies) policyData.value = policies
    } catch (e) {
      console.warn('[Court] 加载数据失败:', e)
    }
  }

  async function refreshCourtData() {
    if (!store.playerFactionId) return
    courtOverviewLoading.value = true
    try {
      const [overview, debateH] = await Promise.all([
        API.getCourtOverview(store.playerFactionId).catch(() => null),
        API.getDebateHistory(store.playerFactionId).catch(() => null),
      ])
      if (overview) courtOverviewData.value = overview
      if (debateH) debateHistory.value = debateH?.history || []
    } catch (e) {
      console.warn('[Court] 加载朝堂数据失败:', e)
    } finally {
      courtOverviewLoading.value = false
    }
  }

  async function unlockPolicy(tier: any) {
    try {
      await API.unlockPolicy({ faction_id: store.playerFactionId, policy_id: tier.id, cost: tier.cost || 0 })
      await store.refreshWorldState()
      await loadCourtData()
    } catch (e) {
      console.warn('国策解锁失败:', e)
    }
  }

  async function appointOfficial() {
    if (!newOfficialName.value.trim() || !newOfficialPosition.value.trim()) return
    try {
      await store.appointOfficial(
        newOfficialName.value.trim(),
        newOfficialPosition.value.trim(),
        newOfficialAbility.value,
        newOfficialLoyalty.value,
      )
      newOfficialName.value = ''
      newOfficialPosition.value = ''
      await loadCourtData()
      await store.refreshWorldState()
    } catch (e) {
      console.warn('官员任命失败:', e)
    }
  }

  async function dismissOfficer(officialId: string) {
    try {
      await store.dismissOfficial(officialId)
      await loadCourtData()
      await store.refreshWorldState()
    } catch (e) { console.warn('罢免官员失败:', e) }
  }

  async function executeOfficer(officialId: string) {
    try {
      await store.executeOfficial(officialId)
      await loadCourtData()
      await store.refreshWorldState()
    } catch (e) { console.warn('处决官员失败:', e) }
  }

  async function publishDecree() {
    if (!decreeText.value.trim()) return
    try {
      await API.issueDecree({ faction_id: store.playerFactionId, text: decreeText.value.trim() })
      decreeText.value = ''
      await store.refreshWorldState()
    } catch (e) { console.warn('敕令颁布失败:', e) }
  }

  function openCourtDebate() {
    const event = new CustomEvent('open-court-debate', { detail: {} })
    window.dispatchEvent(event)
  }

  function issueDecree() {
    courtTab.value = 'decrees'
  }

  async function doSacrifice() {
    try {
      await API.performSacrifice(store.playerFactionId)
      await store.refreshWorldState()
    } catch (e) { console.warn('祭祀失败:', e) }
  }

  async function doRecruitOfficials() {
    try {
      await API.recruitOfficials(store.playerFactionId)
      await loadCourtData()
      await store.refreshWorldState()
    } catch (e) { console.warn('科举选拔失败:', e) }
  }

  // ===== AI推演面板 =====
  const aiLoading = ref(false)
  const aiResult = ref<any>(null)

  async function runAIStrategy() {
    aiLoading.value = true
    aiResult.value = null
    try {
      const result = await API.strategicAdvice({
        faction_id: store.playerFactionId,
        question: '请分析当前天下形势，给出详细的战略建议',
        world_state: {
          factions: store.factions,
          tiles: store.tiles,
          relations: store.relations,
          current_round: store.currentRound,
          current_season: store.currentSeason,
          player_faction_id: store.playerFactionId,
        },
        round: store.currentRound,
      })
      aiResult.value = result
    } catch (e) {
      console.warn('AI推演失败:', e)
    } finally {
      aiLoading.value = false
    }
  }

  // ===== 面板自动加载 =====
  watch(() => store.activePanel, async (panel) => {
    if (panel === 'diplomacy' && store.playerFactionId) {
      await loadDiplomacyRecommendations()
    }
    if (panel === 'court') {
      await loadCourtData()
      refreshCourtData()
    }
  })

  return {
    // 通用
    playerFaction,
    formatNum,
    // 国库
    treasuryTab,
    estimateTaxIncome,
    estimateGrainOutput,
    estimateTradeIncome,
    estimateWorkshopOutput,
    estimateMilitaryCost,
    estimateNetIncome,
    countTileType,
    // 外交
    diploFeedback,
    diploRecommendations,
    diploRecLoading,
    getStance,
    getStanceLabel,
    getAttitude,
    doDiplomacy,
    loadDiplomacyRecommendations,
    // 朝堂
    courtTab,
    activePolicyCat,
    officialsData,
    policyData,
    decreeText,
    newOfficialName,
    newOfficialPosition,
    newOfficialAbility,
    newOfficialLoyalty,
    courtOverviewData,
    debateHistory,
    courtOverviewLoading,
    policyCategories,
    quickDecrees,
    currentPolicyBranches,
    isPolicyUnlocked,
    canUnlockPolicy,
    getLockReason,
    effectLabel,
    getStatClass,
    loyaltyColor,
    loadCourtData,
    refreshCourtData,
    unlockPolicy,
    appointOfficial,
    dismissOfficer,
    executeOfficer,
    publishDecree,
    openCourtDebate,
    issueDecree,
    doSacrifice,
    doRecruitOfficials,
    // AI推演
    aiLoading,
    aiResult,
    runAIStrategy,
  }
}
