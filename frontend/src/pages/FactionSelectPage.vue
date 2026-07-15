<template>
  <div class="faction-page">
    <!-- 动态背景层 -->
    <div class="bg-layer" ref="bgLayerRef" @mousemove="onBgMouseMove" @mouseleave="onBgMouseLeave">
      <img
        class="bg-image"
        src="/assets/factions/faction_select_bg.jpg"
        alt="乱世山河"
        :style="bgParallaxStyle"
      />
      <!-- 鼠标光晕 -->
      <div class="bg-glow" :style="mouseGlowStyle" />
      <div class="bg-overlay" />
      <!-- 动态粒子/战火效果 -->
      <div class="bg-particles">
        <span
          v-for="i in 30"
          :key="i"
          class="particle"
          :style="particleStyle(i)"
        />
      </div>
    </div>

    <!-- 加载中状态 -->
    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p class="loading-title">天下大势，加载中……</p>
      <p class="loading-hint">正在与后端同步势力数据</p>
    </div>

    <!-- 空状态（加载完成后仍无数据） -->
    <div v-else-if="factions.length === 0" class="empty-state">
      <p class="empty-title">暂无可用势力</p>
      <p class="empty-hint">
        <template v-if="loadError">网络请求失败：{{ loadError }}</template>
        <template v-else>请确认后端服务已启动（端口 8800），然后刷新页面重试</template>
      </p>
      <div class="empty-actions">
        <button class="empty-btn" @click="retryLoad">重试加载</button>
        <button class="empty-btn secondary" @click="useBuiltinData">使用内置数据</button>
      </div>
    </div>

    <!-- 主界面 -->
    <div v-else class="faction-main">
      <!-- 标题区 -->
      <header class="page-header">
        <button class="btn-back" v-audio @click="router.push('/')">
          <span class="back-icon">←</span>
          <span>返回首页</span>
        </button>
        <div class="title-group">
          <h1 class="page-title">择 主 入 世</h1>
          <p class="page-subtitle">元末乱世 · 择一雄主 · 共逐鹿天下</p>
        </div>
        <div class="header-actions">
          <button class="icon-btn" :title="isMuted ? '开启音效' : '静音'" @click="toggleMute">
            <span class="icon">{{ isMuted ? '🔇' : '🔊' }}</span>
          </button>
          <button class="icon-btn" title="切换全屏" @click="toggleFullscreen">
            <span class="icon">{{ isFullscreen ? '⤡' : '⤢' }}</span>
          </button>
        </div>
      </header>

      <!-- 主体区域：左侧列表 + 右侧展台 -->
      <div class="faction-body">
        <!-- 左侧可折叠势力列表 -->
        <div class="faction-sidebar" :class="{ collapsed: sidebarCollapsed }">
          <div class="sidebar-inner">
            <div class="sidebar-header">
              <span class="sidebar-title">群 雄 列 传</span>
              <span class="sidebar-count">{{ factions.length }} 位</span>
            </div>
            <div class="sidebar-list">
              <div
                v-for="faction in factions"
                :key="faction.id"
                class="sidebar-item"
                :class="{ active: confirmedId === faction.id, hover: hoveredId === faction.id }"
                v-audio
                @click="onCardClick(faction)"
                @mouseenter="onCardHover(faction.id)"
                @mouseleave="onCardLeave(faction.id)"
              >
                <div class="si-portrait">
                  <img :src="faction.image" :alt="faction.name" />
                </div>
                <div class="si-info">
                  <div class="si-name">{{ faction.name }}</div>
                  <div class="si-title">{{ faction.title }}</div>
                </div>
                <span class="si-difficulty" :class="'diff-' + getDiffClass(faction.difficulty)">
                  {{ faction.difficulty }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 折叠/展开手柄 -->
        <button v-audio class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed" :title="sidebarCollapsed ? '展开势力列表' : '收起势力列表'">
          <span class="toggle-arrow" :class="{ flipped: sidebarCollapsed }">◀</span>
        </button>

        <!-- 人物散布区域 -->
        <div class="characters-stage">
          <div
            v-for="(faction, index) in factions"
            :key="faction.id"
            class="character-card"
            :class="{
              hovered: hoveredId === faction.id,
              confirmed: confirmedId === faction.id,
              leaving: leavingId === faction.id,
            }"
            :style="cardPosition(index)"
            v-audio
            @mouseenter="onCardHover(faction.id)"
            @mouseleave="onCardLeave(faction.id)"
            @click="onCardClick(faction)"
          >
            <!-- 卡片背面装饰 -->
            <div class="card-backdrop" />
            <!-- 人物立绘 -->
            <div class="card-figure">
              <img :src="faction.image" :alt="faction.name" />
            </div>
            <!-- 底部铭牌 -->
            <div class="card-plaque">
              <span class="plaque-difficulty" :class="'diff-' + getDiffClass(faction.difficulty)">
                {{ faction.difficulty }}
              </span>
              <h3 class="plaque-name">{{ faction.name }}</h3>
              <p class="plaque-title">{{ faction.title }}</p>
            </div>
            <!-- 选中光效 -->
            <div class="card-glow-ring" />
            <!-- 悬浮提示 -->
            <div class="hover-hint" v-if="hoveredId === faction.id && confirmedId !== faction.id">
              点击查看详情
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 详情面板（确认选择后显示） -->
    <Transition name="panel-slide">
      <div v-if="confirmedFaction" class="detail-overlay" @click.self="cancelConfirm">
        <div class="detail-panel" :style="{ '--accent': confirmedFaction.color }">
          <button v-audio class="panel-close" @click="cancelConfirm">✕</button>

          <div class="panel-body">
            <!-- 大幅肖像 -->
            <div class="panel-portrait">
              <img :src="confirmedFaction.image" :alt="confirmedFaction.name" />
              <div class="portrait-vignette" />
            </div>

            <!-- 信息区 -->
            <div class="panel-info">
              <div class="panel-header">
                <span class="panel-difficulty" :class="'diff-' + getDiffClass(confirmedFaction.difficulty)">
                  {{ confirmedFaction.difficulty }}
                </span>
                <h2 class="panel-name">{{ confirmedFaction.name }}</h2>
                <p class="panel-title">{{ confirmedFaction.title }}</p>
              </div>

              <!-- 独白 -->
              <blockquote v-if="confirmedFaction.voice" class="panel-voice">
                "{{ confirmedFaction.voice }}"
              </blockquote>

              <!-- AI 音色信息 -->
              <div v-if="voiceInfo" class="panel-voice-info">
                <span class="voice-info-label">🎙 AI配音</span>
                <span class="voice-info-desc">{{ voiceInfo.role }} · {{ voiceInfo.desc }}</span>
              </div>

              <!-- 三维数据 -->
              <div class="panel-stats">
                <div class="panel-stat">
                  <span class="stat-icon">⚔</span>
                  <span class="stat-val">{{ formatNumber(confirmedFaction.initial_troops) }}</span>
                  <span class="stat-label">兵力</span>
                </div>
                <div class="panel-stat">
                  <span class="stat-icon">◈</span>
                  <span class="stat-val">{{ formatNumber(confirmedFaction.initial_treasury) }}</span>
                  <span class="stat-label">银两</span>
                </div>
                <div class="panel-stat">
                  <span class="stat-icon">⬡</span>
                  <span class="stat-val">{{ confirmedFaction.initial_territory.length }}</span>
                  <span class="stat-label">领地</span>
                </div>
              </div>

              <!-- 个性标签 -->
              <div class="panel-tags">
                <span v-for="tag in confirmedFaction.personality_tags" :key="tag" class="panel-tag">
                  {{ tag }}
                </span>
              </div>

              <!-- 优劣势 -->
              <div class="panel-traits">
                <div v-if="confirmedFaction.buffs.length" class="trait-block buffs">
                  <span class="trait-label">✦ 优势</span>
                  <p v-for="b in confirmedFaction.buffs" :key="b.name" class="trait-line buff">
                    {{ b.name }}：{{ b.effect }}
                  </p>
                </div>
                <div v-if="confirmedFaction.debuffs.length" class="trait-block debuffs">
                  <span class="trait-label">✧ 劣势</span>
                  <p v-for="d in confirmedFaction.debuffs" :key="d.name" class="trait-line debuff">
                    {{ d.name }}：{{ d.effect }}
                  </p>
                </div>
              </div>

              <!-- 操作按钮 -->
              <div class="panel-actions">
                <button v-audio class="btn-voice" @click="playFactionVoice">
                  <span class="btn-icon">🔊</span>
                  <span>听其言</span>
                </button>
                <button v-audio class="btn-enter" :disabled="isStarting" @click="startGame">
                  <span class="enter-text">举 兵 入 世</span>
                  <span class="enter-sub">逐 鹿 天 下</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/gameStore'
