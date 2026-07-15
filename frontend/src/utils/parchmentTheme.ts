/**
 * 竹简舆图复古主题常量 V4.1
 * 统一适配《元末逐鹿》竹简墨色视觉体系
 * 全局字体统一仿古衬线宋体
 */

// ============================================================
// 全局字体
// ============================================================
export const FONT_FAMILY = '"Noto Serif SC", "Source Han Serif SC", "STSong", "SimSun", "FangSong", serif'
export const FONT_FAMILY_TITLE = '"STKaiti", "KaiTi", "Noto Serif SC", "SimSun", serif'
export const FONT_FAMILY_MONO = '"STKaiti", "KaiTi", "FangSong", "SimSun", serif'

// ============================================================
// 竹简舆图底色体系 V4.1
// ============================================================
export const PARCHMENT = {
  /** 全局竹简底层底色 */
  BASE: '#221d16',
  /** 略深的木牍 */
  MEDIUM: '#27221a',
  /** 深木牍 */
  DARK: '#1c1812',
  /** 竹简纹理覆盖色 */
  TEXTURE: 'rgba(184, 150, 62, 0.03)',
  /** 舆图边框色 */
  BORDER: '#3d3228',
  /** 舆图内阴影 */
  INNER_SHADOW: 'rgba(24, 20, 16, 0.5)',
}

// ============================================================
// 地形肌理底色（竹简水墨风格）
// ============================================================
export const TERRAIN_COLORS: Record<string, { fill: string; stroke: string; pattern: string }> = {
  farmland: {
    fill: '#b8c898',
    stroke: '#8a9a60',
    pattern: '#a8b888',
  },
  mountain: {
    fill: '#b0a090',
    stroke: '#8a7a64',
    pattern: '#a49880',
  },
  water: {
    fill: '#7a9ab0',
    stroke: '#4a7a90',
    pattern: '#6a8ea8',
  },
  coast: {
    fill: '#8aa8b8',
    stroke: '#5a8898',
    pattern: '#7a9cb0',
  },
  city: {
    fill: '#c8b898',
    stroke: '#b8a068',
    pattern: '#c0b088',
  },
  pass: {
    fill: '#b0a088',
    stroke: '#7a6a58',
    pattern: '#a09078',
  },
  port: {
    fill: '#7898b0',
    stroke: '#2a6888',
    pattern: '#688ea0',
  },
  desert: {
    fill: '#d8c8a0',
    stroke: '#c8b888',
    pattern: '#d0c098',
  },
  grassland: {
    fill: '#a8b888',
    stroke: '#7a9848',
    pattern: '#98a870',
  },
}

// ============================================================
// 势力色彩体系 V4.1（竹简底色适配）
// ============================================================
export const FACTION_PALETTE: Record<string, { primary: string; secondary: string; glow: string }> = {
  faction_yuan:          { primary: '#9B4A3A', secondary: '#B86858', glow: 'rgba(155, 74, 58, 0.35)' },
  faction_zhuyuanzhang:  { primary: '#B85050', secondary: '#D47070', glow: 'rgba(184, 80, 80, 0.35)' },
  faction_chenyouliang:  { primary: '#4A6A8A', secondary: '#6A8AAA', glow: 'rgba(74, 106, 138, 0.35)' },
  faction_zhangshicheng: { primary: '#B89850', secondary: '#D4B870', glow: 'rgba(184, 152, 80, 0.35)' },
  faction_fangguozhen:   { primary: '#3A7888', secondary: '#5A98A8', glow: 'rgba(58, 120, 136, 0.35)' },
  faction_xushouhui:     { primary: '#C47060', secondary: '#E09080', glow: 'rgba(196, 112, 96, 0.35)' },
  faction_mingyuzhen:    { primary: '#A88848', secondary: '#C8A868', glow: 'rgba(168, 136, 72, 0.35)' },
  faction_wangbaobao:    { primary: '#6A5888', secondary: '#8A78A8', glow: 'rgba(106, 88, 136, 0.35)' },
  faction_mobei:         { primary: '#6A7A5A', secondary: '#8A9A7A', glow: 'rgba(106, 122, 90, 0.35)' },
}

// ============================================================
// 三级战争迷雾 V4.1（竹简底色适配）
// ============================================================
export const FOG_OF_WAR = {
  /** 未探索 - 全竹简遮挡 */
  UNEXPLORED: {
    fill: '#27221a',
    opacity: 0.94,
    stroke: 'transparent',
  },
  /** 已探索褪色 - 半可见 */
  EXPLORED: {
    fill: '#322b20',
    opacity: 0.6,
    stroke: 'rgba(184, 150, 62, 0.15)',
  },
  /** 完全可视 - 无蒙版 */
  VISIBLE: {
    fill: 'transparent',
    opacity: 0,
    stroke: 'transparent',
  },
}

// ============================================================
// 路线样式 V4.1
// ============================================================
export const ROUTE_STYLES = {
  march: {
    stroke: '#c43a3a',
    dash: [8, 4],
    width: 2.5,
    glow: 'rgba(196, 58, 58, 0.35)',
  },
  spy: {
    stroke: '#4a4a4a',
    dash: [3, 6],
    width: 1.5,
    glow: 'rgba(74, 74, 74, 0.2)',
  },
  trade: {
    stroke: '#b8963e',
    dash: [6, 4, 2, 4],
    width: 2,
    glow: 'rgba(184, 150, 62, 0.3)',
  },
}

// ============================================================
// 文本色系 V4.1
// ============================================================
export const TEXT_COLORS = {
  PRIMARY: '#e0d5b8',
  SECONDARY: '#c4b898',
  DIM: '#8c8068',
  GOLD: '#b8963e',
  ACCENT: '#c43a3a',
}

// ============================================================
// 阴影与高亮 V4.1
// ============================================================
export const EFFECTS = {
  SELECTED_GLOW: 'rgba(184, 150, 62, 0.5)',
  HOVER_GLOW: 'rgba(255, 255, 255, 0.12)',
  PLAYER_HIGHLIGHT: 'rgba(184, 150, 62, 0.15)',
  SIEGE_GLOW: 'rgba(196, 58, 58, 0.45)',
  DISASTER_GLOW: 'rgba(196, 58, 58, 0.4)',
}
