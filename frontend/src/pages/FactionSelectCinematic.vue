<template>
  <div class="cinematic-page" :class="{ 'selection-mode': showSelection }">

    <!-- ============ 15秒电影镜头阶段 ============ -->
    <div v-if="!showSelection" class="cinematic-stage">
      <!-- 全屏暗色背景（地图已移除） -->
      <div class="cinematic-map-wrap">
        <div class="cinematic-bg-fallback" />
      </div>

      <!-- 地图上方的暗色遮罩 -->
      <div class="cinematic-overlay" />

      <!-- 全屏按钮 -->
      <button class="cinematic-fullscreen-btn" title="切换全屏" @click="toggleFullscreen">
        {{ isFullscreen ? '⤡' : '⤢' }}
      </button>
      <!-- 跳过按钮 -->
      <button class="skip-btn" @click="skipCinematic">
        <span class="skip-text">跳过</span>
        <span class="skip-hint">点击跳过开场动画</span>
      </button>

      <!-- 中央标题 -->
      <div class="cinematic-title" :class="{ 'title-fade-out': titleFadingOut }">
        <h1 class="main-title">元末逐鹿</h1>
        <p class="sub-title">至正十一年 · 天下大乱 · 群雄并起</p>
        <div class="title-divider"></div>
        <p class="title-quote">"石人一只眼，挑动黄河天下反"</p>
      </div>

      <!-- 底部进度条 -->
      <div class="cinematic-progress">
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }" />
        </div>
        <div class="progress-label">{{ currentFactionName || '舆图纵览' }}</div>
      </div>
    </div>

    <!-- ============ 势力选择阶段 ============ -->
    <div v-else class="selection-stage">
      <!-- 背景（地图已移除） -->
      <div class="selection-map-bg">
        <div class="selection-bg-fallback" />
      </div>

      <!-- 顶部标题 -->
      <div class="selection-header">
        <h2 class="selection-title">择 主 入 世</h2>
        <p class="selection-subtitle">元末乱世 · 择一雄主 · 共逐鹿天下</p>
      </div>

      <!-- 势力卡片网格 -->
      <div class="faction-cards-container">
        <div class="faction-cards-grid">
          <div
            v-for="faction in factions"
            :key="faction.id"
            class="faction-card"
            :class="{ 'card-enter': cardEntered }"
            :style="{
              '--accent-color': faction.color,
              '--card-delay': faction.index * 0.08 + 's',
            }"
            @click="selectFaction(faction.id)"
          >
            <!-- 卡片顶部色条 -->
            <div class="card-accent" :style="{ background: faction.color }" />

            <!-- 卡片内容 -->
            <div class="card-body">
              <div class="card-name" :style="{ color: faction.color }">
                {{ faction.name }}
              </div>
              <div class="card-title">{{ faction.title }}</div>
              <div class="card-capital">
                <span class="capital-icon">&#x2302;</span>
                <span>{{ faction.capital }}</span>
              </div>
              <div class="card-desc">{{ faction.description }}</div>
            </div>

            <!-- 卡片底部发光边框 -->
            <div class="card-glow" :style="{ borderColor: faction.color }" />

            <!-- 悬停时的角标 -->
            <div class="card-corner-tl" :style="{ borderColor: faction.color }" />
            <div class="card-corner-br" :style="{ borderColor: faction.color }" />
          </div>
        </div>
      </div>

      <!-- 底部提示 -->
      <div class="selection-footer">
        <p class="footer-text">点击势力卡片，开始你的帝王霸业</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { gsap } from 'gsap'
import { useFullscreen } from '@/composables/useFullscreen'

const router = useRouter()

// ===== 状态 =====
const showSelection = ref(false)
const titleFadingOut = ref(false)
const cardEntered = ref(false)
const progressPercent = ref(0)
const currentFactionName = ref('')
let cinematicTimeline: gsap.core.Timeline | null = null
const isFullscreen = ref(false)

// ===== 势力数据 =====
interface FactionCard {
  id: string
  name: string
  title: string
  color: string
  capital: string
  description: string
  index: number
}

