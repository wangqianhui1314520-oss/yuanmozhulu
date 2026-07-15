<template>
  <div class="story-page" ref="pageRef" @click.self="advanceOrSkip">
    <!-- 背景层：古地图纹理感 -->
    <div class="bg-layer"></div>
    
    <!-- 卷轴容器 -->
    <div class="scroll-container" ref="scrollRef">
      <!-- 卷轴装饰顶边 -->
      <div class="scroll-ornament scroll-ornament-top">
        <span class="orn-line"></span>
        <span class="orn-diamond">◆</span>
        <span class="orn-line"></span>
      </div>

      <!-- 标题 -->
      <div class="story-header" :class="{ 'visible': step >= 0 }">
        <h1 class="story-title">元 末 逐 鹿</h1>
        <p class="story-subtitle">天 下 大 势</p>
        <div class="title-divider">━ ◆ ━</div>
      </div>

      <!-- 序幕：黄河起义 -->
      <div class="story-section" :class="{ 'visible': step >= 1 }">
        <p class="story-year">至正十一年 · 1351年</p>
        <p class="story-text">
          元顺帝在位，黄河屡决，饿殍遍野。朝廷强征十五万民夫修治黄河，
          白莲教韩山童、刘福通凿独眼石人埋于河堤，上刻——<br/>
          <span class="stone-quote">"石人一只眼，挑动黄河天下反"</span>
        </p>
        <p class="story-text">
          红巾烽火，由此燎原。大元社稷，风雨飘摇。
        </p>
      </div>

      <!-- 朱元璋 -->
      <div class="story-section" :class="{ 'visible': step >= 2 }">
        <div class="faction-tag" style="border-color: #DC143C; color: #DC143C;">朱元璋 · 吴国公</div>
        <p class="story-text">
          濠州钟离人，幼年家贫，曾入皇觉寺为僧。至正十二年投郭子兴红巾军，
          屡立战功，自领一军，取集庆为根基。奉行<span class="key-phrase">「高筑墙、广积粮、缓称王」</span>
          之策，于群雄中最为深谋远虑，步步为营。
        </p>
      </div>

      <!-- 陈友谅 -->
      <div class="story-section" :class="{ 'visible': step >= 3 }">
        <div class="faction-tag" style="border-color: #1E90FF; color: #1E90FF;">陈友谅 · 汉帝</div>
        <p class="story-text">
          沔阳渔家子，初为县吏，后投徐寿辉麾下。野心勃勃，弑主自立，
          国号大汉，据荆楚而拥长江水师之利。兵锋最盛时号<span class="key-phrase">六十万众</span>，
          巨舰如城，为朱元璋之头号劲敌。
        </p>
      </div>

      <!-- 张士诚 -->
      <div class="story-section" :class="{ 'visible': step >= 4 }">
        <div class="faction-tag" style="border-color: #FF8C00; color: #FF8C00;">张士诚 · 周王</div>
        <p class="story-text">
          泰州盐贩出身，率盐丁起兵，克平江而据江南膏腴之地。富甲一方，
          却<span class="key-phrase">优柔寡断、偏安一隅</span>，坐拥吴越繁华而无意北伐，
          在元廷与各方势力间首鼠两端。
        </p>
      </div>

      <!-- 其他势力群像 -->
      <div class="story-section" :class="{ 'visible': step >= 5 }">
        <div class="faction-tag" style="border-color: #20B2AA; color: #20B2AA;">方国珍 · 浙东节度</div>
        <p class="story-text">
          台州人，贩盐浮海为业。率先起兵反元，割据浙东三路，
          拥舟师之利，<span class="key-phrase">时叛时降、投机取利</span>，为海上枭雄。
        </p>
        
        <div class="faction-tag" style="border-color: #666699; color: #666699; margin-top: 16px;">王保保 · 河南王</div>
        <p class="story-text">
          扩廓帖木儿，元末第一名将。继其养父察罕帖木儿之军，
          受封河南王，总制天下兵马。善用骑兵，骁勇善战，
          为<span class="key-phrase">大元最后的柱石</span>。
        </p>
        
        <div class="faction-tag" style="border-color: #996633; color: #996633; margin-top: 16px;">徐寿辉 · 天完帝</div>
        <p class="story-text">
          罗田布贩，白莲教南方首领。蕲州起义建国，席卷湖广，
          却大权旁落，<span class="key-phrase">终为部将陈友谅所弑</span>。
        </p>
        
        <div class="faction-tag" style="border-color: #B8860B; color: #B8860B; margin-top: 16px;">明玉珍 · 大夏帝</div>
        <p class="story-text">
          徐寿辉旧部，奉命入川。闻陈友谅弑主，遂据蜀自立，
          保境安民，<span class="key-phrase">蜀中赖以安宁</span>。
        </p>
        
        <div class="faction-tag" style="border-color: #8B0000; color: #8B0000; margin-top: 16px;">元顺帝 · 大元天子</div>
        <p class="story-text">
          虽据大都而号令天下，实已<span class="key-phrase">政令不出京畿</span>。
          勋贵内斗、国库空虚，大厦将倾，回天乏术。
        </p>
        
        <div class="faction-tag" style="border-color: #887766; color: #887766; margin-top: 16px;">漠北诸部 · 草原大汗</div>
        <p class="story-text">
          和林故都，游牧铁骑。元室衰微，草原枭雄蠢蠢欲动，
          欲复<span class="key-phrase">成吉思汗之荣光</span>，再饮马黄河。
        </p>
      </div>

      <!-- 结语 -->
      <div class="story-section story-finale" :class="{ 'visible': step >= 6 }">
        <div class="title-divider">━ ◆ ━</div>
        <p class="story-finale-text">
          九州烽烟四起，群雄逐鹿中原。<br/>
          汝为一方幕府主官，辅佐主公<span class="key-phrase">运筹帷幄、决胜千里</span>。
        </p>
        <p class="story-finale-call">
          或北伐中原，一统天下；或偏安江南，固守一方。<br/>
          历史的笔锋，已握于君手。
        </p>
        <div class="title-divider">━ ◆ ━</div>
      </div>

      <!-- 卷轴装饰底边 -->
      <div class="scroll-ornament scroll-ornament-bottom">
        <span class="orn-line"></span>
        <span class="orn-diamond">◆</span>
        <span class="orn-line"></span>
      </div>

      <!-- 进入游戏按钮 -->
      <div class="enter-section" :class="{ 'visible': step >= 6 }">
        <button class="enter-btn" @click.stop="enterGame">
          <span class="enter-main">整军经武，入主天下</span>
          <span class="enter-sub">前 方 即 是 山 河 万 里</span>
        </button>
      </div>
    </div>

    <!-- 底部提示 -->
    <div class="hint-bar" :class="{ 'hidden': step >= 6 }">
      <span class="hint-text">点击任意位置继续</span>
      <span class="hint-dots">
        <span v-for="i in 7" :key="i" class="dot" :class="{ 'active': step >= i }"></span>
      </span>
    </div>

    <!-- 跳过按钮 -->
    <button class="skip-btn" v-if="step < 6" @click.stop="skipToEnd">
      跳过背景
    </button>

    <!-- 音频控件 -->
    <div class="audio-controls">
      <button class="audio-btn" @click="toggleMute" :title="isMuted ? '取消静音' : '静音'">
        {{ isMuted ? '🔇' : '🔊' }}
      </button>
      <button class="audio-btn" :title="isFullscreen ? '退出全屏' : '切换全屏'" @click="toggleFullscreen">
        {{ isFullscreen ? '⤡' : '⤢' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { audioManager } from '@/utils/audioManager'
import { useFullscreen } from '@/composables/useFullscreen'

const router = useRouter()
const route = useRoute()

const pageRef = ref<HTMLDivElement>()
const scrollRef = ref<HTMLDivElement>()
const step = ref(0)
const isMuted = ref(false)
const { isFullscreen, toggleFullscreen } = useFullscreen()
const isEntering = ref(false)
const factionId = ref('')

const totalSteps = 7 // 0-6 are the 7 content sections

let scrollTimer: ReturnType<typeof setTimeout> | null = null

onMounted(() => {
  factionId.value = (route.query.faction as string) || localStorage.getItem('yuanmo_player_faction') || ''
  
  // 渐进式展示：每1.2秒展示一段
  showNextStep()
})

onUnmounted(() => {
  if (scrollTimer) clearTimeout(scrollTimer)
})

function showNextStep() {
  if (step.value < totalSteps) {
    step.value++
    // 滚动到当前新增内容区域
    scrollToLatest()
    
    scrollTimer = setTimeout(() => {
      showNextStep()
    }, step.value === 6 ? 1800 : 1200) // 结语停留更久
  }
}

function scrollToLatest() {
  if (!scrollRef.value) return
  // 平滑滚动到最新可见区域
  const sections = scrollRef.value.querySelectorAll('.story-section.visible')
  if (sections.length > 0) {
    const last = sections[sections.length - 1]
    last.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function advanceOrSkip() {
  if (step.value >= totalSteps) return
  
  // 点击快进：跳到下一段
  if (scrollTimer) clearTimeout(scrollTimer)
  showNextStep()
}

function skipToEnd() {
  if (scrollTimer) clearTimeout(scrollTimer)
  step.value = totalSteps
  // 延迟一点让所有内容渲染完
  setTimeout(() => {
    scrollRef.value?.scrollTo({ top: scrollRef.value.scrollHeight, behavior: 'smooth' })
  }, 100)
}

function toggleMute() {
  isMuted.value = audioManager.toggleMute()
}

async function enterGame() {
  if (isEntering.value) return
  isEntering.value = true
  
  // 确保 localStorage 中有势力ID（容错：若 URL 参数丢失，从 localStorage 恢复）
  if (factionId.value) {
    localStorage.setItem('yuanmo_player_faction', factionId.value)
  } else {
    factionId.value = localStorage.getItem('yuanmo_player_faction') || ''
  }

  audioManager.stopAll()
  router.push(`/game?faction=${factionId.value}`)
}
</script>

<style scoped>
.story-page {
  width: 100vw; height: 100vh;
  overflow: hidden;
  position: relative;
  background: radial-gradient(ellipse at center, #1a1410 0%, #0a0806 70%);
  color: #d4c5a0;
  font-family: 'STKaiti', 'KaiTi', 'Noto Serif SC', 'SimSun', serif;
  user-select: none;
}

/* ===== 背景纹理层 ===== */
.bg-layer {
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse at 50% 0%, rgba(180, 140, 60, 0.04) 0%, transparent 60%),
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(180, 140, 60, 0.015) 2px,
      rgba(180, 140, 60, 0.015) 4px
    );
  pointer-events: none;
  z-index: 0;
}

/* ===== 卷轴容器 ===== */
.scroll-container {
  position: absolute;
  inset: 60px 0 100px;
  overflow-y: auto;
  overflow-x: hidden;
  z-index: 1;
  padding: 0 10vw;
  scroll-behavior: smooth;
  
  /* 自定义滚动条 */
  scrollbar-width: thin;
  scrollbar-color: rgba(180, 140, 60, 0.15) transparent;
}

.scroll-container::-webkit-scrollbar {
  width: 4px;
}

.scroll-container::-webkit-scrollbar-track {
  background: transparent;
}

.scroll-container::-webkit-scrollbar-thumb {
  background: rgba(180, 140, 60, 0.15);
  border-radius: 2px;
}

/* ===== 卷轴装饰 ===== */
.scroll-ornament {
  display: flex; align-items: center; justify-content: center;
  gap: 16px;
  padding: 20px 0;
  opacity: 0.35;
}

.orn-line {
  flex: 1; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(200, 160, 60, 0.5), transparent);
}

.orn-diamond {
  font-size: 10px; color: rgba(200, 160, 60, 0.5);
  text-shadow: 0 0 6px rgba(200, 160, 60, 0.2);
}

/* ===== 标题区 ===== */
.story-header {
  text-align: center;
  padding: 40px 0 30px;
  opacity: 0;
  transition: opacity 1s ease-out;
}

.story-header.visible { opacity: 1; }

.story-title {
  font-size: 48px;
  color: #c8a84a;
  letter-spacing: 24px;
  margin: 0;
  font-weight: normal;
  text-shadow: 0 0 40px rgba(200, 168, 74, 0.3), 0 0 80px rgba(200, 168, 74, 0.1);
}

.story-subtitle {
  font-size: 20px;
  color: rgba(200, 168, 74, 0.55);
  letter-spacing: 16px;
  margin: 14px 0 0;
}

.title-divider {
  text-align: center;
  font-size: 14px;
  color: rgba(200, 160, 60, 0.25);
  letter-spacing: 8px;
  padding: 10px 0;
}

/* ===== 内容段落 ===== */
.story-section {
  max-width: 680px;
  margin: 0 auto;
  padding: 20px 0 8px;
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.8s ease-out, transform 0.8s ease-out;
}

.story-section.visible {
  opacity: 1;
  transform: translateY(0);
}

.story-year {
  font-size: 16px;
  color: rgba(200, 168, 74, 0.5);
  letter-spacing: 6px;
  margin: 0 0 14px;
  text-align: left;
}

.story-text {
  font-size: 17px;
  line-height: 2.1;
  color: rgba(212, 197, 160, 0.85);
  text-align: justify;
  margin: 0 0 12px;
  letter-spacing: 1.5px;
  text-indent: 2em;
}

/* 石刻引文样式 */
.stone-quote {
  display: inline-block;
  color: #c8a84a;
  font-size: 19px;
  letter-spacing: 4px;
  margin: 6px 0;
  text-shadow: 0 0 10px rgba(200, 168, 74, 0.3);
  text-indent: 0;
}

/* 关键短语高亮 */
.key-phrase {
  color: #d4b860;
  border-bottom: 1px dotted rgba(200, 168, 74, 0.25);
}

/* ===== 势力标签 ===== */
.faction-tag {
  display: inline-block;
  padding: 3px 14px;
  border: 1px solid;
  font-size: 13px;
  letter-spacing: 3px;
  margin-bottom: 8px;
  opacity: 0.75;
}

/* ===== 结语区 ===== */
.story-finale {
  padding: 30px 0 10px;
}

.story-finale-text {
  font-size: 18px;
  line-height: 2.3;
  color: rgba(212, 197, 160, 0.9);
  text-align: center;
  margin: 0 0 16px;
  letter-spacing: 2px;
  text-indent: 0;
}

.story-finale-call {
  font-size: 17px;
  line-height: 2.2;
  color: rgba(200, 168, 74, 0.7);
  text-align: center;
  margin: 0;
  letter-spacing: 2.5px;
  text-indent: 0;
}

/* ===== 进入游戏按钮 ===== */
.enter-section {
  text-align: center;
  padding: 40px 0 60px;
  opacity: 0;
  transition: opacity 1s ease-out;
}

.enter-section.visible { opacity: 1; }

.enter-btn {
  padding: 20px 50px;
  background: transparent;
  border: 2px solid rgba(200, 168, 74, 0.4);
  cursor: pointer;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  transition: all 0.4s ease;
  position: relative;
  overflow: hidden;
  animation: btnGlow 3s ease-in-out infinite;
}

.enter-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, rgba(200, 168, 74, 0.06), transparent 70%);
  opacity: 0;
  transition: opacity 0.4s;
}