import { loadFactionsConfig } from '@/services/api'
import { audioManager } from '@/utils/audioManager'
import { useFullscreen } from '@/composables/useFullscreen'
import type { FactionConfig } from '@/types'
const router = useRouter()
const gameStore = useGameStore()

const loading = ref(true)
const loadError = ref('')
const factions = ref<FactionConfig[]>([])
const hoveredId = ref('')
const confirmedId = ref('')
const leavingId = ref('')
const confirmedFaction = ref<FactionConfig | null>(null)
const isStarting = ref(false)
const sidebarCollapsed = ref(false)
const { isFullscreen, toggleFullscreen } = useFullscreen()

/** 当前选中势力的 AI 音色配置信息 */
const voiceInfo = computed(() => {
  if (!confirmedFaction.value) return null
  return audioManager.getVoiceInfo(confirmedFaction.value.id)
})
const isMuted = ref(false)

// ============================================================
// 鼠标轨迹动态化
// ============================================================
const bgLayerRef = ref<HTMLElement | null>(null)
const mouseX = ref(0.5)
const mouseY = ref(0.5)
const mouseActive = ref(false)
// 缓动后的值，用于平滑跟随
const smoothX = ref(0.5)
const smoothY = ref(0.5)
const smoothGlowX = ref(50)
const smoothGlowY = ref(50)
let animFrameId = 0

function onBgMouseMove(e: MouseEvent) {
  if (!bgLayerRef.value) return
  const rect = bgLayerRef.value.getBoundingClientRect()
  mouseX.value = (e.clientX - rect.left) / rect.width
  mouseY.value = (e.clientY - rect.top) / rect.height
  mouseActive.value = true
}

function onBgMouseLeave() {
  mouseActive.value = false
}

// 平滑跟随动画循环
function animateMouseTrail() {
  // 用 lerp 平滑缓动
  const lerp = 0.06
  if (mouseActive.value) {
    smoothX.value += (mouseX.value - smoothX.value) * lerp
    smoothY.value += (mouseY.value - smoothY.value) * lerp
  } else {
    // 鼠标离开后缓慢回中
    smoothX.value += (0.5 - smoothX.value) * lerp * 0.4
    smoothY.value += (0.5 - smoothY.value) * lerp * 0.4
  }
  // 光晕位置更快跟随
  const glowLerp = 0.12
  smoothGlowX.value += (mouseX.value * 100 - smoothGlowX.value) * glowLerp
  smoothGlowY.value += (mouseY.value * 100 - smoothGlowY.value) * glowLerp

  animFrameId = requestAnimationFrame(animateMouseTrail)
}

onMounted(() => {
  animFrameId = requestAnimationFrame(animateMouseTrail)
  // 预加载势力 AI 配音配置 + 音频文件（非阻塞，静默失败）
  audioManager.loadVoiceConfigs().then(() => {
    audioManager.preloadAllFactionVoices()
  }).catch(() => { /* 配音预加载失败不影响主流程 */ })
})

onUnmounted(() => {
  if (animFrameId) cancelAnimationFrame(animFrameId)
  // 离开势力选择界面时，只停止配音/语音，BGM 保持不变（首页和势力选择共用同一段音频）
  audioManager.stopVoice()
})

// 背景视差偏移样式
const bgParallaxStyle = computed(() => {
  const ox = (smoothX.value - 0.5) * 24  // ±12px
  const oy = (smoothY.value - 0.5) * 16  // ±8px
  const scale = mouseActive.value ? 1.06 : 1.02
  return {
    transform: `translate(${ox}px, ${oy}px) scale(${scale})`,
    transition: mouseActive.value ? 'none' : 'transform 1.5s ease-out',
  }
})

// 鼠标光晕样式
const mouseGlowStyle = computed(() => {
  return {
    left: `${smoothGlowX.value}%`,
    top: `${smoothGlowY.value}%`,
    opacity: mouseActive.value ? 0.55 : 0,
    transition: mouseActive.value ? 'opacity 0.3s ease' : 'opacity 1s ease',
  }
})

