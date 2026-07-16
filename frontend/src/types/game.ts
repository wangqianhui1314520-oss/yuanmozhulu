/**
 * 元末逐鹿 3.0 - 游戏核心类型定义
 *
 * 集中定义所有游戏相关的 TypeScript 类型，
 * 替代代码中泛滥的 Record<string, any> 和 as any
 */

// ================================================================
// 基础地理类型
// ================================================================

/** 地形类型 */
export type TerrainType =
  | 'plain' | 'mountain' | 'hill' | 'forest' | 'desert'
  | 'water' | 'coastal' | 'swamp' | 'pass' | 'river'
  | 'ocean' | 'urban';

/** 六边形地块坐标 */
export interface HexCoord {
  q: number;
  r: number;
}

/** 地块基础数据 */
export interface TileData {
  id: string;
  name: string;
  coord: HexCoord;
  terrain: TerrainType;
  faction_id: string;
  population: number;
  development: number;
  fortification: number;
  garrison: number;
  building: TileBuilding;
  province: string;
}

/** 地块建筑 */
export interface TileBuilding {
  farmland?: number;
  workshop?: number;
  beacon?: number;
  dock?: number;
  barracks?: number;
  granary?: number;
  clinic?: number;
  armory?: number;
  stable?: number;
  temple?: number;
  wall?: number;
}

// ================================================================
// 势力类型
// ================================================================

/** 势力难度 */
export type Difficulty = '简单' | '普通' | '中等' | '困难' | '地狱';

/** 势力Buff/Debuff */
export interface FactionModifier {
  name: string;
  effect: string;
  type: 'military' | 'economy' | 'civil' | 'diplomacy' | 'court';
}

/** AI行为逻辑 */
export interface AILogic {
  expansion: number;
  consolidation: number;
  diplomacy: number;
  military: number;
  economy: number;
}

/** 势力完整数据 */
export interface FactionData {
  id: string;
  name: string;
  full_name: string;
  title: string;
  color: string;
  capital_tile: string;
  initial_territory: string[];
  initial_treasury: number;
  initial_grain: number;
  initial_arms: number;
  initial_horses: number;
  initial_troops: number;
  initial_reputation: number;
  personality_tags: string[];
  difficulty: Difficulty;
  playable: boolean;
  adviser_team: string[];
  adviser_description: string;
  buffs: FactionModifier[];
  debuffs: FactionModifier[];
  ai_logic: AILogic;
  image: string;
  voice: string;
}

/** Buff/Debuff 效果项（与 types/index.ts 对齐） */
export interface BuffDebuff {
  name: string;
  effect: string;
  type: string;
}

/** 势力运行时状态 — 与 types/index.ts FactionState 兼容 */
export interface FactionState {
  id: string;
  name: string;
  title?: string;
  color?: string;
  capital_tile?: string;
  treasury: number;
  grain: number;
  arms: number;
  horses: number;
  troops: number;
  /** 与 index.ts total_troops 兼容别名 */
  total_troops?: number;
  population: number;
  /** 与 index.ts total_population 兼容别名 */
  total_population?: number;
  reputation: number;
  stability: number;
  /** 与 index.ts court_stability 兼容 */
  court_stability?: number;
  /** 与 index.ts realm_stability 兼容 */
  realm_stability?: number;
  morale: number;
  territory_count: number;
  /** 与 index.ts tile_count 兼容别名 */
  tile_count?: number;
  development: number;
  /** 与 index.ts development_level 兼容别名 */
  development_level?: number;
  is_player: boolean;
  is_alive: boolean;
  // 扩展字段（types/index.ts 完整字段）
  faction_loyalties?: Record<string, number>;
  personality_tags?: string[];
  unlocked_policies?: string[];
  officials?: string[];
  prisoners?: string[];
  buffs?: BuffDebuff[];
  debuffs?: BuffDebuff[];
  // 情报脱敏字段
  _intel_visible?: boolean;
  _intel_source?: string;
  _intel_age?: number | null;
  _infiltration?: number;
}

// ================================================================
// 世界状态
// ================================================================

