<template>
  <Teleport to="body">
    <div class="replay-overlay" @click.self="$emit('close')" v-if="visible">
      <div class="replay-dialog animate-fade-in artifact-panel artifact-codex">
        <div class="replay-header">
          <h2>🎬 观战回放</h2>
          <span class="replay-subtitle">对局录影 · 复盘推演</span>
          <button v-audio class="replay-close" @click="$emit('close')">✕</button>
        </div>

        <div class="replay-body">
          <!-- 回放控制栏 -->
          <div class="replay-controls">
            <div class="replay-speed-group">
              <span class="ctrl-label">倍速</span>
              <button
                v-for="s in speeds"
                :key="s"
                v-audio class="speed-btn"
                :class="{ active: playbackSpeed === s }"
                @click="setSpeed(s)"
              >{{ s }}x</button>
            </div>

            <div class="replay-transport">
              <button v-audio class="transport-btn" @click="stepBack" :disabled="currentStep <= 0" title="上一回合">⏮</button>
              <button v-audio class="transport-btn" @click="togglePlay" :title="isPlaying ? '暂停' : '播放'">
                {{ isPlaying ? '⏸' : '▶' }}
              </button>
              <button v-audio class="transport-btn" @click="stepForward" :disabled="currentStep >= totalSteps - 1" title="下一回合">⏭</button>
              <button v-audio class="transport-btn" @click="resetReplay" title="回到开头">⏹</button>
            </div>

            <div class="replay-progress">
              <span class="progress-label">回合</span>
              <input
                type="range"
                :min="0"
                :max="totalSteps - 1"
                v-model.number="currentStep"
                class="progress-slider"
                @input="seekTo"
              />
              <span class="progress-num">{{ currentStep + 1 }} / {{ totalSteps }}</span>
            </div>
          </div>

          <!-- 回合信息 -->
          <div class="replay-info">
            <div class="info-item">
              <span class="info-label">当前回合</span>
              <span class="info-value">{{ currentSnapshot?.round || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">时间</span>
              <span class="info-value">{{ currentSnapshot?.year || '' }}年{{ currentSnapshot?.month || '' }}月·{{ currentSnapshot?.season || '' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">存活势力</span>
              <span class="info-value">{{ livingFactionCount }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">回放模式</span>
              <span class="info-value mode-badge">只读查看</span>
            </div>
          </div>

          <!-- 快照内容（简化版地图数据展示） -->
          <div class="replay-content">
            <div v-if="isLoading" class="replay-empty">
              <p>正在加载回放数据...</p>
            </div>
            <div v-else-if="loadError" class="replay-empty">
              <p>{{ loadError }}</p>
              <p class="replay-hint">完成对局后，每回合自动生成世界快照供回放查看。</p>
            </div>
            <div v-else-if="!currentSnapshot" class="replay-empty">
              <p>暂无回放快照数据。</p>
              <p class="replay-hint">完成对局后，每回合自动生成世界快照供回放查看。</p>
            </div>
            <div v-else class="snapshot-view">
              <div class="snapshot-section">
                <h4>势力状态</h4>
                <div class="snapshot-grid">
                  <div
                    v-for="(f, fid) in snapshotFactions"
                    :key="fid"
                    class="snapshot-faction"
                    :style="{ borderLeftColor: getFactionColor(String(fid)) }"
                  >
                    <div class="sf-name" :style="{ color: getFactionColor(String(fid)) }">{{ f.name }}</div>
                    <div class="sf-stats">
                      兵{{ formatNum(f.total_troops) }} · 银{{ formatNum(f.treasury) }} · 地{{ f.tile_count || 0 }}
                      <span v-if="!f.is_alive" class="sf-dead">[覆灭]</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="snapshot-section">
                <h4>本回合事件</h4>
                <div v-if="!currentSnapshot.events?.length" class="no-events">无重大事件</div>
                <div v-for="e in currentSnapshot.events" :key="e.id" class="snapshot-event">
                  <span class="se-round">[{{ e.round }}]</span>
                  {{ e.title }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="replay-footer">
          <button v-audio class="rpl-btn" @click="exportReplay">导出回放文件</button>
          <button v-audio class="rpl-btn" @click="importReplay">导入回放文件</button>
          <button class="rpl-btn rpl-close-btn" @click="$emit('close')">关闭回放</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, onMounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import { getReplaySnapshots, getReplaySnapshot } from '@/services/api'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

// 进入回放模式时锁定所有操作
watch(() => props.visible, (val) => {
  if (val) {
    // 回放模式：暂停自动播放，锁定修改操作
    if (store.modeInfo) {
      store.modeInfo.player_can_operate = false
    }
  } else {
    // 退出回放：恢复操作权限（仅当非观战模式时）
    if (store.modeInfo && store.gameMode === 'player_turn') {
      store.modeInfo.player_can_operate = true
    }
  }
})

const store = useGameStore()
const speeds = [0.25, 0.5, 1, 2, 4, 8]
const playbackSpeed = ref(1)
const isPlaying = ref(false)
const currentStep = ref(0)
const totalSteps = ref(0)
const snapshots = ref<any[]>([])
const isLoading = ref(false)
const loadError = ref('')

let playTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await loadRealSnapshots()
})

async function loadRealSnapshots() {
  isLoading.value = true
  loadError.value = ''
  try {
    const result = await getReplaySnapshots()
    if (result.snapshots && result.snapshots.length > 0) {
      snapshots.value = result.snapshots
      totalSteps.value = result.snapshots.length
      currentStep.value = result.snapshots.length - 1 // 默认显示最新
      return
    }
  } catch (_) { console.warn('加载回放数据失败:', _) }
  
  // 后端无数据时使用 store 中的 _round_snapshots（如果有的话从 advanceTurn 返回）
  loadError.value = '暂无回放数据，请先进行游戏。'
  isLoading.value = false
}

const currentSnapshot = computed(() => snapshots.value[currentStep.value] || null)

// 兼容后端快照格式：{ factions_snapshot: { fid: {...} } } 或 { factions: [...] }
const snapshotFactions = computed(() => {
  const snap = currentSnapshot.value
  if (!snap) return {}
  // 新格式：factions_snapshot 对象
  if (snap.factions_snapshot) return snap.factions_snapshot
  // 旧格式：factions 数组
  if (Array.isArray(snap.factions)) {
    const obj: Record<string, any> = {}
    for (const f of snap.factions) {
      obj[f.id || f.faction_id] = f
    }
    return obj
  }
  return snap.factions || {}
})

const livingFactionCount = computed(() => {
  const factions = snapshotFactions.value
  return Object.values(factions).filter((f: any) => f.is_alive !== false).length
})

function getFactionColor(fid: string): string {
  const factions = store.factions
  if (factions && factions[fid]) return factions[fid].color
  // 预设颜色 fallback
  const presetColors: Record<string, string> = {
    faction_yuan: '#8B0000', faction_zhuyuanzhang: '#DC143C', faction_chenyouliang: '#1E90FF',
    faction_zhangshicheng: '#FF8C00', faction_fangguozhen: '#20B2AA', faction_xushouhui: '#996633',
    faction_mingyuzhen: '#B8860B', faction_wangbaobao: '#666699', faction_mobei: '#887766',
    // 旧格式兼容
    ruler_yuan: '#8B0000', ruler_zhuyuan: '#DC143C', ruler_chen: '#1E90FF',
    ruler_zhang: '#228B22', ruler_fang: '#FF8C00', ruler_wang: '#9370DB',
    ruler_ming: '#DAA520', ruler_tatar: '#CD853F', ruler_xushou: '#2E8B57',
  }
  return presetColors[fid] || 'var(--text-dim)'
}

function setSpeed(s: number) {
  playbackSpeed.value = s
  if (isPlaying.value) {
    stopPlay()
    startPlay()
  }
}

function togglePlay() {
  if (isPlaying.value) {
    stopPlay()
  } else {
    if (currentStep.value >= totalSteps.value - 1) {
      currentStep.value = 0
    }
    startPlay()
  }
}

function startPlay() {
  isPlaying.value = true
  const interval = Math.max(100, 2000 / playbackSpeed.value)
  playTimer = setInterval(() => {
    if (currentStep.value < totalSteps.value - 1) {
      currentStep.value++
    } else {
      stopPlay()
    }
  }, interval)
}

function stopPlay() {
  isPlaying.value = false
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
}

function stepForward() {
  if (currentStep.value < totalSteps.value - 1) {
    currentStep.value++
  }
}

function stepBack() {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

function seekTo() {
  // 拖动进度条时暂停播放
  if (isPlaying.value) stopPlay()
}

function resetReplay() {
  stopPlay()
  currentStep.value = 0
}

function exportReplay() {
  const data = JSON.stringify(snapshots.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `yuanmo_replay_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function importReplay() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = (e: any) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev: any) => {
      try {
        const data = JSON.parse(ev.target.result)
        if (Array.isArray(data)) {
          snapshots.value = data
          totalSteps.value = data.length
          currentStep.value = 0
          stopPlay()
        }
      } catch {
        console.warn('回放文件解析失败')
        alert('无效的回放文件格式')
      }
    }
    reader.readAsText(file)
  }
  input.click()
}

function formatNum(n: number | undefined): string {
  if (n === undefined) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

watch(() => currentStep.value, () => {
  if (isPlaying.value) {
    // 播放中到达末尾自动停止
    if (currentStep.value >= totalSteps.value - 1) {
      stopPlay()
    }
  }
})

onUnmounted(() => {
  stopPlay()
})
</script>

<style scoped>
.replay-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4500;
}

.replay-dialog {
  width: 90vw;
  max-width: 750px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.replay-header {
  display: flex;
  align-items: center;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(180deg, var(--bg-hover) 0%, var(--border-main) 100%);
}

.replay-header h2 {
  font-size: 18px;
  font-weight: normal;
  letter-spacing: 3px;
}

.replay-subtitle {
  font-size: 11px;
  color: var(--text-dim);
  margin-left: 12px;
  flex: 1;
  letter-spacing: 2px;
}

.replay-close {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  font-size: 16px;
  cursor: pointer;
  color: var(--text-secondary);
}

.replay-close:hover { color: #8b0000; }

.replay-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

/* 回放控制 */
.replay-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 14px;
  background: rgba(44, 24, 16, 0.05);
  border: 1px solid var(--border-light);
  border-radius: 2px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.replay-speed-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

.ctrl-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-right: 4px;
}

.speed-btn {
  padding: 3px 8px;
  font-size: 11px;
  font-family: "SimSun", serif;
  background: none;
  border: 1px solid var(--text-dim);
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s;
}

.speed-btn.active {
  background: rgba(139, 0, 0, 0.1);
  border-color: #8b0000;
  color: #8b0000;
}

.speed-btn:hover { background: rgba(139, 115, 85, 0.1); }

.replay-transport {
  display: flex;
  gap: 4px;
}

.transport-btn {
  width: 32px;
  height: 32px;
  font-size: 14px;
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-card) 100%);
  border: 1px solid var(--text-dim);
  color: var(--text-main);
  cursor: pointer;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.transport-btn:hover:not(:disabled) { background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-hover) 100%); }
.transport-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.replay-progress {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.progress-slider {
  flex: 1;
  accent-color: #8b0000;
}

.progress-num {
  font-size: 12px;
  color: var(--text-main);
  min-width: 60px;
  text-align: right;
}

/* 回合信息 */
.replay-info {
  display: flex;
  gap: 16px;
  padding: 8px 14px;
  margin-bottom: 12px;
  background: rgba(240, 228, 204, 0.6);
  border: 1px solid var(--border-light);
  border-radius: 2px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 1px;
}

.info-value {
  font-size: 14px;
  color: var(--text-main);
  font-weight: bold;
}

.mode-badge {
  font-size: 11px;
  padding: 1px 8px;
  background: rgba(139, 0, 0, 0.1);
  color: #8b0000;
  border: 1px solid rgba(139, 0, 0, 0.2);
  border-radius: 2px;
}

/* 快照内容 */
.replay-content {
  max-height: 300px;
  overflow-y: auto;
}

.replay-empty {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-dim);
}

.replay-empty p {
  font-size: 14px;
  letter-spacing: 2px;
}

.replay-hint {
  font-size: 12px !important;
  color: var(--text-dim) !important;
  margin-top: 8px;
}

.snapshot-section {
  margin-bottom: 16px;
}

.snapshot-section h4 {
  font-size: 13px;
  font-weight: normal;
  color: var(--text-main);
  letter-spacing: 2px;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border-light);
}

.snapshot-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.snapshot-faction {
  padding: 6px 10px;
  background: rgba(240, 228, 204, 0.5);
  border-left: 3px solid;
  border-radius: 2px;
}

.sf-name {
  font-size: 14px;
  font-weight: bold;
}

.sf-stats {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.snapshot-event {
  padding: 4px 8px;
  font-size: 12px;
  color: var(--text-secondary);
  border-bottom: 1px dotted var(--border-light);
}

.se-round {
  color: var(--text-dim);
  font-size: 10px;
  margin-right: 4px;
}

.no-events {
  font-size: 12px;
  color: var(--text-dim);
  padding: 8px;
}

/* 底部 */
.replay-footer {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-light);
  justify-content: flex-end;
}

.rpl-btn {
  padding: 6px 16px;
  font-size: 12px;
  font-family: "SimSun", serif;
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-card) 100%);
  border: 1px solid #c9a94e;
  color: var(--text-main);
  cursor: pointer;
  border-radius: 2px;
  letter-spacing: 2px;
  transition: all 0.2s;
}

.rpl-btn:hover {
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-hover) 100%);
}

.rpl-close-btn {
  background: linear-gradient(180deg, #8b0000 0%, #6b0000 100%);
  color: var(--bg-card);
  border-color: #a00000;
}

.rpl-close-btn:hover {
  background: linear-gradient(180deg, #a00000 0%, #800000 100%);
}

.animate-fade-in {
  animation: fadeIn 0.25s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}
</style>
