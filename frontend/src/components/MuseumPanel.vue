<script setup lang="ts">
/**
 * 史馆 — 文化沉浸面板
 * 展示本回合大事、势力专史预览、历史知识卡片、AI画师。
 * 纯展示已有数据，AI画师可选调用混元文生图，API不可用时优雅降级。
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import { aiPaint } from '@/services/api'

const store = useGameStore()
const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

// ===== 历史知识卡片库（硬编码，零API调用） =====
const KNOWLEDGE_CARDS = [
  { title: '红巾军起义', text: '至正十一年（1351年），韩山童、刘福通以"石人一只眼，挑动黄河天下反"为号，发动红巾军起义，拉开了元末天下大乱的序幕。', era: '1351' },
  { title: '朱元璋崛起', text: '朱元璋出身濠州钟离（今安徽凤阳）贫农家庭，少年出家皇觉寺，后投郭子兴红巾军，因战功卓著逐渐自立门户，最终建立大明。', era: '1352–1368' },
  { title: '鄱阳湖之战', text: '至正二十三年（1363年），朱元璋与陈友谅在鄱阳湖决战。朱元璋以二十万兵力击败陈友谅六十万水军，成为元末最大规模水战。', era: '1363' },
  { title: '大都陷落', text: '至正二十八年（1368年），徐达、常遇春率明军北伐，攻陷元大都（今北京）。元顺帝北逃上都，元朝在中原的统治宣告终结。', era: '1368' },
  { title: '元代行省制', text: '元朝创立行中书省制度，将全国划分为十一行省，是中国历史上首次以"省"为一级行政区划，奠定了后世省制基础。', era: '1271–1368' },
  { title: '马可·波罗', text: '元世祖忽必烈时期，威尼斯商人马可·波罗来到中国，其《东方见闻录》向欧洲描绘了元朝的繁华，激发了大航海时代的探索欲望。', era: '1275–1292' },
  { title: '元曲四大家', text: '关汉卿、白朴、马致远、郑光祖并称"元曲四大家"。《窦娥冤》《西厢记》等名作奠定了中国戏曲文学的基础。', era: '13世纪' },
  { title: '黄河改道', text: '至正四年（1344年），黄河在曹州白茅堤决口，泛滥七年未治，数百万灾民流离失所。至正十一年征发民夫修河，间接催生了红巾军起义。', era: '1344–1351' },
  { title: '张士诚据吴', text: '张士诚以盐贩起家，据有江浙最富庶之地，建都平江（今苏州），自称吴王。其治下文教兴盛、经济繁荣，但因保守战略终为朱元璋所灭。', era: '1353–1367' },
  { title: '陈友谅篡徐', text: '陈友谅原为徐寿辉部将，后弑徐自立为大汉皇帝，据有湖广江西。其水师强盛，造大楼船数百艘，曾一度成为江南最大势力。', era: '1360–1363' },
  { title: '大明建立', text: '至正二十八年（1368年）正月初四，朱元璋在应天府（今南京）即皇帝位，国号大明，年号洪武。中国历史进入明朝时代。', era: '1368' },
  { title: '科举复兴', text: '元朝前期废弃科举长达数十年，至元仁宗延祐年间始恢复。朱元璋立国后大力推行科举，确立八股取士，影响中国此后五百余年。', era: '1315–' },
]

/** 随机抽取3张知识卡片 */
function randomCards() {
  const shuffled = [...KNOWLEDGE_CARDS].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, 3)
}

const knowledgeCards = ref<typeof KNOWLEDGE_CARDS>([])
const cardTab = ref<'events' | 'chronicle' | 'knowledge' | 'painter'>('events')

