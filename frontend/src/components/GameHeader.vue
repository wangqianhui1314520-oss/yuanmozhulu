<template>
  <header class="game-header">
    <div class="header-left">
      <span class="faction-name" :style="{ color: playerColor }">
        {{ playerFaction?.name || '——' }}
      </span>
      <span class="faction-title">{{ playerFaction?.title || '' }}</span>
      <span class="header-sep">|</span>
      <span class="mode-badge" :class="store.gameMode">
        {{ store.gameMode === 'player_turn' ? '君主亲政' : '观战模式' }}
      </span>
      <span class="header-sep">|</span>
      <span class="date-inline">
        至正{{ store.currentYear }}年 · {{ store.currentMonth }}月 · <span class="season-badge" :class="'season-' + store.seasonName">{{ store.seasonName }}</span>
        <span class="weather-inline" v-if="weatherDisplay" :title="weatherDisplay.title">· {{ weatherDisplay.icon }} {{ weatherDisplay.type }}</span>
        <span class="round-inline">· 第{{ store.currentRound }}回合</span>
      </span>
    </div>

    <div class="header-center">
      <!-- 中间留空，日期已移至左上角 -->
    </div>

    <div class="header-right">
      <!-- 资源条 -->
      <div class="resource-group">
        <span class="resource r-gold" title="国库银两">
          <span class="r-icon">◈</span>银 {{ formatNum(playerFaction?.treasury) }}
        </span>
        <span class="resource r-grain" title="粮草储备">
          <span class="r-icon">◆</span>粮 {{ formatNum(playerFaction?.grain) }}
        </span>
        <span class="resource r-arms" title="军械">
          <span class="r-icon">⚒</span>械 {{ formatNum(playerFaction?.arms) }}
        </span>
        <span class="resource r-horses" title="战马">
          <span class="r-icon">♞</span>马 {{ formatNum(playerFaction?.horses) }}
        </span>
        <span class="resource r-troops" title="总兵力">
          <span class="r-icon">⚔</span>兵 {{ formatNum(store.totalTroops) }}
        </span>
      </div>
      <div class="header-sep-v"></div>
      <!-- 民心安定声望灾厄 -->
      <div class="stat-mini" :class="getStatAlertClass(store.realmStability, 40, 70)" title="境内民心：影响税收、人口增长、叛军概率">
        <span class="stat-label">民心</span>
        <span class="stat-val">{{ store.realmStability }}</span>
      </div>
      <div class="stat-mini" :class="getStatAlertClass(store.courtStability, 40, 70)" title="朝堂安定：影响官员忠诚、政令执行成功率">
        <span class="stat-label">朝纲</span>
        <span class="stat-val">{{ store.courtStability }}</span>
      </div>
      <div class="stat-mini" :class="getStatAlertClass(store.reputation, 30, 60)" title="声望：影响外交、纳贡、人才投奔">
        <span class="stat-label">声望</span>
        <span class="stat-val">{{ store.reputation }}</span>
      </div>
      <div class="stat-mini" id="stat-disaster" :class="getDisasterAlertClass(store.disasterIndex, 10, 30)" title="灾厄指数：越高越容易触发洪水/旱灾/蝗灾/瘟疫">
        <span class="stat-label">灾厄</span>
        <span class="stat-val">{{ store.disasterIndex }}</span>
      </div>
    </div>

    <!-- 功能按钮组 -->
    <div class="header-actions">
      <button v-audio class="hdr-btn" @click="$emit('open-policy')" title="国策总览">
        <span class="hdr-btn-icon">📜</span>三国策
      </button>
      <button v-audio class="hdr-btn" @click="$emit('open-advisor')" title="谋臣策问">
        <span class="hdr-btn-icon">🎓</span>策策问
      </button>
      <button v-audio class="hdr-btn" @click="$emit('open-factions-overview')" title="天下大势">
        <span class="hdr-btn-icon">🗺</span>势大势
      </button>
      <button v-audio class="hdr-btn" @click="$emit('open-save')" title="存档管理">
        <span class="hdr-btn-icon">💾</span>存存档
      </button>
      <button v-audio class="hdr-btn" @click="$emit('open-replay')" title="回放观战">
        <span class="hdr-btn-icon">🎬</span>回放
      </button>
      <button v-audio class="hdr-btn" @click="$router.push('/faction-gallery')" title="势力图鉴">
        <span class="hdr-btn-icon">📖</span>图鉴
      </button>
      <button v-audio class="hdr-btn" @click="$emit('open-settings')" title="游戏设置">
        <span class="hdr-btn-icon">⚙</span>设置
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '@/stores/gameStore'

defineEmits<{
  'open-policy': []
  'open-advisor': []
  'open-factions-overview': []
  'open-save': []
  'open-replay': []
  'open-settings': []
}>()

const store = useGameStore()

const playerFaction = computed(() => store.playerFaction)
const playerColor = computed(() => playerFaction.value?.color || '#B89B68')

