<script setup lang="ts">
/**
 * EndingPanel - 四大结局演出面板
 * 
 * 功能：
 * - 多场景分镜演出
 * - NPC专属对话序列
 * - 史官评语展示
 * - 玩家内心独白
 * - 渐进提示与解锁展示
 * - 传承数据导出
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'

const store = useGameStore()

// 演出阶段
type Stage = 'loading' | 'fade_in' | 'scene' | 'dialogues' | 'epilogue' | 'stats' | 'unlocks' | 'complete'

const currentStage = ref<Stage>('loading')
const currentScene = ref(0)
const currentDialogue = ref(0)
const fullNarrative = ref('')
const narrativeProgress = ref(0)  // 打字机效果进度
let typewriterTimer: ReturnType<typeof setInterval> | null = null
let stageTimer: ReturnType<typeof setTimeout> | null = null

// 结局数据
const endingData = computed(() => store.endingData)
const tierClass = computed(() => {
  const tier = endingData.value?.tier || 'normal'
  return `ending-tier-${tier}`
})

// 演出场景
const scenes = computed(() => endingData.value?.performance?.scenes || [])
const maxScenes = computed(() => scenes.value.length)

// NPC对话
const dialogues = computed(() => endingData.value?.narrative?.npc_dialogues || [])
const maxDialogues = computed(() => dialogues.value.length)

// 游戏统计
const stats = computed(() => endingData.value?.statistics || {})

// 渐进信息
const progression = computed(() => endingData.value?.progression || {})
const hasNextTier = computed(() => {
  return progression.value?.next_tier_hint && progression.value.current_tier !== 'true'
})

// 解锁内容
const unlocks = computed(() => endingData.value?.unlocks?.rewards || [])

// 情感图标映射
const emotionIcon = (emotion: string): string => {
  const map: Record<string, string> = {
    despair: '😢', regret: '😔', panic: '😱', grief: '💔',
    contemplative: '🤔', content: '😌', grateful: '🙏',
    joyful: '😄', proud: '😤', wise: '🧠', cheering: '🎉',
    awed: '🤩', humble_proud: '🫡', tearful_joy: '🥲', tender: '💕', reverent: '🙇',
  }
  return map[emotion] || '💬'
}

// 统计标签映射
const statLabels: Record<string, string> = {
  rounds_played: '总回合数',
  final_year: '终局年份',
  territory_count: '领地数',
  territory_ratio: '领土占比',
  reputation: '声望',
  court_stability: '朝堂稳定度',
  realm_stability: '全域稳定度',
  development_level: '发展度',
  treasury: '国库银两',
  grain: '粮草',
  total_troops: '总兵力',
  total_population: '总人口',
  policies_unlocked: '已解锁国策',
}

// ==================== 演出流程控制 ====================

function startPerformance() {
  if (!endingData.value) return
  
  currentStage.value = 'fade_in'
  currentScene.value = 0
  currentDialogue.value = 0
  narrativeProgress.value = 0
  fullNarrative.value = ''

  // 阶段1: 淡入 → 2000ms后开始场景
  stageTimer = setTimeout(() => {
    advanceScene()
  }, 2000)
}

function advanceScene() {
  if (currentScene.value < maxScenes.value) {
    currentStage.value = 'scene'
    const scene = scenes.value[currentScene.value]
    fullNarrative.value = scene.narrative || ''
    narrativeProgress.value = 0
    startTypewriter(scene.duration ? Math.min(scene.duration * 1000 * 0.6, 3000) : 2000)
    
    stageTimer = setTimeout(() => {
      currentScene.value++
      if (currentScene.value >= maxScenes.value) {
        // 所有场景完成，进入对话阶段
        advanceToDialogues()
      } else {
        advanceScene()
      }
    }, (scene.duration || 3) * 1000 + 500)
  }
}

function advanceToDialogues() {
  currentStage.value = 'dialogues'
  currentDialogue.value = 0
  advanceDialogue()
}

function advanceDialogue() {
  if (currentDialogue.value < maxDialogues.value) {
    const dlg = dialogues.value[currentDialogue.value]
    fullNarrative.value = `"${dlg.text}"`
    narrativeProgress.value = 0
    startTypewriter(2500)

    stageTimer = setTimeout(() => {
      currentDialogue.value++
      if (currentDialogue.value >= maxDialogues.value) {
        advanceToEpilogue()
      } else {
        advanceDialogue()
      }
    }, 3500)
  } else {
    advanceToEpilogue()
  }
}

function advanceToEpilogue() {
  currentStage.value = 'epilogue'
  fullNarrative.value = endingData.value?.narrative?.player_monologue || ''
  narrativeProgress.value = 0
  startTypewriter(3500)

  stageTimer = setTimeout(() => {
    advanceToStats()
  }, 5000)
}

function advanceToStats() {
  stopTypewriter()
  currentStage.value = 'stats'
  
  stageTimer = setTimeout(() => {
    if (unlocks.value.length > 0) {
      currentStage.value = 'unlocks'
      stageTimer = setTimeout(() => {
        currentStage.value = 'complete'
      }, 6000)
    } else {
      currentStage.value = 'complete'
    }
  }, 4000)
}

function startTypewriter(duration: number) {
  stopTypewriter()
  const text = fullNarrative.value
  const totalChars = text.length
  const interval = Math.max(30, duration / totalChars)
  
  typewriterTimer = setInterval(() => {
    narrativeProgress.value++
    if (narrativeProgress.value >= totalChars) {
      stopTypewriter()
      narrativeProgress.value = totalChars
    }
  }, interval)
}

function stopTypewriter() {
  if (typewriterTimer) {
    clearInterval(typewriterTimer)
    typewriterTimer = null
  }
}

const displayText = computed(() => {
  return fullNarrative.value.slice(0, narrativeProgress.value)
})

// 跳过演出
function skipPerformance() {
  stopTypewriter()
  if (stageTimer) clearTimeout(stageTimer)
  currentStage.value = 'complete'
  narrativeProgress.value = fullNarrative.value.length
}

// 关闭面板
function closeEnding() {
  stopTypewriter()
  if (stageTimer) clearTimeout(stageTimer)
  store.showEnding = false
}

// 查看传承数据（可在新周目中使用）
function viewLegacy() {
  API.getEndingsLegacy().then(data => {
    alert(`【传承数据】\n已达成结局数：${store.endingData?.progression?.endings_reached || 0}/${store.endingData?.progression?.total_endings || 4}\n\n${JSON.stringify(data.legacy, null, 2)}`)
  }).catch(() => {})
}

// 重新开始（带传承加成）
function restartWithLegacy() {
  closeEnding()
  // 触发重新开始，附带传承数据
  store.resetGame()
}

// ==================== 生命周期 ====================

watch(() => store.showEnding, (show) => {
  if (show && store.endingData) {
    setTimeout(() => startPerformance(), 500)
  } else {
    stopTypewriter()
    if (stageTimer) clearTimeout(stageTimer)
  }
})

onMounted(() => {
  if (store.showEnding && store.endingData) {
    setTimeout(() => startPerformance(), 500)
  }
})

onUnmounted(() => {
  stopTypewriter()
  if (stageTimer) clearTimeout(stageTimer)
})

const showAllStats = ref(false)
const showAllUnlocks = ref(false)
</script>

<template>
  <Transition name="ending-fade">
    <div v-if="store.showEnding" class="ending-overlay" :class="tierClass">
      <div class="ending-container">
        
        <!-- ===== 标题区 ===== -->
        <div class="ending-header" v-show="currentStage !== 'loading'">
          <div class="ending-tier-badge">
            {{ endingData?.tier_label || '结局' }}
          </div>
          <h1 class="ending-title">{{ endingData?.title || '' }}</h1>
          <p class="ending-subtitle">{{ endingData?.subtitle || '' }}</p>
        </div>

        <!-- ===== 演出区 ===== -->
        <div class="ending-stage" v-show="currentStage === 'scene' || currentStage === 'dialogues' || currentStage === 'epilogue'">
          <!-- 场景指示器 -->
          <div v-if="currentStage === 'scene'" class="scene-indicator">
            <span class="scene-dots">
              <span v-for="i in maxScenes" :key="i"
                class="dot" :class="{ active: i - 1 === currentScene, past: i - 1 < currentScene }" />
            </span>
            <span class="scene-label">{{ scenes[currentScene]?.visual || '' }}</span>
          </div>
          
          <!-- NPC对话指示器 -->
          <div v-if="currentStage === 'dialogues'" class="dialogue-indicator">
            <div v-if="dialogues[currentDialogue]" class="speaker-info">
              <span class="speaker-icon">{{ emotionIcon(dialogues[currentDialogue]?.emotion || '') }}</span>
              <span class="speaker-name">{{ dialogues[currentDialogue]?.speaker || '' }}</span>
              <span class="dialogue-progress">{{ currentDialogue + 1 }} / {{ maxDialogues }}</span>
            </div>
          </div>

          <!-- 叙事文本（打字机效果） -->
          <div class="narrative-box" :class="currentStage">
            <p class="narrative-text">{{ displayText }}<span class="cursor" v-if="narrativeProgress < fullNarrative.length">|</span></p>
          </div>
        </div>

        <!-- ===== 统计区 ===== -->
        <div class="ending-stage" v-show="currentStage === 'stats'">
          <h3 class="section-title">📊 终局统计</h3>
          <div class="stats-grid">
            <div class="stat-item" v-for="(value, key) in stats" :key="key"
              v-show="!['achievements', 'bonus_label', 'bonus_score', 'battles_won', 'battles_total', 'officials_count'].includes(String(key))">
              <span class="stat-value">{{ typeof value === 'number' ? value.toLocaleString() : value }}{{ key === 'territory_ratio' ? '%' : '' }}</span>
              <span class="stat-label">{{ statLabels[String(key)] || key }}</span>
            </div>
          </div>
          
          <!-- 更多统计 -->
          <button class="toggle-detail-btn" @click="showAllStats = !showAllStats">
            {{ showAllStats ? '收起' : '查看详细统计' }}
          </button>
          <div v-if="showAllStats" class="stats-extra animate-fade-in">
            <div class="stat-item" v-if="stats.battles_total !== undefined">
              <span class="stat-value">{{ stats.battles_won || 0 }} / {{ stats.battles_total || 0 }}</span>
              <span class="stat-label">胜/总战役</span>
            </div>
            <div class="stat-item" v-if="stats.officials_count !== undefined">
              <span class="stat-value">{{ stats.officials_count }}</span>
              <span class="stat-label">在朝官员</span>
            </div>
            <div class="stat-item" v-if="stats.bonus_score !== undefined">
              <span class="stat-value">{{ (stats.bonus_score || 0).toLocaleString() }}</span>
              <span class="stat-label">{{ stats.bonus_label || '综合评分' }}</span>
            </div>
          </div>
        </div>

        <!-- ===== 解锁区 ===== -->
        <div class="ending-stage" v-show="currentStage === 'unlocks'">
          <h3 class="section-title">🎁 解锁内容</h3>
          <div class="unlocks-list">
            <div v-for="(reward, i) in unlocks" :key="i" class="unlock-item animate-fade-in"
              :style="{ animationDelay: `${i * 0.3}s` }">
              <div class="unlock-icon">
                {{ reward.type === 'save_slot' ? '💾' : reward.type === 'hidden_clue' ? '🔮' : reward.type === 'new_game_plus' ? '🔄' : reward.type === 'legacy_policy' ? '📜' : reward.type === 'legacy_strategy' ? '📖' : reward.type === 'art_gallery' ? '🖼' : '⭐' }}
              </div>
              <div class="unlock-info">
                <span class="unlock-name">{{ reward.name }}</span>
                <span class="unlock-desc">{{ reward.description }}</span>
              </div>
            </div>
          </div>
          <button class="toggle-detail-btn" style="margin-top: 12px;" 
            @click="showAllUnlocks = !showAllUnlocks">
            {{ showAllUnlocks ? '收起' : '更多详情' }}
          </button>
          <div v-if="showAllUnlocks" class="unlock-detail animate-fade-in">
            <p style="color: #ccc; font-size: 13px; line-height: 1.6;">
              • 黄金存档：可在特殊存档槽保存盛世，随时重温<br/>
              • 王朝真相：揭示元末乱世背后的隐藏剧情<br/>
              • 天命再临：新周目继承部分国力重新挑战<br/>
              • 盛世画廊：解锁结局概念CG艺术集
            </p>
          </div>
        </div>

        <!-- ===== 完成区（含渐进提示） ===== -->
        <div class="ending-stage" v-show="currentStage === 'complete'">
          <!-- 史官评语 -->
          <div class="historian-box" v-if="endingData?.narrative?.historian_comment">
            <div class="historian-icon">📜</div>
            <p class="historian-text">"{{ endingData?.narrative?.historian_comment }}"</p>
          </div>

          <!-- 渐进提示 -->
          <div class="progression-hint" v-if="hasNextTier">
            <div class="hint-header">🔮 天命启示</div>
            <p class="hint-text">{{ progression.next_tier_hint }}</p>
            <div class="gap-analysis" v-if="progression.gap_analysis?.gaps?.length">
              <span class="gap-title">距离《{{ progression.gap_analysis.next_ending_title }}》还需：</span>
              <div class="gap-list">
                <span class="gap-item" v-for="(gap, i) in progression.gap_analysis.gaps" :key="i">
                  {{ gap.dimension }}: {{ gap.current }}{{ gap.unit }} → {{ gap.target }}{{ gap.unit }}
                </span>
              </div>
            </div>
          </div>

          <!-- 继承人提示 -->
          <div v-if="endingData?.tier === 'true'" class="legacy-hint">
            <p>✨ 你创造了万世不朽的盛世。你的名字将永远镌刻在青史之上。</p>
          </div>
        </div>

        <!-- ===== 底部操作 ===== -->
        <div class="ending-actions" v-show="currentStage !== 'loading'">
          <button v-if="currentStage !== 'complete'" class="action-btn skip-btn" @click="skipPerformance">
            跳过演出
          </button>
          <button v-if="currentStage === 'complete' && endingData?.tier !== 'bad'" 
            class="action-btn legacy-btn" @click="viewLegacy">
            查看传承
          </button>
          <button v-if="currentStage === 'complete'" class="action-btn close-btn" @click="closeEnding">
            {{ endingData?.tier === 'bad' ? '退出游戏' : '返回主菜单' }}
          </button>
        </div>

      </div>

      <!-- 加载中 -->
      <div v-if="currentStage === 'loading'" class="ending-loading">
        <div class="loading-spinner" />
        <p>命运正在编织结局...</p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ==================== 遮罩与容器 ==================== */