const factions = ref<FactionCard[]>([
  {
    id: 'faction_yuan', name: '元顺帝', title: '大元皇帝', color: '#8B0000',
    capital: '大都',
    description: '大元帝国末代皇帝，坐拥北地精锐铁骑。虽朝纲渐弛，勋贵侵蚀，然百足之虫死而不僵。',
    index: 0,
  },
  {
    id: 'faction_zhuyuanzhang', name: '朱元璋', title: '吴国公', color: '#DC143C',
    capital: '应天府',
    description: '出身寒微，崛起于濠州红巾。占据应天府为基业，广纳贤才，深谋远虑，以"驱逐胡虏，恢复中华"为号召。',
    index: 1,
  },
  {
    id: 'faction_chenyouliang', name: '陈友谅', title: '汉帝', color: '#1E90FF',
    capital: '武昌',
    description: '渔家出身，弑徐寿辉自立为汉帝。拥水师之利，据长江中游，兵锋最盛，野心勃勃欲吞并天下。',
    index: 2,
  },
  {
    id: 'faction_zhangshicheng', name: '张士诚', title: '周王', color: '#FF8C00',
    capital: '平江（苏州）',
    description: '盐贩起家，据江浙富庶之地。坐拥盐铁之利，府库充盈，然胸无大志，偏安一隅。',
    index: 3,
  },
  {
    id: 'faction_fangguozhen', name: '方国珍', title: '浙东节度', color: '#20B2AA',
    capital: '庆元（宁波）',
    description: '海上巨贾，据浙东沿海。精于海上贸易，富可敌国，然反复无常，首鼠两端。',
    index: 4,
  },
  {
    id: 'faction_xushouhui', name: '徐寿辉', title: '天完皇帝', color: '#996633',
    capital: '襄阳',
    description: '红巾军领袖，以弥勒降世号召民众，率先称帝建国。据荆襄形胜之地，然内忧外患。',
    index: 5,
  },
  {
    id: 'faction_mingyuzhen', name: '明玉珍', title: '大夏皇帝', color: '#B8860B',
    capital: '重庆',
    description: '红巾军将领，据巴蜀称帝。仁厚爱民，坐拥天府粮仓，然偏安蜀地，进取不足。',
    index: 6,
  },
  {
    id: 'faction_wangbaobao', name: '王保保', title: '河南王', color: '#666699',
    capital: '太原',
    description: '元末第一名将扩廓帖木儿，统率蒙古精锐铁骑。忠勇无双，为元室最后的中流砥柱。',
    index: 7,
  },
  {
    id: 'faction_mobei', name: '漠北诸部', title: '草原大汗', color: '#887766',
    capital: '和林',
    description: '蒙古草原部落联盟，游牧骑射如风。以战养战，纵横大漠，伺机南下逐鹿中原。',
    index: 8,
  },
])

// ===== 电影镜头动画（纯时间驱动，不依赖地图SVG） =====
function startCinematic() {
  const factionIds = [
    'faction_yuan', 'faction_zhuyuanzhang', 'faction_chenyouliang', 'faction_zhangshicheng',
    'faction_fangguozhen', 'faction_xushouhui', 'faction_mingyuzhen', 'faction_wangbaobao', 'faction_mobei',
  ]

  const totalDuration = 15
  const segDuration = 1.5
  const obj = { progress: 0 }

  cinematicTimeline = gsap.timeline({
    onUpdate: () => {
      progressPercent.value = Math.min(obj.progress * 100, 100)
      const elapsed = obj.progress * totalDuration
      // 根据时间更新当前显示的势力名称
      const segIndex = Math.min(Math.floor(elapsed / segDuration) - 1, factionIds.length - 1)
      if (segIndex >= 0) {
        const fid = factionIds[segIndex]
        const faction = factions.value.find(f => f.id === fid)
        if (faction) {
          currentFactionName.value = faction.name + ' · ' + faction.title
        }
      } else {
        currentFactionName.value = '舆图纵览'
      }
    },
    onComplete: () => {
      transitionToSelection()
    },
  })

  // 简单的时间进度动画
  cinematicTimeline.to(obj, {
    progress: 1,
    duration: totalDuration,
    ease: 'none',
  }, 0)

  // 标题淡出（在动画进行到一半时开始）
  gsap.to('.cinematic-title', {
    opacity: 0,
    duration: 1.5,
    delay: 8,
    ease: 'power2.out',
    onStart: () => { titleFadingOut.value = true },
  })
}