// ============================================================
// 内置势力数据（后端不可用时兜底）
// ============================================================
const BUILTIN_FACTIONS: FactionConfig[] = [
  {
    id: 'faction_yuan', name: '元顺帝', title: '大元皇帝', color: '#8B0000',
    capital_tile: 'tile_dadu', initial_territory: ['tile_dadu', 'tile_shangdu', 'tile_taiyuan', 'tile_datong', 'tile_jinan', 'tile_zhending', 'tile_baoding', 'tile_hejian', 'tile_daming', 'tile_pingyang', 'tile_yanan', 'tile_xian', 'tile_ganzhou', 'tile_suzhou_gs', 'tile_ningxia', 'tile_liaoyang', 'tile_shenyang', 'tile_helin', 'tile_karakorum'],
    initial_treasury: 20000, initial_grain: 8000, initial_arms: 300, initial_horses: 200, initial_troops: 6000, initial_reputation: 60,
    personality_tags: ['蒙古铁骑', '正统名分', '勋贵侵蚀', '民族隔阂'], difficulty: '地狱', playable: true,
    image: '/assets/factions/ruler_yuan.jpg',
    voice: '朕承大元社稷，君临天下。然乱世汹汹，红巾四起。卿既来辅朕，当重整河山，中兴大元。',
    buffs: [
      { name: '北地铁骑', effect: '骑兵战力+35%', type: 'military' },
      { name: '正统名分', effect: '初始声望+20', type: 'diplomacy' }
    ],
    debuffs: [
      { name: '勋贵侵蚀', effect: '每月国库流失2%银两', type: 'economy' },
      { name: '民族隔阂', effect: '汉人地块每月民心-5', type: 'civil' },
      { name: '朝堂腐败', effect: '朝堂稳定度每月-2', type: 'court' }
    ],
    ai_logic: { expansion: 0.2, consolidation: 0.6, diplomacy: 0.3, military: 0.5, economy: 0.2 }
  },
  {
    id: 'faction_zhuyuanzhang', name: '朱元璋', title: '吴国公', color: '#DC143C',
    capital_tile: 'tile_yingtian', initial_territory: ['tile_yingtian', 'tile_chuzhou', 'tile_hezhou', 'tile_taiping', 'tile_zhenjiang', 'tile_changzhou', 'tile_huizhou', 'tile_ningguo', 'tile_guangde', 'tile_raozhou', 'tile_xinzhou'],
    initial_treasury: 8000, initial_grain: 4000, initial_arms: 80, initial_horses: 30, initial_troops: 3000, initial_reputation: 40,
    personality_tags: ['深谋远虑', '严刑峻法', '知人善任'], difficulty: '普通', playable: true,
    image: '/assets/factions/ruler_zhuyuan.jpg',
    voice: '孤起于淮右，布衣提三尺剑，渡江取金陵。高筑墙，广积粮，缓称王。今日择我入世，必当驱除鞑虏，恢复中华。',
    buffs: [
      { name: '安民之治', effect: '流民转化率+30%', type: 'civil' },
      { name: '屯田养兵', effect: '驻军粮草消耗-20%', type: 'military' }
    ],
    debuffs: [
      { name: '文武党争', effect: '朝堂派系冲突概率+20%', type: 'court' },
      { name: '根基未固', effect: '初始兵力较少', type: 'military' }
    ],
    ai_logic: { expansion: 0.6, consolidation: 0.4, diplomacy: 0.4, military: 0.6, economy: 0.5 }
  },
  {
    id: 'faction_chenyouliang', name: '陈友谅', title: '汉帝', color: '#1E90FF',
    capital_tile: 'tile_wuchang', initial_territory: ['tile_wuchang', 'tile_jiangzhou', 'tile_yuezhou', 'tile_changsha', 'tile_hengzhou', 'tile_jingjiang', 'tile_longxing', 'tile_jian', 'tile_ganzhou_jx', 'tile_xiangyang', 'tile_jingzhou', 'tile_yichang', 'tile_huangzhou', 'tile_de_an'],
    initial_treasury: 12000, initial_grain: 6000, initial_arms: 150, initial_horses: 50, initial_troops: 5000, initial_reputation: 35,
    personality_tags: ['野心勃勃', '猜忌多疑', '水战精通'], difficulty: '困难', playable: true,
    image: '/assets/factions/ruler_chen.jpg',
    voice: '朕据荆楚，拥水师之利，志在一统。朱元璋、张士诚皆不足惧。择我者，当共图九五之尊。',
    buffs: [
      { name: '倾国水师', effect: '水战战力+50%', type: 'military' },
      { name: '荆楚粮仓', effect: '粮食产量+20%', type: 'economy' }
    ],
    debuffs: [
      { name: '苛政失心', effect: '民心下降速度+30%', type: 'civil' },
      { name: '弑主之名', effect: '外交好感度-15', type: 'diplomacy' }
    ],
    ai_logic: { expansion: 0.7, consolidation: 0.2, diplomacy: 0.2, military: 0.8, economy: 0.3 }
  },
  {
    id: 'faction_zhangshicheng', name: '张士诚', title: '周王', color: '#FF8C00',
    capital_tile: 'tile_pingjiang', initial_territory: ['tile_pingjiang', 'tile_hangzhou', 'tile_songjiang', 'tile_huzhou', 'tile_jiaxin', 'tile_shaoxing', 'tile_gaoyou', 'tile_yangzhou', 'tile_taizhou_js'],
    initial_treasury: 15000, initial_grain: 7000, initial_arms: 100, initial_horses: 40, initial_troops: 3500, initial_reputation: 45,
    personality_tags: ['偏安一隅', '富甲一方', '优柔寡断'], difficulty: '简单', playable: true,
    image: '/assets/factions/ruler_zhang.jpg',
    voice: '吾据江南膏腴之地，富甲一方。然天下未定，岂能偏安？愿与卿共治吴越，以成霸业。',
    buffs: [
      { name: '江南富庶', effect: '税收+30%', type: 'economy' },
      { name: '海运通商', effect: '贸易收入+25%', type: 'economy' }
    ],
    debuffs: [
      { name: '偏安惰性', effect: '扩张意愿-40%', type: 'military' },
      { name: '盐贩出身', effect: '士绅支持度-20%', type: 'court' }
    ],
    ai_logic: { expansion: 0.2, consolidation: 0.7, diplomacy: 0.5, military: 0.3, economy: 0.8 }
  },
  {
    id: 'faction_fangguozhen', name: '方国珍', title: '浙东节度', color: '#20B2AA',
    capital_tile: 'tile_qingyuan', initial_territory: ['tile_qingyuan', 'tile_taizhou_zj', 'tile_wenzhou', 'tile_zhoushan'],
    initial_treasury: 6000, initial_grain: 3000, initial_arms: 60, initial_horses: 20, initial_troops: 2000, initial_reputation: 30,
    personality_tags: ['海上枭雄', '投机善变', '重利轻义'], difficulty: '中等', playable: true,
    image: '/assets/factions/ruler_fang.jpg',
    voice: '海上有舟，舟山有兵。吾以海贸立世，进退自如。卿若随我，纵横浙东，何愁大事不成。',
    buffs: [
      { name: '海上通商', effect: '海上贸易收入+50%', type: 'economy' },
      { name: '水师精锐', effect: '水战战力+40%', type: 'military' }
    ],
    debuffs: [
      { name: '海运命脉', effect: '海上封锁时经济崩溃', type: 'economy' },
      { name: '根基浅薄', effect: '领地防御薄弱', type: 'military' }
    ],
    ai_logic: { expansion: 0.3, consolidation: 0.5, diplomacy: 0.6, military: 0.3, economy: 0.7 }
  },
  {
    id: 'faction_xushouhui', name: '徐寿辉', title: '天完皇帝', color: '#996633',
    capital_tile: 'tile_xiangyang', initial_territory: ['tile_xiangyang', 'tile_huangzhou', 'tile_de_an', 'tile_runing', 'tile_yingzhou', 'tile_nanyang'],
    initial_treasury: 6000, initial_grain: 4000, initial_arms: 90, initial_horses: 40, initial_troops: 3500, initial_reputation: 35,
    personality_tags: ['弥勒信徒', '红巾领袖', '仁厚之主'], difficulty: '困难', playable: true,
    image: '/assets/factions/ruler_xushou.jpg',
    voice: '弥勒降世，明王出世。吾举义旗，为天下苍生。卿来辅我，当共复光明世界。',
    buffs: [
      { name: '弥勒号召', effect: '流民征兵效率+50%', type: 'military' },
      { name: '红巾正统', effect: '占领地块民心转化+20%', type: 'civil' }
    ],
    debuffs: [
      { name: '根基不稳', effect: '朝堂稳定度每月-3', type: 'court' },
      { name: '四面楚歌', effect: '邻国关系初始-10', type: 'diplomacy' }
    ],
    ai_logic: { expansion: 0.5, consolidation: 0.3, diplomacy: 0.3, military: 0.6, economy: 0.3 }
  },
  {
    id: 'faction_mingyuzhen', name: '明玉珍', title: '大夏皇帝', color: '#B8860B',
    capital_tile: 'tile_chongqing', initial_territory: ['tile_chongqing', 'tile_chengdu', 'tile_kuizhou', 'tile_baoning', 'tile_xuzhou_sc', 'tile_zunyi', 'tile_shunqing', 'tile_jiading'],
    initial_treasury: 6500, initial_grain: 5000, initial_arms: 90, initial_horses: 30, initial_troops: 3000, initial_reputation: 40,
    personality_tags: ['仁厚之主', '蜀道自守', '偏安一隅'], difficulty: '简单', playable: true,
    image: '/assets/factions/ruler_ming.jpg',
    voice: '孤据蜀道天险，守大夏之土。民安物阜，关河稳固。卿来辅我，可共保西陲，以观天下之变。',
    buffs: [
      { name: '蜀道天险', effect: '防御战力+40%', type: 'military' },
      { name: '天府粮仓', effect: '粮食产量+25%', type: 'economy' }
    ],
    debuffs: [
      { name: '封闭桎梏', effect: '贸易收入-30%', type: 'economy' },
      { name: '出川艰难', effect: '进攻行军消耗+50%', type: 'military' }
    ],
    ai_logic: { expansion: 0.2, consolidation: 0.7, diplomacy: 0.4, military: 0.3, economy: 0.6 }
  },
  {
    id: 'faction_wangbaobao', name: '王保保', title: '河南王', color: '#666699',
    capital_tile: 'tile_taiyuan', initial_territory: ['tile_taiyuan', 'tile_datong', 'tile_pingyang', 'tile_yanan', 'tile_ganzhou', 'tile_lintao'],
    initial_treasury: 8000, initial_grain: 5000, initial_arms: 120, initial_horses: 150, initial_troops: 4000, initial_reputation: 45,
    personality_tags: ['忠勇无双', '骑兵统帅', '元廷柱石', '蒙古铁骑'], difficulty: '中等', playable: true,
    image: '/assets/factions/ruler_wang.jpg',
    voice: '吾乃扩廓帖木儿，大元最后的名将。铁骑所向，天下莫敢当。卿若随我，共保大元江山。',
    buffs: [
      { name: '铁骑无双', effect: '骑兵战力+40%', type: 'military' },
      { name: '忠义之名', effect: '将领忠诚度+20%', type: 'court' }
    ],
    debuffs: [
      { name: '两线作战', effect: '南北同时用兵，资源消耗+30%', type: 'military' },
      { name: '朝堂猜忌', effect: '元廷内部掣肘', type: 'court' }
    ],
    ai_logic: { expansion: 0.5, consolidation: 0.4, diplomacy: 0.3, military: 0.8, economy: 0.3 }
  },
  {
    id: 'faction_mobei', name: '漠北诸部', title: '草原大汗', color: '#887766',
    capital_tile: 'tile_helin', initial_territory: ['tile_helin', 'tile_karakorum', 'tile_shangdu', 'tile_liaoyang', 'tile_shenyang'],
    initial_treasury: 5000, initial_grain: 2000, initial_arms: 80, initial_horses: 200, initial_troops: 4500, initial_reputation: 25,
    personality_tags: ['游牧骑射', '劫掠为生', '草原雄风'], difficulty: '困难', playable: true,
    image: '/assets/factions/ruler_tatar.jpg',
    voice: '草原雄鹰，驰骋万里。漠北诸部，铁骑所至，皆为牧场。卿若随我，纵横大漠，逐鹿中原。',
    buffs: [
      { name: '游牧骑射', effect: '骑兵战力+45%', type: 'military' },
      { name: '以战养战', effect: '战斗胜利获得额外银两+30%', type: 'economy' }
    ],
    debuffs: [
      { name: '无固定根基', effect: '非草原地块收益-40%', type: 'economy' },
      { name: '部落内斗', effect: '朝堂稳定度每月-2', type: 'court' }
    ],
    ai_logic: { expansion: 0.7, consolidation: 0.2, diplomacy: 0.2, military: 0.8, economy: 0.2 }
  }
]