// ===== AI画师状态 =====
const painterPrompt = ref('')
const painterResult = ref<string>('')      // base64 或 image_url
const painterFormat = ref<string>('')      // 'url' | 'base64'
const painterLoading = ref(false)
const painterError = ref('')
const painterPlaceholder = computed(() => {
  const suggestions = [
    '赤壁之战 · 火光映江',
    '鄱阳湖水战 · 楼船蔽日',
    '朱元璋登基 · 应天新朝',
    '元顺帝北狩 · 大漠孤烟',
    '张士诚平江城 · 江南烟雨',
    '常遇春北伐 · 铁骑踏雪',
    '刘伯温观星 · 夜观天象',
    '大都城破 · 烽火连天',
    '红巾军起义 · 黄河怒吼',
    '江南三月 · 杏花春雨',
  ]
  const idx = Math.floor(Math.random() * suggestions.length)
  return suggestions[idx]
})
const currentPlaceholder = ref(painterPlaceholder.value)

/** 读取本地存储的画师 API Key */
function getPainterApiKey(): string {
  try {
    const keys = JSON.parse(localStorage.getItem('yuanmo_llm_api_keys') || '{}')
    return keys?.painter || ''
  } catch { return '' }
}

async function doAIPaint() {
  const prompt = painterPrompt.value.trim()
  if (!prompt || painterLoading.value) return
  painterLoading.value = true
  painterError.value = ''
  painterResult.value = ''
  try {
    const painterKey = getPainterApiKey()
    const res = await aiPaint({ prompt, api_key: painterKey || undefined })
    if (res.image_url) {
      painterResult.value = res.image_url
      painterFormat.value = 'url'
    } else if (res.base64) {
      painterResult.value = res.base64
      painterFormat.value = 'base64'
    } else {
      painterError.value = res.message || '生成失败，请重试'
    }
  } catch (e: any) {
    painterError.value = e?.message || '网络错误，请检查后端服务'
  } finally {
    painterLoading.value = false
  }
}

function refreshPlaceholder() {
  currentPlaceholder.value = painterPlaceholder.value
}

onMounted(() => {
  knowledgeCards.value = randomCards()
})
watch(() => props.visible, (v) => {
  if (v) knowledgeCards.value = randomCards()
})

/** 本回合事件（最近20条） */
const recentEvents = computed(() => {
  return (store.events || []).slice(0, 20)
})

/** 势力专史预览 — 从事件中提取 story 类型 */
const storyEvents = computed(() => {
  return (store.events || [])
    .filter((e: any) => e.event_type === 'story' || e.severity === 'story')
    .slice(0, 10)
})

/** 当前年代 */
const eraLabel = computed(() => {
  const y = store.currentYear || 1
  return `至正${y}年（公元${1351 + y - 1}年）`
})

function severityClass(s: string) {
  if (s === 'major' || s === 'critical') return 'severity-major'
  if (s === 'minor') return 'severity-minor'
  return 'severity-normal'
}

function eventTypeLabel(type: string) {
  const map: Record<string, string> = {
    battle: '兵事', economy: '财政', diplomacy: '邦交',
    disaster: '灾异', court: '朝政', story: '青史',
    narrative: '逸闻', ai_review: '廷议', world_narrative: '天下',
  }
  return map[type] || type || '杂录'
}
</script>

