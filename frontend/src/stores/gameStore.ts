/**
 * 游戏状态管理 - Pinia Store
 * 
 * 原则:
 * - 前端不存游戏核心逻辑，纯展示层
 * - 所有游戏数据唯一源在后端
 * - 每回合后强制拉取最新 world_state
 * - 所有面板打开时实时请求后端数据
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { WorldState, FactionState, TileState, GameEvent, PanelType } from '@/types'
import * as API from '@/services/api'

export const useGameStore = defineStore('game', () => {
  // ===== 游戏核心状态（全部从后端同步） =====
  const currentRound = ref(0)
  const currentYear = ref(1351)
  const currentMonth = ref(4)
  const currentSeason = ref('春')
  const gameMode = ref<'player_turn' | 'ai_watch'>('player_turn')
  const isProcessing = ref(false)
  const isGameStarted = ref(false)
  const isGameActive = ref(false)

  // ===== 势力与地块 =====
  const playerFactionId = ref('')
  const factions = ref<Record<string, FactionState>>({})
  const tiles = ref<Record<string, TileState>>({})

  // ===== 外交 =====
  const relations = ref<Record<string, any>>({})

  // ===== 事件 =====
  const events = ref<GameEvent[]>([])
  const decrees = ref<any[]>([])

  // ===== 地盘变更 =====
  const tileChanges = ref<any[]>([])
  const tileChangesThisRound = ref<any[]>([])

  // ===== 朝堂 =====
  const courtStability = ref(50)
  const realmStability = ref(50)
  const reputation = ref(50)
  const factionLoyalties = ref<Record<string, number>>({})
  const officials = ref<any[]>([])

  // ===== 谍报 =====
  const spyNetworks = ref<any[]>([])
  const spyIntel = ref<any[]>([])

  // ===== 叛军（3.2） =====
  const rebelArmies = ref<any[]>([])

  // ===== 灾害 =====
  const disasterIndex = ref(0)
  const activeDisasters = ref<any[]>([])

  // ===== 外交子系统 =====
  const coalitions = ref<Record<string, any>>({})
  const tradeRoutes = ref<any[]>([])
  const vassalRelations = ref<Record<string, string>>({})
  const allianceTreaties = ref<any[]>([])
  /** 2026-07-15: 展开的外交关系数组（来自 game/status 顶层 diplomatic_relations） */
  const diplomaticRelations = ref<Array<{
    target_faction_id: string
    target_name: string
    stance: string
    attitude: number
    relation_key: string
  }>>([])

  // ===== 权责追踪 =====
  const responsibilityStats = ref<any>(null)

  // ===== 结局 =====
  const showEnding = ref(false)
  const endingData = ref<any>(null)
  const gameStatistics = ref<any>(null)

  // ===== UI状态 =====
  const activePanel = ref<PanelType>('')
  const selectedTile = ref('')

  // ===== 圣旨指令队列（地图右键生成，自动填充到圣旨框） =====
  const pendingEdictCommands = ref<{ action: string; params: Record<string, any>; label: string }[]>([])

  // ===== 出征面板状态 =====
  const showMarchPanel = ref(false)
  const marchTargetTileId = ref('')  // 预选目标地块

  // ===== 战争面板状态 (v3.0) =====
  const showWarPanel = ref(false)
  const warPanelData = ref<any>(null)  // 预选战争数据（用于打开和平谈判）
  const showPeacePanel = ref(false)
  const activeWars = ref<any[]>([])

  // ===== 路线显示开关 =====
  const showRoutes = ref(true)  // 控制所有路线（行军/谍报/通商）的显示/隐藏
  const activeRoutes = ref<Array<{ type: 'march' | 'spy' | 'trade'; path: string[]; id: string }>>([])

  // ===== 图层系统数据 v2.0（供HexMapView 14层渲染） =====
  /** 迷雾可见地块ID集合 */
  const fogVisibleTileIds = ref<Set<string>>(new Set())
  /** 行军路线 */
  const activeMarchRoutes = ref<Array<{
    id: string; type: 'march'|'retreat'|'supply'
    path: string[]; factionId: string; color?: string
  }>>([])
  /** 补给线 */
  const activeSupplyLines = ref<Array<{
    id: string; path: string[]; broken: boolean
  }>>([])
  /** 外交关系连线 */
  const activeDiploRelations = ref<Array<{
    from: string; to: string; type: 'vassal'|'alliance'|'war'|'trade'
  }>>([])
  /** 地块驻防 (tile_id → {troops, resting}) */
  const tileGarrisonData = ref<Record<string, { troops: number; resting: boolean }>>({})
  /** 玩家法理宣称地块 */
  const playerClaimTiles = ref<Set<string>>(new Set())
  /** 地块灾害数据 */
  const tileDisasterData = ref<Record<string, Array<{ type: string; severity: number }>>>({})
  /** 水域航道 */
  const waterRoutes = ref<Array<{ id: string; path: string[] }>>([])
  /** 城建建筑数据 */
  const tileBuildingData = ref<Record<string, Array<{ type: string; level: number }>>>({})

  // ===== 3.1 新增：模式与操作锁 =====
  const modeInfo = ref<any>({ mode: 'player_turn', mode_label: '君主亲政', player_can_operate: true })
  const lockedActions = ref<string[]>([])
  const coolingTiles = ref<Record<string, any[]>>({})

  // ===== 地块邻接关系（从后端 march/neighbors API 加载） =====
  const tileNeighbors = ref<Record<string, string[]>>({})
  const canOperate = computed(() => modeInfo.value?.player_can_operate !== false)
  const isWatchMode = computed(() => modeInfo.value?.mode === 'ai_watch')

  // ===== 计算属性 =====
  const playerFaction = computed(() => {
    return factions.value[playerFactionId.value] || null
  })

  const livingFactions = computed(() => {
    return Object.values(factions.value).filter(f => f.is_alive)
  })

  /**
   * 判断某势力的情报是否对玩家可见
   * 通过 _intel_visible 字段（后端脱敏时注入）判断
   */
  function isFactionIntelVisible(factionId: string): boolean {
    if (factionId === playerFactionId.value) return true
    const f = factions.value[factionId]
    if (!f) return false
    // 后端注入的脱敏标记
    return (f as any)._intel_visible === true
  }

  /**
   * 获取对某势力的渗透度（0-100）
   */
  function getFactionInfiltration(factionId: string): number {
    const f = factions.value[factionId]
    if (!f) return 0
    return (f as any)._infiltration || 0
  }

  /**
   * 格式化势力数值：未知时显示 "?"
   */
  function formatIntelValue(factionId: string, value: number, formatter?: (v: number) => string): string {
    if (isFactionIntelVisible(factionId) && value >= 0) {
      return formatter ? formatter(value) : String(value)
    }
    return '?'
  }

  /** 2026-07-15: 玩家控制的领地ID列表（来自 init_game 的 controlled_tiles） */
  const controlledTiles = ref<string[]>([])
  /** 2026-07-15: 玩家领地数量（来自 init_game 的 controlled_tile_count） */
  const controlledTileCount = ref(0)

  const playerTiles = computed(() => {
    return Object.values(tiles.value).filter(t => t.faction_id === playerFactionId.value)
  })

  const totalTroops = computed(() => {
    return playerTiles.value.reduce((sum, t) => sum + t.troops, 0)
  })

  const totalPopulation = computed(() => {
    return playerTiles.value.reduce((sum, t) => sum + t.population, 0)
  })

  const seasonName = computed(() => {
    const month = currentMonth.value
    if (month >= 3 && month <= 5) return '春'
    if (month >= 6 && month <= 8) return '夏'
    if (month >= 9 && month <= 11) return '秋'
    return '冬'
  })

  // 天气信息（从 world_state.weather 同步）
  const weatherInfo = ref<Record<string, any>>({})

  // ===== 操作方法 =====

  /**
   * 开局初始化 - 调用后端 /api/game/init
   */
  async function startGame(factionId: string, mode: string = 'player_turn', customFaction?: any) {
    isProcessing.value = true
    try {
      const result = await API.initGame({
        faction_id: factionId,
        mode,
        custom_faction: customFaction,
      })

      // 全量同步世界状态
      _applyWorldState(result.world_state)

      // 核心规则：使用后端返回的 player_faction_id 作为权威来源
      playerFactionId.value = result.player_faction_id || factionId
      isGameStarted.value = true
      isGameActive.value = true
      gameMode.value = mode as any

      // 3.1: 同步模式信息
      if (result.mode_info) {
        modeInfo.value = result.mode_info
      }

      // 2026-07-15: 合并 player_faction 顶层的额外字段（controlled_tiles 等）
      if (result.player_faction && playerFactionId.value) {
        _mergePlayerFactionFields(result.player_faction, playerFactionId.value)
      }

      // 后台检查 AI 状态
      checkAIStatus()
    } finally {
      isProcessing.value = false
    }
  }

  /**
   * 推进回合 - 调用后端 /api/game/advance-turn
   * 返回最新世界状态后全量刷新
   */
  async function advanceTurn() {
    if (isProcessing.value) return

    isProcessing.value = true
    try {
      const result = await API.advanceTurn()

      // 全量同步世界状态（events_log 由后端权威返回，避免本地重复）
      if (result.world_state) {
        _applyWorldState(result.world_state)
      }

      // 2026-07-15: advance-turn 可能也在顶层返回 player_faction（如果有的话）
      if ((result as any).player_faction && playerFactionId.value) {
        _mergePlayerFactionFields((result as any).player_faction, playerFactionId.value)
      }
      // 2026-07-15: 同步外交关系
      if ((result as any).diplomatic_relations) {
        diplomaticRelations.value = (result as any).diplomatic_relations
      }

      // 新事件：仅当 world_state 中未包含时追加（兼容旧版后端）
      if (result.new_events && !result.world_state?.events_log) {
        for (const evt of result.new_events) {
          events.value.unshift(evt as GameEvent)
        }
      }

      // 结局判定
      if (result.ending) {
        showEnding.value = true
        endingData.value = result.ending
      }

      // 地盘变更（本回合）
      if (result.tile_changes) {
        tileChangesThisRound.value = result.tile_changes
      } else {
        tileChangesThisRound.value = []
      }

      // 2026-07-15: 同步 controlled_tiles（回合结算后领土可能变化）
      if (playerFactionId.value && result.world_state?.factions) {
        const pf = (result.world_state.factions as any)[playerFactionId.value]
        if (pf?.controlled_tiles !== undefined) {
          controlledTiles.value = pf.controlled_tiles
          controlledTileCount.value = pf.controlled_tile_count ?? pf.controlled_tiles.length
        }
      }

      // 3.1: 同步操作锁状态
      if (result.mode_info) {
        modeInfo.value = result.mode_info
      }
      if (result.locked_actions !== undefined) {
        lockedActions.value = result.locked_actions
      }
      if (result.cooling_tiles) {
        coolingTiles.value = result.cooling_tiles
      }
      if (result.responsibility_stats) {
        responsibilityStats.value = result.responsibility_stats
      }

      // 图层数据刷新（非阻塞）
      _fetchLayerData()

      // AI 事件生成（每3回合自动触发一次，非阻塞）
      if (currentRound.value % 3 === 0 && aiAvailable.value) {
        generateAIEvents().then(aiResult => {
          if (aiResult?.events_text) {
            addEvent({
              event_id: `ai_event_${Date.now()}`,
              event_type: 'random',
              severity: 'minor',
              round: currentRound.value,
              title: '邸报',
              description: aiResult.events_text.slice(0, 200),
              faction_id: '',
              tile_id: '',
              effects: {},
              narrative: aiResult.events_text,
            })
          }
        }).catch((err: unknown) => {
          console.warn('自动保存事件记录失败:', err)
        })
      }

      return result
    } finally {
      isProcessing.value = false
    }
  }

  /**
   * 从后端强制刷新世界状态
   */
  async function refreshWorldState() {
    try {
      const status = await API.getGameStatus()
      if (status?.world_state) {
        _applyWorldState(status.world_state)
      }
      if (status?.game_active !== undefined) {
        isGameActive.value = status.game_active
      }
      // 2026-07-15: 合并 player_faction 顶层字段（修复面板数据不全问题）
      if (status?.player_faction && playerFactionId.value) {
        _mergePlayerFactionFields(status.player_faction, playerFactionId.value)
      }
      // 2026-07-15: 同步外交关系数组（供前端面板直接使用）
      if (status?.diplomatic_relations) {
        diplomaticRelations.value = status.diplomatic_relations
      }
    } catch (err) {
      console.warn('刷新世界状态失败:', err)
    }
  }

  /**
   * 应用 WorldState 到 Store（内部方法）
   */
  /**
   * 2026-07-15: 将后端 game/status 或 game/init 返回的顶层 player_faction 字段
   * 合并到 factions[fid] 中，补全 panels 所需字段（troops/morale/authority 等）
   */
  function _mergePlayerFactionFields(pfData: Record<string, any>, fid: string) {
    if (!factions.value[fid]) return
    const mergeFields: Record<string, string | undefined> = {
      troops: 'total_troops',
      total_troops: 'total_troops',
      morale: 'realm_stability',
      authority: 'court_stability',
      controlled_tiles: undefined,
      controlled_tile_count: undefined,
      field_troops: undefined,
      field_grain: undefined,
    }
    // 合并数值字段（仅当源值 >= 0 时更新，避免 -1 污染）
    for (const [srcKey, dstKey] of Object.entries(mergeFields)) {
      if (pfData[srcKey] !== undefined) {
        const val = Number(pfData[srcKey])
        if (dstKey && val >= 0) {
          (factions.value[fid] as any)[dstKey] = val
        } else if (!dstKey) {
          // 无映射的字段直接存到 faction 对象上
          (factions.value[fid] as any)[srcKey] = val
        }
      }
    }
    // 同步 controlled_tiles 到 store 顶级 ref
    if (pfData.controlled_tiles !== undefined) {
      controlledTiles.value = pfData.controlled_tiles
      controlledTileCount.value = pfData.controlled_tile_count ?? pfData.controlled_tiles.length
    }
    // 同步 ruler_name（宗室面板等需要）
    if (pfData.ruler_name && !(factions.value[fid] as any).ruler_name) {
      (factions.value[fid] as any).ruler_name = pfData.ruler_name
    }
  }

  function _applyWorldState(state: WorldState) {
    if (state.current_round !== undefined) currentRound.value = state.current_round
    if (state.current_year !== undefined) currentYear.value = state.current_year
    if (state.current_month !== undefined) currentMonth.value = state.current_month
    if (state.current_season !== undefined) currentSeason.value = state.current_season
    if (state.game_mode) gameMode.value = state.game_mode as any
    if (state.factions) {
      // 2026-07-15: 净化负值资源（避免前端显示 -1）
      const cleanFactions = state.factions as Record<string, FactionState>
      for (const fid of Object.keys(cleanFactions)) {
        const f = cleanFactions[fid] as any
        for (const field of ['treasury', 'grain', 'arms', 'horses', 'reputation', 'total_troops', 'total_population', 'court_stability', 'realm_stability']) {
          if (typeof f[field] === 'number' && f[field] < 0) {
            f[field] = 0
          }
        }
        // clamp 0-100 范围
        for (const field of ['court_stability', 'realm_stability', 'reputation']) {
          if (typeof f[field] === 'number') {
            f[field] = Math.max(0, Math.min(100, f[field]))
          }
        }
      }
      factions.value = cleanFactions
    }
    if (state.tiles) tiles.value = state.tiles as Record<string, TileState>
    if (state.relations) relations.value = state.relations
    // 合并 events_log：保留本地独有事件（如 AI 思考），追加后端新事件
    if (state.events_log) {
      const existingIds = new Set(events.value.map(e => (e as any).event_id))
      const merged = [...events.value]
      for (const evt of (state.events_log as GameEvent[])) {
        if (!existingIds.has((evt as any).event_id)) {
          merged.unshift(evt)
        }
      }
      events.value = merged
    }
    if (state.tile_changes) tileChanges.value = state.tile_changes
    if (state.decrees) decrees.value = state.decrees as any[]
    // 核心规则：同步 player_faction_id（WorldState 权威来源）
    if (state.player_faction_id) playerFactionId.value = state.player_faction_id
    // 同步天气
    if ((state as any).weather) weatherInfo.value = (state as any).weather

    // 3.1: 同步外交子系统
    if (state.coalitions) coalitions.value = state.coalitions
    if (state.alliance_treaties) allianceTreaties.value = state.alliance_treaties
    if (state.trade_routes) tradeRoutes.value = state.trade_routes
    if (state.vassal_relations) vassalRelations.value = state.vassal_relations

    // 3.2: 同步叛军数据
    if (state.rebel_armies) {
      rebelArmies.value = Object.entries(state.rebel_armies).map(([rid, rdata]: [string, any]) => ({
        rebel_id: rid,
        ...rdata,
      }))
    }

    // 3.1: 同步谍报网络
    // 保留 faction_id 键用于前端按目标势力查询
    if (state.spy_networks) {
      spyNetworks.value = Object.entries(state.spy_networks).map(([fid, data]) => ({
        target_faction_id: fid,
        ...(data as any),
      })) as any[]
    }
    if (state.spy_intel) spyIntel.value = state.spy_intel

    // 更新玩家势力数据
    const pf = playerFaction.value
    if (pf) {
      courtStability.value = pf.court_stability
      realmStability.value = pf.realm_stability || 50
      reputation.value = pf.reputation || 50
      factionLoyalties.value = pf.faction_loyalties || {}
      // 从 WorldState.officials 中查找属于玩家势力的官员详情
      if (state.officials) {
        const pfOfficials: any[] = []
        for (const [oid, odata] of Object.entries(state.officials)) {
          if ((odata as any).faction_id === playerFactionId.value) {
            pfOfficials.push(odata)
          }
        }
        officials.value = pfOfficials
      }
    }

    // 3.1: 同步灾害指数
    if (state.disaster_index !== undefined) {
      disasterIndex.value = state.disaster_index
    }
    if (state.disasters !== undefined) {
      activeDisasters.value = state.disasters  // 空数组也应更新（灾害结束后清除）
    }

    // 图层数据 v2.0：提取迷雾/驻防/灾害/建筑/宣称
    _extractLayerData(state)
    // 异步加载己方各地块邻接关系（用于判断前线）
    _loadTileNeighbors()
  }

  /** 从后端获取图层渲染数据 */
  async function _fetchLayerData() {
    try {
      const layerData = await API.getLayersData(playerFactionId.value)
      if (!layerData) return

      if (layerData.fog_visible) {
        fogVisibleTileIds.value = new Set(layerData.fog_visible)
      }
      if (layerData.march_routes) {
        activeMarchRoutes.value = layerData.march_routes
      }
      if (layerData.supply_lines) {
        activeSupplyLines.value = layerData.supply_lines
      }
      if (layerData.diplomacy) {
        activeDiploRelations.value = layerData.diplomacy
      }
      if (layerData.claims) {
        playerClaimTiles.value = new Set(layerData.claims)
      }
      if (layerData.water_routes) {
        waterRoutes.value = layerData.water_routes
      }
      if (layerData.buildings) {
        tileBuildingData.value = layerData.buildings
      }
      if (layerData.disasters) {
        tileDisasterData.value = layerData.disasters
      }
    } catch (e) {
      // 图层数据获取失败不影响主流程
      console.warn('[图层系统] 数据获取失败:', e)
    }
  }

  /**
   * 从WorldState中提取所有图层渲染所需数据
   */
  function _extractLayerData(state: WorldState) {
    // 迷雾：玩家可见地块
    const fogSet = new Set<string>()
    if (state.tiles) {
      for (const [tid, t] of Object.entries(state.tiles)) {
        if (t.faction_id === playerFactionId.value || (t as any)._intel_visible) {
          fogSet.add(tid)
          // 添加邻接地块作为前线可视
        }
      }
    }
    fogVisibleTileIds.value = fogSet

    // 驻防数据
    const garrison: Record<string, { troops: number; resting: boolean }> = {}
    if (state.tiles) {
      for (const [tid, t] of Object.entries(state.tiles)) {
        if (t.troops > 0) {
          garrison[tid] = {
            troops: t.troops,
            resting: (t as any).garrison_resting || false,
          }
        }
      }
    }
    tileGarrisonData.value = garrison

    // 灾害数据
    const disasters: Record<string, Array<{ type: string; severity: number }>> = {}
    if (state.tiles) {
      for (const [tid, t] of Object.entries(state.tiles)) {
        const dList = (t as any).disasters || t.disasters
        if (dList && dList.length > 0) {
          disasters[tid] = dList.map((d: any) => ({
            type: typeof d === 'string' ? d : d.type || 'unknown',
            severity: typeof d === 'object' ? (d.severity || 0.5) : 0.5,
          }))
        }
      }
    }
    tileDisasterData.value = disasters

    // 法理宣称（玩家势力对特定地块的claim）
    const claims = new Set<string>()
    if ((state as any).player_claims) {
      for (const tid of (state as any).player_claims) {
        claims.add(tid)
      }
    }
    playerClaimTiles.value = claims

    // 建筑数据
    const buildings: Record<string, Array<{ type: string; level: number }>> = {}
    if (state.tiles) {
      for (const [tid, t] of Object.entries(state.tiles)) {
        const bld: Array<{ type: string; level: number }> = []
        const f = t as any
        if (f.fortification > 0) bld.push({ type: 'wall', level: Math.ceil(f.fortification / 3) })
        if (f.granary > 0) bld.push({ type: 'granary', level: Math.ceil(f.granary / 2) })
        if (f.stable > 0) bld.push({ type: 'stable', level: Math.ceil(f.stable / 2) })
        if (f.armory > 0) bld.push({ type: 'workshop', level: Math.ceil(f.armory / 2) })
        if (t.is_port) bld.push({ type: 'port', level: 1 })
        if (bld.length > 0) buildings[tid] = bld
      }
    }
    tileBuildingData.value = buildings

    // 外交关系连线
    const diploRels: Array<{ from: string; to: string; type: 'vassal'|'alliance'|'war'|'trade' }> = []
    if (state.vassal_relations) {
      for (const [vassal, suzerain] of Object.entries(state.vassal_relations)) {
        diploRels.push({ from: suzerain, to: vassal, type: 'vassal' })
      }
    }
    if (state.relations) {
      for (const [key, rel] of Object.entries(state.relations)) {
        // 后端 relation_key 使用 "|" 拼接：fid_a|fid_b
        const parts = key.split('|')
        if (parts.length < 2) continue
        const a = parts[0], b = parts[1]
        if (rel.stance === 'alliance') {
          diploRels.push({ from: a, to: b, type: 'alliance' })
        } else if (rel.stance === 'war') {
          diploRels.push({ from: a, to: b, type: 'war' })
        }
        if (rel.trade_active) {
          diploRels.push({ from: a, to: b, type: 'trade' })
        }
      }
    }
    activeDiploRelations.value = diploRels

    // 水域航道（含港口的地块连接线）
    const waters: Array<{ id: string; path: string[] }> = []
    if (state.tiles) {
      const portTiles = Object.entries(state.tiles)
        .filter(([_, t]) => t.is_port && t.faction_id === playerFactionId.value)
      for (const [tid] of portTiles) {
        waters.push({ id: `water_${tid}`, path: [tid] })
      }
    }
    waterRoutes.value = waters
  }

  /**
   * 加载地块邻接关系（批量并发，单次失败不影响其他）
   */
  async function _loadTileNeighbors() {
    const myTiles = Object.values(tiles.value).filter(t => t.faction_id === playerFactionId.value)
    if (myTiles.length === 0) return
    // 并发加载，但限制并发数避免压垮服务器
    const batchSize = 3
    for (let i = 0; i < myTiles.length; i += batchSize) {
      const batch = myTiles.slice(i, i + batchSize)
      await Promise.allSettled(
        batch.map(async (tile) => {
          try {
            const data = await API.getMarchNeighbors(tile.tile_id, playerFactionId.value)
            if (data?.neighbors) {
              tileNeighbors.value[tile.tile_id] = data.neighbors.map((n: any) => n.tile_id)
            }
          } catch (err: unknown) {
            // 静默忽略单个地块的邻接加载失败
          }
        })
      )
    }
  }

  /**
   * 提交玩家指令（核心规则：只能向自身势力下发政令）
   * 同时自动记录到圣旨台待办列表，供回合推进时与圣旨文本合并推演
   */
  async function submitCommand(action: string, params: Record<string, any>) {
    // 自动生成指令标签并添加到圣旨台待办
    const label = _buildCommandLabel(action, params)
    if (label) {
      pendingEdictCommands.value.push({ action, params, label })
    }
    return await API.submitCommand({ 
      action, 
      params,
      faction_id: playerFactionId.value,  // 归属校验：前端提交时必须带上自身势力ID
    })
  }

  /** 根据 action 和 params 生成圣旨台可读标签 */
  function _buildCommandLabel(action: string, params: Record<string, any>): string {
    const tileName = params.tile_id ? (tiles.value[params.tile_id]?.tile_name || params.tile_id) : ''
    switch (action) {
      case 'recruit': return `在${tileName}征兵${params.amount || '?'}人`
      case 'buy_horses': return `购买${params.amount || '?'}匹战马`
      case 'train_troops': return `在${tileName}训练${params.amount || '?'}士卒`
      case 'march': return `从${tileName}发兵${params.troops || '?'}人`
      case 'fortify': return `加固${tileName}城防`
      case 'develop': return `在${tileName}${params.type === 'water' ? '兴修水利' : params.type === 'farmland' ? '开垦农田' : '开发'}`
      case 'build': return `在${tileName}建造${params.building || '建筑'}`
      case 'scout': return `侦查${tileName || params.target_tile || ''}`
      case 'ambush': return `在${params.target_tile ? tiles.value[params.target_tile]?.tile_name : ''}设伏`
      case 'plunder': return `劫掠${params.target_tile ? tiles.value[params.target_tile]?.tile_name : ''}`
      case 'move_capital': return `迁都至${params.new_tile_id ? tiles.value[params.new_tile_id]?.tile_name : ''}`
      case 'diplomacy': return `向${params.target_faction || ''}发起${params.diplomacy_type || '外交'}`
      case 'spy': return `向${params.target_faction || ''}派遣细作`
      case 'enfeoff': return `分封官员`
      case 'amnesty': return '大赦天下'
      case 'cultural_policy': return '推行文教政策'
      case 'sea_policy': return '推行海策'
      case 'medical': return `在${tileName}建立医馆`
      case 'convict_labor': return `在${tileName}征发徭役`
      case 'law': return `执行律法：${params.action || ''}`
      case 'relief': return `在${tileName}赈灾救济`
      case 'claim': return `宣示${tileName}主权`
      case 'navy_patrol': return `派遣水师巡逻${tileName}`
      case 'sea_trade': return `开辟经过${tileName}的贸易航线`
      case 'sea_explore': return `探索${tileName}海域`
      case 'sea_fish': return `征调${tileName}渔业资源`
      case 'build_port': return `在${tileName}修建港口`
      case 'inspect': return `体察${tileName}民情`
      case 'sabotage': return `暗中破坏${tileName}`
      default: return `执行${action}操作`
    }
  }

  /**
   * 派遣细作
   */
  async function deploySpy(targetFaction: string) {
    const result = await API.deploySpy({
      owner_faction: playerFactionId.value,
      target_faction: targetFaction,
    })
    return result
  }

  /**
   * 执行谍报行动
   */
  async function executeSpyAction(targetFaction: string, actionType: string) {
    return await API.spyAction({
      owner_faction: playerFactionId.value,
      target_faction: targetFaction,
      action_type: actionType,
    })
  }

  /**
   * 刷新谍报网络
   */
  async function refreshSpyNetworks() {
    try {
      const result = await API.getSpyNetworks(playerFactionId.value)
      spyNetworks.value = result.networks || []
    } catch (_) { /* 忽略 */ }
  }

  /**
   * 行军/战斗结算（支持粮草参数）
   * 3.2: 战斗后自动更新外交关系
   */
  async function marchTo(fromTile: string, toTile: string, troops: number, grain: number = 0) {
    const result = await API.resolveMarch({
      from_tile: fromTile,
      to_tile: toTile,
      troops,
      grain,
      attacker_faction: playerFactionId.value,
    })
    // 3.2: 如果战斗导致外交状态变更，刷新世界状态
    if (result?.diplomacy_changed) {
      await refreshWorldState()
    }
    return result
  }

  /**
   * 获取行军路径
   */
  async function getMarchPath(fromTile: string, toTile: string, troops: number = 100) {
    return await API.getMarchPath({ from_tile: fromTile, to_tile: toTile, troops })
  }

  /**
   * 改变外交姿态
   */
  async function changeDiplomacy(targetFaction: string, newStance: string, reason?: string) {
    return await API.changeDiplomaticStance({
      faction_a: playerFactionId.value,
      faction_b: targetFaction,
      new_stance: newStance,
      reason,
    })
  }

  /**
   * 开通贸易
   */
  async function openTrade(targetFaction: string) {
    return await API.openTradeRoute({
      faction_a: playerFactionId.value,
      faction_b: targetFaction,
    })
  }

  /**
   * 联姻
   */
  async function marryTo(targetFaction: string) {
    return await API.proposeMarriage({
      from_faction: playerFactionId.value,
      to_faction: targetFaction,
    })
  }

  /**
   * 任命官员
   */
  async function appointOfficial(name: string, position: string, ability?: number, loyalty?: number) {
    return await API.appointOfficial({
      faction_id: playerFactionId.value,
      name,
      position,
      ability,
      loyalty,
    })
  }

  /**
   * 罢免官员
   */
  async function dismissOfficial(officialId: string) {
    return await API.dismissOfficial(officialId)
  }

  /**
   * 处决官员
   */
  async function executeOfficial(officialId: string) {
    return await API.executeOfficial(officialId)
  }

  /**
   * 处置俘虏
   */
  async function handlePrisoner(prisonerId: string, action: string) {
    return await API.handlePrisoner({ prisoner_id: prisonerId, action })
  }

  /**
   * 检查藩镇叛乱
   */
  async function checkVassalRebellion() {
    return await API.checkVassalRebellion(playerFactionId.value)
  }

  /**
   * 获取工坊信息
   */
  async function refreshWorkshops() {
    return await API.getWorkshops(playerFactionId.value)
  }

  /**
   * 获取结局与统计（增强版：含演出数据）
   */
  async function refreshEnding() {
    try {
      const result = await API.getEnding()
      if (result.ending) {
        endingData.value = result.ending
        showEnding.value = result.ending.is_game_over || false
      }
      if (result.statistics) {
        gameStatistics.value = result.statistics
      }
      return result
    } catch (_) { /* 忽略 */ }
  }

  /**
   * 获取所有结局的进度状态
   */
  async function refreshEndingsProgress() {
    try {
      return await API.getEndingsProgress()
    } catch (_) { return null }
  }

  /**
   * 获取结局达成历史
   */
  async function refreshEndingsHistory() {
    try {
      return await API.getEndingsHistory()
    } catch (_) { return { history: [] } }
  }

  /**
   * 获取传承数据
   */
  async function refreshEndingsLegacy() {
    try {
      return await API.getEndingsLegacy()
    } catch (_) { return { legacy: {} } }
  }

  // ===== AI 智能体方法 =====

  /** AI 健康状态 */
  const aiAvailable = ref(false)
  const aiStatus = ref<any>(null)

  async function checkAIStatus() {
    try {
      const status = await API.agentStatus()
      aiAvailable.value = status?.llm_available ?? false
      aiStatus.value = status
      return status
    } catch (err: unknown) {
      aiAvailable.value = false
      console.warn('AI状态检查失败:', err)
      return null
    }
  }

  /** 谋臣对话（AdvisorPanel）- 支持指定 NPC，自动附加游戏上下文 */
  async function chatWithMinister(message: string, npcId?: string): Promise<any> {
    try {
      // 构建增强的提问：融入游戏上下文
      const enhancedQuestion = _buildAdvisorQuestion(message)

      const result = await API.strategicAdvice({
        faction_id: playerFactionId.value,
        question: enhancedQuestion,
        world_state: _buildWorldSnapshot(),
        round: currentRound.value,
        npc_id: npcId || '',
      })
      return result
    } catch (err: unknown) {
      console.warn('谋臣献策失败:', err)
      return null
    }
  }

  /** 构建增强的谋臣提问（附加游戏上下文） */
  function _buildAdvisorQuestion(userMessage: string): string {
    const pf = playerFaction
    if (!pf) return userMessage

    // 计算邻国关系
    const neighbors: string[] = []
    const enemies: string[] = []
    const allies: string[] = []
    for (const [k, r] of Object.entries(relations.value)) {
      const parts = k.split('|')
      if (!parts.includes(playerFactionId.value)) continue
      const otherId = parts[0] === playerFactionId.value ? parts[1] : parts[0]
      const otherFaction = factions.value[otherId]
      const otherName = otherFaction?.name || otherId
      if (r.stance === 'war') enemies.push(otherName)
      else if (r.stance === 'alliance') allies.push(otherName)
      else neighbors.push(otherName)
    }

    const contextParts = [
      `[游戏状态] 第${currentRound.value}回合 ${currentYear.value}年${currentSeason.value}季`,
      `我方势力: ${pf.name || '未知'}`,
      `领地: ${playerTiles.length}块  总兵力: ${totalTroops.value}人`,
      `国库: ${pf.treasury || 0}两  粮草: ${pf.grain || 0}  声望: ${reputation.value}`,
      `民心: ${realmStability.value}  朝纲: ${courtStability.value}`,
    ]
    if (enemies.length) contextParts.push(`敌方: ${enemies.join('、')}`)
    if (allies.length) contextParts.push(`盟友: ${allies.join('、')}`)
    if (neighbors.length) contextParts.push(`邻国: ${neighbors.slice(0, 4).join('、')}`)

    return `${contextParts.join(' | ')}\n\n${userMessage}`
  }

  // ===== NPC 文臣系统 =====

  const npcList = ref<any[]>([])
  const factionAdvisers = ref<any[]>([])
  const selectedNpcId = ref('')
  const npcConversations = ref<Record<string, any[]>>({})

  /** 加载 NPC 列表（支持按势力筛选） */
  async function loadNPCList(role?: string, factionId?: string) {
    try {
      const fid = factionId || playerFactionId.value
      const result = await API.listNPCs(role, fid)
      npcList.value = result?.npcs || []
      // 筛选本势力专属谋士
      factionAdvisers.value = npcList.value.filter(
        (n: any) => n.faction === fid
      )
      return npcList.value
    } catch (err: unknown) {
      console.warn('NPC列表加载失败:', err)
      return []
    }
  }

  /** 加载势力谋士团详情 */
  async function loadFactionAdvisers(factionId?: string) {
    try {
      const fid = factionId || playerFactionId.value
      const result = await API.getFactionAdvisers(fid)
      if (result?.advisers) {
        factionAdvisers.value = result.advisers.filter(
          (a: any) => a.faction === fid
        )
        return result
      }
      return null
    } catch (err: unknown) {
      console.warn('势力谋士团加载失败:', err)
      return null
    }
  }

  /** 与指定 NPC 对话 */
  async function chatWithNPC(npcId: string, message: string): Promise<any> {
    try {
      // 获取该 NPC 的历史对话
      const history = npcConversations.value[npcId] || []
      const result = await API.npcChat({
        npc_id: npcId,
        faction_id: playerFactionId.value,
        message,
        world_state: _buildWorldSnapshot(),
        conversation_history: history,
      })
      if (result) {
        // 保存对话历史
        if (!npcConversations.value[npcId]) {
          npcConversations.value[npcId] = []
        }
        npcConversations.value[npcId].push({ role: 'user', content: message })
        npcConversations.value[npcId].push({ role: 'assistant', content: result.response })
        // 限制历史长度
        if (npcConversations.value[npcId].length > 30) {
          npcConversations.value[npcId] = npcConversations.value[npcId].slice(-30)
        }
      }
      return result
    } catch (err: unknown) {
      console.warn('NPC对话失败:', err)
      return null
    }
  }

  /** 廷议辩论 */
  async function startCourtDebate(topic: string, npcIds?: string[]): Promise<any> {
    try {
      return await API.courtDebate({
        topic,
        faction_id: playerFactionId.value,
        npc_ids: npcIds,
        world_state: _buildWorldSnapshot(),
      })
    } catch (err: unknown) {
      console.warn('廷议辩论失败:', err)
      return null
    }
  }

  /** 清除 NPC 对话历史 */
  function clearNPCConversation(npcId: string) {
    delete npcConversations.value[npcId]
  }

  /** AI 自由对话（4种模式） */
  async function agentChat(message: string, mode: string = 'ruler'): Promise<string> {
    try {
      const result = await API.agentChat({
        faction_id: playerFactionId.value,
        message,
        chat_mode: mode,
        world_state: _buildWorldSnapshot(),
      })
      return result?.response || ''
    } catch (err: unknown) {
      console.warn('AI自由对话失败:', err)
      return ''
    }
  }

  /** 律法审讯对话 */
  async function lawInterrogate(prisonerName: string, question: string): Promise<string> {
    try {
      const result = await API.lawChat({
        faction_id: playerFactionId.value,
        prisoner_name: prisonerName,
        question,
        world_state: _buildWorldSnapshot(),
      })
      return result?.response || ''
    } catch (err: unknown) {
      console.warn('律法审讯失败:', err)
      return ''
    }
  }

  /** AI 生成随机事件 */
  async function generateAIEvents() {
    try {
      const result = await API.eventGenerate({
        round: currentRound.value,
        season: currentSeason.value,
        disaster_index: disasterIndex.value,
      })
      return result
    } catch (err: unknown) {
      console.warn('AI事件生成失败:', err)
      return null
    }
  }

  /** NPC 势力 AI 决策 */
  async function requestFactionAIDecision(factionId: string) {
    const faction = factions.value[factionId]
    try {
      return await API.factionAIDecision({
        faction_id: factionId,
        faction_name: faction?.name || factionId,
        tile_count: faction?.tile_count,
        troops: faction?.total_troops,
        treasury: faction?.treasury,
        reputation: faction?.reputation,
        realm_stability: faction?.realm_stability,
        court_stability: faction?.court_stability,
        turn: currentRound.value,
        season: currentSeason.value,
      })
    } catch (err: unknown) {
      console.warn('NPC势力AI决策失败:', err)
      return null
    }
  }

  /** AI 战斗结算 */
  async function resolveBattleAI(params: {
    attacker_faction: string; defender_faction: string; tile_id: string
    attacker_troops: number; defender_troops: number
    wall_level?: number; terrain?: string; is_siege?: boolean
  }) {
    try {
      return await API.resolveBattle({ ...params, season: currentSeason.value })
    } catch (err: unknown) {
      console.warn('AI战斗结算失败:', err)
      return null
    }
  }

  /** AI 外交判定 */
  async function diplomacyAIAction(params: {
    from_faction: string; to_faction: string; action_type: string; terms?: any
  }) {
    try {
      return await API.diplomacyAction({ ...params, turn: currentRound.value })
    } catch (err: unknown) {
      console.warn('AI外交判定失败:', err)
      return null
    }
  }

  /** AI 灾害预判 */
  async function forecastDisaster() {
    try {
      const result = await API.disasterForecast({
        faction_id: playerFactionId.value,
        turn: currentRound.value,
        season: currentSeason.value,
        active_disasters: activeDisasters.value,
        disaster_index: disasterIndex.value,
      })
      if (result?.forecast) {
        addEvent({
          event_id: `disaster_forecast_${Date.now()}`,
          event_type: 'disaster',
          severity: 'minor',
          round: currentRound.value,
          title: '钦天监禀报',
          description: result.forecast,
          faction_id: playerFactionId.value,
          tile_id: '',
          effects: {},
          narrative: result.forecast,
        })
      }
      return result
    } catch (err: unknown) {
      console.warn('AI灾害预判失败:', err)
      return null
    }
  }

  /** 圣旨 AI 解析（旧版兼容） */
  async function parseEdictAI(edictText: string) {
    try {
      const pf = playerFaction.value
      return await API.parseEdict({
        edict_text: edictText,
        faction_id: playerFactionId.value,
        turn: currentRound.value,
        season: currentSeason.value,
        treasury: pf?.treasury,
        troops: totalTroops.value,
        reputation: reputation.value,
        court_stability: courtStability.value,
        realm_stability: realmStability.value,
      })
    } catch (err: unknown) {
      console.warn('圣旨AI解析失败:', err)
      return null
    }
  }

  /**
   * 圣旨 AI 推演执行（新版核心）
   * 
   * 玩家用自然语言输入圣旨 → AI 解析为操作指令 → 直接执行到游戏状态
   * 返回完整的执行结果和更新后的 world_state
   */
  async function executeEdictAI(edictText: string) {
    if (!edictText.trim()) return null
    isProcessing.value = true
    try {
      const result = await API.executeEdict({
        edict_text: edictText,
        faction_id: playerFactionId.value,
      })

      // 全量同步世界状态
      if (result?.world_state) {
        _applyWorldState(result.world_state)
      }

      // 更新操作锁状态
      if (result?.locked_actions !== undefined) {
        lockedActions.value = result.locked_actions
      }
      if (result?.cooling_tiles) {
        coolingTiles.value = result.cooling_tiles
      }

      // 地盘变更
      if (result?.tile_changes) {
        tileChangesThisRound.value = result.tile_changes
      }

      return result
    } catch (err: any) {
      console.error('圣旨执行失败:', err)
      return null
    } finally {
      isProcessing.value = false
    }
  }

  /** 完整自动推演 */
  async function autoStepAI() {
    try {
      const result = await API.agentAutoStep({ world_state: _buildWorldSnapshot() })
      return result
    } catch (err: unknown) {
      console.warn('Agent自动推演失败:', err)
      return null
    }
  }

  /** AI 工具调用 */
  async function agentToolCallAI(prompt: string, tools?: string[]) {
    try {
      return await API.agentToolCall({
        faction_id: playerFactionId.value,
        prompt,
        world_state: _buildWorldSnapshot(),
        tools,
      })
    } catch (err: unknown) {
      console.warn('Agent工具调用失败:', err)
      return null
    }
  }

  /** 获取可用工具列表 */
  async function listAgentTools(category?: string) {
    try {
      return await API.listTools(category)
    } catch (err: unknown) {
      console.warn('Agent工具列表加载失败:', err)
      return null
    }
  }

  /** 构建世界快照（供 AI 调用） */
  function _buildWorldSnapshot(): any {
    return {
      current_round: currentRound.value,
      current_year: currentYear.value,
      current_month: currentMonth.value,
      current_season: currentSeason.value,
      factions: factions.value,
      tiles: tiles.value,
      relations: relations.value,
      player_faction_id: playerFactionId.value,
      disaster_index: disasterIndex.value,
      realm_stability: realmStability.value,
      court_stability: courtStability.value,
      reputation: reputation.value,
    }
  }

  function togglePanel(panelName: PanelType) {
    activePanel.value = activePanel.value === panelName ? '' : panelName
  }

  function addEvent(event: GameEvent) {
    events.value.unshift(event)
    if (events.value.length > 500) {
      events.value = events.value.slice(0, 500)
    }
  }

  function selectTile(tileId: string) {
    selectedTile.value = tileId
  }

  // 从右键菜单直接打开营造司并选中地块
  function setBuildTargetTile(tileId: string) {
    selectedTile.value = tileId
  }

  async function resetGame() {
    try {
      await API.restartGame()
    } catch (_) { /* 忽略 */ }

    currentRound.value = 0
    currentYear.value = 1351
    currentMonth.value = 4
    currentSeason.value = '春'
    playerFactionId.value = ''
    factions.value = {}
    tiles.value = {}
    relations.value = {}
    events.value = []
    decrees.value = []
    tileChanges.value = []
    tileChangesThisRound.value = []
    courtStability.value = 50
    realmStability.value = 50
    reputation.value = 50
    factionLoyalties.value = {}
    officials.value = []
    disasterIndex.value = 0
    activeDisasters.value = []
    activePanel.value = ''
    showEnding.value = false
    endingData.value = null
    isGameStarted.value = false
    isGameActive.value = false
    isProcessing.value = false
    selectedTile.value = ''
    
    // 3.1: 清除操作锁状态
    modeInfo.value = { mode: 'player_turn', mode_label: '君主亲政', player_can_operate: true }
    lockedActions.value = []
    coolingTiles.value = {}
    tileNeighbors.value = {}
    // 遗漏重置的字段
    weatherInfo.value = {}
    spyNetworks.value = []
    spyIntel.value = []
    rebelArmies.value = []
    coalitions.value = {}
    allianceTreaties.value = []
    tradeRoutes.value = []
    vassalRelations.value = {}
    responsibilityStats.value = null
    pendingEdictCommands.value = []
    showMarchPanel.value = false
    marchTargetTileId.value = ''
    showWarPanel.value = false
    showPeacePanel.value = false
    warPanelData.value = null
    activeWars.value = []
    gameStatistics.value = null
    npcList.value = []
    factionAdvisers.value = []
    selectedNpcId.value = ''
    npcConversations.value = {}
  }

  return {
    // 核心状态
    currentRound, currentYear, currentMonth, currentSeason,
    gameMode, isProcessing, isGameStarted, isGameActive,
    // 势力与地块
    playerFactionId, factions, tiles,
    // 外交
    relations, coalitions, tradeRoutes, vassalRelations, allianceTreaties,
    // 事件
    events, decrees,
    // 地盘变更
    tileChanges, tileChangesThisRound,
    // 朝堂
    courtStability, realmStability, reputation, factionLoyalties, officials,
    // 谍报
    spyNetworks, spyIntel,
    // 叛军（3.2）
    rebelArmies,
    // 灾害
    disasterIndex, activeDisasters,
    // 结局
    showEnding, endingData, gameStatistics,
    // AI
    aiAvailable, aiStatus,
    // NPC 文臣
    npcList, factionAdvisers, selectedNpcId, npcConversations,
    // UI
    activePanel, selectedTile, setBuildTargetTile, pendingEdictCommands,
    // 出征面板
    showMarchPanel, marchTargetTileId,
    // 战争面板 (v3.0)
    showWarPanel, warPanelData, showPeacePanel, activeWars,
    // 路线显示开关
    showRoutes, activeRoutes,
    // 图层系统数据 v2.0
    fogVisibleTileIds, activeMarchRoutes, activeSupplyLines,
    activeDiploRelations, tileGarrisonData, playerClaimTiles,
    tileDisasterData, waterRoutes, tileBuildingData,
    // 3.1 模式与操作锁
    modeInfo, lockedActions, coolingTiles, canOperate, isWatchMode,
    // 权责追踪
    responsibilityStats,
    // 地块邻接
    tileNeighbors,
    // 计算属性
    playerFaction, livingFactions, playerTiles,
    totalTroops, totalPopulation, seasonName,
    // 情报可见性
    isFactionIntelVisible, getFactionInfiltration, formatIntelValue,
    // 核心方法
    startGame, advanceTurn, refreshWorldState, submitCommand,
    // 谍报
    deploySpy, executeSpyAction, refreshSpyNetworks,
    // 行军
    marchTo, getMarchPath,
    // 外交
    changeDiplomacy, openTrade, marryTo,
    // 朝堂
    appointOfficial, dismissOfficial, executeOfficial, handlePrisoner,
    // 藩镇
    checkVassalRebellion,
    // 工坊
    refreshWorkshops,
    // 结局
    refreshEnding,
    // 结局（3.3 增强：进度/历史/传承）
    refreshEndingsProgress, refreshEndingsHistory, refreshEndingsLegacy,
    // AI 智能体
    checkAIStatus, chatWithMinister, agentChat, lawInterrogate,
    generateAIEvents, requestFactionAIDecision, resolveBattleAI,
    diplomacyAIAction, forecastDisaster, parseEdictAI,
    autoStepAI, agentToolCallAI, listAgentTools,
    // 圣旨 AI 推演
    executeEdictAI,
    // NPC 文臣
    loadNPCList, loadFactionAdvisers,
    chatWithNPC, startCourtDebate, clearNPCConversation,
    // UI
    togglePanel, addEvent, selectTile, resetGame,

    /** 读档专用：用后端返回的 world_state 全量覆盖前端状态 */
    applyLoadState(state: WorldState, playerFactionIdStr: string) {
      _applyWorldState(state)
      playerFactionId.value = playerFactionIdStr
      isGameStarted.value = true
      isGameActive.value = true
      isProcessing.value = false
      // 清空临时状态
      activePanel.value = ''
      showEnding.value = false
      endingData.value = null
      tileChangesThisRound.value = []
      pendingEdictCommands.value = []
      showMarchPanel.value = false
    },
  }
})
