/**
 * 古风 UI 音效合成器 (Web Audio API)
 *
 * 所有 UI 交互音效均由五声音阶合成生成，无需外部音频文件。
 * 分类：
 *   click   - 按钮点击（确认/取消/导航/危险）
 *   panel   - 面板开合
 *   toggle  - 开关切换
 *   tab     - 标签切换
 *   select  - 选择/取消选择
 *   notify  - 通知（成功/失败/信息）
 *   hover   - 悬停
 *   action  - 游戏操作（出征/征兵/营造/课税/细作/开发）
 *   turn    - 回合/圣旨
 *   misc    - 杂项（滚动/输入/弹窗）
 */

// ─── 五声音阶频率（中国风音色基础） ───
const PENTATONIC = {
  C2: 65, D2: 73, E2: 82, G2: 98, A2: 110,
  C3: 131, D3: 147, E3: 165, G3: 196, A3: 220,
  C4: 262, D4: 294, E4: 330, G4: 392, A4: 440,
  C5: 523, D5: 587, E5: 659, G5: 784, A5: 880,
  C6: 1047, D6: 1175, E6: 1319, G6: 1568, A6: 1760,
}

type Note = keyof typeof PENTATONIC

// ─── 内部工具函数 ───

let _ctx: AudioContext | null = null
let _mutedAt: number = 0  // 静音时间戳，用于冷却

function ctx(): AudioContext {
  if (!_ctx) {
    _ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
  }
  if (_ctx.state === 'suspended') _ctx.resume()
  return _ctx
}

function now(): number {
  return ctx().currentTime
}

/** 基础音色发生器 */
function tone(
  freq: number,
  type: OscillatorType,
  startTime: number,
  duration: number,
  volume: number,
  fadeOut: number = 0.02
): void {
  const c = ctx()
  const gain = c.createGain()
  const osc = c.createOscillator()
  osc.type = type
  osc.frequency.setValueAtTime(freq, startTime)
  gain.gain.setValueAtTime(volume, startTime)
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration + fadeOut)
  osc.connect(gain)
  gain.connect(c.destination)
  osc.start(startTime)
  osc.stop(startTime + duration + fadeOut + 0.01)
}

/** 短促打击音（类似木鱼/梆子） */
function perc(
  freq: number,
  startTime: number,
  volume: number = 0.18,
  duration: number = 0.08
): void {
  const c = ctx()
  // 噪声层 — 敲击质感
  const buf = c.createBuffer(1, c.sampleRate * duration, c.sampleRate)
  const data = buf.getChannelData(0)
  for (let i = 0; i < data.length; i++) {
    data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / data.length, 3)
  }
  const noise = c.createBufferSource()
  noise.buffer = buf
  const noiseGain = c.createGain()
  noiseGain.gain.setValueAtTime(volume * 0.5, startTime)
  noiseGain.gain.exponentialRampToValueAtTime(0.001, startTime + duration)
  noise.connect(noiseGain)
  noiseGain.connect(c.destination)
  noise.start(startTime)
  noise.stop(startTime + duration + 0.01)

  // 音调层
  tone(freq, 'sine', startTime, duration * 0.6, volume, 0.005)
}

/** 钟磬余韵音 */
function chime(
  freq: number,
  startTime: number,
  volume: number = 0.15,
  duration: number = 0.25
): void {
  tone(freq, 'sine', startTime, duration * 0.15, volume, duration * 0.8)
  tone(freq * 2, 'sine', startTime + 0.01, duration * 0.1, volume * 0.5, duration * 0.6)
  tone(freq * 3, 'sine', startTime + 0.02, duration * 0.06, volume * 0.25, duration * 0.4)
}

/** 琶音（上行/下行） */
function arpeggio(
  notes: Note[],
  startTime: number,
  gap: number,
  volume: number = 0.12,
  duration: number = 0.12,
  ascending: boolean = true
): void {
  const seq = ascending ? notes : [...notes].reverse()
  seq.forEach((n, i) => {
    chime(PENTATONIC[n], startTime + i * gap, volume, duration)
  })
}

/** 低频嗡鸣（环境/确认） */
function hum(
  freq: number,
  startTime: number,
  volume: number = 0.08,
  duration: number = 0.5
): void {
  const c = ctx()
  const gain = c.createGain()
  const osc = c.createOscillator()
  osc.type = 'triangle'
  osc.frequency.setValueAtTime(freq, startTime)
  osc.frequency.linearRampToValueAtTime(freq * 1.2, startTime + duration * 0.3)
  osc.frequency.linearRampToValueAtTime(freq, startTime + duration)
  gain.gain.setValueAtTime(volume, startTime)
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration)
  osc.connect(gain)
  gain.connect(c.destination)
  osc.start(startTime)
  osc.stop(startTime + duration + 0.01)
}

