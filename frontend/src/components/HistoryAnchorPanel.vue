<script setup lang="ts">
/**
 * 历史剧情面板 - 展示历史锚点、分支选择、剧情回放
 */
import { ref, watch, onMounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import * as API from '@/services/api'

const store = useGameStore()
const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

const loading = ref(false)
const message = ref('')

// 历史剧情
const triggeredAnchors = ref<any[]>([])
const availableAnchors = ref<any[]>([])
const selectedAnchor = ref<any>(null)
const showBranchDetail = ref(false)
const anchorNarratives = ref<any[]>([])

// 选择的分支
const chosenBranchId = ref('')

onMounted(() => { if (props.visible) loadData() })
watch(() => props.visible, (v) => { if (v) loadData() })

async function loadData() {
  loading.value = true
  try {
    const fid = store.playerFactionId || store.playerFaction?.faction_id || ''
    const data = await API.getHistoryAnchors(fid)
    triggeredAnchors.value = data.triggered || []
    availableAnchors.value = data.available || []
  } catch (e) {
    console.error(e)
    triggeredAnchors.value = []
  } finally { loading.value = false }

  // 从事件日志中提取锚点叙述
  anchorNarratives.value = (store.events || [])
    .filter((e: any) => e.event_type === 'story')
    .reverse()
    .slice(0, 50)
}

async function chooseBranch(anchorId: string, branchId: string) {
  loading.value = true
  try {
    const data = await API.chooseHistoryBranch({
      anchor_id: anchorId,
      branch_id: branchId,
      faction_id: store.playerFactionId || store.playerFaction?.faction_id,
    })
    message.value = data.message || `已选择：${data.chosen_branch}`
    if (data.narrative) {
      selectedAnchor.value = { ...selectedAnchor.value, narrative: data.narrative, chosen_branch: branchId }
    }
    await loadData()
  } catch (e: any) {
    message.value = '选择失败'
  } finally { loading.value = false }
}

function getEndingClass(title: string) {
  if (title?.includes('大一统') || title?.includes('统一')) return 'ending-golden'
  if (title?.includes('失败') || title?.includes('崩溃')) return 'ending-dark'
  return 'ending-neutral'
}
</script>

<template>
  <div v-if="visible" class="history-overlay" @click.self="emit('close')">
    <div class="history-panel artifact-panel artifact-codex">
      <div class="panel-header">
        <h3>📜 历史长河</h3>
        <div class="header-info">
          <span class="year-tag">至正{{ store.worldState?.current_year ? store.worldState.current_year - 1340 : '' }}年</span>
          <button @click="emit('close')" class="close-btn">✕</button>
        </div>
      </div>

      <div class="panel-body">
        <!-- 已触发剧情锚点 -->
        <div v-if="triggeredAnchors.length" class="section">
          <h4>⚡ 历史转折</h4>
          <div class="anchor-list">
            <div
              v-for="a in triggeredAnchors" :key="a.anchor_id"
              class="anchor-card"
              :class="{ chosen: a.chosen_branch, pending: !a.chosen_branch }"
              @click="selectedAnchor = a; showBranchDetail = true"
            >
              <div class="anchor-header">
                <span class="anchor-title">{{ a.title }}</span>
                <span v-if="a.chosen_branch" class="chosen-tag">已抉择</span>
                <span v-else class="pending-tag">待抉择</span>
              </div>
              <p class="anchor-desc">{{ a.description }}</p>
              <div v-if="!a.chosen_branch" class="branch-choices">
                <div v-for="b in a.branches" :key="b.id" class="branch-option">
                  <button @click.stop="chooseBranch(a.anchor_id, b.id)" class="branch-btn" :class="{ ending: b.is_ending }">
                    {{ b.name }}
                  </button>
                  <span v-if="b.is_ending" class="ending-hint">【决定性结局】</span>
                </div>
              </div>
              <div v-else class="branch-result">
                ✅ 已选择，{{ a.narrative?.slice(0, 50) }}...
              </div>
            </div>
          </div>
        </div>

        <!-- 分支详情弹窗 -->
        <div v-if="showBranchDetail && selectedAnchor" class="detail-overlay" @click.self="showBranchDetail = false">
          <div class="detail-content">
            <h3>{{ selectedAnchor.title }}</h3>
            <p>{{ selectedAnchor.description }}</p>
            <div v-if="selectedAnchor.narrative" class="narrative">
              {{ selectedAnchor.narrative }}
            </div>
            <div v-if="!selectedAnchor.chosen_branch" class="branch-list">
              <h4>选择你的命运：</h4>
              <div v-for="b in selectedAnchor.branches" :key="b.id" class="branch-item">
                <button
                  @click="chooseBranch(selectedAnchor.anchor_id, b.id); showBranchDetail = false"
                  class="branch-btn-big"
                  :class="getEndingClass(b.ending_title || '')"
                >
                  <span class="branch-name">{{ b.name }}</span>
                  <span v-if="b.ending_title" class="branch-ending">→ {{ b.ending_title }}</span>
                </button>
              </div>
            </div>
            <button @click="showBranchDetail = false" class="close-detail">关闭</button>
          </div>
        </div>

        <!-- 历史年表 -->
        <div class="section">
          <h4>📖 大事年表</h4>
          <div v-if="!anchorNarratives.length" class="empty">暂无历史记录</div>
          <div v-else class="timeline">
            <div v-for="(evt, i) in anchorNarratives" :key="i" class="timeline-item">
              <div class="timeline-dot" />
              <div class="timeline-content">
                <div class="timeline-title">{{ evt.title }}</div>
                <div class="timeline-desc">{{ evt.description }}</div>
                <div class="timeline-round">第{{ evt.round }}回合 · {{ evt.year || '' }}年</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="message" class="panel-message">{{ message }}</div>
    </div>
  </div>
</template>

<style scoped>
.history-overlay { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.6); }
.history-panel { width: 640px; max-width: 95vw; max-height: 82vh; display: flex; flex-direction: column; color: #e2e8f0; font-size: 13px; box-shadow: inset 3px 0 0 var(--wuxing-metal); }
.panel-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid #2d3748; }
.panel-header h3 { margin: 0; font-size: 16px; }
.header-info { display: flex; align-items: center; gap: 12px; }
.year-tag { font-size: 12px; color: #fbbf24; background: #78350f; padding: 2px 10px; border-radius: 4px; }
.close-btn { background: none; border: none; color: #a0aec0; font-size: 18px; cursor: pointer; }

.panel-body { flex: 1; overflow-y: auto; padding: 12px; }
.section { margin-bottom: 16px; }
.section h4 { font-size: 14px; color: #94a3b8; margin-bottom: 8px; }
.empty { text-align: center; padding: 20px; color: #718096; }

/* 锚点 */
.anchor-list { display: flex; flex-direction: column; gap: 8px; }
.anchor-card { padding: 12px; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
.anchor-card.pending { background: #1e293b; border: 1px dashed #fbbf24; }
.anchor-card.chosen { background: #1e293b; border: 1px solid #334155; }
.anchor-card:hover { border-color: #60a5fa; }
.anchor-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.anchor-title { font-weight: bold; font-size: 14px; }
.chosen-tag { font-size: 10px; background: #065f46; color: #6ee7b7; padding: 1px 6px; border-radius: 3px; }
.pending-tag { font-size: 10px; background: #92400e; color: #fbbf24; padding: 1px 6px; border-radius: 3px; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
.anchor-desc { font-size: 12px; color: #94a3b8; margin: 4px 0; }

.branch-choices { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.branch-option { display: flex; align-items: center; gap: 4px; }
.branch-btn { padding: 4px 12px; background: #334155; color: #e2e8f0; border: 1px solid #4a5568; border-radius: 6px; cursor: pointer; font-size: 12px; }
.branch-btn:hover { background: #475569; }
.branch-btn.ending { border-color: #fbbf24; color: #fbbf24; }
.ending-hint { font-size: 10px; color: #fbbf24; }

/* 详情弹窗 */
.detail-overlay { position: fixed; inset: 0; z-index: 120; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
.detail-content { width: 500px; max-height: 70vh; overflow-y: auto; background: #1a1a2e; border: 1px solid #4a5568; border-radius: 12px; padding: 20px; }
.detail-content h3 { color: #fbbf24; margin-bottom: 8px; }
.detail-content p { color: #94a3b8; margin-bottom: 12px; }
.narrative { padding: 12px; background: #1e293b; border-left: 3px solid #fbbf24; font-size: 14px; line-height: 1.8; white-space: pre-line; margin-bottom: 12px; }
.branch-list h4 { margin-bottom: 8px; }
.branch-item { margin-bottom: 6px; }
.branch-btn-big { width: 100%; padding: 10px; background: #1e293b; border: 1px solid #334155; border-radius: 8px; color: #e2e8f0; cursor: pointer; text-align: left; font-size: 13px; display: flex; justify-content: space-between; }
.branch-btn-big:hover { background: #334155; }
.branch-btn-big.ending-golden { border-color: #fbbf24; background: #1a1a2e; }
.branch-btn-big.ending-dark { border-color: #991b1b; }
.branch-name { font-weight: bold; }
.branch-ending { color: #fbbf24; font-size: 12px; }
.close-detail { margin-top: 12px; padding: 8px 20px; background: #334155; color: #e2e8f0; border: none; border-radius: 6px; cursor: pointer; float: right; }

/* 时间线 */
.timeline { position: relative; padding-left: 20px; }
.timeline::before { content: ''; position: absolute; left: 6px; top: 0; bottom: 0; width: 2px; background: #334155; }
.timeline-item { position: relative; margin-bottom: 12px; }
.timeline-dot { position: absolute; left: -18px; top: 5px; width: 10px; height: 10px; background: #fbbf24; border-radius: 50%; border: 2px solid #1a1a2e; }
.timeline-content { padding: 8px; background: #1e293b; border-radius: 6px; }
.timeline-title { font-weight: bold; font-size: 13px; color: #fbbf24; }
.timeline-desc { font-size: 12px; color: #94a3b8; margin: 2px 0; }
.timeline-round { font-size: 10px; color: #64748b; }

.panel-message { padding: 8px 16px; background: #1e3a5f; color: #93c5fd; font-size: 12px; border-top: 1px solid #2d3748; }
</style>