.enter-btn:hover {
  border-color: rgba(200, 168, 74, 0.7);
  box-shadow: 0 0 50px rgba(200, 168, 74, 0.15),
              inset 0 0 50px rgba(200, 168, 74, 0.04);
  transform: scale(1.03);
}

.enter-btn:hover::before {
  opacity: 1;
}

@keyframes btnGlow {
  0%, 100% { border-color: rgba(200, 168, 74, 0.4); }
  50% { border-color: rgba(200, 168, 74, 0.6); }
}

.enter-main {
  font-size: 22px;
  color: #e0d5b8;
  letter-spacing: 10px;
  font-family: 'STKaiti', 'KaiTi', 'Noto Serif SC', serif;
}

.enter-sub {
  font-size: 12px;
  color: rgba(200, 168, 74, 0.4);
  letter-spacing: 8px;
}

/* ===== 底部提示 ===== */
.hint-bar {
  position: absolute;
  bottom: 30px; left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  transition: opacity 0.5s;
}

.hint-bar.hidden { opacity: 0; pointer-events: none; }

.hint-text {
  font-size: 12px;
  color: rgba(200, 168, 74, 0.35);
  letter-spacing: 4px;
  animation: hintPulse 2s ease-in-out infinite;
}

@keyframes hintPulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 0.65; }
}

.hint-dots {
  display: flex; gap: 6px;
}

.dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: rgba(200, 168, 74, 0.15);
  transition: all 0.4s;
}

.dot.active {
  background: rgba(200, 168, 74, 0.5);
  box-shadow: 0 0 6px rgba(200, 168, 74, 0.3);
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

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .scroll-container { padding: 0 6vw; }
  .story-title { font-size: 36px; letter-spacing: 16px; }
  .story-text { font-size: 15px; line-height: 1.9; }
  .enter-main { font-size: 18px; letter-spacing: 6px; }
}
</style>