/** 失谐音（错误/警告） */
function discord(
  freq: number,
  startTime: number,
  volume: number = 0.1,
  duration: number = 0.3
): void {
  tone(freq, 'square', startTime, duration, volume * 0.3, 0.03)
  tone(freq * 0.98, 'square', startTime + 0.02, duration, volume * 0.25, 0.03)
  tone(freq * 0.5, 'sawtooth', startTime + 0.01, duration * 0.6, volume * 0.15, 0.04)
}

/** 风铃散落音 */
function windChime(
  notes: Note[],
  startTime: number,
  volume: number = 0.1
): void {
  notes.forEach((n, i) => {
    const delay = startTime + Math.random() * 0.12 + i * 0.04
    chime(PENTATONIC[n], delay, volume * (0.6 + Math.random() * 0.4), 0.15 + Math.random() * 0.1)
  })
}

// ─── 音效分类定义 ───

export type SfxCategory =
  | 'btn_primary'    // 主要确认按钮
  | 'btn_secondary'  // 次要按钮
  | 'btn_danger'     // 危险操作按钮
  | 'btn_nav'        // 导航按钮
  | 'panel_open'     // 面板打开
  | 'panel_close'    // 面板关闭
  | 'toggle_on'      // 开关开启
  | 'toggle_off'     // 开关关闭
  | 'tab_switch'     // 标签切换
  | 'select'         // 选择
  | 'deselect'       // 取消选择
  | 'notify_success' // 操作成功
  | 'notify_error'   // 操作失败
  | 'notify_info'    // 一般通知
  | 'notify_warning' // 警告通知
  | 'hover'          // 悬停
  | 'action_march'   // 出征
  | 'action_recruit' // 征兵
  | 'action_build'   // 营造
  | 'action_tax'     // 课税
  | 'action_spy'     // 细作
  | 'action_develop' // 开发
  | 'edict_submit'   // 颁布圣旨
  | 'turn_advance'   // 回合推进
  | 'hex_select'     // 地块选中
  | 'hex_deselect'   // 地块取消
  | 'modal_open'     // 弹窗打开
  | 'modal_close'    // 弹窗关闭
  | 'scroll_tick'    // 滚动选项

// ─── 音效实现映射 ───

const _sfxImpl: Record<SfxCategory, () => void> = {} as any

function def(key: SfxCategory, fn: () => void) {
  _sfxImpl[key] = fn
}

// ─ 按钮类 ─
def('btn_primary', () => {
  const t = now()
  perc(PENTATONIC.C4, t, 0.2, 0.06)
  chime(PENTATONIC.C5, t + 0.02, 0.12, 0.2)
  hum(PENTATONIC.C3, t, 0.07, 0.35)
})

def('btn_secondary', () => {
  const t = now()
  perc(PENTATONIC.E4, t, 0.14, 0.05)
  chime(PENTATONIC.E5, t + 0.01, 0.08, 0.15)
})

def('btn_danger', () => {
  const t = now()
  perc(PENTATONIC.G3, t, 0.22, 0.07)
  discord(PENTATONIC.G4, t + 0.01, 0.12, 0.25)
})

def('btn_nav', () => {
  const t = now()
  perc(PENTATONIC.A4, t, 0.15, 0.05)
  chime(PENTATONIC.A5, t + 0.02, 0.09, 0.18)
})

// ─ 面板类 ─
def('panel_open', () => {
  const t = now()
  arpeggio(['G3', 'C4', 'E4', 'G4', 'C5'], t, 0.04, 0.1, 0.1, true)
  hum(PENTATONIC.G3, t, 0.06, 0.6)
})

def('panel_close', () => {
  const t = now()
  arpeggio(['C5', 'G4', 'E4', 'C4', 'G3'], t, 0.04, 0.08, 0.08, false)
})

// ─ 开关类 ─
def('toggle_on', () => {
  const t = now()
  perc(PENTATONIC.E4, t, 0.12, 0.04)
  chime(PENTATONIC.G5, t + 0.02, 0.1, 0.15)
})

def('toggle_off', () => {
  const t = now()
  perc(PENTATONIC.A3, t, 0.1, 0.04)
  tone(PENTATONIC.E4, 'sine', t + 0.01, 0.06, 0.06, 0.03)
})

// ─ 标签切换 ─
def('tab_switch', () => {
  const t = now()
  perc(PENTATONIC.D4, t, 0.1, 0.04)
  chime(PENTATONIC.D5, t + 0.015, 0.07, 0.1)
})

// ─ 选择类 ─
def('select', () => {
  const t = now()
  perc(PENTATONIC.E4, t, 0.11, 0.04)
  chime(PENTATONIC.G5, t + 0.015, 0.1, 0.12)
})

