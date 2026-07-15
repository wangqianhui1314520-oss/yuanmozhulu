<template>
  <div class="sandbox-intro-page" ref="pageRef">
    <!-- ===== 中央加载动画区 ===== -->
    <div class="intro-center" :class="{ 'done': animationDone }">
      <!-- 军旗十字交错背景 -->
      <div class="emblem-bg" :style="{ opacity: emblemOpacity }">
        <div class="emblem-ring"></div>
        <div class="emblem-ring emblem-ring-inner"></div>
        <div class="emblem-cross-h"></div>
        <div class="emblem-cross-v"></div>
        <div class="emblem-text">{{ factionAbbr }}</div>
      </div>

      <!-- 进度条轨道 -->
      <div class="progress-track" v-if="!animationDone">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        <div class="progress-glow" :style="{ left: progressPercent + '%' }"></div>
      </div>

      <!-- 加载文字 -->
      <div class="intro-texts" v-if="!animationDone">
        <p class="intro-phase">{{ currentPhase }}</p>
        <p class="intro-hint">{{ currentHint }}</p>
      </div>

      <!-- 完成后静态印记 -->
      <div class="done-stamp" v-if="animationDone">
        <p class="stamp-title">天 命 所 归</p>
        <p class="stamp-sub">{{ selectedFaction?.name }}</p>
      </div>
    </div>

    <!-- ===== 底部势力信息条（动画完成后出现） ===== -->
    <Transition name="slide-up">
      <div v-if="showFactionBar" class="faction-bar">
        <div class="bar-accent" :style="{ background: selectedFaction?.color }" />
        <div class="bar-content">
          <div class="bar-portrait" v-if="selectedFaction?.image">
            <img :src="selectedFaction.image" :alt="selectedFaction.name" />
          </div>
          <div class="bar-info">
            <div class="bar-difficulty" :class="'diff-' + getDiffClass(selectedFaction?.difficulty || '')">
              {{ selectedFaction?.difficulty }}
            </div>
            <h2 class="bar-name">{{ selectedFaction?.name }}</h2>
            <p class="bar-title">{{ selectedFaction?.title }}</p>
          </div>
          <div class="bar-stats">
            <div class="bar-stat">
              <span class="bs-val">{{ formatNum(selectedFaction?.initial_troops || 0) }}</span>
              <span class="bs-label">兵力</span>
            </div>
            <div class="bar-stat">
              <span class="bs-val">{{ formatNum(selectedFaction?.initial_treasury || 0) }}</span>
              <span class="bs-label">银两</span>
            </div>
            <div class="bar-stat">
              <span class="bs-val">{{ selectedFaction?.initial_territory?.length || 0 }}</span>
              <span class="bs-label">领地</span>
            </div>
          </div>
          <button class="bar-enter-btn" :disabled="isEntering" @click="enterGame">
            <span class="enter-main">举世入兵</span>
            <span class="enter-sub">逐 鹿 天 下</span>
          </button>
        </div>
      </div>
    </Transition>

    <!-- ===== 跳过按钮（动画期间可见） ===== -->
    <button class="skip-btn" v-if="!animationDone" @click="skipToEnd">
      跳过
    </button>

    <!-- ===== 控制栏 ===== -->
    <div class="audio-controls">
      <button class="audio-btn" @click="toggleMute" :title="isMuted ? '取消静音' : '静音'">
        {{ isMuted ? '🔇' : '🔊' }}
      </button>
      <button class="audio-btn" title="切换全屏" @click="toggleFullscreen">
        {{ isFullscreen ? '⤡' : '⤢' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useGameStore } from '@/stores/gameStore'
import { audioManager } from '@/utils/audioManager'
import { useFullscreen } from '@/composables/useFullscreen'
import type { FactionConfig } from '@/types'

const router = useRouter()
const route = useRoute()
const store = useGameStore()

const pageRef = ref<HTMLDivElement>()

// 势力数据
const selectedFaction = ref<FactionConfig | null>(null)
const selectedFactionId = ref('')
const isMuted = ref(false)
const { isFullscreen, toggleFullscreen } = useFullscreen()

// 动画状态
const showFactionBar = ref(false)
const isEntering = ref(false)
const animationDone = ref(false)
const emblemOpacity = ref(0)
const progressPercent = ref(0)

// 势力缩写（用于中央纹章）
const factionAbbr = computed(() => {
  const name = selectedFaction.value?.name || '?'
  return name.length > 2 ? name.slice(0, 2) : name
})

// 加载阶段文案
const phaseTexts = [
  { phase: '奉天命 · 承运启', hint: '山河舆图载入中…' },
  { phase: '聚群雄 · 列土疆', hint: '势力版图绘刻中…' },
  { phase: '整军备 · 厉兵秣马', hint: '军力数据演算中…' },
  { phase: '开国策 · 定朝纲', hint: '内政体系筹建中…' },
  { phase: '观星象 · 测天命', hint: '天时地利演算中…' },
]

const currentPhase = ref(phaseTexts[0].phase)
const currentHint = ref(phaseTexts[0].hint)

// ===== 生命周期 =====
let animTimer: ReturnType<typeof setTimeout> | null = null
let progressInterval: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  const factionId = (route.query.faction as string) || localStorage.getItem('yuanmo_player_faction') || ''
  if (!factionId) {
    router.push('/faction-select')
    return
  }

  selectedFactionId.value = factionId

  // 加载势力配置
  try {
    const { loadFactionsConfig } = await import('@/services/api')
    const config = await loadFactionsConfig()
    const faction = Object.values(config.factions || {}).find((f: any) => f.id === factionId) as FactionConfig
    if (faction) {
      selectedFaction.value = faction
    } else {
      selectedFaction.value = getBuiltinFaction(factionId)
    }
  } catch {
    selectedFaction.value = getBuiltinFaction(factionId)
  }

  // 启动动画
  startIntroAnimation()
})

