/**
 * 游戏场景氛围音乐（Web Audio 步进音序器 + 持续音垫）
 * 
 * 每个场景提供极淡的氛围层，作为主 BGM 的情绪基底补充。
 * 所有音乐均为程序化合成，无需外部音频文件。
 * 与 uiSfx.ts 共享 AudioContext（通过 GameAudioCore 统一管理）。
 */

import { getGameAudioContext, getMasterGain, audioNow } from './GameAudioCore'

// ===== 五声音阶频率 =====
const P = {
  C2: 65, D2: 73, E2: 82, G2: 98, A2: 110,
  C3: 131, D3: 147, E3: 165, G3: 196, A3: 220,
  C4: 262, D4: 294, E4: 330, G4: 392, A4: 440,
  C5: 523, D5: 587, E5: 659, G5: 784, A5: 880,
  C6: 1047,
}

export type SceneType = 'map' | 'war' | 'diplomacy' | 'court' | 'ending_victory' | 'ending_defeat'

interface AmbientNode {
  nodes: AudioScheduledSourceNode[]
  intervals: number[]
}

let _currentScene: SceneType | null = null
let _currentNodes: AmbientNode | null = null

// ===== 基础音色构建函数 =====

/** 创建持续低音垫 */
function createDrone(
  ctx: AudioContext, dest: AudioNode,
  freq: number, startTime: number, volume: number
): { osc: OscillatorNode; gain: GainNode } {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'triangle'
  osc.frequency.setValueAtTime(freq, startTime)
  // 微颤效果
  osc.frequency.setValueAtTime(freq * 0.997, startTime + 0.8)
  osc.frequency.linearRampToValueAtTime(freq * 1.003, startTime + 2.0)
  osc.frequency.linearRampToValueAtTime(freq, startTime + 3.5)
  gain.gain.setValueAtTime(0, startTime)
  gain.gain.linearRampToValueAtTime(volume, startTime + 2.5)
  osc.connect(gain)
  gain.connect(dest)
  osc.start(startTime)
  return { osc, gain }
}

/** 创建钟磬泛音（有自然衰减） */
function createChime(
  ctx: AudioContext, dest: AudioNode,
  freq: number, startTime: number, volume: number, decay: number = 3.0
): OscillatorNode {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'sine'
  osc.frequency.setValueAtTime(freq, startTime)
  gain.gain.setValueAtTime(volume, startTime)
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + decay)
  osc.connect(gain)
  gain.connect(dest)
  osc.start(startTime)
  osc.stop(startTime + decay + 0.05)
  return osc
}

/** 钟磬和弦（多频率同时触发） */
function createBellChord(
  ctx: AudioContext, dest: AudioNode,
  freqs: number[], startTime: number, volume: number
): OscillatorNode[] {
  return freqs.map((freq, i) =>
    createChime(ctx, dest, freq, startTime + i * 0.12, volume * (0.7 - i * 0.1), 3.5)
  )
}

/** 打击音（鼓/钟的瞬态） */
function createPerc(
  ctx: AudioContext, dest: AudioNode,
  freq: number, startTime: number, volume: number, duration: number = 0.2
): OscillatorNode {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'sine'
  osc.frequency.setValueAtTime(freq, startTime)
  osc.frequency.exponentialRampToValueAtTime(freq * 0.3, startTime + duration)
  gain.gain.setValueAtTime(volume, startTime)
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration + 0.01)
  osc.connect(gain)
  gain.connect(dest)
  osc.start(startTime)
  osc.stop(startTime + duration + 0.02)
  return osc
}

/** 噪声冲击（鼓噪质感） */
function createNoiseHit(
  ctx: AudioContext, dest: AudioNode,
  startTime: number, volume: number, duration: number = 0.1
): AudioBufferSourceNode {
  const buf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * duration), ctx.sampleRate)
  const data = buf.getChannelData(0)
  for (let i = 0; i < data.length; i++) {
    data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / data.length, 3)
  }
  const src = ctx.createBufferSource()
  src.buffer = buf
  const g = ctx.createGain()
  g.gain.setValueAtTime(volume, startTime)
  g.gain.exponentialRampToValueAtTime(0.001, startTime + duration)
  src.connect(g)
  g.connect(dest)
  src.start(startTime)
  src.stop(startTime + duration + 0.01)
  return src
}