.ending-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.92);
  backdrop-filter: blur(12px);
}

.ending-container {
  width: min(90vw, 800px);
  max-height: 90vh;
  overflow-y: auto;
  padding: 40px 48px;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

/* ==================== 结局等级配色 ==================== */

.ending-tier-bad .ending-container {
  background: linear-gradient(180deg, #1a0000 0%, #2d0000 40%, #1a0a0a 100%);
  border: 2px solid #8B0000;
  box-shadow: 0 0 60px rgba(139, 0, 0, 0.3), inset 0 0 100px rgba(139, 0, 0, 0.05);
}

.ending-tier-normal .ending-container {
  background: linear-gradient(180deg, #1a1a0a 0%, #2d2d1a 40%, #1a1a10 100%);
  border: 2px solid #B8860B;
  box-shadow: 0 0 60px rgba(184, 134, 11, 0.25), inset 0 0 100px rgba(184, 134, 11, 0.04);
}

.ending-tier-good .ending-container {
  background: linear-gradient(180deg, #1a1a00 0%, #3d2d0a 40%, #1a1a08 100%);
  border: 2px solid #DAA520;
  box-shadow: 0 0 80px rgba(218, 165, 32, 0.35), inset 0 0 120px rgba(218, 165, 32, 0.06);
}

.ending-tier-true .ending-container {
  background: linear-gradient(180deg, #0a0a1a 0%, #1a1040 30%, #2d1a50 60%, #1a1030 100%);
  border: 2px solid #FFD700;
  box-shadow: 0 0 100px rgba(255, 215, 0, 0.45), 0 0 200px rgba(255, 215, 0, 0.15),
    inset 0 0 150px rgba(255, 215, 0, 0.08);
  animation: golden-glow 3s ease-in-out infinite;
}

@keyframes golden-glow {
  0%, 100% { box-shadow: 0 0 100px rgba(255, 215, 0, 0.45), 0 0 200px rgba(255, 215, 0, 0.15), inset 0 0 150px rgba(255, 215, 0, 0.08); }
  50% { box-shadow: 0 0 140px rgba(255, 215, 0, 0.6), 0 0 260px rgba(255, 215, 0, 0.25), inset 0 0 180px rgba(255, 215, 0, 0.12); }
}

/* ==================== 标题区 ==================== */

.ending-header {
  text-align: center;
}

.ending-tier-badge {
  display: inline-block;
  padding: 4px 16px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 2px;
  margin-bottom: 12px;
}

.ending-tier-bad .ending-tier-badge { background: rgba(139, 0, 0, 0.4); color: #cc4444; border: 1px solid #8B0000; }
.ending-tier-normal .ending-tier-badge { background: rgba(184, 134, 11, 0.3); color: #d4a534; border: 1px solid #B8860B; }
.ending-tier-good .ending-tier-badge { background: rgba(218, 165, 32, 0.3); color: #e6c860; border: 1px solid #DAA520; }
.ending-tier-true .ending-tier-badge { background: rgba(255, 215, 0, 0.3); color: #ffd700; border: 1px solid #FFD700; }

.ending-title {
  font-size: 36px;
  font-weight: 700;
  margin: 0;
  letter-spacing: 4px;
}

.ending-tier-bad .ending-title { color: #cc4444; text-shadow: 0 0 20px rgba(204, 68, 68, 0.5); }
.ending-tier-normal .ending-title { color: #d4a534; text-shadow: 0 0 20px rgba(212, 165, 52, 0.4); }
.ending-tier-good .ending-title { color: #e6c860; text-shadow: 0 0 30px rgba(230, 200, 96, 0.5); }
.ending-tier-true .ending-title { color: #ffd700; text-shadow: 0 0 40px rgba(255, 215, 0, 0.7), 0 0 80px rgba(255, 215, 0, 0.3); }

.ending-subtitle {
  font-size: 16px;
  color: #aaa;
  margin: 8px 0 0;
  letter-spacing: 2px;
}

/* ==================== 演出区 ==================== */

.ending-stage {
  width: 100%;
  min-height: 120px;
}

.scene-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.scene-dots {
  display: flex;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
  transition: all 0.3s;
}
.dot.active { background: #888; transform: scale(1.4); }
.dot.past { background: rgba(255,255,255,0.4); }

.scene-label {
  font-size: 12px;
  color: #666;
  letter-spacing: 1px;
}

.dialogue-indicator {
  margin-bottom: 16px;
}

.speaker-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.speaker-icon { font-size: 20px; }
.speaker-name { font-weight: 600; color: #ddd; }
.dialogue-progress { font-size: 12px; color: #666; margin-left: auto; }

/* 叙事文本框 */
.narrative-box {
  padding: 20px 24px;
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  min-height: 60px;
}

.narrative-box.scene {
  border-color: rgba(255,255,255,0.1);
}

.narrative-box.dialogues {
  border-color: rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.05);
}

.narrative-box.epilogue {
  border-color: rgba(255,255,255,0.2);
  background: rgba(255,255,255,0.06);
  font-style: italic;
}

.narrative-text {
  font-size: 17px;
  line-height: 1.8;
  color: #ddd;
  margin: 0;
  white-space: pre-wrap;
}

.cursor {
  color: #fff;
  animation: blink 0.8s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ==================== 统计区 ==================== */

.section-title {
  font-size: 18px;
  color: #ccc;
  margin: 0 0 16px;
  text-align: center;
  letter-spacing: 2px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 8px;
  border-radius: 8px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #e6c860;
  margin-bottom: 4px;
}

.ending-tier-true .stat-value { color: #ffd700; }

.stat-label {
  font-size: 12px;
  color: #888;
}

.stats-extra {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.toggle-detail-btn {
  display: block;
  margin: 12px auto 0;
  padding: 6px 16px;
  font-size: 12px;
  color: #888;
  background: transparent;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.toggle-detail-btn:hover { color: #ccc; border-color: rgba(255,255,255,0.3); }

/* ==================== 解锁区 ==================== */

.unlocks-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.unlock-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
}

.unlock-icon {
  font-size: 28px;
  flex-shrink: 0;
}

.unlock-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.unlock-name {
  font-size: 15px;
  font-weight: 600;
  color: #e6c860;
}

.unlock-desc {
  font-size: 12px;
  color: #999;
}

.unlock-detail {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
}

/* ==================== 完成区 ==================== */

.historian-box {
  display: flex;
  gap: 12px;
  padding: 20px;
  border-radius: 10px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.1);
  margin-bottom: 16px;
}

.historian-icon {
  font-size: 28px;
  flex-shrink: 0;
}

.historian-text {
  font-size: 15px;
  line-height: 1.7;
  color: #bbb;
  font-style: italic;
  margin: 0;
}

.progression-hint {
  padding: 20px;
  border-radius: 10px;
  background: rgba(100, 149, 237, 0.08);
  border: 1px solid rgba(100, 149, 237, 0.2);
  margin-bottom: 16px;
}

.hint-header {
  font-size: 16px;
  font-weight: 600;
  color: #6495ED;
  margin-bottom: 10px;
}

.hint-text {
  font-size: 14px;
  line-height: 1.7;
  color: #bbb;
  margin: 0;
  white-space: pre-line;
}

.gap-analysis {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(100, 149, 237, 0.15);
}

.gap-title {
  font-size: 13px;
  color: #888;
}

.gap-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.gap-item {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(100, 149, 237, 0.1);
  color: #aaa;
}

.legacy-hint {
  text-align: center;
  padding: 16px;
  border-radius: 10px;
  background: rgba(255, 215, 0, 0.08);
  border: 1px solid rgba(255, 215, 0, 0.2);
}

.legacy-hint p {
  font-size: 16px;
  color: #ffd700;
  margin: 0;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
}

/* ==================== 操作按钮 ==================== */

.ending-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.action-btn {
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.skip-btn {
  background: rgba(255,255,255,0.1);
  color: #888;
  border: 1px solid rgba(255,255,255,0.15);
}
.skip-btn:hover { background: rgba(255,255,255,0.2); color: #bbb; }

.legacy-btn {
  background: rgba(100, 149, 237, 0.2);
  color: #6495ED;
  border: 1px solid rgba(100, 149, 237, 0.3);
}
.legacy-btn:hover { background: rgba(100, 149, 237, 0.35); }

.close-btn {
  background: rgba(218, 165, 32, 0.2);
  color: #e6c860;
  border: 1px solid rgba(218, 165, 32, 0.3);
}
.close-btn:hover { background: rgba(218, 165, 32, 0.35); }

.ending-tier-true .close-btn {
  background: rgba(255, 215, 0, 0.25);
  color: #ffd700;
  border-color: rgba(255, 215, 0, 0.4);
}

/* ==================== 加载 ==================== */

.ending-loading {
  text-align: center;
  color: #888;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  margin: 0 auto 16px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #e6c860;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ==================== 过渡动画 ==================== */

.ending-fade-enter-active { transition: opacity 0.8s ease; }
.ending-fade-leave-active { transition: opacity 0.5s ease; }
.ending-fade-enter-from, .ending-fade-leave-to { opacity: 0; }

.animate-fade-in { animation: fadeIn 0.5s ease both; }

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ==================== 滚动条 ==================== */

.ending-container::-webkit-scrollbar { width: 4px; }
.ending-container::-webkit-scrollbar-track { background: transparent; }
.ending-container::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 2px; }
</style>