const fallbackMap = new Map(BUILTIN_FACTIONS.map(f => [f.id, f]))

// ============================================================
// 数据加载（带 loading 状态 + 安全超时）
// ============================================================
const LOAD_TIMEOUT_MS = 8000  // 8秒超时后自动降级

async function loadFactions() {
  loading.value = true
  loadError.value = ''
  try {
    // 使用 Promise.race 设置加载超时，避免无限等待
    const config = await Promise.race([
      loadFactionsConfig(),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('势力配置加载超时')), LOAD_TIMEOUT_MS)
      ),
    ])
    const list = Object.values(config.factions || {}).filter(f => f.playable)
    if (list.length > 0) {
      factions.value = list.map(f => {
        const fallback = fallbackMap.get(f.id)
        return { ...fallback, ...f, image: f.image || fallback?.image, voice: f.voice || fallback?.voice }
      })
    } else {
      console.warn('[FactionSelect] 后端势力列表为空，使用内置默认数据')
      factions.value = BUILTIN_FACTIONS
    }
  } catch (err: any) {
    const msg = err?.message || String(err)
    console.warn('[FactionSelect] 势力配置加载失败:', msg)
    loadError.value = msg
    // 自动降级到内置数据（静默回退，确保用户始终能看到势力选择界面）
    console.warn('[FactionSelect] 自动回退到内置势力数据')
    factions.value = BUILTIN_FACTIONS
    loadError.value = ''  // 使用内置数据后清除错误
  } finally {
    loading.value = false
  }
}

function retryLoad() {
  loadFactions()
}

function useBuiltinData() {
  factions.value = BUILTIN_FACTIONS
  loading.value = false
  loadError.value = ''
}

onMounted(async () => {
  await loadFactions()

  // 同步静音状态
  isMuted.value = audioManager.isMuted
  try {
    const saved = localStorage.getItem('yuanmo_audio')
    if (saved) {
      const parsed = JSON.parse(saved)
      isMuted.value = parsed.muted || false
      if (isMuted.value !== audioManager.isMuted) {
        audioManager.toggleMute()
      }
    }
  } catch { /* ignore */ }

  // 确保背景音乐继续播放
  if (!audioManager.isBgmPlaying()) {
    audioManager.playBgm('main_menu', 1.5)
  }
})

function toggleMute() {
  isMuted.value = audioManager.toggleMute()
  try {
    const saved = localStorage.getItem('yuanmo_audio')
    const audio = saved ? JSON.parse(saved) : {}
    audio.muted = isMuted.value
    localStorage.setItem('yuanmo_audio', JSON.stringify(audio))
  } catch { /* ignore */ }
}

// ============================================================
// 9 人物在画布上的位置编排（模拟参考图布局）
// ============================================================
function cardPosition(index: number) {
  // 3x3 网格映射到画面各位置，大卡片适配
  const positions = [
    // 第一行
    { left: '5%',  top: '6%',   rx: '-2deg', ry: '3deg' },   // 0: 左上
    { left: '37%', top: '3%',   rx: '0deg',  ry: '-2deg' },  // 1: 中上
    { left: '69%', top: '6%',   rx: '2deg',  ry: '3deg' },   // 2: 右上
    // 第二行
    { left: '5%',  top: '35%',  rx: '-3deg', ry: '1deg' },   // 3: 左中
    { left: '37%', top: '32%',  rx: '0deg',  ry: '0deg' },   // 4: 正中
    { left: '69%', top: '35%',  rx: '3deg',  ry: '-1deg' },  // 5: 右中
    // 第三行
    { left: '5%',  top: '64%',  rx: '-1deg', ry: '-2deg' },  // 6: 左下
    { left: '37%', top: '61%',  rx: '1deg',  ry: '2deg' },   // 7: 中下
    { left: '69%', top: '64%',  rx: '2deg',  ry: '-2deg' },  // 8: 右下
  ]
  const p = positions[index] || positions[4]
  const delay = index * 0.08
  return {
    '--card-left': p.left,
    '--card-top': p.top,
    '--card-rx': p.rx,
    '--card-ry': p.ry,
    '--card-delay': `${delay}s`,
  }
}

