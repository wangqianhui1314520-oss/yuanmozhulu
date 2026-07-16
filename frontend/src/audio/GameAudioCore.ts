/**
 * 游戏事件音频核心 (Web Audio API)
 * 
 * 与现有 audioManager.ts（HTML5 BGM/配音）和 uiSfx.ts（UI交互音效）完全独立，
 * 使用独立的 AudioContext 和 master gain 节点，互不干扰。
 * 
 * 用途：
 * - 游戏场景氛围层（战争、外交、朝堂等）
 * - 游戏事件音效（战斗结果、领土变更、回合推进等）
 */

let _ctx: AudioContext | null = null
let _masterGain: GainNode | null = null
let _isMuted = false
let _masterVolume = 0.45  // 游戏事件音效比 UI 音效稍低，避免干扰

/** 获取共享的 AudioContext */
export function getGameAudioContext(): AudioContext {
  if (!_ctx) {
    _ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    _masterGain = _ctx.createGain()
    _masterGain.gain.value = _masterVolume
    _masterGain.connect(_ctx.destination)
  }
  if (_ctx.state === 'suspended') {
    _ctx.resume().catch(() => {})
  }
  return _ctx
}

/** 获取 master gain 节点（所有音频都应连接到此处输出） */
export function getMasterGain(): GainNode {
  getGameAudioContext() // ensure context exists
  return _masterGain!
}

/** 当前 AudioContext 时间 */
export function audioNow(): number {
  return getGameAudioContext().currentTime
}

/** 设置主音量 (0-1) */
export function setGameAudioVolume(v: number): void {
  _masterVolume = Math.max(0, Math.min(1, v))
  if (_masterGain) {
    _masterGain.gain.setValueAtTime(_masterVolume, audioNow())
  }
}

/** 获取主音量 */
export function getGameAudioVolume(): number {
  return _masterVolume
}

/** 静音/取消静音 */
export function setGameAudioMuted(muted: boolean): void {
  _isMuted = muted
  if (_masterGain) {
    const target = muted ? 0 : _masterVolume
    _masterGain.gain.setValueAtTime(target, audioNow())
  }
}

export function isGameAudioMuted(): boolean {
  return _isMuted
}

/** 初始化游戏音频（预热 AudioContext） */
export function initGameAudio(): void {
  const c = getGameAudioContext()
  // 静默预热
  if (c.state !== 'running') {
    const resume = () => {
      c.resume().catch(() => {})
    }
    document.addEventListener('click', resume, { once: true })
    document.addEventListener('keydown', resume, { once: true })
    document.addEventListener('touchstart', resume, { once: true })
  }
  // 额外静默脉冲，让浏览器确认音频可用
  try {
    const osc = c.createOscillator()
    const g = c.createGain()
    g.gain.value = 0
    osc.connect(g)
    g.connect(c.destination)
    osc.start(c.currentTime)
    osc.stop(c.currentTime + 0.001)
  } catch {}
}

/** 销毁游戏音频 */
export function destroyGameAudio(): void {
  if (_ctx) {
    _ctx.close().catch(() => {})
    _ctx = null
    _masterGain = null
  }
}