<template>
  <div v-if="visible" class="museum-overlay" @click.self="emit('close')">
    <div class="museum-panel animate-fade-in">
      <!-- 头部 -->
      <div class="museum-header">
        <div class="museum-title-row">
          <span class="museum-icon">&#x1F4DC;</span>
          <h3>史馆 · 元末札记</h3>
          <span class="museum-era">{{ eraLabel }}</span>
        </div>
        <button class="museum-close" @click="emit('close')" title="关闭史馆">&#x2715;</button>
      </div>

      <!-- 标签切换 -->
      <div class="museum-tabs">
        <button :class="{ active: cardTab === 'events' }" @click="cardTab = 'events'">&#x1F4CB; 天下大事</button>
        <button :class="{ active: cardTab === 'chronicle' }" @click="cardTab = 'chronicle'">&#x1F3F0; 势力列传</button>
        <button :class="{ active: cardTab === 'knowledge' }" @click="cardTab = 'knowledge'">&#x1F4D6; 元末掌故</button>
        <button :class="{ active: cardTab === 'painter' }" @click="cardTab = 'painter'">&#x1F3A8; AI画师</button>
      </div>

      <!-- 内容区 -->
      <div class="museum-body">
        <!-- 天下大事 -->
        <div v-if="cardTab === 'events'" class="museum-events">
          <div v-if="recentEvents.length === 0" class="museum-empty">
            <p>天下初定，尚无大事记录</p>
            <small>推进回合后，AI 将自动记录时事</small>
          </div>
          <div
            v-for="(evt, i) in recentEvents" :key="i"
            class="event-card"
            :class="severityClass((evt as any).severity || (evt as any).event_type)"
          >
            <div class="event-card-meta">
              <span class="event-type-badge">{{ eventTypeLabel((evt as any).event_type) }}</span>
              <span class="event-round" v-if="(evt as any).round">第{{ (evt as any).round }}回</span>
            </div>
            <div class="event-card-title">{{ (evt as any).title || (evt as any).description || '时局记述' }}</div>
            <div class="event-card-narrative" v-if="(evt as any).narrative">{{ (evt as any).narrative }}</div>
          </div>
        </div>

        <!-- 势力列传 -->
        <div v-if="cardTab === 'chronicle'" class="museum-chronicle">
          <div v-if="storyEvents.length === 0" class="museum-empty">
            <p>青史未成，诸侯列传待书</p>
            <small>AI 将在回合推进中自动编修势力专史</small>
          </div>
          <div
            v-for="(evt, i) in storyEvents" :key="i"
            class="chronicle-card"
          >
            <div class="chronicle-meta">
              <span class="chronicle-faction" v-if="(evt as any).faction_name || (evt as any).title">
                {{ (evt as any).faction_name || (evt as any).title }}
              </span>
            </div>
            <div class="chronicle-text">{{ (evt as any).narrative || (evt as any).description }}</div>
          </div>
        </div>

        <!-- 元末掌故 -->
        <div v-if="cardTab === 'knowledge'" class="museum-knowledge">
          <div
            v-for="card in knowledgeCards" :key="card.title"
            class="knowledge-card"
          >
            <div class="knowledge-card-title">
              <span class="knowledge-icon">&#x1F3AE;</span>
              {{ card.title }}
              <span class="knowledge-era">{{ card.era }}</span>
            </div>
            <div class="knowledge-card-text">{{ card.text }}</div>
          </div>
          <div class="knowledge-footer">
            <small>AI 驱动的历史知识卡片 · 每局随机展示</small>
          </div>
        </div>

        <!-- AI画师 -->
        <div v-if="cardTab === 'painter'" class="museum-painter">
          <div class="painter-intro">
            <p>输入一个历史场景描述，AI将为你生成一幅水墨风格的元代画作。</p>
          </div>
          <div class="painter-input-row">
            <input
              v-model="painterPrompt"
              :placeholder="currentPlaceholder"
              class="painter-input"
              @keyup.enter="doAIPaint"
              :disabled="painterLoading"
            />
            <button class="painter-roll-btn" @click="refreshPlaceholder" title="换一个提示">🎲</button>
          </div>
          <button
            class="painter-generate-btn"
            @click="doAIPaint"
            :disabled="painterLoading || !painterPrompt.trim()"
          >
            <span v-if="painterLoading" class="painter-spinner"></span>
            {{ painterLoading ? 'AI作画中…' : '🖌 生成画作' }}
          </button>

          <div v-if="painterError" class="painter-error">{{ painterError }}</div>

          <div v-if="painterResult" class="painter-result">
            <img
              v-if="painterFormat === 'url'"
              :src="painterResult"
              alt="AI生成画作"
              class="painter-image"
            />
            <img
              v-else-if="painterFormat === 'base64'"
              :src="'data:image/png;base64,' + painterResult"
              alt="AI生成画作"
              class="painter-image"
            />
          </div>

          <div class="painter-footer">
            <small>由混元文生图驱动 · 中国水墨风格 · 每次生成消耗API额度</small>
          </div>
        </div>
      </div>

      <!-- 底部 -->
      <div class="museum-footer">
        <span>本功能由 AI 驱动生成</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.museum-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(2px);
}

