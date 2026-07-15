// ===== 游戏核心类型定义 =====

export interface FactionState {
  faction_id: string
  name: string
  title: string
  color: string
  capital_tile: string
  is_player: boolean
  is_alive: boolean
  treasury: number
  grain: number
  arms: number
  horses: number
  reputation: number
  total_troops: number
  total_population: number
  court_stability: number
  realm_stability: number
  development_level: number
  faction_loyalties: Record<string, number>
  personality_tags: string[]
  unlocked_policies: string[]
  officials: string[]
  prisoners: string[]
  buffs: BuffDebuff[]
  debuffs: BuffDebuff[]
  tile_count?: number
  // 情报脱敏字段（后端注入）
  _intel_visible?: boolean
  _intel_source?: string
  _intel_age?: number | null
  _infiltration?: number
}

export interface BuffDebuff {
  name: string
  effect: string
  type: string
}

export interface TileState {
  tile_id: string
  tile_name: string
  tile_type: TileType
  region: string
  faction_id: string
  population: number
  troops: number
  grain: number
  morale: number
  treasury: number
  refugee_ratio: number
  water_works: number
  granary: number
  clinic: number
  fortification: number
  siege_state: string | null
  garrison_resting: boolean
  elite_ratio: number
  stable: number
  armory: number
  disasters: string[]
  is_capital: boolean
  is_port: boolean
  special_effect: string | null
}

export type TileType = 'farmland' | 'mountain' | 'water' | 'coast' | 'city' | 'pass' | 'port' | 'desert' | 'grassland' | 'sea'

export interface RelationState {
  faction_a: string
  faction_b: string
  stance: DiplomaticStance
  attitude: number
  treaty_expiry: number
  trade_active: boolean
  coalition_id: string
}

export type DiplomaticStance = 'war' | 'neutral' | 'truce' | 'alliance' | 'vassal'

export interface GameEvent {
  event_id: string
  event_type: EventType
  severity: EventSeverity
  round: number
  title: string
  description: string
  faction_id: string
  tile_id: string
  effects: Record<string, any>
  narrative: string
}

export type EventType = 'battle' | 'diplomacy' | 'disaster' | 'court' | 'economy' | 'spy' | 'civil' | 'royal' | 'random' | 'ending' | 'policy' | 'decree'
export type EventSeverity = 'trivial' | 'minor' | 'major' | 'critical'

// ===== WorldState 内部数据类型（替换 any） =====

export interface AllianceTreaty {
  treaty_id: string
  treaty_type: string
  parties: string[]
  signed_round: number
  expires_round: number
  terms: Record<string, unknown>
}

export interface TradeRoute {
  route_id: string
  origin: string
  destination: string
  income: number
  active: boolean
}

export interface SpyIntel {
  network_id: string
  source_faction: string
  target_faction: string
  level: number
  intel: Record<string, unknown>
  timestamp: number
}

export interface Official {
  official_id: string
  name: string
  title: string
  faction_id: string
  loyalty: number
  stats: Record<string, number>
}

export interface Prisoner {
  prisoner_id: string
  name: string
  original_faction: string
  captor_faction: string
  captured_round: number
  freed: boolean
}

export interface RebelArmy {
  rebel_id: string
  name: string
  faction_id: string
  troops: number
  tile_id: string
  leader: string
}

export interface DisasterRecord {
  disaster_id: string
  type: string
  severity: string
  tile_id: string
  start_round: number
  end_round: number | null
  effects: Record<string, number>
}

export interface DecreeRecord {
  decree_id: string
  decree_type: string
  content: string
  issued_round: number
  executed: boolean
}

export interface SiegeState {
  siege_id: string
  tile_id: string
  attacker: string
  defender: string
  start_round: number
  progress: number
}

export interface PurgeRecord {
  purge_id: string
  target_id: string
  target_type: string
  reason: string
  round: number
}

export interface WeatherState {
  current: string
  next: string
  effects: Record<string, unknown>
}

export interface WorldState {
  current_round: number
  current_year: number
  current_month: number
  current_season: string
  player_faction_id: string  // 核心规则：玩家操控势力ID（该势力A2 RulerAgent强制休眠）
  factions: Record<string, FactionState>
  tiles: Record<string, TileState>
  relations: Record<string, RelationState>
  coalitions: Record<string, string[]>
  alliance_treaties: AllianceTreaty[]
  trade_routes: TradeRoute[]
  vassal_relations: Record<string, string>
  spy_networks: Record<string, Record<string, unknown>>
  spy_intel: SpyIntel[]
  planted_false_intel: SpyIntel[]
  officials: Record<string, Official>
  exiled_officials: string[]
  purges: PurgeRecord[]
  new_officials: Official[]
  siege_states: Record<string, SiegeState>
  prisoners: Record<string, Prisoner>
  rebel_armies: Record<string, RebelArmy>
  events_log: GameEvent[]
  disasters: DisasterRecord[]
  disaster_index: number
  decrees: DecreeRecord[]
  diplomatic_archive: Record<string, unknown>[]
  governance_logs: Record<string, unknown>[]
  govern_merit: Record<string, number>
  tile_changes: Record<string, unknown>[]
  weather: WeatherState
  game_mode: string
  version: string
}

export interface HexCoord {
  q: number
  r: number
}

export interface EdictResult {
  intent: string
  params: Record<string, any>
  confidence: number
  resource_check: {
    valid: boolean
    warnings: string[]
  }
  narrative: string
}

export interface BattleResult {
  victory: boolean
  attacker_losses: number
  defender_losses: number
  tile_captured: boolean
  narrative: string
  effects: Record<string, any>
}

export interface FactionConfig {
  id: string
  name: string
  title: string
  color: string
  capital_tile: string
  initial_territory: string[]
  initial_treasury: number
  initial_grain: number
  initial_arms: number
  initial_horses: number
  initial_troops: number
  initial_reputation: number
  personality_tags: string[]
  difficulty: string
  playable: boolean
  image?: string
  voice?: string
  buffs: BuffDebuff[]
  debuffs: BuffDebuff[]
  ai_logic: {
    expansion: number
    consolidation: number
    diplomacy: number
    military: number
    economy: number
  }
}

export interface CounterRelation {
  attacker: string
  defender: string
  relation: number
  reason: string
}

export type PanelType = 
  | 'treasury' 
  | 'factions' 
  | 'court' 
  | 'disaster' 
  | 'military' 
  | 'diplomacy' 
  | 'events' 
  | 'construction' 
  | 'ai-strategy'
  | 'audio'
  | 'law'
  | 'law-interrogate'
  | 'spy'
  | 'royal'
  | 'medical'
  | 'sea'
  | 'vassal'
  | 'workshop'
  | 'prisoner'
  | 'personnel'
  | 'culture'
  | 'territory'
  | 'recruit'
  | 'rebel'
  | 'ambush'
  | 'plunder'
  | 'moveCapital'
  | 'agent'
  | 'faction_network'
  | ''