// ===== 过渡到选择界面 =====
function transitionToSelection() {
  showSelection.value = true

  // 淡入选择界面的元素
  nextTick(() => {
    // 使用 GSAP 动画显示卡片
    gsap.fromTo('.selection-header', 
      { opacity: 0, y: -30 },
      { opacity: 1, y: 0, duration: 0.8, ease: 'power2.out' }
    )

    gsap.fromTo('.selection-footer',
      { opacity: 0 },
      { opacity: 1, duration: 0.6, delay: 0.3, ease: 'power2.out' }
    )

    // 卡片依次出现
    cardEntered.value = true

    gsap.fromTo('.selection-map-bg',
      { opacity: 0 },
      { opacity: 1, duration: 1.2, ease: 'power2.out' }
    )
  })
}

// ===== 跳过电影镜头 =====
function skipCinematic() {
  if (cinematicTimeline) {
    cinematicTimeline.kill()
    cinematicTimeline = null
  }
  progressPercent.value = 100
  transitionToSelection()
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().then(() => { isFullscreen.value = true }).catch(() => {})
  } else {
    document.exitFullscreen().then(() => { isFullscreen.value = false }).catch(() => {})
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}

// ===== 选择势力 =====
function selectFaction(factionId: string) {
  // 存储选择
  localStorage.setItem('yuanmo_player_faction', factionId)
  // 路由跳转
  router.push({ path: '/game', query: { faction: factionId } })
}

// ===== 生命周期 =====
onMounted(() => {
  // 延迟启动电影镜头，给地图渲染留出时间
  setTimeout(() => {
    startCinematic()
  }, 600)
})

onUnmounted(() => {
  if (cinematicTimeline) {
    cinematicTimeline.kill()
    cinematicTimeline = null
  }
})
</script>

<style scoped>
/* ============================================================
   全局
   ============================================================ */
.cinematic-page {
  width: 100vw;
  height: 100vh;
  background: #120d08;
  overflow: hidden;
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  position: fixed;
  top: 0;
  left: 0;
}

/* ============================================================
   电影镜头阶段
   ============================================================ */