// 粒子样式
function particleStyle(i: number) {
  const seed = (i * 137.508) % 360
  const sizeType = i % 4
  const sizes = ['1.5px', '2px', '2.5px', '3px']
  const glows = ['3px', '4px', '5px', '6px']
  const floatX = [-12, 18, -8, 22, -15, 10][i % 6]
  const floatY = [-40, -70, -55, -80, -45, -65][i % 6]
  return {
    '--px': `${10 + (i * 47) % 80}%`,
    '--py': `${8 + (i * 31) % 84}%`,
    '--pd': `${3.5 + (i % 5) * 1.8}s`,
    '--ps': `${0.35 + (i % 4) * 0.2}`,
    '--ph': `${seed}deg`,
    '--psize': sizes[sizeType],
    '--pglow': glows[sizeType],
    '--pfx': `${floatX}px`,
    '--pfy': `${floatY}px`,
  }
}

// ============================================================
// 交互逻辑
// ============================================================
function onCardHover(id: string) {
  hoveredId.value = id
}

function onCardLeave(id: string) {
  if (hoveredId.value === id) {
    hoveredId.value = ''
  }
}

function onCardClick(faction: FactionConfig) {
  // 如果已经确认了另一个，先取消
  if (confirmedId.value && confirmedId.value !== faction.id) {
    leavingId.value = confirmedId.value
    setTimeout(() => { leavingId.value = '' }, 400)
  }
  confirmedId.value = faction.id
  confirmedFaction.value = faction
  hoveredId.value = ''
  // 点击确认后播放语音
  setTimeout(() => playFactionVoice(), 500)
}

function cancelConfirm() {
  confirmedId.value = ''
  confirmedFaction.value = null
  // 停止当前配音（AI 音频 + 浏览器 TTS 降级）
  audioManager.stopVoice()
}

function playFactionVoice() {
  const faction = confirmedFaction.value
  if (!faction) return
  const voiceText = faction.voice || ''
  // 使用 AI 音频管理器播放，自动处理：
  // 1. 优先本地 edge-tts 生成的 MP3 文件
  // 2. 文件缺失时请求后端实时生成
  // 3. 最终降级到浏览器 SpeechSynthesis
  audioManager.playFactionVoiceAI(faction.id, voiceText)
}

async function startGame() {
  if (!confirmedFaction.value || isStarting.value) return
  const factionId = confirmedFaction.value.id

  // 停止当前配音
  audioManager.stopVoice()
  // 逐渐消声——选完势力后 BGM 淡出，过渡到加载界面
  audioManager.fadeOutBgm(2.5)
  localStorage.setItem('yuanmo_player_faction', factionId)

  // 直接跳转沙盘介绍（→故事背景→游戏对局）
  isStarting.value = true
  await router.push(`/sandbox-intro?faction=${factionId}`).catch(() => {})
  // 导航完成后重置状态（仅在导航失败时有效；成功时组件已卸载）
  isStarting.value = false
}

function formatNumber(n: number): string {
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
</script>

<style scoped>
/* ============================================================
 * 势力选择页 — 动态背景 + 散布人物卡片 + 详情面板
 * ============================================================ */

.faction-page {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
  background: #0a0806;
  color: #e0d5b8;
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
  user-select: none;
}

/* ============================================================
 * 背景层
 * ============================================================ */
.bg-layer {
  position: absolute;
  inset: -20px;
  z-index: 0;
  cursor: crosshair;
}
.bg-image {
  width: calc(100% + 40px);
  height: calc(100% + 40px);
  object-fit: cover;
  object-position: center;
  /* 默认缓慢漂移，被 JS 视差覆盖 */
  animation: bgDrift 40s ease-in-out infinite alternate;
}
@keyframes bgDrift {
  0% { transform: translate(0, 0) scale(1.02); }
  25% { transform: translate(-8px, -4px) scale(1.04); }
  50% { transform: translate(4px, -12px) scale(1.06); }
  75% { transform: translate(10px, 2px) scale(1.03); }
  100% { transform: translate(-4px, 8px) scale(1.05); }
}

/* 鼠标光晕 */
.bg-glow {
  position: absolute;
  width: 380px;
  height: 380px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle at center,
    rgba(220, 160, 60, 0.25) 0%,
    rgba(200, 130, 40, 0.12) 20%,
    rgba(180, 100, 30, 0.04) 40%,
    rgba(150, 80, 20, 0.01) 60%,
    transparent 70%
  );
  pointer-events: none;
  z-index: 5;
  mix-blend-mode: screen;
  filter: blur(2px);
  will-change: left, top, opacity;
}

.bg-overlay {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 50% 30%, transparent 0%, rgba(10, 8, 6, 0.55) 50%, rgba(10, 8, 6, 0.88) 100%),
    linear-gradient(180deg, rgba(10, 8, 6, 0.75) 0%, rgba(10, 8, 6, 0.35) 35%, rgba(10, 8, 6, 0.8) 100%);
  pointer-events: none;
}

/* 浮动粒子（战火/尘埃） */
.bg-particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.particle {
  position: absolute;
  left: var(--px, 50%);
  top: var(--py, 50%);
  width: var(--psize, 2px);
  height: var(--psize, 2px);
  background: rgba(200, 160, 80, 0.6);
  border-radius: 50%;
  box-shadow: 0 0 var(--pglow, 4px) var(--pglow, 2px) rgba(200, 120, 30, 0.3);
  animation: particleFloat var(--pd, 5s) ease-in-out infinite;
  animation-delay: calc(var(--pd, 5s) * -0.5);
  opacity: 0;
}
@keyframes particleFloat {
  0% { opacity: 0; transform: translateY(0) translateX(0) scale(1); }
  20% { opacity: var(--ps, 0.6); }
  80% { opacity: var(--ps, 0.6); }
  100% { opacity: 0; transform: translateY(calc(var(--pfy, -60px))) translateX(calc(var(--pfx, 15px))) scale(0.3); }
}

/* ============================================================
 * 加载中状态
 * ============================================================ */
