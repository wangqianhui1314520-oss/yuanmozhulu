<template>
  <footer class="game-footer">
    <!-- 3.1: 观战模式提示 -->
    <div v-if="store.isWatchMode" class="watch-mode-banner">
      <span class="watch-icon">👁</span>
      观战模式 · 天下大势尽收眼底 · 所有操作已锁定
    </div>


    <!-- 圣旨输入栏（3.1: 观战模式隐藏） -->
    <div class="edict-bar" v-if="store.canOperate">
      <div class="edict-label">
        <svg viewBox="0 0 36 36" width="36" height="36">
          <rect x="1" y="1" width="34" height="34" rx="4" fill="none" stroke="#b89b68" stroke-width="1.5" opacity="0.6"/>
          <rect x="4" y="4" width="28" height="28" rx="2" fill="none" stroke="#b89b68" stroke-width="0.6" opacity="0.35"/>
          <text x="18" y="24" text-anchor="middle" fill="#c8a84a" font-size="18" font-family="STKaiti,KaiTi,serif" font-weight="bold">敕</text>
        </svg>
      </div>
      <textarea
        v-model="edictText"
        class="edict-input"
        placeholder="颁布圣旨...（例：减免赋税、征调粮草、北伐大都、与陈友谅议和）"
        rows="2"
        @keydown.enter.ctrl="submitEdict"
        ref="edictRef"
      ></textarea>
      <div class="edict-actions">
        <button class="btn btn-gold edict-submit" @click="submitEdict" :disabled="isProcessing || !edictText.trim()">
          {{ isProcessing ? '拟旨中...' : '颁布圣旨' }}
        </button>
        <button class="btn edict-advance" @click="advanceTurn" :disabled="isProcessing">
          空过回合
        </button>
      </div>
    </div>

    <!-- 圣旨执行结果（AI 推演反馈） -->
    <div class="edict-result" v-if="edictResult && store.canOperate">
      <div class="er-header">
        <span class="er-icon">📜</span>
        <span class="er-title">尚书省批复</span>
        <button class="er-close" @click="edictResult = null">×</button>
      </div>
      <div class="er-narrative" v-if="edictResult.ai_analysis?.narrative">
        {{ edictResult.ai_analysis.narrative }}
      </div>
      <div class="er-summary" v-if="edictResult.ai_analysis?.summary">
        {{ edictResult.ai_analysis.summary }}
      </div>
      <!-- 执行成功的指令 -->
      <div class="er-section" v-if="edictResult.execution?.executed?.length">
        <div class="er-section-title">✓ 已执行政令（{{ edictResult.execution.total_executed }}条）</div>
        <div class="er-item er-item-success" v-for="(cmd, i) in edictResult.execution.executed" :key="'ok'+i">
          <span class="er-action">{{ cmd.action }}</span>
          <span class="er-reason">{{ cmd.result?.message || cmd.ai_reason }}</span>
        </div>
      </div>
      <!-- 执行失败的指令 -->
      <div class="er-section" v-if="edictResult.execution?.failed?.length">
        <div class="er-section-title er-fail-title">✗ 无法执行（{{ edictResult.execution.total_failed }}条）</div>
        <div class="er-item er-item-fail" v-for="(cmd, i) in edictResult.execution.failed" :key="'fail'+i">
          <span class="er-action">{{ cmd.action }}</span>
          <span class="er-reason">{{ cmd.reason }}</span>
        </div>
      </div>
    </div>

    <!-- 全局推演：圣旨颁布后天下各势力反应 -->
    <div class="deduction-panel" v-if="globalDeduction && globalDeduction.summary && store.canOperate">
      <div class="ded-header">
        <span class="ded-icon">🌏</span>
        <span class="ded-title">天下震动 · 局势推演</span>
        <button class="ded-close" @click="globalDeduction = null">×</button>
      </div>
      <!-- 全局叙事 -->
      <div class="ded-narrative" v-if="globalDeduction.global_narrative">
        {{ globalDeduction.global_narrative }}
      </div>
      <!-- 各势力反应 -->
      <div class="ded-factions" v-if="globalDeduction.faction_reactions?.length">
        <div class="ded-section-label">▸ 各方势力动向</div>
        <div class="ded-faction-card" v-for="(fr, i) in globalDeduction.faction_reactions" :key="'fr'+i"
          :style="{ borderLeftColor: fr.color || '#b89b68' }">
          <div class="ded-faction-head">
            <span class="ded-faction-name" :style="{ color: fr.color }">{{ fr.faction_name }}</span>
            <span class="ded-faction-stance" :class="stanceClass(fr.stance)">{{ fr.stance }}</span>
          </div>
          <div class="ded-faction-narr">{{ fr.narrative }}</div>
          <div class="ded-faction-action" v-if="fr.likely_action">
            <span class="ded-action-icon">⚔</span>{{ fr.likely_action }}
          </div>
        </div>
      </div>
      <!-- 外交变动 -->
      <div class="ded-diplo" v-if="globalDeduction.diplomatic_shifts?.length">
        <div class="ded-section-label">▸ 外交格局变化</div>
        <div class="ded-diplo-item" v-for="(ds, i) in globalDeduction.diplomatic_shifts" :key="'ds'+i">
          <span class="ded-diplo-parties">{{ ds.from }} ↔ {{ ds.to }}</span>
          <span class="ded-diplo-change" :class="ds.change > 0 ? 'ded-positive' : 'ded-negative'">
            {{ ds.change > 0 ? '+' : '' }}{{ ds.change }}
          </span>
          <span class="ded-diplo-reason">{{ ds.reason }}</span>
        </div>
      </div>
      <!-- 触发事件 -->
      <div class="ded-events" v-if="globalDeduction.event_triggers?.length">
        <div class="ded-section-label">▸ 连锁事件</div>
        <div class="ded-event-item" v-for="(ev, i) in globalDeduction.event_triggers" :key="'ev'+i"
          :class="'ded-sev-' + (ev.severity || 'minor')">
          <span class="ded-event-sev" :class="'ded-sev-' + (ev.severity || 'minor')">
            {{ ev.severity === 'major' ? '◆' : ev.severity === 'minor' ? '◇' : '·' }}
          </span>
          <div class="ded-event-body">
            <span class="ded-event-title">{{ ev.title }}</span>
            <span class="ded-event-desc">{{ ev.description }}</span>
          </div>
        </div>
      </div>
      <!-- 经济涟漪 -->
      <div class="ded-econ" v-if="globalDeduction.economic_ripples">
        <div class="ded-section-label">▸ 经济涟漪</div>
        <div class="ded-econ-text">{{ globalDeduction.economic_ripples }}</div>
      </div>
      <!-- 战略建议 -->
      <div class="ded-advice" v-if="globalDeduction.strategic_advice">
        <div class="ded-section-label">▸ 谋士献策</div>
        <div class="ded-advice-text">{{ globalDeduction.strategic_advice }}</div>
      </div>
      <div class="ded-footer">
        <span class="ded-footer-text">{{ globalDeduction.summary }}</span>
        <button class="ded-advance-btn" @click="advanceTurn" :disabled="isProcessing">
          推进次月 →
        </button>
      </div>
    </div>

    <!-- 待办指令队列（地图右键生成） -->
    <div class="pending-commands" v-if="store.canOperate && store.pendingEdictCommands.length > 0">
      <div class="pc-header">
        <span class="pc-title">📋 待办指令（{{ store.pendingEdictCommands.length }}条）</span>
        <button class="pc-clear" @click="store.pendingEdictCommands = []">清空</button>
      </div>
      <div class="pc-list">
        <div v-for="(cmd, i) in store.pendingEdictCommands" :key="i" class="pc-item"
          @click="edictText = cmd.label; store.pendingEdictCommands.splice(i, 1); edictRef?.focus()">
          <span class="pc-label">{{ cmd.label }}</span>
          <span class="pc-action">{{ cmd.action }}</span>
        </div>
      </div>
    </div>

    <!-- 快捷政令（3.1: 观战模式隐藏） -->
    <div class="quick-edicts" v-if="store.canOperate">
      <button
        v-for="qe in quickEdicts"
        :key="qe"
        class="quick-btn"
        @click="edictText = qe; edictRef?.focus()"
      >{{ qe }}</button>
    </div>


  </footer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import type { GlobalDeduction } from '@/services/api'