onUnmounted(() => {
  audioManager.stopAll()
  if (animTimer) clearTimeout(animTimer)
  if (progressInterval) clearInterval(progressInterval)
})

// ===== 动画逻辑 =====
function startIntroAnimation() {
  // 纹章渐显
  setTimeout(() => {
    emblemOpacity.value = 0.6
  }, 200)

  // 进度条动画：分5阶段，每阶段约1.2秒，最后停在第6秒
  const totalDuration = 6000 // 6秒总时长
  const steps = 100
  const stepInterval = totalDuration / steps // 每步60ms
  let step = 0

  progressInterval = setInterval(() => {
    step++
    // 缓出曲线：快速到90%，然后慢下来
    const t = step / steps
    const eased = 1 - Math.pow(1 - t, 3)
    progressPercent.value = Math.min(eased * 100, 100)

    // 阶段文字切换
    const phaseIndex = Math.min(Math.floor(t * phaseTexts.length), phaseTexts.length - 1)
    currentPhase.value = phaseTexts[phaseIndex].phase
    currentHint.value = phaseTexts[phaseIndex].hint

    // 第5.8秒时纹章变亮
    if (t > 0.9) {
      emblemOpacity.value = 0.6 + (t - 0.9) * 6 // 递增到1.2（clamped in CSS）
    }

    if (step >= steps) {
      if (progressInterval) clearInterval(progressInterval)
      progressInterval = null

      // 进度条到达100%后停留1秒，然后完成
      animTimer = setTimeout(() => {
        onAnimationComplete()
      }, 1000)
    }
  }, stepInterval)
}

function skipToEnd() {
  if (progressInterval) clearInterval(progressInterval)
  if (animTimer) clearTimeout(animTimer)
  progressPercent.value = 100
  emblemOpacity.value = 1
  setTimeout(() => onAnimationComplete(), 300)
}

function onAnimationComplete() {
  animationDone.value = true
  emblemOpacity.value = 1

  // 短暂延迟后显示势力条
  setTimeout(() => {
    showFactionBar.value = true
  }, 500)

  // 播放势力配音
  const faction = selectedFaction.value
  if (faction) {
    const voicePlayed = audioManager.playFactionVoice(selectedFactionId.value)
    if (!voicePlayed && faction.voice) {
      audioManager.speakText(faction.voice)
    }
  }
}

// ===== 进入游戏 =====
async function enterGame() {
  if (isEntering.value) return
  isEntering.value = true

  const factionId = selectedFactionId.value
  localStorage.setItem('yuanmo_player_faction', factionId)

  try {
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('timeout')), 6000)
    )
    await Promise.race([store.startGame(factionId), timeoutPromise])
  } catch (err: any) {
    console.warn('后端开局未完成，将在游戏页使用本地数据:', err?.message || err)
  } finally {
    audioManager.stopAll()
    router.push(`/story-intro?faction=${factionId}`)
  }
}

