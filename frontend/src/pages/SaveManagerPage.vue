<template>
  <div class="save-page">
    <SaveArchiveBg />

    <div class="save-header">
      <button class="btn back-btn" @click="$router.back()">← 返回</button>
      <h2>存档管理</h2>
      <div class="header-actions">
        <button class="icon-btn" @click="refreshSaves" title="刷新列表">
          <span class="icon">↻</span>
        </button>
        <button class="icon-btn" title="切换全屏" @click="toggleFullscreen">
          <span class="icon">{{ isFullscreen ? '⤡' : '⤢' }}</span>
        </button>
      </div>
    </div>

    <div class="save-content animate-fade-in">
      <!-- 状态提示 -->
      <div class="save-hint" v-if="!store.isGameStarted">
        当前无活跃游戏，仅可读取已有存档。开始新游戏后可保存。
      </div>

      <!-- 游戏内快捷操作 -->
      <div class="quick-bar" v-if="store.isGameStarted">
        <span class="quick-label">快捷存档：</span>
        <button class="btn btn-quick" @click="doQuickSave" :disabled="saving">
          {{ saving ? '保存中...' : '⚡ 一键存档' }}
        </button>
        <span class="quick-info" v-if="quickResult">{{ quickResult }}</span>
      </div>

      <!-- === 手动存档槽位 === -->
      <div class="section-title">📁 存档槽位 <span class="title-hint">（共 10 个）</span></div>
      <div class="save-grid">
        <div
          v-for="slot in 10"
          :key="slot"
          class="save-slot"
          :class="{ empty: !getSaveForSlot(slot), active: getSaveForSlot(slot) }"
        >
          <div class="slot-number">存档 {{ slot }}</div>
          <template v-if="getSaveForSlot(slot)">
            <div class="slot-info">
              <p class="slot-name">
                <span class="faction-dot" :style="{ background: getFactionColor(getSaveForSlot(slot).faction) }"></span>
                {{ getSaveForSlot(slot).faction_name || getSaveForSlot(slot).faction || '未知势力' }}
              </p>
              <p class="slot-meta">
                第 {{ getSaveForSlot(slot).round }} 回合
                · {{ getSaveForSlot(slot).year }}年
                <template v-if="getSaveForSlot(slot).season">{{ getSaveForSlot(slot).season }}</template>
                · {{ getSaveForSlot(slot).territory_count || '?' }}城
              </p>
              <p class="slot-meta slot-note" v-if="getSaveForSlot(slot).note">
                📝 {{ getSaveForSlot(slot).note }}
              </p>
              <p class="slot-meta slot-time">{{ formatTime(getSaveForSlot(slot).saved_at) }}</p>
            </div>
            <div class="slot-actions">
              <button class="btn btn-sm btn-load" @click="loadSlot(slot)" :disabled="loading">
                {{ loading && loadingSlot === slot ? '读取中...' : '读取' }}
              </button>
              <button class="btn btn-sm btn-overwrite" @click="openOverwriteDialog(slot)" :disabled="saving">
                覆盖
              </button>
              <button class="btn btn-sm btn-export" @click="doExport(getSaveForSlot(slot))" title="导出存档">↓</button>
              <button class="btn btn-sm btn-delete" @click="confirmDeleteSlot(slot)">删除</button>
            </div>
          </template>
          <template v-else>
            <div class="slot-empty">
              <div class="slot-empty-text">空</div>
              <div class="slot-save-form">
                <input
                  v-model="saveNotes[slot - 1]"
                  class="note-input"
                  placeholder="备注（可选）"
                  maxlength="30"
                />
                <button
                  class="btn btn-sm btn-save"
                  @click="saveSlot(slot)"
                  :disabled="!store.isGameStarted || saving"
                >
                  {{ saving && savingSlot === slot ? '保存中...' : '💾 保存到此' }}
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- === 自动存档 === -->
      <template v-if="autoSaves.length > 0">
        <div class="section-title auto-title">🕐 自动存档 <span class="title-hint">（最近 {{ autoSaves.length }} 个）</span></div>
        <div class="save-grid">
          <div
            v-for="aSave in autoSaves"
            :key="aSave.filename"
            class="save-slot auto-slot"
            :class="{ active: true }"
          >
            <div class="slot-number auto-num">自动 · 第{{ aSave.round }}回合</div>
            <div class="slot-info">
              <p class="slot-name">
                <span class="faction-dot" :style="{ background: getFactionColor(aSave.faction) }"></span>
                {{ aSave.faction_name || aSave.faction || '未知势力' }}
              </p>
              <p class="slot-meta">
                {{ aSave.year }}年{{ aSave.season || '' }}
                · {{ aSave.territory_count || '?' }}城
                · {{ aSave.size_kb }}KB
              </p>
              <p class="slot-meta slot-time">{{ formatTime(aSave.saved_at) }}</p>
            </div>
            <div class="slot-actions">
              <button class="btn btn-sm btn-load" @click="loadAutoSave(aSave)" :disabled="loading">
                {{ loading && loadingSlot === 'auto' ? '读取中...' : '读取' }}
              </button>
              <button class="btn btn-sm btn-export" @click="doExport(aSave)" title="导出存档">↓</button>
              <button class="btn btn-sm btn-delete" @click="confirmDeleteAuto(aSave)">删除</button>
            </div>
          </div>
        </div>
      </template>

      <!-- 底部操作 -->
      <div class="section-actions">
        <button class="btn btn-danger-outline" @click="confirmClearAll" :disabled="!hasAnySaves">
          🗑 清空全部存档
        </button>
        <button class="btn btn-import" @click="triggerImport">
          📥 导入存档
        </button>
        <input
          ref="importInput"
          type="file"
          accept=".json"
          style="display:none"
          @change="handleImportFile"
        />
      </div>
    </div>

    <!-- === 自定义确认对话框 === -->
    <Teleport to="body">
      <div class="confirm-overlay" v-if="confirmMsg" @click.self="confirmMsg = ''">
        <div class="confirm-dialog">
          <p>{{ confirmMsg }}</p>
          <div class="confirm-actions">
            <button class="btn btn-cancel" @click="confirmMsg = ''">取消</button>
            <button class="btn btn-danger" @click="confirmAction()">确认</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- === 覆盖存档备注对话框 === -->
    <Teleport to="body">
      <div class="confirm-overlay" v-if="overwriteSlot > 0" @click.self="overwriteSlot = 0">
        <div class="confirm-dialog">
          <p>覆盖「存档 {{ overwriteSlot }}」</p>
          <p class="confirm-sub" v-if="getSaveForSlot(overwriteSlot)">
            {{ getSaveForSlot(overwriteSlot).faction_name }} · 第{{ getSaveForSlot(overwriteSlot).round }}回合
          </p>
          <input
            v-model="overwriteNote"
            class="note-input dialog-input"
            placeholder="新备注（可选）"
            maxlength="30"
          />
          <div class="confirm-actions">
            <button class="btn btn-cancel" @click="overwriteSlot = 0">取消</button>
            <button class="btn btn-save-confirm" @click="doOverwrite()" :disabled="saving">
              {{ saving ? '保存中...' : '覆盖保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/gameStore'
import { useFullscreen } from '@/composables/useFullscreen'
import {
  listSaves, loadGame, saveGame, deleteSave,
  quickSave, clearAllSaves as apiClearAll,
  exportSaveFile, importSaveFile,
} from '@/services/api'

const router = useRouter()
const store = useGameStore()
const saves = ref<any[]>([])
const autoSaves = ref<any[]>([])
const saving = ref(false)
const savingSlot = ref(-1)
const loading = ref(false)
const loadingSlot = ref<number | 'auto' | null>(null)
const { isFullscreen, toggleFullscreen } = useFullscreen()
const saveNotes = ref<string[]>(Array(10).fill(''))
const quickResult = ref('')
const confirmMsg = ref('')
const confirmCallback = ref<(() => void) | null>(null)
const overwriteSlot = ref(0)
const overwriteNote = ref('')
const importInput = ref<HTMLInputElement | null>(null)

const FACTION_COLORS: Record<string, string> = {
  faction_yuan: '#8B0000',
  faction_xushouhui: '#FFD700',
  faction_zhangshicheng: '#228B22',
  faction_fangguozhen: '#4169E1',
  faction_chenyouliang: '#FF4500',
  faction_zhuyuanzhang: '#DC143C',
  faction_mingyuzhen: '#8B008B',
  faction_wangbaobao: '#6A5888',
  faction_mobei: '#6A7A5A',
}

function getFactionColor(factionId: string): string {
  return FACTION_COLORS[factionId] || '#666'
}

const hasAnySaves = computed(() => saves.value.length > 0 || autoSaves.value.length > 0)

function formatTime(isoStr: string): string {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return isoStr }
}

onMounted(async () => {
  await refreshSaves()
})

function getSaveForSlot(slot: number) {
  return saves.value.find((s: any) => s.slot === slot - 1) || null
}

async function refreshSaves() {
  try {
    const data = await listSaves()
    saves.value = data.saves || []
    autoSaves.value = data.auto_saves || []
  } catch {
    console.warn('刷新存档列表失败')
    saves.value = []
    autoSaves.value = []
  }
}

async function doQuickSave() {
  if (saving.value || !store.isGameStarted) return
  saving.value = true
  quickResult.value = ''
  try {
    const result = await quickSave()
    quickResult.value = `已保存到槽${result.slot + 1} (第${result.round}回合)`
    await refreshSaves()
    setTimeout(() => { quickResult.value = '' }, 5000)
  } catch (e: any) {
    quickResult.value = '保存失败: ' + (e?.response?.data?.msg || e?.message || '未知错误')
  } finally {
    saving.value = false
  }
}

async function loadSlot(slot: number) {
  const save = getSaveForSlot(slot)
  if (!save) return

  // 如果当前有活跃游戏，警告
  if (store.isGameStarted) {
    confirmMsg.value = `当前游戏进度（第${store.currentRound}回合）将丢失，确认读取「${save.faction_name || '未知'}」第${save.round}回合存档？`
    confirmCallback.value = () => doLoad(save, slot)
    return
  }
  await doLoad(save, slot)
}

async function loadAutoSave(aSave: any) {
  if (store.isGameStarted) {
    confirmMsg.value = `当前游戏进度（第${store.currentRound}回合）将丢失，确认读取自动存档（第${aSave.round}回合）？`
    confirmCallback.value = () => doLoad(aSave, 'auto')
    return
  }
  await doLoad(aSave, 'auto')
}

async function doLoad(save: any, slot: number | 'auto') {
  if (loading.value) return
  loading.value = true
  loadingSlot.value = slot
  try {
    const data = await loadGame(save.slot, save.filename)
    if (data.world_state) {
      store.applyLoadState(data.world_state, data.world_state.player_faction_id || '')
    }
    router.push('/game')
  } catch (e: any) {
    alert('读档失败: ' + (e?.response?.data?.msg || e?.message || '未知错误'))
  } finally {
    loading.value = false
    loadingSlot.value = null
  }
}

async function saveSlot(slot: number) {
  if (saving.value || !store.isGameStarted) return
  saving.value = true
  savingSlot.value = slot
  try {
    const note = saveNotes.value[slot - 1] || `存档${slot}`
    await saveGame(slot - 1, note)
    saveNotes.value[slot - 1] = ''
    await refreshSaves()
  } catch (e: any) {
    alert('保存失败: ' + (e?.response?.data?.msg || e?.message || '未知错误'))
  } finally {
    saving.value = false
    savingSlot.value = -1
  }
}

function openOverwriteDialog(slot: number) {
  overwriteSlot.value = slot
  overwriteNote.value = ''
}

async function doOverwrite() {
  const slot = overwriteSlot.value
  if (saving.value || !store.isGameStarted || slot <= 0) return
  saving.value = true
  savingSlot.value = slot
  try {
    const note = overwriteNote.value || `存档${slot}`
    await saveGame(slot - 1, note)
    overwriteSlot.value = 0
    overwriteNote.value = ''
    await refreshSaves()
  } catch (e: any) {
    alert('保存失败: ' + (e?.response?.data?.msg || e?.message || '未知错误'))
  } finally {
    saving.value = false
    savingSlot.value = -1
  }
}

function confirmDeleteSlot(slot: number) {
  const save = getSaveForSlot(slot)
  if (!save) return
  confirmMsg.value = `确定删除「${save.faction_name || '未知势力'}」第${save.round}回合的存档吗？此操作不可撤销。`
  confirmCallback.value = () => doDeleteSlot(slot)
}

async function doDeleteSlot(slot: number) {
  const save = getSaveForSlot(slot)
  if (!save) return
  try {
    await deleteSave(save.filename)
    await refreshSaves()
  } catch (e: any) {
    alert('删除失败: ' + (e?.response?.data?.msg || e?.message || '未知错误'))
  }
}

function confirmDeleteAuto(aSave: any) {
  confirmMsg.value = `确定删除自动存档（第${aSave.round}回合）吗？`
  confirmCallback.value = () => doDeleteAuto(aSave)
}

async function doDeleteAuto(aSave: any) {
  try {
    await deleteSave(aSave.filename)
    await refreshSaves()
  } catch (e: any) {
    alert('删除失败: ' + (e?.response?.data?.msg || e?.message || '未知错误'))
  }
}

function confirmClearAll() {
  confirmMsg.value = `确定清空全部 ${saves.value.length + autoSaves.value.length} 个存档？此操作不可撤销！`
  confirmCallback.value = doClearAll
}

async function doClearAll() {
  try {
    const result = await apiClearAll()
    await refreshSaves()
    alert(`已清空 ${result.deleted_count || 0} 个存档`)
  } catch (e: any) {
    alert('清空失败: ' + (e?.response?.data?.msg || e?.message || '未知错误'))
  }
}

function confirmAction() {
  const cb = confirmCallback.value
  confirmMsg.value = ''
  confirmCallback.value = null
  if (cb) cb()
}

async function doExport(save: any) {
  try {
    const result = await exportSaveFile(save.filename)
    const blob = new Blob([JSON.stringify(result.save_data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = save.filename
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    alert('导出失败: ' + (e?.response?.data?.msg || e?.message || '未知错误'))
  }
}

function triggerImport() {
  importInput.value?.click()
}

async function handleImportFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    const saveData = JSON.parse(text)
    // 基本校验
    if (!saveData.world_state && !saveData.round) {
      alert('无效的存档文件：缺少 world_state 或 round 字段')
      return
    }
    const result = await importSaveFile(saveData, file.name)
    await refreshSaves()
    alert(`存档导入成功: ${result.filename} (${result.faction_name || '未知'} · 第${result.round}回合)`)
  } catch (e: any) {
    alert('导入失败: ' + (e?.response?.data?.msg || e?.message || '文件格式错误'))
  }
  // 重置 input 以允许重复导入同一文件
  if (importInput.value) importInput.value.value = ''
}
</script>

<style scoped>
.save-page {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  background: var(--bg-base);
  padding: 20px;
  position: relative;
}
.save-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 900px;
  margin: 0 auto 20px;
}
.save-header h2 { font-size: 22px; font-weight: normal; letter-spacing: 6px; }
.header-actions { display: flex; gap: 10px; }

.icon-btn {
  width: 34px; height: 34px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(20, 16, 12, 0.55);
  border: 1px solid rgba(184, 150, 62, 0.25);
  border-radius: 2px;
  color: var(--gold-dim, #b8a070);
  cursor: pointer; transition: all 0.2s;
  backdrop-filter: blur(4px);
}
.icon-btn:hover {
  background: rgba(184, 150, 62, 0.12);
  border-color: rgba(184, 150, 62, 0.5);
  transform: translateY(-1px);
}
.icon-btn .icon { font-size: 14px; }
.save-content { max-width: 900px; margin: 0 auto; }

.save-hint {
  text-align: center; color: var(--text-dim); font-size: 13px;
  margin-bottom: 16px; padding: 8px 16px;
  background: rgba(255, 193, 7, 0.08);
  border: 1px solid rgba(255, 193, 7, 0.2);
  border-radius: 4px;
}

/* 快捷操作栏 */
.quick-bar {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 16px; padding: 10px 16px;
  background: rgba(184, 150, 62, 0.06);
  border: 1px solid rgba(184, 150, 62, 0.15);
  border-radius: 4px;
}
.quick-label { font-size: 13px; color: var(--text-dim); }
.btn-quick {
  background: linear-gradient(135deg, #b8963e, #8b6914);
  color: #fff; border: none; cursor: pointer;
  border-radius: 3px; padding: 5px 16px; font-size: 13px;
  transition: all 0.2s;
}
.btn-quick:hover:not(:disabled) { filter: brightness(1.1); transform: translateY(-1px); }
.btn-quick:disabled { opacity: 0.5; cursor: not-allowed; }
.quick-info { font-size: 12px; color: #4caf50; }

/* 区域标题 */
.section-title {
  font-size: 16px; font-weight: bold; color: var(--text-ink);
  margin: 24px 0 12px; padding-bottom: 6px;
  border-bottom: 1px solid var(--border-light);
}
.auto-title { border-bottom-color: rgba(100, 149, 237, 0.2); }
.title-hint { font-size: 12px; font-weight: normal; color: var(--text-dim); }

/* 存档网格 */
.save-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }

.save-slot {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  padding: 16px;
  min-height: 120px;
  display: flex; flex-direction: column;
  justify-content: space-between;
  transition: all 0.2s;
}
.save-slot.active { border-color: var(--border-gold); box-shadow: 0 0 10px rgba(255, 193, 7, 0.12); }
.save-slot.empty { opacity: 0.65; }
.auto-slot { border-color: rgba(100, 149, 237, 0.3); }
.auto-slot.active { border-color: rgba(100, 149, 237, 0.6); box-shadow: 0 0 10px rgba(100, 149, 237, 0.1); }

.slot-number {
  font-size: 13px; font-weight: bold; color: var(--text-ink);
  margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
}
.auto-num { color: #6495ed; }

.faction-dot {
  display: inline-block; width: 8px; height: 8px;
  border-radius: 50%; margin-right: 4px; flex-shrink: 0;
}

.slot-info { margin-bottom: 10px; }
.slot-name { font-size: 15px; color: var(--text-ink); margin-bottom: 4px; display: flex; align-items: center; }
.slot-meta { font-size: 12px; color: var(--text-dim); margin-bottom: 2px; }
.slot-note { color: #b8963e; font-style: italic; }
.slot-time { font-size: 11px; color: var(--text-dim); opacity: 0.65; }

/* 空槽位 */
.slot-empty { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.slot-empty-text { font-size: 24px; color: var(--text-dim); margin: 10px 0; }
.slot-save-form {
  display: flex; flex-direction: column; gap: 6px;
  width: 100%; align-items: center;
}
.note-input {
  width: 80%;
  padding: 4px 10px;
  font-size: 12px;
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--border-light);
  border-radius: 3px;
  color: var(--text-ink);
  outline: none;
  transition: border-color 0.2s;
}
.note-input:focus { border-color: rgba(184, 150, 62, 0.5); }
.note-input::placeholder { color: var(--text-dim); opacity: 0.5; }
.dialog-input { width: 100%; margin: 8px 0; }

.slot-actions { display: flex; gap: 6px; margin-top: auto; flex-wrap: wrap; }
.btn-sm { padding: 4px 12px; font-size: 12px; border-radius: 3px; }
.btn-load { background: var(--btn-primary-bg); color: #fff; border: none; cursor: pointer; }
.btn-load:hover:not(:disabled) { filter: brightness(1.1); }
.btn-save { background: #2d6a4f; color: #fff; border: none; cursor: pointer; }
.btn-save:hover:not(:disabled) { background: #40916c; }
.btn-overwrite { background: rgba(184, 150, 62, 0.15); color: #b8963e; border: 1px solid rgba(184, 150, 62, 0.35); cursor: pointer; }
.btn-overwrite:hover:not(:disabled) { background: rgba(184, 150, 62, 0.25); }
.btn-export { background: transparent; color: var(--text-dim); border: 1px solid var(--border-light); cursor: pointer; font-size: 11px; padding: 4px 8px; }
.btn-export:hover { border-color: var(--text-ink); color: var(--text-ink); }
.btn-delete { background: transparent; color: #e74c3c; border: 1px solid #e74c3c; cursor: pointer; }
.btn-delete:hover { background: rgba(231, 76, 60, 0.1); }
.btn-sm:disabled { opacity: 0.4; cursor: not-allowed; }

/* 底部操作 */
.section-actions {
  display: flex; gap: 12px;
  justify-content: center;
  margin-top: 24px; padding-top: 16px;
  border-top: 1px solid var(--border-light);
}
.btn-danger-outline {
  background: transparent; color: #e74c3c; border: 1px solid #e74c3c;
  cursor: pointer; padding: 6px 18px; border-radius: 3px; font-size: 13px;
}
.btn-danger-outline:hover:not(:disabled) { background: rgba(231, 76, 60, 0.1); }
.btn-danger-outline:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-import {
  background: rgba(184, 150, 62, 0.1); color: #b8963e;
  border: 1px solid rgba(184, 150, 62, 0.3);
  cursor: pointer; padding: 6px 18px; border-radius: 3px; font-size: 13px;
}
.btn-import:hover { background: rgba(184, 150, 62, 0.18); }

/* 确认对话框 */
.confirm-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.65);
  display: flex; align-items: center; justify-content: center;
  z-index: 5000;
}
.confirm-dialog {
  background: var(--bg-card);
  border: 1px solid var(--border-gold);
  border-radius: 4px;
  padding: 24px 28px;
  min-width: 360px; max-width: 480px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.confirm-dialog p { font-size: 14px; color: var(--text-ink); margin: 0 0 8px; line-height: 1.6; }
.confirm-sub { font-size: 12px !important; color: var(--text-dim) !important; }
.confirm-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 16px; }
.btn-cancel {
  background: transparent; color: var(--text-dim);
  border: 1px solid var(--border-light);
  cursor: pointer; padding: 5px 20px; border-radius: 3px; font-size: 13px;
}
.btn-danger {
  background: #c0392b; color: #fff;
  border: none; cursor: pointer; padding: 5px 20px; border-radius: 3px; font-size: 13px;
}
.btn-save-confirm {
  background: #2d6a4f; color: #fff;
  border: none; cursor: pointer; padding: 5px 20px; border-radius: 3px; font-size: 13px;
}
</style>