const store = useGameStore()
const edictText = ref('')
const isProcessing = ref(false)
const edictRef = ref<HTMLTextAreaElement>()
const edictResult = ref<any>(null)  // 圣旨执行结果
const globalDeduction = ref<GlobalDeduction | null>(null)  // 全局推演结果

const quickEdicts = [
  '减免赋税，安抚百姓',
  '征调粮草，储备军需',
  '修缮城墙，加固城防',
  '开仓赈灾，救济灾民',
  '招募新兵，扩充军力',
  '遣使修好，联姻结盟',
]

/** 势力态度 class 映射 */
function stanceClass(stance: string): string {
  const m: Record<string, string> = {
    '警觉': 'ded-stance-alert',
    '敌视': 'ded-stance-hostile',
    '恐慌': 'ded-stance-panic',
    '亲近': 'ded-stance-friendly',
    '中立': 'ded-stance-neutral',
    '嘲笑': 'ded-stance-mock',
    '愤怒': 'ded-stance-hostile',
  }
  return m[stance] || 'ded-stance-neutral'
}



/**
 * 颁布圣旨 - AI 推演模式
 * 
 * 用户用自然语言输入圣旨 → AI 解析为具体操作指令 → 直接执行并反映到游戏状态
 * 所有数值变化（银两、兵马粮草等）即时在后端更新并通过 world_state 同步到前端
 */