.loading-state {
  position: absolute; inset: 0; z-index: 10;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;
  background: rgba(10, 8, 6, 0.92);
}
.loading-spinner {
  width: 48px; height: 48px;
  border: 3px solid rgba(184, 150, 62, 0.15);
  border-top-color: rgba(184, 150, 62, 0.7);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.loading-title { font-size: 20px; color: #b8963e; letter-spacing: 6px; }
.loading-hint { font-size: 12px; color: rgba(180, 160, 130, 0.35); }

/* ============================================================
 * 空状态
 * ============================================================ */
.empty-state {
  position: absolute; inset: 0; z-index: 10;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;
  background: rgba(10, 8, 6, 0.9);
}
.empty-title { font-size: 22px; color: #b8963e; letter-spacing: 6px; }
.empty-hint { font-size: 13px; color: rgba(180, 160, 130, 0.5); max-width: 420px; text-align: center; line-height: 1.6; }
.empty-actions { display: flex; gap: 12px; }
.empty-btn {
  padding: 8px 24px; background: rgba(184, 150, 62, 0.12);
  border: 1px solid rgba(184, 150, 62, 0.3); color: #b8963e;
  cursor: pointer; letter-spacing: 3px; font-size: 13px; transition: all 0.2s;
}
.empty-btn:hover { background: rgba(184, 150, 62, 0.2); border-color: rgba(184, 150, 62, 0.5); }
.empty-btn.secondary {
  background: rgba(120, 120, 120, 0.08);
  border-color: rgba(120, 120, 120, 0.2);
  color: rgba(180, 160, 130, 0.5);
}
.empty-btn.secondary:hover { background: rgba(120, 120, 120, 0.15); border-color: rgba(120, 120, 120, 0.35); }

/* ============================================================
 * 主界面
 * ============================================================ */
.faction-main {
  position: relative; z-index: 1;
  width: 100%; height: 100%;
  display: flex; flex-direction: column;
  padding: 0 20px 20px; box-sizing: border-box;
}

/* 标题栏 */
.page-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 0; flex-shrink: 0;
}
.title-group { text-align: center; flex: 1; }
.page-title {
  font-size: 30px; font-weight: normal; color: #e0d5b8;
  letter-spacing: 14px; margin: 0;
  text-shadow: 0 0 30px rgba(184, 150, 62, 0.3), 0 2px 4px rgba(0,0,0,0.8);
  animation: titleGlow 3s ease-in-out infinite alternate;
}
@keyframes titleGlow {
  from { text-shadow: 0 0 20px rgba(184, 150, 62, 0.2), 0 2px 4px rgba(0,0,0,0.8); }
  to { text-shadow: 0 0 40px rgba(184, 150, 62, 0.4), 0 2px 8px rgba(0,0,0,0.9); }
}
.page-subtitle {
  font-size: 13px; color: rgba(184, 150, 62, 0.5);
  letter-spacing: 6px; margin: 6px 0 0;
}

.btn-back {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px; background: rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(184, 150, 62, 0.2);
  color: rgba(184, 150, 62, 0.7); font-size: 13px;
  cursor: pointer; letter-spacing: 2px; transition: all 0.2s; flex-shrink: 0;
}
.btn-back:hover { border-color: rgba(184, 150, 62, 0.5); color: #b8963e; background: rgba(0, 0, 0, 0.5); }
.back-icon { font-size: 14px; }
.header-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20, 16, 12, 0.55);
  border: 1px solid rgba(184, 150, 62, 0.25);
  border-radius: 2px;
  color: var(--gold-dim, #b8a070);
  cursor: pointer;
  transition: all 0.2s;
  backdrop-filter: blur(4px);
}

.icon-btn:hover {
  background: rgba(184, 150, 62, 0.12);
  border-color: rgba(184, 150, 62, 0.5);
  transform: translateY(-1px);
}

.icon-btn .icon { font-size: 14px; }

/* ============================================================
 * 主体布局：左侧列表 + 右侧展台
 * ============================================================ */
.faction-body {
  flex: 1;
  display: flex;
  align-items: stretch;
  min-height: 0;
  position: relative;
}

/* ============================================================
 * 左侧势力列表（可折叠）
 * ============================================================ */
.faction-sidebar {
  width: 280px;
  flex-shrink: 0;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.22, 0.61, 0.36, 1),
              opacity 0.35s ease,
              margin 0.4s cubic-bezier(0.22, 0.61, 0.36, 1);
  margin-right: 8px;
  opacity: 1;
}
.faction-sidebar.collapsed {
  width: 0;
  margin-right: 0;
  opacity: 0;
}

.sidebar-inner {
  width: 280px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, rgba(16, 12, 8, 0.92) 0%, rgba(10, 8, 6, 0.95) 100%);
  border: 1px solid rgba(184, 150, 62, 0.15);
  border-radius: 4px;
  overflow: hidden;
}

.sidebar-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(184, 150, 62, 0.1);
  flex-shrink: 0;
}
.sidebar-title {
  font-size: 16px; color: #e0d5b8;
  letter-spacing: 6px;
  text-shadow: 0 0 8px rgba(184, 150, 62, 0.15);
}
.sidebar-count {
  font-size: 11px; color: rgba(184, 150, 62, 0.35); letter-spacing: 2px;
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 0;
}
.sidebar-list::-webkit-scrollbar { width: 3px; }
.sidebar-list::-webkit-scrollbar-track { background: transparent; }
.sidebar-list::-webkit-scrollbar-thumb {
  background: rgba(184, 150, 62, 0.15); border-radius: 2px;
}

.sidebar-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: all 0.25s ease;
  border-left: 3px solid transparent;
  position: relative;
}
.sidebar-item:hover {
  background: rgba(184, 150, 62, 0.05);
}
.sidebar-item.active {
  background: rgba(184, 150, 62, 0.08);
  border-left-color: var(--accent, rgba(184, 150, 62, 0.6));
}
.sidebar-item.hover:not(.active) {
  background: rgba(184, 150, 62, 0.03);
}

.si-portrait {
  width: 44px; height: 56px;
  border-radius: 3px; overflow: hidden;
  border: 1px solid rgba(184, 150, 62, 0.15);
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.4);
}
.si-portrait img {
  width: 100%; height: 100%; object-fit: cover; object-position: top center;
}

.si-info {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; gap: 2px;
}
.si-name {
  font-size: 15px; color: #e0d5b8;
  letter-spacing: 3px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.si-title {
  font-size: 10px; color: rgba(184, 150, 62, 0.45); letter-spacing: 2px;
}

.si-difficulty {
  padding: 1px 6px; font-size: 9px; border-radius: 2px; letter-spacing: 1px;
  flex-shrink: 0;
}

/* 折叠/展开手柄 */
.sidebar-toggle {
  width: 24px;
  flex-shrink: 0;
  background: rgba(16, 12, 8, 0.5);
  border: 1px solid rgba(184, 150, 62, 0.15);
  border-radius: 0 4px 4px 0;
  color: rgba(184, 150, 62, 0.5);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.25s ease;
  margin-right: 6px;
  z-index: 20;
  height: 60px;
  align-self: center;
  position: absolute;
  left: 280px;
  top: 50%;
  transform: translateY(-50%);
}
.sidebar-toggle:hover {
  background: rgba(184, 150, 62, 0.1);
  border-color: rgba(184, 150, 62, 0.35);
  color: rgba(184, 150, 62, 0.8);
}
.faction-sidebar.collapsed ~ .sidebar-toggle {
  left: 0;
}
.toggle-arrow {
  display: inline-block; font-size: 10px; transition: transform 0.4s ease;
}
.toggle-arrow.flipped {
  transform: rotate(180deg);
}

/* ============================================================
 * 人物散布舞台
 * ============================================================ */
.characters-stage {
  flex: 1;
  position: relative;
  min-width: 0;
}

/* 人物卡片 — 放大版 */
.character-card {
  position: absolute;
  left: var(--card-left, 37%);
  top: var(--card-top, 32%);
  width: 250px;
  height: 360px;
  cursor: pointer;
  transform-style: preserve-3d;
  perspective: 800px;
  /* 持续微动 */
  animation: cardBreathe 4s ease-in-out infinite;
  animation-delay: var(--card-delay, 0s);
  transition: transform 0.5s cubic-bezier(0.22, 0.61, 0.36, 1),
              filter 0.4s ease,
              z-index 0s;
  z-index: 1;
  filter: brightness(0.85) saturate(0.8);
}

/* 呼吸动画 */
@keyframes cardBreathe {
  0%, 100% { transform: translateY(0) rotateX(var(--card-rx, 0deg)) rotateY(var(--card-ry, 0deg)); }
  50% { transform: translateY(-6px) rotateX(var(--card-rx, 0deg)) rotateY(var(--card-ry, 0deg)); }
}

/* 悬停立起 — 基础状态，鼠标位置通过 JS 精细微调 */
.character-card.hovered {
  transform: translateY(-20px) rotateX(-8deg) scale(1.12) !important;
  z-index: 100 !important;
  filter: brightness(1.15) saturate(1.2) !important;
  animation: none !important;
  /* 光效增强 */
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.65),
              0 0 50px rgba(184, 150, 62, 0.18);
}