function toggleMute() {
  isMuted.value = audioManager.toggleMute()
}

// ===== 工具函数 =====
function formatNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function getDiffClass(diff: string): string {
  const map: Record<string, string> = {
    '简单': 'easy', '普通': 'normal', '中等': 'medium',
    '困难': 'hard', '地狱': 'hell', '特殊': 'special',
  }
  return map[diff] || 'normal'
}

// 内置势力兜底数据
function getBuiltinFaction(factionId: string): FactionConfig {
  const BUILTIN: Record<string, FactionConfig> = {
    faction_yuan: {
      id: 'faction_yuan', name: '元顺帝', title: '大元皇帝', color: '#8B0000',
      capital_tile: 'tile_dadu', initial_territory: [], initial_treasury: 20000,
      initial_grain: 8000, initial_arms: 300, initial_horses: 200, initial_troops: 6000,
      initial_reputation: 60, personality_tags: ['蒙古铁骑', '正统名分', '勋贵侵蚀', '民族隔阂'],
      difficulty: '地狱', playable: true, image: '/assets/factions/ruler_yuan.jpg',
      voice: '朕承大元社稷，君临天下。卿既来辅朕，当重整河山，中兴大元。', buffs: [], debuffs: [],
      ai_logic: { expansion: 0.2, consolidation: 0.6, diplomacy: 0.3, military: 0.5, economy: 0.2 }
    },
    faction_zhuyuanzhang: {
      id: 'faction_zhuyuanzhang', name: '朱元璋', title: '吴国公', color: '#DC143C',
      capital_tile: 'tile_yingtian', initial_territory: [], initial_treasury: 8000,
      initial_grain: 4000, initial_arms: 80, initial_horses: 30, initial_troops: 3000,
      initial_reputation: 40, personality_tags: ['深谋远虑', '严刑峻法', '知人善任'],
      difficulty: '普通', playable: true, image: '/assets/factions/ruler_zhuyuan.jpg',
      voice: '孤起于淮右，布衣提三尺剑。高筑墙，广积粮，缓称王。', buffs: [], debuffs: [],
      ai_logic: { expansion: 0.6, consolidation: 0.4, diplomacy: 0.4, military: 0.6, economy: 0.5 }
    },
    faction_chenyouliang: {
      id: 'faction_chenyouliang', name: '陈友谅', title: '汉帝', color: '#1E90FF',
      capital_tile: 'tile_wuchang', initial_territory: [], initial_treasury: 12000,
      initial_grain: 6000, initial_arms: 150, initial_horses: 50, initial_troops: 5000,
      initial_reputation: 35, personality_tags: ['野心勃勃', '猜忌多疑', '水战精通'],
      difficulty: '困难', playable: true, image: '/assets/factions/ruler_chen.jpg',
      voice: '朕据荆楚，拥水师之利。朱元璋、张士诚皆不足惧。', buffs: [], debuffs: [],
      ai_logic: { expansion: 0.7, consolidation: 0.2, diplomacy: 0.2, military: 0.8, economy: 0.3 }
    },
    faction_zhangshicheng: {
      id: 'faction_zhangshicheng', name: '张士诚', title: '周王', color: '#FF8C00',
      capital_tile: 'tile_pingjiang', initial_territory: [], initial_treasury: 15000,
      initial_grain: 7000, initial_arms: 100, initial_horses: 40, initial_troops: 3500,
      initial_reputation: 45, personality_tags: ['偏安一隅', '富甲一方', '优柔寡断'],
      difficulty: '简单', playable: true, image: '/assets/factions/ruler_zhang.jpg',
      voice: '吾据江南膏腴之地。愿与卿共治吴越，以成霸业。', buffs: [], debuffs: [],
      ai_logic: { expansion: 0.2, consolidation: 0.7, diplomacy: 0.5, military: 0.3, economy: 0.8 }
    },
    faction_fangguozhen: {
      id: 'faction_fangguozhen', name: '方国珍', title: '浙东节度', color: '#20B2AA',
      capital_tile: 'tile_qingyuan', initial_territory: [], initial_treasury: 6000,
      initial_grain: 3000, initial_arms: 60, initial_horses: 20, initial_troops: 2000,
      initial_reputation: 30, personality_tags: ['海上枭雄', '投机善变', '重利轻义'],
      difficulty: '中等', playable: true, image: '/assets/factions/ruler_fang.jpg',
      voice: '海上有舟，舟山有兵。卿若随我，纵横浙东。', buffs: [], debuffs: [],
      ai_logic: { expansion: 0.3, consolidation: 0.5, diplomacy: 0.6, military: 0.3, economy: 0.7 }
    },
    faction_xushouhui: {
      id: 'faction_xushouhui', name: '徐寿辉', title: '天完皇帝', color: '#996633',
      capital_tile: 'tile_xiangyang', initial_territory: [], initial_treasury: 6000,
      initial_grain: 4000, initial_arms: 90, initial_horses: 40, initial_troops: 3500,
      initial_reputation: 35, personality_tags: ['弥勒信徒', '红巾领袖', '仁厚之主'],
      difficulty: '困难', playable: true, image: '/assets/factions/ruler_xushou.jpg',
      voice: '弥勒降世，明王出世。卿来辅我，当共复光明世界。', buffs: [], debuffs: [],
      ai_logic: { expansion: 0.5, consolidation: 0.3, diplomacy: 0.3, military: 0.6, economy: 0.3 }
    },
    faction_mingyuzhen: {
      id: 'faction_mingyuzhen', name: '明玉珍', title: '大夏皇帝', color: '#B8860B',
      capital_tile: 'tile_chongqing', initial_territory: [], initial_treasury: 6500,
      initial_grain: 5000, initial_arms: 90, initial_horses: 30, initial_troops: 3000,
      initial_reputation: 40, personality_tags: ['仁厚之主', '蜀道自守', '偏安一隅'],
      difficulty: '简单', playable: true, image: '/assets/factions/ruler_ming.jpg',
      voice: '孤据蜀道天险，守大夏之土。卿来辅我，共保西陲。', buffs: [], debuffs: [],
      ai_logic: { expansion: 0.2, consolidation: 0.7, diplomacy: 0.4, military: 0.3, economy: 0.6 }
    },
      faction_wangbaobao: {
      id: 'faction_wangbaobao', name: '王保保', title: '河南王', color: '#666699',
      capital_tile: 'tile_taiyuan', initial_territory: [], initial_treasury: 8000,
      initial_grain: 5000, initial_arms: 120, initial_horses: 150, initial_troops: 4000,
      initial_reputation: 45, personality_tags: ['忠勇无双', '骑兵统帅', '元廷柱石'],
      difficulty: '中等', playable: true, image: '/assets/factions/ruler_wang.jpg',
      voice: '吾乃扩廓帖木儿，大元最后的名将。铁骑所向，天下莫敢当。', buffs: [], debuffs: [],
      ai_logic: { expansion: 0.5, consolidation: 0.4, diplomacy: 0.3, military: 0.8, economy: 0.3 }
    },
    faction_mobei: {
      id: 'faction_mobei', name: '漠北诸部', title: '草原大汗', color: '#887766',
      capital_tile: 'tile_helin', initial_territory: [], initial_treasury: 5000,
      initial_grain: 2000, initial_arms: 80, initial_horses: 200, initial_troops: 4500,
      initial_reputation: 25, personality_tags: ['游牧骑射', '劫掠为生', '草原雄风'],
      difficulty: '困难', playable: true, image: '/assets/factions/ruler_tatar.jpg',
      voice: '草原雄鹰，驰骋万里。铁骑所至，皆为牧场。', buffs: [], debuffs: [],
      ai_logic: { expansion: 0.7, consolidation: 0.2, diplomacy: 0.2, military: 0.8, economy: 0.2 }
    },
  }
  return BUILTIN[factionId] || BUILTIN.faction_zhuyuanzhang
}
</script>

