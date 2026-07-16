/**
 * 势力纹章映射表 — Phase 2 视觉优化
 *
 * 为九大势力提供古典纹章设计（内联 SVG）。
 * 后续可由 illustrator Skill 生成矢量文件替换。
 */
export interface FactionEmblem {
  /** 势力 ID */
  id: string
  /** 纹章 SVG data URI */
  svg: string
  /** 纹章含义 */
  meaning: string
}

export const FACTION_EMBLEMS: FactionEmblem[] = [
  {
    id: 'faction_yuan',
    meaning: '蟠龙逐日 — 大元正统',
    svg: `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <circle cx="32" cy="20" r="8" fill="#C42828" opacity="0.8"/>
        <path d="M20 44 Q32 28 44 44 Q32 52 20 44Z" fill="#8B0000"/>
        <path d="M24 40 Q32 30 40 40" fill="none" stroke="#D4A860" stroke-width="1.5"/>
        <circle cx="32" cy="50" r="3" fill="#D4A860"/>
      </svg>`
    )}`,
  },
  {
    id: 'faction_zhuyuanzhang',
    meaning: '日月同辉 — 驱除鞑虏',
    svg: `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r="8" fill="#DC143C"/>
        <path d="M32 24 A12 8 0 0 1 32 40 A12 8 0 0 0 32 24Z" fill="#FF6B6B" opacity="0.6"/>
        <circle cx="32" cy="32" r="12" fill="none" stroke="#DC143C" stroke-width="1.5"/>
        <line x1="20" y1="8" x2="26" y2="18" stroke="#DC143C" stroke-width="1"/>
        <line x1="44" y1="8" x2="38" y2="18" stroke="#DC143C" stroke-width="1"/>
        <line x1="20" y1="56" x2="26" y2="46" stroke="#DC143C" stroke-width="1"/>
        <line x1="44" y1="56" x2="38" y2="46" stroke="#DC143C" stroke-width="1"/>
      </svg>`
    )}`,
  },
  {
    id: 'faction_chenyouliang',
    meaning: '汉江沧浪 — 水师无双',
    svg: `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <path d="M8 28 Q20 22 32 28 Q44 22 56 28" fill="none" stroke="#1E90FF" stroke-width="2"/>
        <path d="M8 38 Q20 32 32 38 Q44 32 56 38" fill="none" stroke="#1E90FF" stroke-width="2"/>
        <path d="M8 48 Q20 42 32 48 Q44 42 56 48" fill="none" stroke="#1E90FF" stroke-width="2"/>
        <path d="M20 16 L24 60" stroke="#1E90FF" stroke-width="2"/>
        <path d="M36 16 L32 60" stroke="#1E90FF" stroke-width="1.5"/>
        <rect x="28" y="18" width="12" height="6" rx="1" fill="#4682B4"/>
      </svg>`
    )}`,
  },
  {
    id: 'faction_zhangshicheng',
    meaning: '周鼎金帛 — 江南富庶',
    svg: `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <rect x="16" y="14" width="32" height="36" rx="4" fill="#FF8C00"/>
        <rect x="22" y="10" width="20" height="8" rx="2" fill="#FFA500"/>
        <rect x="28" y="6" width="8" height="6" rx="1" fill="#FFB347"/>
        <rect x="22" y="24" width="20" height="2" fill="#FFD700" opacity="0.5"/>
        <rect x="22" y="30" width="20" height="2" fill="#FFD700" opacity="0.5"/>
        <rect x="22" y="36" width="20" height="2" fill="#FFD700" opacity="0.5"/>
        <circle cx="32" cy="18" r="4" fill="none" stroke="#FFD700" stroke-width="1"/>
      </svg>`
    )}`,
  },
  {
    id: 'faction_fangguozhen',
    meaning: '海波翻涌 — 海上枭雄',
    svg: `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <path d="M4 32 Q12 24 20 32 Q28 40 36 32 Q44 24 52 32 Q60 40 60 32" fill="none" stroke="#20B2AA" stroke-width="2"/>
        <path d="M4 44 Q12 36 20 44 Q28 52 36 44 Q44 36 52 44 Q60 52 60 44" fill="none" stroke="#20B2AA" stroke-width="2" opacity="0.6"/>
        <path d="M24 12 L24 56" stroke="#20B2AA" stroke-width="2"/>
        <path d="M32 16 L32 52" stroke="#20B2AA" stroke-width="1.5"/>
        <rect x="20" y="10" width="24" height="8" rx="1" fill="#48D1CC" opacity="0.7"/>
      </svg>`
    )}`,
  },
  {
    id: 'faction_xushouhui',
    meaning: '莲花天完 — 弥勒降世',
    svg: `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <ellipse cx="32" cy="28" rx="6" ry="12" fill="#996633"/>
        <ellipse cx="20" cy="34" rx="5" ry="10" fill="#996633" opacity="0.7"/>
        <ellipse cx="44" cy="34" rx="5" ry="10" fill="#996633" opacity="0.7"/>
        <line x1="32" y1="16" x2="32" y2="60" stroke="#8B6914" stroke-width="2"/>
        <circle cx="32" cy="16" r="4" fill="#DAA520" opacity="0.5"/>
      </svg>`
    )}`,
  },
  {
    id: 'faction_mingyuzhen',
    meaning: '蜀道夏鼎 — 天府粮仓',
    svg: `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <rect x="18" y="12" width="28" height="36" rx="3" fill="#B8860B"/>
        <rect x="24" y="8" width="16" height="8" rx="2" fill="#DAA520"/>
        <path d="M20 28 L28 20 L44 20 L44 28" fill="none" stroke="#FFD700" stroke-width="1.5" opacity="0.6"/>
        <path d="M36 36 L44 28 L20 28 L20 36" fill="none" stroke="#FFD700" stroke-width="1.5" opacity="0.4"/>
        <circle cx="32" cy="14" r="3" fill="none" stroke="#FFD700" stroke-width="1"/>
      </svg>`
    )}`,
  },
  {
    id: 'faction_wangbaobao',
    meaning: '苍狼白鹿 — 铁骑无双',
    svg: `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <path d="M16 44 Q16 32 32 28 Q48 32 48 44 Q40 48 32 44 Q24 48 16 44Z" fill="#666699"/>
        <path d="M20 40 Q24 34 32 32 Q40 34 44 40" fill="none" stroke="#8888BB" stroke-width="1.5"/>
        <line x1="32" y1="8" x2="32" y2="28" stroke="#666699" stroke-width="2"/>
        <path d="M24 12 L32 8 L40 12" fill="none" stroke="#8888BB" stroke-width="1.5"/>
        <circle cx="28" cy="36" r="2" fill="#AAAACC"/>
        <circle cx="36" cy="36" r="2" fill="#AAAACC"/>
      </svg>`
    )}`,
  },
  {
    id: 'faction_mobei',
    meaning: '草原白鹿 — 成吉思汗',
    svg: `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <path d="M8 44 L24 12 L40 44 L48 60 L16 60Z" fill="#887766"/>
        <path d="M16 44 L24 20 L32 44 L40 28 L48 44" fill="none" stroke="#AA9988" stroke-width="1"/>
        <path d="M24 12 Q28 4 32 12" fill="none" stroke="#AA9988" stroke-width="1.5"/>
        <rect x="24" y="56" width="16" height="4" rx="1" fill="#665544"/>
      </svg>`
    )}`,
  },
]

/** 根据势力 ID 获取纹章 SVG */
export function getFactionEmblem(factionId: string): string | undefined {
  return FACTION_EMBLEMS.find(e => e.id === factionId)?.svg
}