/* 确认选中 */
.character-card.confirmed {
  transform: translateY(-24px) rotateX(-10deg) scale(1.15) !important;
  z-index: 200 !important;
  filter: brightness(1.22) saturate(1.35) !important;
  animation: none !important;
}

/* 退场 */
.character-card.leaving {
  transform: translateY(20px) scale(0.9) !important;
  opacity: 0.5;
  z-index: 0 !important;
  filter: brightness(0.5) saturate(0.5) !important;
  transition: all 0.4s ease-in !important;
}

/* 卡片背面 */
.card-backdrop {
  position: absolute; inset: -4px;
  background: linear-gradient(180deg, rgba(30, 20, 10, 0.9) 0%, rgba(10, 8, 6, 0.95) 100%);
  border: 1px solid rgba(184, 150, 62, 0.15);
  border-radius: 2px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  transition: border-color 0.4s, box-shadow 0.4s;
}
.character-card.hovered .card-backdrop,
.character-card.confirmed .card-backdrop {
  border-color: rgba(184, 150, 62, 0.5);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6), 0 0 24px rgba(184, 150, 62, 0.15);
}

/* 人物立绘 */
.card-figure {
  position: absolute; inset: 0;
  overflow: hidden;
}
.card-figure img {
  width: 100%; height: 100%;
  object-fit: cover; object-position: top center;
  transition: transform 0.5s ease;
}
.character-card.hovered .card-figure img,
.character-card.confirmed .card-figure img {
  transform: scale(1.08);
}

/* 底部铭牌 */
.card-plaque {
  position: absolute; left: 0; right: 0; bottom: 0;
  padding: 18px 14px 16px;
  background: linear-gradient(0deg, rgba(10, 8, 6, 0.97) 0%, rgba(10, 8, 6, 0.75) 55%, transparent 100%);
  display: flex; flex-direction: column; gap: 4px;
  pointer-events: none;
  transition: padding 0.4s;
}
.character-card.hovered .card-plaque,
.character-card.confirmed .card-plaque {
  padding-bottom: 22px;
}
.plaque-difficulty {
  align-self: flex-start;
  padding: 2px 8px; font-size: 10px; border-radius: 2px; letter-spacing: 1px;
}
.plaque-name {
  font-size: 26px; font-weight: normal; color: #f5ede0;
  letter-spacing: 8px; margin: 0;
  text-shadow: 0 0 12px rgba(220, 180, 80, 0.35), 0 2px 8px rgba(0, 0, 0, 0.95);
}
.plaque-title {
  font-size: 13px; color: rgba(200, 165, 80, 0.7); letter-spacing: 3px; margin: 0;
}

/* 选中光效环 */
.card-glow-ring {
  position: absolute; inset: -6px;
  border: 2px solid transparent;
  border-radius: 3px;
  transition: border-color 0.4s, box-shadow 0.4s;
  pointer-events: none;
  opacity: 0;
}
.character-card.hovered .card-glow-ring {
  opacity: 1;
  border-color: rgba(184, 150, 62, 0.3);
  box-shadow: 0 0 20px rgba(184, 150, 62, 0.1), inset 0 0 20px rgba(184, 150, 62, 0.05);
}
.character-card.confirmed .card-glow-ring {
  opacity: 1;
  border-color: rgba(184, 150, 62, 0.6);
  box-shadow: 0 0 30px rgba(184, 150, 62, 0.2), inset 0 0 30px rgba(184, 150, 62, 0.08);
  animation: glowPulse 1.5s ease-in-out infinite;
}
@keyframes glowPulse {
  0%, 100% { box-shadow: 0 0 20px rgba(184, 150, 62, 0.15); }
  50% { box-shadow: 0 0 40px rgba(184, 150, 62, 0.3); }
}