<style scoped>
.sandbox-intro-page {
  width: 100vw; height: 100vh;
  overflow: hidden; position: relative;
  background: radial-gradient(ellipse at center, #1a1410 0%, #0a0806 70%);
  color: #e0d5b8;
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  user-select: none;
}

/* ===== 中央区：纹章 + 进度条 + 文字 ===== */
.intro-center {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  display: flex; flex-direction: column;
  align-items: center; gap: 32px;
  z-index: 10;
  transition: opacity 0.6s;
}

/* -- 军旗纹章 -- */
.emblem-bg {
  position: relative;
  width: 180px; height: 180px;
  opacity: 0;
  transition: opacity 0.8s ease-out;
}

.emblem-ring {
  position: absolute; inset: 0;
  border: 2px solid rgba(200, 160, 60, 0.35);
  border-radius: 50%;
  animation: ringPulse 3s ease-in-out infinite;
}

.emblem-ring-inner {
  inset: 18px;
  border-color: rgba(200, 160, 60, 0.2);
  animation-delay: 0.6s;
  animation-duration: 3.5s;
}

@keyframes ringPulse {
  0%, 100% { transform: scale(1); opacity: 0.35; }
  50% { transform: scale(1.04); opacity: 0.55; }
}

.emblem-cross-h,
.emblem-cross-v {
  position: absolute;
  background: linear-gradient(90deg, transparent, rgba(200, 160, 60, 0.3), transparent);
}

.emblem-cross-h {
  top: 50%; left: 10%; right: 10%;
  height: 1px;
  transform: translateY(-0.5px);
}

.emblem-cross-v {
  left: 50%; top: 10%; bottom: 10%;
  width: 1px;
  background: linear-gradient(180deg, transparent, rgba(200, 160, 60, 0.3), transparent);
  transform: translateX(-0.5px);
}

.emblem-text {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 40px; color: rgba(200, 160, 60, 0.7);
  letter-spacing: 12px;
  text-shadow: 0 0 20px rgba(200, 160, 60, 0.3);
}

/* -- 进度条 -- */
.progress-track {
  width: 260px; height: 3px;
  background: rgba(200, 160, 60, 0.1);
  border-radius: 2px;
  position: relative;
  overflow: visible;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg,
    rgba(180, 130, 30, 0.5),
    rgba(200, 160, 60, 0.8),
    rgba(220, 180, 70, 0.6)
  );
  border-radius: 2px;
  transition: width 0.12s linear;
  box-shadow: 0 0 8px rgba(200, 160, 60, 0.2);
}