// 天气显示映射
const WEATHER_MAP: Record<string, { icon: string; title: string }> = {
  '晴': { icon: '☀', title: '晴空万里' },
  '多云': { icon: '⛅', title: '多云' },
  '阴': { icon: '☁', title: '阴天' },
  '小雨': { icon: '🌧', title: '细雨绵绵' },
  '小雪': { icon: '🌨', title: '小雪纷飞' },
  '雷雨': { icon: '⛈', title: '雷雨交加' },
  '暴雨': { icon: '🌊', title: '暴雨倾盆' },
  '大雪': { icon: '❄', title: '大雪封山' },
  '大风': { icon: '💨', title: '狂风呼啸' },
  '霜冻': { icon: '🌫', title: '霜冻' },
  '酷热': { icon: '🔥', title: '酷热难耐' },
  '酷寒': { icon: '🥶', title: '天寒地冻' },
}

const weatherDisplay = computed(() => {
  const weather = store.weatherInfo as any
  if (!weather || !weather.type) return null
  const mapped = WEATHER_MAP[weather.type]
  return mapped ? { type: weather.type, icon: mapped.icon, title: mapped.title } : null
})

function formatNum(n: number | undefined): string {
  if (n === undefined) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function getStatAlertClass(v: number, low: number, high: number): string {
  if (v >= high) return ''
  if (v >= low) return 'stat-warn'
  return 'stat-bad'
}

function getDisasterAlertClass(v: number, low: number, high: number): string {
  if (v <= low) return ''
  if (v <= high) return 'stat-warn'
  return 'stat-bad'
}
</script>

<style scoped>
.game-header {
  display: flex;
  align-items: center;
  padding: 6px 14px;
  background: linear-gradient(180deg, #2C2824 0%, #1A1815 100%);
  border-bottom: 2px solid var(--gold);
  z-index: 100;
  flex-shrink: 0;
  gap: 10px;
  flex-wrap: wrap;
  min-height: 46px;
  position: relative;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-shrink: 0;
}

.faction-name {
  font-size: 22px;
  font-weight: bold;
  letter-spacing: 6px;
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
  text-shadow: 0 0 12px rgba(220, 180, 80, 0.25), 0 2px 4px rgba(0,0,0,0.7);
}

.faction-title {
  font-size: 13px;
  color: rgba(184, 150, 62, 0.55);
  letter-spacing: 3px;
}

.header-sep {
  color: var(--gold);
  opacity: 0.4;
  font-size: 12px;
}

.mode-badge {
  font-size: 10px;
  padding: 1px 8px;
  border: 1px solid var(--gold-dim);
  border-radius: var(--radius-sm);
  opacity: 0.8;
  letter-spacing: 2px;
  color: var(--gold);
}

.date-inline {
  font-size: 13px;
  letter-spacing: 2px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.weather-inline {
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 1px;
}

.round-inline {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 1px;
}

.header-center {
  text-align: center;
  flex-shrink: 0;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.season-badge {
  display: inline-block;
  padding: 0 2px;
  border-radius: 3px;
  font-weight: bold;
  transition: all 0.4s var(--ease-out);
}

.season-春 {
  color: #7EC87E;
  text-shadow: 0 0 6px rgba(126, 200, 126, 0.4);
}

.season-夏 {
  color: #E8985E;
  text-shadow: 0 0 6px rgba(232, 152, 94, 0.4);
}

.season-秋 {
  color: #D4B860;
  text-shadow: 0 0 6px rgba(212, 184, 96, 0.4);
}

.season-冬 {
  color: #88B8D8;
  text-shadow: 0 0 6px rgba(136, 184, 216, 0.4);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.resource-group {
  display: flex;
  gap: 10px;
}

.resource {
  font-size: 12px;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 3px;
  color: var(--text-secondary);
}

.r-icon {
  font-size: 10px;
  opacity: 0.6;
}

.r-gold { color: #D4B860; }
.r-grain { color: #8AB88A; }
.r-arms { color: #A0B4C8; }
.r-horses { color: #C8A870; }
.r-troops { color: #D07070; }

.header-sep-v {
  width: 1px;
  height: 20px;
  background: var(--border-main);
}

.stat-mini {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}

.stat-label {
  font-size: 9px;
  color: var(--text-dim);
  letter-spacing: 1px;
  font-family: "FangSong", "FangSong_GB2312", serif;
}

.stat-val {
  font-size: 13px;
  font-weight: bold;
  color: var(--jade);
}

.stat-mini.stat-warn .stat-val { color: var(--gold); animation: pulseGold 2s infinite; }
.stat-mini.stat-bad .stat-val { color: var(--danger); animation: pulseDanger 2s infinite; }

.header-actions {
  display: flex;
  gap: 3px;
  flex-shrink: 0;
}

.hdr-btn {
  padding: 5px 12px;
  font-size: 11px;
  font-family: "SimSun", serif;
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.15);
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: var(--radius-sm);
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all var(--duration-fast) var(--ease-out);
  white-space: nowrap;
}

.hdr-btn:hover {
  background: rgba(184, 155, 104, 0.12);
  border-color: var(--gold);
  color: var(--gold);
}

.hdr-btn:active { transform: translateY(1px); }

.hdr-btn-icon {
  font-size: 13px;
}
</style>