.museum-panel {
  width: min(640px, 92vw);
  max-height: 82vh;
  background: linear-gradient(180deg, #2a1f14 0%, #1a1208 100%);
  border: 2px solid #b89b68;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 60px rgba(180, 140, 80, 0.25), 0 8px 32px rgba(0,0,0,0.5);
  overflow: hidden;
}

.museum-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(184, 155, 104, 0.3);
  background: linear-gradient(180deg, rgba(184, 155, 104, 0.12), transparent);
}

.museum-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.museum-icon { font-size: 24px; }

.museum-title-row h3 {
  margin: 0;
  font-size: 18px;
  font-family: 'STKaiti', 'KaiTi', serif;
  color: #d4c098;
  letter-spacing: 2px;
}

.museum-era {
  font-size: 12px;
  color: #998866;
  font-family: 'STKaiti', 'KaiTi', serif;
}

.museum-close {
  background: none;
  border: 1px solid rgba(184, 155, 104, 0.3);
  color: #998866;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.museum-close:hover { background: rgba(184, 155, 104, 0.15); color: #d4c098; }

.museum-tabs {
  display: flex;
  border-bottom: 1px solid rgba(184, 155, 104, 0.2);
  padding: 0 16px;
}

.museum-tabs button {
  flex: 1;
  background: none;
  border: none;
  color: #887755;
  padding: 12px 8px;
  cursor: pointer;
  font-size: 13px;
  font-family: 'STKaiti', 'KaiTi', serif;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.museum-tabs button:hover { color: #c8b080; }
.museum-tabs button.active {
  color: #d4c098;
  border-bottom-color: #b89b68;
}

.museum-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  min-height: 0;
}

.museum-body::-webkit-scrollbar { width: 4px; }
.museum-body::-webkit-scrollbar-track { background: transparent; }
.museum-body::-webkit-scrollbar-thumb { background: rgba(184, 155, 104, 0.25); border-radius: 2px; }

.museum-empty {
  text-align: center;
  color: #887755;
  padding: 40px 20px;
}
.museum-empty p { margin: 0 0 8px; font-size: 15px; }
.museum-empty small { font-size: 12px; color: #665544; }

/* 事件卡片 */
.event-card {
  background: rgba(184, 155, 104, 0.06);
  border-left: 3px solid #665544;
  border-radius: 4px;
  padding: 12px 14px;
  margin-bottom: 10px;
  transition: border-color 0.3s;
}
.event-card.severity-major { border-left-color: #c0392b; background: rgba(192, 57, 43, 0.08); }
.event-card.severity-minor { border-left-color: #7f8c8d; }

.event-card-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 6px;
}

.event-type-badge {
  font-size: 11px;
  background: rgba(184, 155, 104, 0.2);
  color: #b89b68;
  padding: 1px 8px;
  border-radius: 3px;
  font-family: 'STKaiti', 'KaiTi', serif;
}

.event-round {
  font-size: 11px;
  color: #665544;
}

.event-card-title {
  font-size: 14px;
  color: #d4c098;
  font-family: 'STKaiti', 'KaiTi', serif;
  margin-bottom: 4px;
}

.event-card-narrative {
  font-size: 13px;
  color: #998866;
  line-height: 1.7;
}

/* 列传卡片 */
.chronicle-card {
  background: rgba(184, 155, 104, 0.05);
  border: 1px solid rgba(184, 155, 104, 0.15);
  border-radius: 6px;
  padding: 14px 16px;
  margin-bottom: 10px;
}

.chronicle-meta { margin-bottom: 6px; }

.chronicle-faction {
  font-size: 13px;
  color: #b89b68;
  font-family: 'STKaiti', 'KaiTi', serif;
  font-weight: bold;
}

.chronicle-text {
  font-size: 14px;
  color: #c8b080;
  line-height: 1.8;
  font-family: 'STKaiti', 'KaiTi', serif;
}

/* 知识卡片 */
.knowledge-card {
  background: rgba(184, 155, 104, 0.05);
  border: 1px solid rgba(184, 155, 104, 0.12);
  border-radius: 6px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

.knowledge-card-title {
  font-size: 15px;
  color: #d4c098;
  font-family: 'STKaiti', 'KaiTi', serif;
  font-weight: bold;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.knowledge-icon { font-size: 16px; }

.knowledge-era {
  font-size: 11px;
  color: #665544;
  background: rgba(184, 155, 104, 0.15);
  padding: 1px 8px;
  border-radius: 3px;
  margin-left: auto;
}

.knowledge-card-text {
  font-size: 13px;
  color: #a09078;
  line-height: 1.8;
}

.knowledge-footer {
  text-align: center;
  padding: 8px;
}
.knowledge-footer small { color: #554433; font-size: 11px; }

/* 底部 */
.museum-footer {
  padding: 10px 20px;
  border-top: 1px solid rgba(184, 155, 104, 0.2);
  text-align: center;
}
.museum-footer span { font-size: 11px; color: #554433; }

/* AI画师 */
.museum-painter {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.painter-intro p {
  margin: 0;
  font-size: 13px;
  color: #998866;
  line-height: 1.6;
}

.painter-input-row {
  display: flex;
  gap: 8px;
}

.painter-input {
  flex: 1;
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(184, 155, 104, 0.3);
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 14px;
  color: #d4c098;
  font-family: 'STKaiti', 'KaiTi', serif;
  outline: none;
  transition: border-color 0.2s;
}
.painter-input:focus { border-color: #b89b68; }
.painter-input::placeholder { color: #665544; }
.painter-input:disabled { opacity: 0.5; }

.painter-roll-btn {
  background: rgba(184, 155, 104, 0.1);
  border: 1px solid rgba(184, 155, 104, 0.3);
  border-radius: 6px;
  color: #b89b68;
  width: 38px;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.painter-roll-btn:hover { background: rgba(184, 155, 104, 0.2); }

.painter-generate-btn {
  background: linear-gradient(135deg, rgba(184, 155, 104, 0.2), rgba(160, 120, 60, 0.15));
  border: 1px solid rgba(184, 155, 104, 0.4);
  border-radius: 8px;
  color: #d4c098;
  padding: 12px;
  font-size: 15px;
  font-family: 'STKaiti', 'KaiTi', serif;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.painter-generate-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(184, 155, 104, 0.35), rgba(160, 120, 60, 0.25));
  border-color: #b89b68;
}
.painter-generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.painter-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(184, 155, 104, 0.3);
  border-top-color: #b89b68;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.painter-error {
  background: rgba(192, 57, 43, 0.12);
  border: 1px solid rgba(192, 57, 43, 0.3);
  border-radius: 6px;
  padding: 10px 14px;
  color: #c0392b;
  font-size: 13px;
  text-align: center;
}

.painter-result {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(184, 155, 104, 0.3);
  background: rgba(0,0,0,0.3);
}

.painter-image {
  width: 100%;
  display: block;
}

.painter-footer {
  text-align: center;
}
.painter-footer small { color: #554433; font-size: 11px; }

/* 动画 */
.animate-fade-in {
  animation: fadeIn 0.25s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: scale(1); }
}
</style>