.cinematic-stage {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.cinematic-map-wrap {
  width: 100%;
  height: 100%;
  position: absolute;
  inset: 0;
}

.cinematic-bg-fallback {
  width: 100%;
  height: 100%;
  background:
    radial-gradient(ellipse at 30% 40%, rgba(184, 150, 62, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 60% 30%, rgba(184, 150, 62, 0.05) 0%, transparent 40%),
    linear-gradient(180deg, #1a1610 0%, #120d08 50%, #0d0a05 100%);
}

/* 地图上方暗色遮罩（营造电影感） */
.cinematic-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  pointer-events: none;
  background:
    radial-gradient(ellipse at 50% 50%, transparent 50%, rgba(18, 13, 8, 0.5) 85%, rgba(18, 13, 8, 0.85) 100%),
    linear-gradient(180deg, rgba(18, 13, 8, 0.6) 0%, transparent 30%, transparent 70%, rgba(18, 13, 8, 0.7) 100%);
}

/* 跳过按钮 */
.skip-btn {
  position: absolute;
  top: 24px;
  right: 28px;
  z-index: 50;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 18px;
  background: rgba(18, 13, 8, 0.7);
  border: 1px solid rgba(184, 150, 62, 0.3);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  font-family: 'STKaiti', 'KaiTi', serif;
}

.skip-btn:hover {
  background: rgba(30, 22, 12, 0.9);
  border-color: rgba(184, 150, 62, 0.6);
  box-shadow: 0 0 16px rgba(184, 150, 62, 0.15);
}

.skip-text {
  color: #b89b68;
  font-size: 13px;
  letter-spacing: 4px;
}

.skip-hint {
  color: #5a4a3a;
  font-size: 9px;
  letter-spacing: 2px;
}

/* 全屏按钮 */
.cinematic-fullscreen-btn {
  position: absolute;
  top: 24px;
  right: 130px;
  z-index: 50;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(18, 13, 8, 0.7);
  border: 1px solid rgba(184, 150, 62, 0.3);
  border-radius: 4px;
  color: #b89b68;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s;
  font-family: 'STKaiti', 'KaiTi', serif;
}

.cinematic-fullscreen-btn:hover {
  background: rgba(30, 22, 12, 0.9);
  border-color: rgba(184, 150, 62, 0.6);
  box-shadow: 0 0 16px rgba(184, 150, 62, 0.15);
}

/* 中央标题 */
.cinematic-title {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 20;
  text-align: center;
  pointer-events: none;
  transition: opacity 0.5s;
}

.main-title {
  font-size: 72px;
  color: #b89b68;
  letter-spacing: 20px;
  font-weight: normal;
  text-shadow:
    0 0 40px rgba(184, 150, 62, 0.4),
    0 0 80px rgba(184, 150, 62, 0.2),
    0 4px 8px rgba(0, 0, 0, 0.6);
  margin: 0 0 16px 0;
  animation: titleGlow 3s ease-in-out infinite alternate;
}

@keyframes titleGlow {
  0% { text-shadow: 0 0 40px rgba(184, 150, 62, 0.4), 0 0 80px rgba(184, 150, 62, 0.2); }
  100% { text-shadow: 0 0 60px rgba(184, 150, 62, 0.6), 0 0 120px rgba(184, 150, 62, 0.35); }
}

.sub-title {
  font-size: 16px;
  color: #8a7a5a;
  letter-spacing: 8px;
  margin: 0 0 20px 0;
}

.title-divider {
  width: 200px;
  height: 1px;
  margin: 0 auto 20px;
  background: linear-gradient(90deg, transparent, rgba(184, 150, 62, 0.5), transparent);
}

.title-quote {
  font-size: 14px;
  color: #6a5a3a;
  letter-spacing: 4px;
  font-style: italic;
}

.title-fade-out {
  opacity: 0;
}

/* 进度条 */
.cinematic-progress {
  position: absolute;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 30;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-width: 300px;
}

.progress-track {
  width: 100%;
  height: 2px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 1px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, rgba(184, 150, 62, 0.4), #b89b68, rgba(184, 150, 62, 0.4));
  border-radius: 1px;
  transition: width 0.1s linear;
}

.progress-label {
  font-size: 11px;
  color: #6a5a3a;
  letter-spacing: 3px;
}

/* ============================================================
   势力选择阶段
   ============================================================ */
.selection-stage {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.selection-map-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  opacity: 0.15;
  pointer-events: none;
}

.selection-bg-fallback {
  width: 100%;
  height: 100%;
  background:
    radial-gradient(ellipse at 50% 40%, rgba(184, 150, 62, 0.15) 0%, transparent 60%),
    linear-gradient(180deg, #1a1610 0%, #120d08 100%);
}

/* 遮罩渐变 */
.selection-stage::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background:
    radial-gradient(ellipse at 50% 30%, transparent 20%, rgba(18, 13, 8, 0.7) 70%),
    linear-gradient(180deg, rgba(18, 13, 8, 0.95) 0%, transparent 25%, transparent 75%, rgba(18, 13, 8, 0.95) 100%);
}

.selection-header {
  position: relative;
  z-index: 10;
  text-align: center;
  padding: 28px 0 0 0;
  flex-shrink: 0;
}

.selection-title {
  font-size: 40px;
  color: #b89b68;
  letter-spacing: 16px;
  font-weight: normal;
  margin: 0;
  text-shadow: 0 0 30px rgba(184, 150, 62, 0.3);
}

.selection-subtitle {
  font-size: 13px;
  color: #6a5a3a;
  letter-spacing: 6px;
  margin: 8px 0 0 0;
}

/* 势力卡片容器 */
.faction-cards-container {
  position: relative;
  z-index: 10;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 40px;
  overflow-y: auto;
}

.faction-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  max-width: 1100px;
  width: 100%;
}

/* 势力卡片 */
.faction-card {
  position: relative;
  background: linear-gradient(180deg, rgba(28, 22, 14, 0.95) 0%, rgba(20, 15, 8, 0.95) 100%);
  border: 1px solid rgba(60, 45, 25, 0.5);
  border-radius: 6px;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.35s cubic-bezier(0.25, 0.8, 0.25, 1.2);
  min-height: 160px;
  display: flex;
  flex-direction: column;
  opacity: 0;
  transform: translateY(30px);
}

.card-enter .faction-card {
  animation: cardSlideIn 0.6s cubic-bezier(0.25, 0.8, 0.25, 1) forwards;
  animation-delay: var(--card-delay);
}

@keyframes cardSlideIn {
  0% {
    opacity: 0;
    transform: translateY(30px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

.faction-card:hover {
  transform: translateY(-4px);
  border-color: var(--accent-color);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.5),
    0 0 20px color-mix(in srgb, var(--accent-color) 20%, transparent);
  background: linear-gradient(180deg, rgba(35, 28, 18, 0.98) 0%, rgba(25, 18, 10, 0.98) 100%);
}

.faction-card:active {
  transform: translateY(-2px) scale(0.98);
}

/* 卡片顶部色条 */
.card-accent {
  height: 3px;
  width: 100%;
  flex-shrink: 0;
  opacity: 0.8;
}

/* 卡片主体 */
.card-body {
  padding: 14px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-name {
  font-size: 20px;
  font-weight: bold;
  letter-spacing: 4px;
  line-height: 1.2;
}

.card-title {
  font-size: 12px;
  color: #8a7a5a;
  letter-spacing: 2px;
}

.card-capital {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #6a5a3a;
  letter-spacing: 1px;
}

.capital-icon {
  font-size: 13px;
  color: #b89b68;
}

.card-desc {
  font-size: 11px;
  color: #5a4a3a;
  line-height: 1.7;
  letter-spacing: 1px;
  margin-top: 4px;
}

/* 卡片底部发光边框 */
.card-glow {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  border-bottom: 1px solid;
  opacity: 0;
  transition: opacity 0.3s;
}

.faction-card:hover .card-glow {
  opacity: 0.6;
}

/* 角标 */
.card-corner-tl,
.card-corner-br {
  position: absolute;
  width: 12px;
  height: 12px;
  border: 1px solid;
  opacity: 0;
  transition: opacity 0.3s;
}

.card-corner-tl {
  top: 0;
  left: 0;
  border-right: none;
  border-bottom: none;
  border-radius: 6px 0 0 0;
}

.card-corner-br {
  bottom: 0;
  right: 0;
  border-left: none;
  border-top: none;
  border-radius: 0 0 6px 0;
}

.faction-card:hover .card-corner-tl,
.faction-card:hover .card-corner-br {
  opacity: 0.8;
}

/* 底部提示 */
.selection-footer {
  position: relative;
  z-index: 10;
  text-align: center;
  padding: 16px 0 24px 0;
  flex-shrink: 0;
}

.footer-text {
  font-size: 13px;
  color: #4a3a2a;
  letter-spacing: 4px;
  margin: 0;
}

/* ============================================================
   响应式
   ============================================================ */
@media (max-width: 900px) {
  .faction-cards-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .main-title {
    font-size: 48px;
    letter-spacing: 12px;
  }

  .selection-title {
    font-size: 28px;
    letter-spacing: 10px;
  }
}

@media (max-width: 600px) {
  .faction-cards-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .main-title {
    font-size: 36px;
    letter-spacing: 8px;
  }

  .faction-cards-container {
    padding: 12px 16px;
  }
}

/* ============================================================
   滚动条
   ============================================================ */
.faction-cards-container::-webkit-scrollbar {
  width: 4px;
}

.faction-cards-container::-webkit-scrollbar-track {
  background: transparent;
}

.faction-cards-container::-webkit-scrollbar-thumb {
  background: rgba(184, 150, 62, 0.15);
  border-radius: 2px;
}
</style>