/** 游戏世界完整状态 — 与 types/index.ts 中 WorldState 保持兼容 */
export interface WorldState {
  // 兼容两套字段名（后端同时使用 snake_case 的 current_ 前缀和无前缀版本）
  current_round?: number;
  round?: number;
  current_year?: number;
  year?: number;
  current_month?: number;
  month?: number;
  current_season?: string;
  season?: string;
  player_faction_id: string;
  factions: Record<string, FactionState>;
  tiles: Record<string, TileData>;
  // 扩展字段（types/index.ts 中的 WorldState 完整字段）
  relations?: Record<string, any>;
  coalitions?: Record<string, string[]>;
  alliance_treaties?: any[];
  trade_routes?: any[];
  vassal_relations?: Record<string, string>;
  spy_networks?: Record<string, Record<string, unknown>>;
  spy_intel?: any[];
  officials?: Record<string, any>;
  siege_states?: Record<string, any>;
  prisoners?: Record<string, any>;
  rebel_armies?: Record<string, any>;
  events_log?: GameEvent[];
  disasters?: any[];
  disaster_index?: number;
  decrees?: any[];
  tile_changes?: any[];
  weather: WeatherState;
  game_mode?: string;
  version?: string;
  mode_info?: ModeInfo;
  ending?: EndingResult;
}

/** 世界状态增量更新（用于 applyDelta 增量同步） */
export interface WorldStateDelta {
  current_round?: number;
  current_year?: number;
  current_month?: number;
  current_season?: string;
  game_mode?: string;
  player_faction_id?: string;
  factions?: Record<string, Partial<FactionState>>;
  tiles?: Record<string, Partial<TileData>>;
  relations?: Record<string, any>;
  coalitions?: Record<string, string[]>;
  alliance_treaties?: any[];
  trade_routes?: any[];
  vassal_relations?: Record<string, string>;
  spy_networks?: Record<string, Record<string, unknown>>;
  spy_intel?: any[];
  officials?: Record<string, any>;
  siege_states?: Record<string, any>;
  prisoners?: Record<string, any>;
  rebel_armies?: Record<string, any>;
  events_log?: GameEvent[];
  new_events?: any[];
  removed_event_ids?: string[];
  events?: GameEvent[];
  disasters?: any[];
  disaster_index?: number;
  decrees?: any[];
  tile_changes?: any[];
  weather?: Partial<WeatherState>;
  mode_info?: Partial<ModeInfo>;
  ending?: Partial<EndingResult>;
}

/** 天气状态 */
export interface WeatherState {
  current: string;
  forecast: string;
  effects: WeatherEffect[];
}

export interface WeatherEffect {
  type: string;
  severity: number;
  affected_tiles: string[];
}