// ===== 场景氛围实现 =====

/** 舆图主界面 — 极淡古琴垫底 + 远山钟声 */
function createMapAmbient(ctx: AudioContext): AmbientNode {
  const dest = getMasterGain()
  const t = audioNow()
  const nodes: AudioScheduledSourceNode[] = []
  const intervals: number[] = []

  // 极淡五度音程垫底（C2 + G2）
  const d1 = createDrone(ctx, dest, P.C2, t, 0.04)
  nodes.push(d1.osc)
  const d2 = createDrone(ctx, dest, P.G2, t + 0.3, 0.03)
  nodes.push(d2.osc)

  // 初响钟磬
  createBellChord(ctx, dest, [P.C4, P.E4, P.G4], t, 0.025).forEach(n => nodes.push(n))

  // 每 8 秒远山钟声
  const timer = window.setInterval(() => {
    if (ctx.state === 'closed') return
    createBellChord(ctx, dest, [P.G3, P.C4, P.E4, P.G4], audioNow(), 0.02).forEach(n => nodes.push(n))
  }, 8000)
  intervals.push(timer)

  return { nodes, intervals }
}

/** 战争面板 — 战鼓低沉 + 铜号泛音 */
function createWarAmbient(ctx: AudioContext): AmbientNode {
  const dest = getMasterGain()
  const t = audioNow()
  const nodes: AudioScheduledSourceNode[] = []
  const intervals: number[] = []

  // 低沉嗡鸣
  const d1 = createDrone(ctx, dest, P.C2, t, 0.055)
  nodes.push(d1.osc)
  const d2 = createDrone(ctx, dest, P.G2, t + 0.3, 0.045)
  nodes.push(d2.osc)

  // 铜号泛音
  createBellChord(ctx, dest, [P.C3, P.G3, P.C4], t, 0.03).forEach(n => nodes.push(n))

  // 战鼓节奏 4/4
  const beat = 0.55
  const timer = window.setInterval(() => {
    if (ctx.state === 'closed') return
    const bt = audioNow()
    // 第一拍（强）
    createNoiseHit(ctx, dest, bt, 0.08, 0.1)
    createPerc(ctx, dest, 85, bt, 0.07, 0.22)
    // 第三拍（次强）
    createNoiseHit(ctx, dest, bt + beat * 2, 0.06, 0.08)
    createPerc(ctx, dest, 75, bt + beat * 2, 0.05, 0.18)
  }, Math.round(beat * 4 * 1000))
  intervals.push(timer)

  return { nodes, intervals }
}

/** 外交面板 — 雅乐钟磬悠远 */
function createDiplomacyAmbient(ctx: AudioContext): AmbientNode {
  const dest = getMasterGain()
  const t = audioNow()
  const nodes: AudioScheduledSourceNode[] = []
  const intervals: number[] = []

  // 淡然无争的低音
  const d1 = createDrone(ctx, dest, P.D2, t, 0.03)
  nodes.push(d1.osc)
  const d2 = createDrone(ctx, dest, P.A2, t + 0.3, 0.025)
  nodes.push(d2.osc)

  // 雅乐泛音
  createBellChord(ctx, dest, [P.D4, P.A4, P.D5], t, 0.028).forEach(n => nodes.push(n))

  // 每 5 秒轻敲
  const timer = window.setInterval(() => {
    if (ctx.state === 'closed') return
    createBellChord(ctx, dest, [P.A4, P.D5, P.A5], audioNow(), 0.018).forEach(n => nodes.push(n))
  }, 5000)
  intervals.push(timer)

  return { nodes, intervals }
}

/** 朝堂/国策 — 庄重低音 */
function createCourtAmbient(ctx: AudioContext): AmbientNode {
  const dest = getMasterGain()
  const t = audioNow()
  const nodes: AudioScheduledSourceNode[] = []

  const d1 = createDrone(ctx, dest, P.G2, t, 0.04)
  nodes.push(d1.osc)
  const d2 = createDrone(ctx, dest, P.C3, t + 0.5, 0.035)
  nodes.push(d2.osc)

  createBellChord(ctx, dest, [P.C3, P.G3, P.C4, P.E4], t, 0.03).forEach(n => nodes.push(n))

  return { nodes, intervals: [] }
}

