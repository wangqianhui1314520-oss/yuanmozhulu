/**
 * NPC 肖像映射表 — Phase 1 视觉优化
 *
 * 覆盖全部 38 名文臣武将 + 9 名势力君主 = 47 个肖像条目。
 * 肖像文件统一放在 /assets/portraits/{npc_id}.webp
 *
 * 当真实图片不存在时，CharacterPortrait 组件会自动回退到 Canvas 程序化绘制。
 */

/** NPC ID → 肖像路径 */
export const NPC_PORTRAIT_MAP: Record<string, string> = {
  // ========== 元廷 (6人) ==========
  tuotuo: '/assets/portraits/tuotuo.webp',
  chahan_temur: '/assets/portraits/chahan_temur.webp',
  hama: '/assets/portraits/hama.webp',
  chen_you_ding: '/assets/portraits/chen_you_ding.webp',
  zhang_han: '/assets/portraits/zhang_han.webp',
  boluo_temur: '/assets/portraits/boluo_temur.webp',

  // ========== 朱元璋 (15人) ==========
  liu_ji: '/assets/portraits/liu_ji.webp',
  li_shanchang: '/assets/portraits/li_shanchang.webp',
  xu_da: '/assets/portraits/xu_da.webp',
  chang_yuchun: '/assets/portraits/chang_yuchun.webp',
  song_lian: '/assets/portraits/song_lian.webp',
  hu_weiyong: '/assets/portraits/hu_weiyong.webp',
  zhu_sheng: '/assets/portraits/zhu_sheng.webp',
  tao_an: '/assets/portraits/tao_an.webp',
  zhang_zhong: '/assets/portraits/zhang_zhong.webp',
  wang_guangyang: '/assets/portraits/wang_guangyang.webp',
  kang_maocai: '/assets/portraits/kang_maocai.webp',
  deng_yu: '/assets/portraits/deng_yu.webp',
  ye_chen: '/assets/portraits/ye_chen.webp',
  ma_huanghou: '/assets/portraits/ma_huanghou.webp',
  feng_guoyong: '/assets/portraits/feng_guoyong.webp',

  // ========== 陈友谅 (5人) ==========
  zhang_dingbian: '/assets/portraits/zhang_dingbian.webp',
  zou_pusheng: '/assets/portraits/zou_pusheng.webp',
  zhang_bixian: '/assets/portraits/zhang_bixian.webp',
  luo_fucheng: '/assets/portraits/luo_fucheng.webp',
  chen_li: '/assets/portraits/chen_li.webp',

  // ========== 张士诚 (4人) ==========
  zhang_shide: '/assets/portraits/zhang_shide.webp',
  lv_zhen: '/assets/portraits/lv_zhen.webp',
  pan_yuanming: '/assets/portraits/pan_yuanming.webp',
  zhang_shixin: '/assets/portraits/zhang_shixin.webp',

  // ========== 方国珍 (1人) ==========
  fang_guozhen: '/assets/portraits/fang_guozhen.webp',

  // ========== 徐寿辉 (4人) ==========
  xushou_hui: '/assets/portraits/xushou_hui.webp',
  ni_wenjun: '/assets/portraits/ni_wenjun.webp',
  liu_futong: '/assets/portraits/liu_futong.webp',
  peng_yingyu: '/assets/portraits/peng_yingyu.webp',

  // ========== 明玉珍 (4人) ==========
  ming_yuzhen: '/assets/portraits/ming_yuzhen.webp',
  liu_zhen: '/assets/portraits/liu_zhen.webp',
  dai_shou: '/assets/portraits/dai_shou.webp',
  wan_sheng: '/assets/portraits/wan_sheng.webp',

  // ========== 王保保 (4人) ==========
  wang_baobao: '/assets/portraits/wang_baobao.webp',
  li_siqi: '/assets/portraits/li_siqi.webp',
  kuo_kuo: '/assets/portraits/kuo_kuo.webp',
  zhang_liangbi: '/assets/portraits/zhang_liangbi.webp',

  // ========== 鞑靼 (1人) ==========
  tatar_khan: '/assets/portraits/tatar_khan.webp',

  // ========== 流浪/中立 (1人) ==========
  yao_guangxiao: '/assets/portraits/yao_guangxiao.webp',
}

/** 势力 ID → 君主肖像路径（与 RULER_IMAGE_MAP 相同，新增场景变体） */
export const RULER_PORTRAIT_MAP: Record<string, string> = {
  faction_yuan: '/assets/factions/ruler_yuan.jpg',
  faction_zhuyuanzhang: '/assets/factions/ruler_zhuyuan.jpg',
  faction_chenyouliang: '/assets/factions/ruler_chen.jpg',
  faction_zhangshicheng: '/assets/factions/ruler_zhang.jpg',
  faction_fangguozhen: '/assets/factions/ruler_fang.jpg',
  faction_xushouhui: '/assets/factions/ruler_xushou.jpg',
  faction_mingyuzhen: '/assets/factions/ruler_ming.jpg',
  faction_wangbaobao: '/assets/factions/ruler_wang.jpg',
  faction_mobei: '/assets/factions/ruler_tatar.jpg',
}

/**
 * 根据 NPC ID 或势力 ID 获取肖像路径。
 * 返回 undefined 表示无图片，由 Canvas 兜底绘制。
 */
export function getPortraitUrl(npcId?: string, factionId?: string): string | undefined {
  if (npcId && NPC_PORTRAIT_MAP[npcId]) {
    return NPC_PORTRAIT_MAP[npcId]
  }
  if (factionId && RULER_PORTRAIT_MAP[factionId]) {
    return RULER_PORTRAIT_MAP[factionId]
  }
  return undefined
}