def('deselect', () => {
  const t = now()
  perc(PENTATONIC.A3, t, 0.08, 0.04)
  tone(PENTATONIC.D4, 'sine', t + 0.01, 0.05, 0.05, 0.02)
})

// ─ 通知类 ─
def('notify_success', () => {
  const t = now()
  arpeggio(['C4', 'E4', 'G4', 'C5'], t, 0.06, 0.1, 0.12, true)
  hum(PENTATONIC.C3, t, 0.05, 0.5)
})

def('notify_error', () => {
  const t = now()
  discord(PENTATONIC.D4, t, 0.12, 0.4)
  perc(PENTATONIC.D3, t, 0.18, 0.06)
})

def('notify_info', () => {
  const t = now()
  windChime(['D5', 'E5', 'G5'], t, 0.08)
})

def('notify_warning', () => {
  const t = now()
  perc(PENTATONIC.D4, t, 0.16, 0.05)
  tone(PENTATONIC.D5, 'triangle', t + 0.01, 0.15, 0.08, 0.06)
  tone(PENTATONIC.A4, 'triangle', t + 0.02, 0.15, 0.06, 0.06)
})

// ─ 悬停 ─
def('hover', () => {
  const t = now()
  tone(PENTATONIC.D6, 'sine', t, 0.02, 0.03, 0.01)
})

// ─ 游戏操作类 ─
def('action_march', () => {
  const t = now()
  // 鼓点 + 号角上行
  perc(PENTATONIC.G3, t, 0.25, 0.08)
  perc(PENTATONIC.G3, t + 0.12, 0.22, 0.08)
  arpeggio(['G3', 'C4', 'E4', 'G4', 'C5'], t + 0.05, 0.05, 0.1, 0.1, true)
  hum(PENTATONIC.C3, t, 0.09, 0.6)
})

def('action_recruit', () => {
  const t = now()
  // 集合号令
  perc(PENTATONIC.E4, t, 0.22, 0.06)
  perc(PENTATONIC.E4, t + 0.1, 0.18, 0.06)
  arpeggio(['E4', 'G4', 'C5'], t + 0.04, 0.06, 0.08, 0.1, true)
  hum(PENTATONIC.E3, t, 0.07, 0.5)
})

def('action_build', () => {
  const t = now()
  // 夯土筑城 — 沉稳敲击
  perc(PENTATONIC.C4, t, 0.2, 0.07)
  perc(PENTATONIC.C4, t + 0.15, 0.16, 0.07)
  chime(PENTATONIC.C5, t + 0.08, 0.1, 0.2)
  hum(PENTATONIC.C3, t, 0.06, 0.55)
})

def('action_tax', () => {
  const t = now()
  // 金属质感/钱币
  tone(PENTATONIC.E5, 'triangle', t, 0.04, 0.08, 0.02)
  tone(PENTATONIC.G5, 'triangle', t + 0.06, 0.04, 0.07, 0.02)
  tone(PENTATONIC.C6, 'triangle', t + 0.12, 0.04, 0.06, 0.02)
  perc(PENTATONIC.E4, t, 0.1, 0.04)
})

def('action_spy', () => {
  const t = now()
  // 诡谲低沉
  tone(PENTATONIC.D3, 'sawtooth', t, 0.3, 0.04, 0.1)
  tone(PENTATONIC.A3, 'sine', t + 0.08, 0.2, 0.05, 0.1)
  tone(PENTATONIC.E4, 'triangle', t + 0.15, 0.12, 0.04, 0.08)
  perc(PENTATONIC.D3, t, 0.12, 0.05)
})

def('action_develop', () => {
  const t = now()
  // 生机盎然 — 轻快风铃
  windChime(['E5', 'G5', 'A5', 'C6'], t, 0.08)
  hum(PENTATONIC.E3, t, 0.04, 0.4)
})

// ─ 回合/圣旨 ─
def('edict_submit', () => {
  const t = now()
  // 洪钟大吕
  perc(PENTATONIC.C3, t, 0.3, 0.1)
  hum(PENTATONIC.C3, t + 0.02, 0.1, 0.8)
  chime(PENTATONIC.C4, t + 0.06, 0.15, 0.35)
  chime(PENTATONIC.G4, t + 0.1, 0.12, 0.3)
  chime(PENTATONIC.C5, t + 0.14, 0.1, 0.5)
})

def('turn_advance', () => {
  const t = now()
  // 战鼓推进
  perc(PENTATONIC.G3, t, 0.28, 0.09)
  perc(PENTATONIC.G3, t + 0.14, 0.24, 0.08)
  perc(PENTATONIC.C4, t + 0.28, 0.2, 0.08)
  hum(PENTATONIC.G2, t, 0.1, 0.7)
})