/** 胜利结局 — 辉煌钟磬 */
function createEndingVictoryAmbient(ctx: AudioContext): AmbientNode {
  const dest = getMasterGain()
  const t = audioNow()
  const nodes: AudioScheduledSourceNode[] = []

  const d1 = createDrone(ctx, dest, P.C2, t, 0.06)
  nodes.push(d1.osc)
  const d2 = createDrone(ctx, dest, P.C3, t + 0.3, 0.05)
  nodes.push(d2.osc)

  createBellChord(ctx, dest, [P.C3, P.E3, P.G3, P.C4, P.E4, P.G4, P.C5], t, 0.05).forEach(n => nodes.push(n))

  // 4 秒后再次泛音
  setTimeout(() => {
    if (ctx.state === 'closed') return
    createBellChord(ctx, dest, [P.C4, P.E4, P.G4, P.C5, P.E5], audioNow(), 0.04).forEach(n => nodes.push(n))
  }, 4000)

  return { nodes, intervals: [] }
}

/** 失败结局 — 沉郁低吟 */
function createEndingDefeatAmbient(ctx: AudioContext): AmbientNode {
  const dest = getMasterGain()
  const t = audioNow()
  const nodes: AudioScheduledSourceNode[] = []

  const d1 = createDrone(ctx, dest, P.D2, t, 0.045)
  nodes.push(d1.osc)
  const d2 = createDrone(ctx, dest, P.A2, t + 0.5, 0.035)
  nodes.push(d2.osc)

  // 微失谐泛音
  const osc = ctx.createOscillator()
  const g = ctx.createGain()
  osc.type = 'sine'
  osc.frequency.setValueAtTime(P.D4 * 0.995, t + 0.4)
  g.gain.setValueAtTime(0, t + 0.4)
  g.gain.linearRampToValueAtTime(0.025, t + 2.0)
  osc.connect(g)
  g.connect(dest)
  osc.start(t + 0.4)
  nodes.push(osc)

  return { nodes, intervals: [] }
}

// ===== 公共 API =====

/** 淡出并停止当前所有节点 */
function fadeOutAndStop(nodes: AudioScheduledSourceNode[], duration: number = 1.5): void {
  // 对 OscillatorNode 设置频率端的淡出只能通过 GainNode 完成，
  // 这里直接 stop 即可，因为 droneNote 已在创建时连接了 GainNode
  const stopTime = audioNow() + duration + 0.05
  for (const n of nodes) {
    try { n.stop(stopTime) } catch {}
  }
}

/** 切换到指定场景氛围 */
export function setGameAmbient(scene: SceneType): void {
  if (scene === _currentScene) return
  _currentScene = scene

  // 停止当前氛围
  if (_currentNodes) {
    fadeOutAndStop(_currentNodes.nodes, 1.5)
    for (const id of _currentNodes.intervals) {
      clearInterval(id)
    }
    _currentNodes = null
  }

  const ctx = getGameAudioContext()

  switch (scene) {
    case 'map':
      _currentNodes = createMapAmbient(ctx)
      break
    case 'war':
      _currentNodes = createWarAmbient(ctx)
      break
    case 'diplomacy':
      _currentNodes = createDiplomacyAmbient(ctx)
      break
    case 'court':
      _currentNodes = createCourtAmbient(ctx)
      break
    case 'ending_victory':
      _currentNodes = createEndingVictoryAmbient(ctx)
      break
    case 'ending_defeat':
      _currentNodes = createEndingDefeatAmbient(ctx)
      break
  }
}

/** 停止当前场景氛围 */
export function stopGameAmbient(): void {
  if (_currentNodes) {
    fadeOutAndStop(_currentNodes.nodes, 1.5)
    for (const id of _currentNodes.intervals) {
      clearInterval(id)
    }
    _currentNodes = null
  }
  _currentScene = null
}