.progress-glow {
  position: absolute; top: -3px;
  width: 12px; height: 9px;
  background: radial-gradient(ellipse, rgba(220, 180, 70, 0.8), transparent 70%);
  border-radius: 50%;
  transform: translateX(-50%);
  transition: left 0.12s linear;
  filter: blur(1px);
}

/* -- 加载文字 -- */
.intro-texts {
  text-align: center;
}

.intro-phase {
  font-size: 18px; color: #c8a84a;
  letter-spacing: 6px; margin: 0;
  text-shadow: 0 0 12px rgba(200, 168, 74, 0.2);
}

.intro-hint {
  font-size: 12px; color: rgba(180, 150, 100, 0.5);
  letter-spacing: 3px; margin: 8px 0 0;
}

/* -- 完成印记 -- */
.intro-center.done .emblem-bg {
  opacity: 1;
}

.done-stamp {
  text-align: center;
  animation: stampIn 0.8s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.stamp-title {
  font-size: 32px; color: #c8a84a;
  letter-spacing: 14px; margin: 0;
  text-shadow: 0 0 30px rgba(200, 168, 74, 0.4), 0 0 60px rgba(200, 168, 74, 0.15);
}

.stamp-sub {
  font-size: 16px; color: rgba(200, 168, 74, 0.5);
  letter-spacing: 10px; margin: 10px 0 0;
}

@keyframes stampIn {
  0% { opacity: 0; transform: scale(1.4); filter: blur(4px); }
  100% { opacity: 1; transform: scale(1); filter: blur(0); }
}

/* ===== 势力信息条 ===== */
.faction-bar {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  z-index: 100;
  background: linear-gradient(0deg,
    rgba(10, 8, 6, 0.96) 0%,
    rgba(10, 8, 6, 0.85) 75%,
    transparent 100%
  );
  padding: 24px 40px 28px;
}

.bar-accent {
  position: absolute; top: 0; left: 0; right: 0;
  height: 3px; opacity: 0.7;
}

.bar-content {
  display: flex; align-items: center; gap: 20px;
  max-width: 1100px; margin: 0 auto;
}

.bar-portrait {
  width: 90px; height: 90px;
  border-radius: 4px; overflow: hidden;
  border: 2px solid rgba(184, 150, 62, 0.3);
  flex-shrink: 0;
  box-shadow: 0 0 20px rgba(184, 150, 62, 0.15);
}

.bar-portrait img {
  width: 100%; height: 100%; object-fit: cover; object-position: top;
}

.bar-info { flex-shrink: 0; }

.bar-difficulty {
  display: inline-block; padding: 1px 8px; font-size: 10px;
  border-radius: 2px; letter-spacing: 1px; margin-bottom: 4px;
}

.bar-name {
  font-size: 30px; font-weight: normal; color: #f0e6d8;
  letter-spacing: 10px; margin: 0;
  text-shadow: 0 0 14px rgba(220, 180, 80, 0.3), 0 2px 8px rgba(0,0,0,0.9);
}

.bar-title {
  font-size: 14px; color: rgba(200, 165, 80, 0.6);
  letter-spacing: 5px; margin: 6px 0 0;
}

.bar-stats {
  display: flex; gap: 24px; flex: 1; justify-content: center;
}

.bar-stat { display: flex; flex-direction: column; align-items: center; }

.bs-val {
  font-size: 22px; font-weight: bold;
  color: #b8963e;
  font-family: 'STKaiti', 'KaiTi', serif;
}

.bs-label {
  font-size: 10px; color: rgba(184, 150, 62, 0.35);
  letter-spacing: 3px; margin-top: 2px;
}

/* -- 举世入兵按钮 -- */
.bar-enter-btn {
  padding: 14px 36px;
  background: transparent;
  border: 2px solid rgba(184, 150, 62, 0.4);
  cursor: pointer;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  transition: all 0.3s; position: relative; overflow: hidden;
  flex-shrink: 0;
  animation: btnGlow 3s ease-in-out infinite;
}

.bar-enter-btn:hover {
  border-color: #b8963e;
  box-shadow: 0 0 40px rgba(184, 150, 62, 0.2),
              inset 0 0 40px rgba(184, 150, 62, 0.06);
  transform: scale(1.03);
}

.bar-enter-btn:disabled {
  opacity: 0.4; cursor: not-allowed; animation: none;
}

@keyframes btnGlow {
  0%, 100% { border-color: rgba(184, 150, 62, 0.4); }
  50% { border-color: rgba(200, 170, 80, 0.6); }
}

.enter-main {
  font-size: 18px; color: #e0d5b8;
  letter-spacing: 8px;
  font-family: 'STKaiti', 'KaiTi', serif;
}

.enter-sub {
  font-size: 10px; color: rgba(224, 213, 184, 0.4);
  letter-spacing: 6px;
}

/* ===== 跳过按钮 ===== */
.skip-btn {
  position: absolute; top: 20px; right: 20px; z-index: 100;
  padding: 8px 20px;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid rgba(184, 150, 62, 0.15);
  color: rgba(184, 150, 62, 0.5);
  font-size: 12px; letter-spacing: 3px; cursor: pointer;
  font-family: 'STKaiti', 'KaiTi', serif;
  transition: all 0.2s; border-radius: 3px;
}

.skip-btn:hover {
  background: rgba(0, 0, 0, 0.65);
  border-color: rgba(184, 150, 62, 0.35);
  color: #b8963e;
}

/* ===== 音量控制 ===== */
.audio-controls {
  position: absolute; top: 20px; left: 20px; z-index: 100;
  display: flex; gap: 10px;
}

.audio-btn {
  width: 36px; height: 36px;
  border: 1px solid rgba(184, 150, 62, 0.15);
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.45);
  font-size: 16px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
  color: rgba(200, 180, 140, 0.6);
}

.audio-btn:hover {
  background: rgba(0, 0, 0, 0.65);
  border-color: rgba(184, 150, 62, 0.35);
}

/* ===== 过渡动画 ===== */
.slide-up-enter-active {
  transition: all 0.7s cubic-bezier(0.22, 0.61, 0.36, 1);
}
.slide-up-leave-active {
  transition: all 0.3s ease-in;
}
.slide-up-enter-from {
  transform: translateY(80px); opacity: 0;
}
.slide-up-leave-to {
  transform: translateY(20px); opacity: 0;
}

/* ===== 难度色 ===== */
.diff-easy { background: #3a5a3a; color: rgba(255,255,255,0.8); }
.diff-normal { background: #4a5a2a; color: rgba(255,255,255,0.8); }
.diff-medium { background: #5a4a1a; color: rgba(255,255,255,0.8); }
.diff-hard { background: #5a2020; color: rgba(255,255,255,0.8); }
.diff-hell { background: #3a1010; color: rgba(255,255,255,0.8); }
.diff-special { background: #2a3a4a; color: rgba(255,255,255,0.8); }
</style>