// ─ 六边形地块 ─
def('hex_select', () => {
  const t = now()
  perc(PENTATONIC.E4, t, 0.13, 0.05)
  chime(PENTATONIC.E5, t + 0.015, 0.1, 0.18)
  chime(PENTATONIC.G5, t + 0.03, 0.06, 0.12)
})

def('hex_deselect', () => {
  const t = now()
  perc(PENTATONIC.A3, t, 0.08, 0.04)
  tone(PENTATONIC.D4, 'sine', t + 0.01, 0.06, 0.04, 0.02)
})

// ─ 弹窗 ─
def('modal_open', () => {
  const t = now()
  arpeggio(['A3', 'C4', 'E4', 'A4'], t, 0.05, 0.08, 0.1, true)
  hum(PENTATONIC.A3, t, 0.04, 0.4)
})

def('modal_close', () => {
  const t = now()
  arpeggio(['A4', 'E4', 'C4', 'A3'], t, 0.04, 0.06, 0.07, false)
})

// ─ 滚动 ─
def('scroll_tick', () => {
  const t = now()
  tone(PENTATONIC.E5, 'sine', t, 0.01, 0.03, 0.005)
})

// ─── 公开 API ───

export type UiSfxOptions = {
  /** 全局音量缩放 (0-1) */
  masterVolume?: number
  /** 是否静音 */
  muted?: boolean
  /** 悬停音效冷却时间 (ms) */
  hoverCooldown?: number
}

const defaults: Required<UiSfxOptions> = {
  masterVolume: 0.7,
  muted: false,
  hoverCooldown: 80,
}

let _opts: Required<UiSfxOptions> = { ...defaults }
let _lastHover = 0

/** 更新全局 UI 音效配置 */
export function setUiSfxOptions(opts: UiSfxOptions) {
  Object.assign(_opts, opts)
}

/** 播放指定分类的 UI 音效 */
export function playUiSfx(category: SfxCategory) {
  if (_opts.muted) return

  // 悬停冷却
  if (category === 'hover') {
    const elapsed = performance.now() - _lastHover
    if (elapsed < _opts.hoverCooldown) return
    _lastHover = performance.now()
  }

  const fn = _sfxImpl[category]
  if (fn) {
    // 临时调整 AudioContext 全局音量
    const c = ctx()
    const origGain = (c as any)._uiSfxGlobalGain
    if (_opts.masterVolume !== 1.0) {
      // 使用主节点控制音量 — 短暂调整 gain
      if (!(c as any)._uiSfxGlobalGainNode) {
        // 不需要全局 gain 节点，每个音效各自控制 volume
      }
    }
    fn()
  }
}

/** 初始化 UI 音效（预初始化 AudioContext，避免首次播放延迟） */
export function initUiSfx() {
  ctx()  // 确保 AudioContext 已创建
  // 预热 — 静默播放一下让浏览器激活音频
  const t = now()
  tone(1000, 'sine', t, 0.001, 0.0, 0)
}

/** 销毁 UI 音效 */
export function destroyUiSfx() {
  if (_ctx) {
    _ctx.close().catch(() => {})
    _ctx = null
  }
}

/** 获取当前 AudioContext 状态 */
export function getAudioContextState(): string {
  return _ctx?.state || 'uninitialized'
}

// ─── 便捷方法 ───

/** 创建可按需调用的音效快捷方法 */
export const uiClick = {
  primary: () => playUiSfx('btn_primary'),
  secondary: () => playUiSfx('btn_secondary'),
  danger: () => playUiSfx('btn_danger'),
  nav: () => playUiSfx('btn_nav'),
  toggle: (on: boolean) => playUiSfx(on ? 'toggle_on' : 'toggle_off'),
}

export const uiPanel = {
  open: () => playUiSfx('panel_open'),
  close: () => playUiSfx('panel_close'),
}

export const uiNotify = {
  success: () => playUiSfx('notify_success'),
  error: () => playUiSfx('notify_error'),
  info: () => playUiSfx('notify_info'),
  warning: () => playUiSfx('notify_warning'),
}

export const uiAction = {
  march: () => playUiSfx('action_march'),
  recruit: () => playUiSfx('action_recruit'),
  build: () => playUiSfx('action_build'),
  tax: () => playUiSfx('action_tax'),
  spy: () => playUiSfx('action_spy'),
  develop: () => playUiSfx('action_develop'),
}

export const uiHex = {
  select: () => playUiSfx('hex_select'),
  deselect: () => playUiSfx('hex_deselect'),
}

export const uiTurn = {
  edict: () => playUiSfx('edict_submit'),
  advance: () => playUiSfx('turn_advance'),
}