/** 游戏事件 */
export interface GameEvent {
  id: string;
  round: number;
  type: string;
  title: string;
  description: string;
  faction_id?: string;
  tile_id?: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

/** 模式信息 */
export interface ModeInfo {
  phase: string;
  locked_actions: string[];
  cooling_tiles: string[];
  description: string;
}

/** 结局结果 */
export interface EndingResult {
  type: string;
  title: string;
  description: string;
  tier: number;
  is_final: boolean;
}

// ================================================================
// 图层渲染数据
// ================================================================

/** 迷雾图层 */
export interface FogLayer {
  visible_tiles: string[];
  explored_tiles: string[];
}

/** 驻防图层 */
export interface GarrisonLayer {
  tiles: Record<string, { troops: number; faction_id: string }>;
}

/** 行军图层 */
export interface MarchLayer {
  routes: MarchRoute[];
}

export interface MarchRoute {
  id: string;
  faction_id: string;
  from_tile: string;
  to_tile: string;
  troops: number;
  progress: number;
  path: string[];
}

/** 灾害图层 */
export interface DisasterLayer {
  disasters: Disaster[];
}

export interface Disaster {
  type: string;
  tile_id: string;
  severity: number;
  duration: number;
}

/** 外交图层 */
export interface DiplomacyLayer {
  alliances: AllianceLine[];
  wars: WarLine[];
}

export interface AllianceLine {
  from_faction: string;
  to_faction: string;
  type: string;
}

export interface WarLine {
  attacker: string;
  defender: string;
  war_score: number;
}

/** 建筑图层 */
export interface BuildingLayer {
  tiles: Record<string, TileBuilding>;
}

/** 图层数据集合 */
export interface LayerData {
  fog: FogLayer;
  garrison: GarrisonLayer;
  march: MarchLayer;
  disaster: DisasterLayer;
  diplomacy: DiplomacyLayer;
  building: BuildingLayer;
}

// ================================================================
// AI 智能体类型
// ================================================================

/** AI智能体状态 */
export interface AgentStatus {
  agent_id: string;        // A1~A8
  agent_name: string;
  status: 'idle' | 'thinking' | 'done' | 'error' | 'timeout';
  progress: number;        // 0-100
  message: string;
  start_time?: number;
  duration_ms?: number;
  result_summary?: string;
}

/** AI思考状态集合 */
export interface AIThinkingState {
  round: number;
  phase: string;
  agents: AgentStatus[];
  overall_progress: number;
}

// ================================================================
// NPC 对话类型
// ================================================================

/** 对话消息 */
export interface ChatMessage {
  role: 'user' | 'npc' | 'system';
  content: string;
  npc_id?: string;
  npc_name?: string;
  timestamp: number;
  emotion?: string;
}

/** 对话会话 */
export interface ConversationSession {
  session_id: string;
  npc_id: string;
  npc_name: string;
  faction_id: string;
  messages: ChatMessage[];
  started_round: number;
  last_active_round: number;
}

/** 廷议发言 */
export interface CourtStatement {
  npc_id: string;
  npc_name: string;
  content: string;
  stance: 'support' | 'oppose' | 'neutral';
  round: number;  // 廷议轮次（1-3）
}

// ================================================================
// 战争系统类型
// ================================================================

/** 宣战理由类型 */
export type CasusBelliType =
  | 'conquest' | 'reconquest' | 'vassal_conquest'
  | 'trade_conflict' | 'punishment' | 'independence'
  | 'holy_war' | 'border_dispute' | 'chastisement';

/** 宣战理由 */
export interface CasusBelli {
  type: CasusBelliType;
  name: string;
  score_multiplier: number;
  can_take_territory: boolean;
  max_territory?: number;
}

/** 战争状态 */
export interface WarState {
  war_id: string;
  attacker: string;
  defender: string;
  war_score: number;
  casus_belli: CasusBelli;
  started_round: number;
  events: WarEvent[];
}

/** 战争事件 */
export interface WarEvent {
  round: number;
  type: 'battle' | 'occupation' | 'siege' | 'treaty';
  description: string;
  score_change: number;
}

// ================================================================
// 圣旨/指令类型
// ================================================================

/** 圣旨指令 */
export interface EdictCommand {
  action: string;
  target?: string;
  tile_id?: string;
  amount?: number;
  params?: Record<string, unknown>;
}

/** 圣旨解析结果 */
export interface EdictResult {
  success: boolean;
  commands: EdictCommand[];
  narration: string;
  warnings: string[];
  costs: ResourceCost;
}

/** 资源消耗 */
export interface ResourceCost {
  treasury: number;
  grain: number;
  arms: number;
  horses: number;
  troops: number;
}

// ================================================================
// API 响应类型
// ================================================================

/** 统一API响应 */
export interface ApiResponse<T = unknown> {
  code: number;
  msg: string;
  data: T;
}

/** 游戏初始化响应 */
export interface GameInitData {
  world_state: WorldState;
  layer_data: LayerData;
  faction_config: Record<string, FactionData>;
}

/** 回合推进响应 */
export interface TurnAdvanceData {
  world_state: WorldState;
  events: GameEvent[];
  thinking_log: AgentStatus[];
  turn_summary: string;
}

/** 圣旨处理响应 */
export interface EdictProcessData {
  result: EdictResult;
  world_state_preview?: WorldState;
}

// ================================================================
// UI 状态类型
// ================================================================

/** 面板类型 */
export type PanelType =
  | 'advisor' | 'war' | 'diplomacy' | 'policy'
  | 'recruit' | 'march' | 'general' | 'spy'
  | 'ending' | 'replay' | 'settings' | 'security'
  | 'talent' | 'history' | 'batch_build' | 'batch_recruit'
  | 'treasury' | 'factions' | 'court' | 'disaster'
  | 'military' | 'events' | 'construction' | 'ai-strategy'
  | 'audio' | 'law' | 'law-interrogate' | 'royal'
  | 'medical' | 'sea' | 'vassal' | 'workshop'
  | 'prisoner' | 'personnel' | 'culture' | 'territory'
  | 'rebel' | 'ambush' | 'plunder' | 'moveCapital'
  | 'agent' | 'faction_network' | 'achievement'
  | 'techTree' | 'tutorial' | '';

/** 面板显示状态 */
export interface PanelVisibility {
  [key: string]: boolean;
}

/** 地图视图模式 */
export type MapViewMode = 'terrain' | 'political' | 'military' | 'economic' | 'admin';

/** 地图视口状态 */
export interface MapViewport {
  x: number;
  y: number;
  scale: number;
  width: number;
  height: number;
}
