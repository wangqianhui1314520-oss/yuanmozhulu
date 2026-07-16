/**
 * 游戏音频桥接器 (Vue3 Composable)
 * 
 * 监听 GamePage 中的游戏状态变化，自动触发对应的场景氛围和事件音效。
 * 
 * 用法：
 *   在 GamePage.vue 的 setup 中调用：
 *   const { syncAmbient } = useGameAudioBridge()
 *   syncAmbient({ showWarPanel, showDiplomacyPanel, ... })
 * 
 * 设计原则：
 *   - 不修改任何现有代码，仅从外部观察 store 状态
 *   - 所有音频操作通过 gameMusic.ts 和 gameSfx.ts 完成
 *   - 与现有 audioManager.ts / uiSfx.ts 完全并行运行
 */

import { watch, ref, type Ref, type WatchStopHandle } from 'vue'
import { setGameAmbient, stopGameAmbient, type SceneType } from './gameMusic'
import {
  sfxTerritoryGain, sfxTerritoryLose,
  sfxBattleVictory, sfxBattleDefeat,
  sfxDiplomacyTreaty, sfxDiplomacyBreak,
  sfxTurnAdvance, sfxTurnSummary,
  sfxRebellion, sfxDisaster,
  sfxEndingVictory, sfxEndingDefeat,
  sfxWarDeclaration, sfxPeaceTreaty,
} from './gameSfx'
import { initGameAudio, setGameAudioMuted, setGameAudioVolume } from './GameAudioCore'

export interface GameAudioBridgeOptions {
  /** 战争面板是否打开 */
  showWarPanel: Ref<boolean>
  /** 外交面板是否打开 */ 
  showDiplomacyPanel: Ref<boolean>
  /** 国策面板是否打开 */
  showPolicyPanel: Ref<boolean>
  /** 结局面板是否显示 */
  showEnding: Ref<boolean>
  /** 结局数据（含胜负判定） */
  endingData: Ref<any>
  /** 是否正在处理回合 */
  isProcessing: Ref<boolean>
  /** 回合数 */
  currentRound: Ref<number>
  /** BGM 是否静音（同步现有静音设置） */
  isBgmMuted?: Ref<boolean>
  /** 游戏音频全局音量 */
  volume?: Ref<number>
}

export interface GameAudioEventHooks {
  /** 领土获得 */
  onTerritoryGain?: () => void
  /** 领土丢失 */
  onTerritoryLose?: () => void
  /** 战斗胜利 */
  onBattleVictory?: () => void
  /** 战斗失败 */
  onBattleDefeat?: () => void
  /** 外交缔约 */
  onDiplomacyTreaty?: () => void
  /** 外交破裂 */
  onDiplomacyBreak?: () => void
  /** 回合推进开始 */
  onTurnAdvance?: () => void
  /** 回合大事揭晓 */
  onTurnSummary?: () => void
  /** 叛军 */
  onRebellion?: () => void
  /** 灾害 */
  onDisaster?: () => void
  /** 宣战 */
  onWarDeclaration?: () => void
  /** 和谈 */
  onPeaceTreaty?: () => void
}

/**
 * 游戏音频桥接器
 * 
 * 传入面板状态 Ref，自动监听并切换场景氛围。
 * 游戏事件音效需要通过 triggerEvent() 或独立调用 SFX 函数触发。
 */
export function useGameAudioBridge(opts: GameAudioBridgeOptions) {
  // 初始化游戏音频（预热 AudioContext）
  initGameAudio()

  const stoppers: WatchStopHandle[] = []
  let _prevRound = opts.currentRound.value

  // 音量同步
  if (opts.volume) {
    setGameAudioVolume(opts.volume.value)
    stoppers.push(watch(opts.volume, (v) => setGameAudioVolume(v)))
  }

  // 静音同步（跟随 BGM 静音设置）
  if (opts.isBgmMuted) {
    setGameAudioMuted(opts.isBgmMuted.value)
    stoppers.push(watch(opts.isBgmMuted, (v) => setGameAudioMuted(v)))
  }

  // ===== 场景氛围自动切换 =====

  function determineScene(): SceneType {
    if (opts.showEnding.value && opts.endingData.value) {
      const ending = opts.endingData.value
      const isVictory = ending.result === 'victory' || ending.type === 'victory' || ending.is_victory
      return isVictory ? 'ending_victory' : 'ending_defeat'
    }
    if (opts.showWarPanel.value) return 'war'
    if (opts.showDiplomacyPanel.value) return 'diplomacy'
    if (opts.showPolicyPanel.value) return 'court'
    return 'map'
  }

  let _currentScene: SceneType = 'map'
  
  // 监听面板状态变化 → 切换氛围
  stoppers.push(watch(
    () => ({
      war: opts.showWarPanel.value,
      diplo: opts.showDiplomacyPanel.value,
      policy: opts.showPolicyPanel.value,
      ending: opts.showEnding.value,
    }),
    () => {
      const scene = determineScene()
      if (scene !== _currentScene) {
        _currentScene = scene
        setGameAmbient(scene)
      }
    },
    { immediate: true }
  ))

  // 回合推进 → 音效
  stoppers.push(watch(opts.isProcessing, (processing) => {
    if (processing) {
      // 回合开始处理 → 氛围切换到地图（退出面板）
      _currentScene = 'map'
      setGameAmbient('map')
    }
  }))

  // 监听回合数变化（round + 1 → 可能刚完成了一回合的事情）
  stoppers.push(watch(opts.currentRound, (newVal, oldVal) => {
    if (newVal > oldVal && oldVal > 0) {
      // 回合推进了，等处理结束后触发大事揭晓
      // （在 detectAndPushEvents 中会调用 triggerEvent）
    }
    _prevRound = newVal
  }))

  // ===== 事件音效触发 =====

  /** 手动触发游戏事件音效 */
  function triggerEvent(event: GameAudioEventHooks): void {
    if (event.onTurnAdvance) sfxTurnAdvance()
    if (event.onTurnSummary) sfxTurnSummary()
    if (event.onTerritoryGain) sfxTerritoryGain()
    if (event.onTerritoryLose) sfxTerritoryLose()
    if (event.onBattleVictory) sfxBattleVictory()
    if (event.onBattleDefeat) sfxBattleDefeat()
    if (event.onDiplomacyTreaty) sfxDiplomacyTreaty()
    if (event.onDiplomacyBreak) sfxDiplomacyBreak()
    if (event.onRebellion) sfxRebellion()
    if (event.onDisaster) sfxDisaster()
    if (event.onWarDeclaration) sfxWarDeclaration()
    if (event.onPeaceTreaty) sfxPeaceTreaty()
  }

  /** 销毁时清理所有 watcher */
  function destroy(): void {
    for (const stop of stoppers) stop()
    stopGameAmbient()
  }

  return {
    /** 手动触发事件音效（在 detectAndPushEvents 回调中调用） */
    triggerEvent,
    /** 销毁桥接器 */
    destroy,
  }
}

export default useGameAudioBridge