/* 悬浮提示 */
.hover-hint {
  position: absolute;
  left: 50%; top: -36px;
  transform: translateX(-50%);
  padding: 4px 14px;
  background: rgba(0, 0, 0, 0.8);
  border: 1px solid rgba(184, 150, 62, 0.4);
  color: #b8963e;
  font-size: 12px; letter-spacing: 2px;
  white-space: nowrap;
  pointer-events: none;
  animation: hintIn 0.2s ease-out;
}
@keyframes hintIn {
  from { opacity: 0; transform: translateX(-50%) translateY(6px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* ============================================================
 * 详情面板（全屏覆盖 + 居中面板）
 * ============================================================ */
.detail-overlay {
  position: fixed; inset: 0; z-index: 2000;
  display: flex; align-items: center; justify-content: center;
  padding: 32px;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(8px);
}

.detail-panel {
  position: relative;
  width: 100%; max-width: 960px; max-height: 90vh;
  background: linear-gradient(145deg, rgba(22, 18, 14, 0.98) 0%, rgba(14, 11, 9, 0.99) 100%);
  border: 1px solid rgba(184, 150, 62, 0.25);
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 24px 72px rgba(0, 0, 0, 0.7),
              0 0 0 1px rgba(0, 0, 0, 0.5),
              0 0 40px var(--accent, rgba(184, 150, 62, 0.1));
}
.detail-panel::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 4px; background: var(--accent); opacity: 0.5;
}

.panel-close {
  position: absolute; top: 14px; right: 14px; z-index: 10;
  width: 34px; height: 34px;
  border: 1px solid rgba(184, 150, 62, 0.2); border-radius: 50%;
  background: rgba(20, 16, 12, 0.7); color: #e0d5b8;
  font-size: 15px; cursor: pointer; transition: all 0.2s;
}
.panel-close:hover {
  border-color: rgba(196, 58, 58, 0.6); background: rgba(196, 58, 58, 0.3); color: #fff;
}

.panel-body {
  display: flex; min-height: 0;
}

.panel-portrait {
  width: 42%; flex-shrink: 0; position: relative;
  background: rgba(0, 0, 0, 0.4); min-height: 480px;
  overflow: hidden;
}
.panel-portrait img {
  width: 100%; height: 100%; object-fit: cover; object-position: top center;
}
.portrait-vignette {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, transparent 60%, rgba(14, 11, 9, 0.6) 100%),
              linear-gradient(90deg, transparent 80%, rgba(14, 11, 9, 0.3) 100%);
  pointer-events: none;
}

.panel-info {
  flex: 1; display: flex; flex-direction: column; gap: 16px;
  padding: 32px 28px; overflow-y: auto; max-height: 90vh;
}

.panel-header { text-align: center; padding-bottom: 14px; border-bottom: 1px solid rgba(184, 150, 62, 0.1); }
.panel-difficulty { display: inline-block; padding: 2px 10px; font-size: 11px; border-radius: 2px; letter-spacing: 1px; margin-bottom: 8px; }
.panel-name { font-size: 30px; font-weight: normal; color: #e0d5b8; letter-spacing: 8px; margin: 0; }
.panel-title { font-size: 13px; color: rgba(184, 150, 62, 0.55); letter-spacing: 4px; margin: 6px 0 0; }

.panel-voice {
  font-size: 14px; line-height: 1.9; color: rgba(224, 213, 184, 0.7);
  text-align: center; font-style: italic;
  padding: 14px 16px; margin: 0;
  background: rgba(184, 150, 62, 0.04);
  border-left: 3px solid var(--accent, rgba(184, 150, 62, 0.3));
}

/* AI 音色信息标签 */
.panel-voice-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  margin: 4px 0 0;
  font-size: 11px;
  letter-spacing: 1px;
  background: rgba(100, 160, 200, 0.06);
  border-radius: 3px;
}

.voice-info-label {
  color: #8cc8e8;
  font-weight: bold;
  white-space: nowrap;
}

.voice-info-desc {
  color: rgba(140, 200, 232, 0.65);
  flex: 1;
}

.panel-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.panel-stat {
  display: flex; flex-direction: column; align-items: center;
  padding: 12px 6px; background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(184, 150, 62, 0.07);
}
.stat-icon { font-size: 13px; color: rgba(184, 150, 62, 0.35); margin-bottom: 4px; }
.stat-val { font-size: 19px; font-weight: bold; color: #b8963e; }
.stat-label { font-size: 10px; color: rgba(184, 150, 62, 0.35); letter-spacing: 2px; }

.panel-tags { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.panel-tag {
  padding: 3px 11px; font-size: 11px; color: rgba(224, 213, 184, 0.55);
  background: rgba(184, 150, 62, 0.05); border: 1px solid rgba(184, 150, 62, 0.1); letter-spacing: 1px;
}

.panel-traits { display: flex; flex-direction: column; gap: 12px; }
.trait-block { font-size: 12px; line-height: 1.8; }
.trait-label { font-size: 10px; letter-spacing: 3px; color: rgba(184, 150, 62, 0.4); display: block; margin-bottom: 3px; }
.trait-line { padding-left: 10px; margin: 2px 0; }
.trait-line.buff { border-left: 2px solid rgba(90, 160, 120, 0.5); color: rgba(140, 200, 160, 0.7); }
.trait-line.debuff { border-left: 2px solid rgba(196, 58, 58, 0.5); color: rgba(220, 100, 100, 0.7); }

.panel-actions { display: flex; gap: 12px; margin-top: auto; padding-top: 6px; }

.btn-voice {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 12px 20px; background: rgba(184, 150, 62, 0.07);
  border: 1px solid rgba(184, 150, 62, 0.22);
  color: #b8963e; font-size: 13px; letter-spacing: 3px;
  cursor: pointer; transition: all 0.2s; flex-shrink: 0;
}
.btn-voice:hover { background: rgba(184, 150, 62, 0.14); border-color: rgba(184, 150, 62, 0.4); }
.btn-icon { font-size: 13px; }

.btn-enter {
  flex: 1; padding: 12px 20px; background: transparent;
  border: 1px solid var(--accent); cursor: pointer;
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  transition: all 0.3s; position: relative; overflow: hidden;
}
.btn-enter::before {
  content: ''; position: absolute; inset: 0;
  background: var(--accent); opacity: 0; transition: opacity 0.3s;
}
.btn-enter:hover::before { opacity: 0.08; }
.btn-enter:hover {
  box-shadow: 0 0 28px var(--accent, rgba(196, 58, 58, 0.15)),
              inset 0 0 28px var(--accent, rgba(196, 58, 58, 0.04));
}
.btn-enter:disabled { opacity: 0.4; cursor: not-allowed; }
.enter-text { font-size: 17px; color: #e0d5b8; letter-spacing: 8px; position: relative; z-index: 1; }
.enter-sub { font-size: 10px; color: rgba(224, 213, 184, 0.4); letter-spacing: 6px; position: relative; z-index: 1; }

/* 难度色 */
.diff-easy { background: #3a5a3a; color: rgba(255,255,255,0.8); }
.diff-normal { background: #4a5a2a; color: rgba(255,255,255,0.8); }
.diff-medium { background: #5a4a1a; color: rgba(255,255,255,0.8); }
.diff-hard { background: #5a2020; color: rgba(255,255,255,0.8); }
.diff-hell { background: #3a1010; color: rgba(255,255,255,0.8); }
.diff-special { background: #2a3a4a; color: rgba(255,255,255,0.8); }

/* 面板过渡 */
.panel-slide-enter-active { transition: all 0.4s cubic-bezier(0.22, 0.61, 0.36, 1); }
.panel-slide-leave-active { transition: all 0.3s ease-in; }
.panel-slide-enter-from { opacity: 0; }
.panel-slide-enter-from .detail-panel { transform: scale(0.9) translateY(30px); opacity: 0; }
.panel-slide-leave-to { opacity: 0; }
.panel-slide-leave-to .detail-panel { transform: scale(0.95) translateY(15px); opacity: 0; }

/* ============================================================
 * 响应式
 * ============================================================ */
@media (max-width: 1200px) {
  .faction-sidebar { width: 240px; }
  .sidebar-inner { width: 240px; }
  .sidebar-toggle { left: 240px; }
  .character-card { width: 200px; height: 290px; }
  .plaque-name { font-size: 22px; letter-spacing: 5px; }
}
@media (max-width: 900px) {
  .faction-sidebar { width: 200px; }
  .sidebar-inner { width: 200px; }
  .sidebar-toggle { left: 200px; }
  .faction-main { padding: 0 16px 16px; }
  .page-title { font-size: 24px; letter-spacing: 10px; }
  .character-card { width: 160px; height: 235px; }
  .plaque-name { font-size: 17px; letter-spacing: 3px; }
  .plaque-title { font-size: 11px; }
  .si-name { font-size: 13px; letter-spacing: 2px; }
  .detail-panel { max-height: 95vh; }
  .panel-body { flex-direction: column; }
  .panel-portrait { width: 100%; min-height: 260px; max-height: 320px; }
  .panel-info { max-height: none; padding: 20px; }
  .panel-actions { flex-direction: column; }
  .btn-voice { width: 100%; }
}
@media (max-width: 600px) {
  .faction-sidebar {
    position: fixed; left: 0; top: 0; bottom: 0; z-index: 1500;
    width: 260px; margin-right: 0;
  }
  .faction-sidebar.collapsed { width: 0; }
  .sidebar-toggle { left: 260px; z-index: 1510; }
  .faction-sidebar.collapsed ~ .sidebar-toggle { left: 0; }
  .sidebar-inner { width: 260px; }
  .characters-stage { 
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; 
    overflow-y: auto; padding: 10px;
  }
  .character-card { 
    position: relative !important; left: auto !important; top: auto !important;
    width: 100%; height: auto; aspect-ratio: 3/4; 
  }
  .plaque-name { font-size: 15px; letter-spacing: 2px; }
}
</style>