async function submitEdict() {
  if (!edictText.value.trim() || isProcessing.value) return
  isProcessing.value = true
  edictResult.value = null
  globalDeduction.value = null

  try {
    // 调用新版 AI 推演执行
    const result = await store.executeEdictAI(edictText.value)
    
    if (!result) {
      throw new Error('圣旨执行失败，请稍后重试')
    }

    edictResult.value = result

    // 获取全局推演结果
    if (result.global_deduction) {
      globalDeduction.value = result.global_deduction

      // 记录全局推演中的事件
      for (const ev of result.global_deduction.event_triggers || []) {
        store.addEvent({
          event_id: `ded_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
          event_type: ev.event_type || 'rumor',
          severity: ev.severity || 'minor',
          round: store.currentRound,
          title: ev.title,
          description: ev.description,
          faction_id: '',
          tile_id: '',
          effects: { source: 'global_deduction' },
          narrative: '',
        })
      }
    }

    // 记录邸报事件
    const exec = result.execution || {}
    const ai = result.ai_analysis || {}
    
    store.addEvent({
      event_id: `edict_${Date.now()}`,
      event_type: 'court',
      severity: 'major',
      round: store.currentRound,
      title: `圣旨：${edictText.value.slice(0, 20)}${edictText.value.length > 20 ? '...' : ''}`,
      description: ai.narrative || ai.summary || `执行${exec.total_executed || 0}条政令`,
      faction_id: store.playerFactionId,
      tile_id: '',
      effects: {
        commands_executed: exec.total_executed,
        commands_failed: exec.total_failed,
      },
      narrative: ai.narrative || '',
    })

    // 如果执行成功，清空输入
    if (exec.total_executed > 0 || !result.ai_analysis?.ai_generated) {
      edictText.value = ''
    }

    // 清空本回待办（圣旨卷轴关闭后由 GamePage 推进回合）
    store.pendingEdictCommands.splice(0, store.pendingEdictCommands.length)
  } catch (e: any) {
    console.error('圣旨颁布失败:', e)
    globalDeduction.value = null
    store.addEvent({
      event_id: `edict_err_${Date.now()}`,
      event_type: 'court',
      severity: 'trivial',
      round: store.currentRound,
      title: '圣旨颁布失败',
      description: e?.message || '未知错误',
      faction_id: store.playerFactionId,
      tile_id: '',
      effects: {},
      narrative: '',
    })
  } finally {
    isProcessing.value = false
  }
}

async function advanceTurn() {
  if (isProcessing.value) return
  isProcessing.value = true
  try {
    // store.advanceTurn() 内部已调用 API.advanceTurn()，无需重复调用
    const result = await store.advanceTurn()
    if (result) {
      store.addEvent({
        event_id: `turn_${Date.now()}`,
        event_type: 'civil',
        severity: 'trivial',
        round: store.currentRound,
        title: `第${store.currentRound}回合结束`,
        description: `至正${store.currentYear}年${store.currentMonth}月·${store.currentSeason}`,
        faction_id: '',
        tile_id: '',
        effects: {},
        narrative: '',
      })
    }
  } catch (e: any) {
    console.error('推进月份失败:', e)
  } finally {
    isProcessing.value = false
  }
}
</script>

<style scoped>
.game-footer {
  background: linear-gradient(180deg, #2C2824 0%, #1A1815 100%);
  border-top: 2px solid var(--gold);
  flex-shrink: 0;
}

/* 3.1: 观战模式横幅 */
.watch-mode-banner {
  padding: 8px 16px;
  text-align: center;
  font-size: 12px;
  font-family: "SimSun", serif;
  color: var(--gold);
  background: rgba(184, 155, 104, 0.08);
  border-bottom: 1px solid rgba(184, 155, 104, 0.2);
  letter-spacing: 2px;
}
.watch-icon {
  margin-right: 6px;
}

/* 圣旨输入栏 */
.edict-bar {
  display: flex;
  gap: 10px;
  padding: 10px 14px;
  align-items: flex-start;
}

.edict-label {
  flex-shrink: 0;
  width: 36px; height: 36px;
  filter: drop-shadow(0 0 4px rgba(200,168,74,0.25));
  transition: filter 0.3s;
  margin-top: 6px;
}
.edict-label:hover { filter: drop-shadow(0 0 8px rgba(200,168,74,0.45)); }

.edict-input {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg-input);
  border: 1px solid var(--border-main);
  border-radius: var(--radius-sm);
  font-family: "SimSun", serif;
  font-size: 13px;
  color: var(--text-main);
  resize: none;
  min-height: 46px;
  line-height: 1.7;
}

.edict-input::placeholder {
  color: var(--text-muted);
  font-family: "FangSong", "FangSong_GB2312", serif;
}

.edict-input:focus {
  outline: none;
  border-color: var(--gold);
  box-shadow: 0 0 0 2px rgba(184, 155, 104, 0.1);
}

.edict-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}

.edict-submit, .edict-advance {
  padding: 8px 16px;
  font-family: "SimSun", serif;
  font-size: 12px;
  letter-spacing: 2px;
  white-space: nowrap;
}

.edict-advance {
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.2);
  color: var(--text-secondary);
}
.edict-advance:hover:not(:disabled) {
  background: rgba(184, 155, 104, 0.12);
  border-color: var(--gold);
  color: var(--text-main);
}

/* 圣旨执行结果 */
.edict-result {
  margin: 0 12px 8px;
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.25);
  border-radius: 2px;
  max-height: 200px;
  overflow-y: auto;
}

.er-header {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  border-bottom: 1px solid rgba(184, 155, 104, 0.15);
}

.er-icon {
  margin-right: 6px;
}

.er-title {
  flex: 1;
  font-size: 12px;
  font-family: "SimSun", serif;
  color: var(--gold);
  letter-spacing: 2px;
}

.er-close {
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
}

.er-close:hover {
  color: var(--danger);
}

.er-narrative {
  padding: 8px 12px;
  font-size: 13px;
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
  color: var(--text-main);
  line-height: 1.8;
  border-bottom: 1px solid rgba(184, 155, 104, 0.1);
}

.er-summary {
  padding: 6px 12px;
  font-size: 11px;
  color: var(--text-secondary);
  font-family: "FangSong", "FangSong_GB2312", serif;
  border-bottom: 1px solid rgba(184, 155, 104, 0.1);
}

.er-section {
  padding: 4px 0;
}

.er-section-title {
  padding: 4px 12px;
  font-size: 11px;
  font-family: "SimSun", serif;
  color: var(--gold);
  letter-spacing: 1px;
}

.er-fail-title {
  color: #D07070;
}

.er-item {
  display: flex;
  gap: 8px;
  padding: 3px 12px;
  font-size: 11px;
  font-family: "SimSun", serif;
  align-items: baseline;
}

.er-item-success {
  border-left: 2px solid var(--gold);
}

.er-item-fail {
  border-left: 2px solid #D07070;
}

.er-action {
  color: var(--text-secondary);
  background: rgba(139, 115, 85, 0.15);
  padding: 1px 6px;
  border-radius: 1px;
  font-size: 10px;
  flex-shrink: 0;
  min-width: 60px;
  text-align: center;
}

.er-reason {
  color: var(--text-dim);
  flex: 1;
  line-height: 1.5;
}

/* 快捷政令 */
.quick-edicts {
  display: flex;
  gap: 6px;
  padding: 0 14px 8px;
  flex-wrap: wrap;
}

.quick-btn {
  padding: 4px 12px;
  font-size: 10px;
  font-family: "FangSong", "FangSong_GB2312", serif;
  background: rgba(184, 155, 104, 0.04);
  border: 1px solid rgba(184, 155, 104, 0.12);
  color: var(--text-dim);
  border-radius: var(--radius-sm);
  cursor: pointer;
  letter-spacing: 1px;
  transition: all var(--duration-fast);
}

.quick-btn:hover {
  background: rgba(184, 155, 104, 0.12);
  color: var(--gold);
  border-color: rgba(184, 155, 104, 0.3);
}

/* 待办指令队列 */
.pending-commands {
  margin: 0 12px 6px;
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.2);
  border-radius: 2px;
}

.pc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  border-bottom: 1px solid rgba(184, 155, 104, 0.15);
}

.pc-title {
  font-size: 11px;
  font-family: "SimSun", serif;
  color: var(--gold);
}

.pc-clear {
  background: none;
  border: 1px solid var(--text-dim);
  color: var(--text-dim);
  padding: 2px 8px;
  font-size: 10px;
  cursor: pointer;
  font-family: "SimSun", serif;
}

.pc-clear:hover {
  color: var(--danger);
  border-color: var(--danger);
}

.pc-list {
  max-height: 120px;
  overflow-y: auto;
}

.pc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 10px;
  font-size: 11px;
  font-family: "SimSun", serif;
  cursor: pointer;
  border-bottom: 1px solid rgba(139, 115, 85, 0.1);
  transition: background 0.15s;
}

.pc-item:hover {
  background: rgba(184, 155, 104, 0.1);
}

.pc-label {
  color: var(--text-main);
  flex: 1;
}

.pc-action {
  color: var(--text-dim);
  font-size: 10px;
  background: rgba(139, 115, 85, 0.15);
  padding: 1px 6px;
  border-radius: 1px;
}

/* ===== 全局推演面板 ===== */
.deduction-panel {
  margin: 0 12px 8px;
  background: linear-gradient(135deg,
    rgba(30, 26, 20, 0.95) 0%,
    rgba(40, 34, 28, 0.93) 50%,
    rgba(30, 26, 20, 0.95) 100%
  );
  border: 1px solid rgba(184, 150, 62, 0.35);
  border-radius: 3px;
  max-height: 360px;
  overflow-y: auto;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4), 0 0 0 1px rgba(184, 150, 62, 0.08);
  animation: dedSlide 0.4s cubic-bezier(0.22, 0.61, 0.36, 1);
}

@keyframes dedSlide {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.deduction-panel::-webkit-scrollbar { width: 4px; }
.deduction-panel::-webkit-scrollbar-track { background: transparent; }
.deduction-panel::-webkit-scrollbar-thumb {
  background: rgba(184, 150, 62, 0.2);
  border-radius: 2px;
}

.ded-header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(184, 150, 62, 0.2);
  background: rgba(184, 150, 62, 0.06);
}

.ded-icon { margin-right: 8px; font-size: 14px; }
.ded-title {
  flex: 1;
  font-size: 13px;
  font-family: "SimSun", serif;
  color: var(--gold);
  letter-spacing: 3px;
  text-shadow: 0 1px 3px rgba(184, 150, 62, 0.3);
}

.ded-close {
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
}
.ded-close:hover { color: var(--danger); }

/* 全局叙事 */
.ded-narrative {
  padding: 10px 14px;
  font-size: 13px;
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
  color: rgba(220, 210, 185, 0.95);
  line-height: 2;
  border-bottom: 1px solid rgba(184, 150, 62, 0.12);
  letter-spacing: 0.5px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.4);
  font-style: italic;
}

/* 区块标签 */
.ded-section-label {
  padding: 8px 12px 4px;
  font-size: 11px;
  font-family: "SimSun", serif;
  color: rgba(184, 150, 62, 0.75);
  letter-spacing: 2px;
}

/* 势力反应卡片 */
.ded-factions {
  padding: 0 12px;
}

.ded-faction-card {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 10px;
  margin-bottom: 6px;
  background: rgba(184, 150, 62, 0.04);
  border-left: 3px solid rgba(184, 150, 62, 0.5);
  border-radius: 0 2px 2px 0;
  transition: background 0.2s;
}
.ded-faction-card:hover {
  background: rgba(184, 150, 62, 0.08);
}

.ded-faction-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ded-faction-name {
  font-size: 13px;
  font-family: "SimSun", serif;
  font-weight: bold;
  letter-spacing: 2px;
}

.ded-faction-stance {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 2px;
  font-family: "SimSun", serif;
  letter-spacing: 1px;
}

.ded-stance-alert { background: rgba(180, 130, 30, 0.2); color: #e0a030; }
.ded-stance-hostile { background: rgba(196, 58, 58, 0.2); color: #d05050; }
.ded-stance-panic { background: rgba(180, 100, 30, 0.2); color: #d08040; }
.ded-stance-friendly { background: rgba(91, 140, 90, 0.2); color: #7aba78; }
.ded-stance-neutral { background: rgba(140, 130, 110, 0.15); color: #a09078; }
.ded-stance-mock { background: rgba(140, 100, 140, 0.2); color: #b080b0; }

.ded-faction-narr {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: "FangSong", "FangSong_GB2312", serif;
  line-height: 1.7;
}

.ded-faction-action {
  font-size: 11px;
  color: rgba(200, 170, 100, 0.8);
  font-family: "SimSun", serif;
  letter-spacing: 1px;
}
.ded-action-icon {
  margin-right: 4px;
  font-size: 10px;
}

/* 外交变动 */
.ded-diplo {
  padding: 0 12px;
}

.ded-diplo-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 8px;
  margin-bottom: 2px;
  font-size: 11px;
  background: rgba(184, 150, 62, 0.03);
  border-radius: 2px;
}

.ded-diplo-parties {
  color: rgba(200, 185, 150, 0.85);
  font-family: "SimSun", serif;
  white-space: nowrap;
}

.ded-diplo-change {
  font-weight: bold;
  min-width: 28px;
  font-family: "SimSun", serif;
}
.ded-positive { color: #6bae68; }
.ded-negative { color: #d05050; }

.ded-diplo-reason {
  color: var(--text-dim);
  font-family: "FangSong", "FangSong_GB2312", serif;
  flex: 1;
}

/* 触发事件 */
.ded-events {
  padding: 0 12px;
}

.ded-event-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 8px;
  margin-bottom: 3px;
  border-radius: 2px;
  background: rgba(184, 150, 62, 0.03);
  transition: background 0.15s;
}
.ded-event-item:hover {
  background: rgba(184, 150, 62, 0.06);
}

.ded-sev-major { border-left: 2px solid #c44b3c; }
.ded-sev-minor { border-left: 2px solid #b8a050; }
.ded-sev-trivial { border-left: 2px solid rgba(140, 130, 110, 0.4); }

.ded-event-sev {
  font-size: 10px;
  flex-shrink: 0;
}
.ded-sev-major .ded-event-sev { color: #c44b3c; }
.ded-sev-minor .ded-event-sev { color: #b8a050; }
.ded-sev-trivial .ded-event-sev { color: rgba(140, 130, 110, 0.5); }

.ded-event-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.ded-event-title {
  font-size: 11px;
  font-family: "SimSun", serif;
  color: var(--text-main);
  letter-spacing: 1px;
}

.ded-event-desc {
  font-size: 10px;
  color: var(--text-dim);
  font-family: "FangSong", "FangSong_GB2312", serif;
  line-height: 1.5;
}

/* 经济涟漪 */
.ded-econ {
  padding: 0 12px;
}

.ded-econ-text {
  font-size: 12px;
  color: rgba(180, 160, 120, 0.8);
  font-family: "FangSong", "FangSong_GB2312", serif;
  padding: 4px 8px;
  line-height: 1.8;
  background: rgba(184, 150, 62, 0.04);
  border-radius: 2px;
  margin: 0 0 4px;
}

/* 谋士献策 */
.ded-advice {
  padding: 0 12px;
}

.ded-advice-text {
  font-size: 12px;
  color: rgba(200, 185, 150, 0.85);
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
  padding: 6px 10px;
  line-height: 1.9;
  background: rgba(184, 155, 104, 0.08);
  border: 1px dashed rgba(184, 155, 104, 0.2);
  border-radius: 2px;
  margin: 0 0 4px;
}

/* 底部摘要 + 推进按钮 */
.ded-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-top: 1px solid rgba(184, 150, 62, 0.18);
  background: rgba(184, 150, 62, 0.04);
}

.ded-footer-text {
  font-size: 11px;
  color: rgba(180, 160, 120, 0.7);
  font-family: "SimSun", serif;
  letter-spacing: 1px;
  flex: 1;
}

.ded-advance-btn {
  padding: 6px 16px;
  font-size: 11px;
  font-family: "SimSun", serif;
  letter-spacing: 2px;
  white-space: nowrap;
  background: linear-gradient(135deg, rgba(184, 150, 62, 0.15), rgba(184, 150, 62, 0.08));
  border: 1px solid rgba(184, 150, 62, 0.3);
  color: var(--gold);
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.ded-advance-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(184, 150, 62, 0.25), rgba(184, 150, 62, 0.15));
  border-color: rgba(184, 150, 62, 0.5);
  color: #e0c060;
}
.ded-advance-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
