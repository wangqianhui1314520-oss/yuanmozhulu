/**
 * 游戏事件音效（Web Audio 程序化合成）
 * 
 * 覆盖游戏逻辑事件（非 UI 交互）：
 * - 战斗结果、领土变更、外交缔约、回合推进
 * - 叛军出现、灾害降临、结局触发
 * 
 * 所有音效均为一次性播放（one-shot），不影响现有 uiSfx.ts 和 BGM 系统。
 */

import { getGameAudioContext, getMasterGain, audioNow } from './GameAudioCore'

// ===== 内部工具 =====

function tone(
  freq: number, type: OscillatorType,
  startTime: number, duration: number, volume: number,
  dest: AudioNode, fadeOut: number = 0.03
): OscillatorNode {
  const ctx = getGameAudioContext()
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, startTime)
  gain.gain.setValueAtTime(volume, startTime)
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration + fadeOut)
  osc.connect(gain)
  gain.connect(dest)
  osc.start(startTime)
  osc.stop(startTime + duration + fadeOut + 0.01)
  return osc
}

function noiseHit(
  startTime: number, duration: number, volume: number, dest: AudioNode
): AudioBufferSourceNode {
  const ctx = getGameAudioContext()
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

function chime(
  freq: number, startTime: number, volume: number, dest: AudioNode,
  decay: number = 0.3
): void {
  tone(freq, 'sine', startTime, 0.06, volume, dest, decay)
  tone(freq * 2, 'sine', startTime + 0.01, 0.05, volume * 0.5, dest, decay * 0.7)
  tone(freq * 3, 'sine', startTime + 0.02, 0.03, volume * 0.25, dest, decay * 0.4)
}

function arpeggio(
  freqs: number[], startTime: number, gap: number,
  volume: number, dest: AudioNode, duration: number = 0.12
): void {
  freqs.forEach((f, i) => {
    chime(f, startTime + i * gap, volume, dest, duration)
  })
}

// ===== 打击/锣声 =====

function gongHit(
  freq: number, startTime: number, volume: number, dest: AudioNode
): void {
  const ctx = getGameAudioContext()
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'triangle'
  osc.frequency.setValueAtTime(freq, startTime)
  osc.frequency.exponentialRampToValueAtTime(freq * 0.6, startTime + 0.3)
  gain.gain.setValueAtTime(volume, startTime)
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + 1.5)
  osc.connect(gain)
  gain.connect(dest)
  osc.start(startTime)
  osc.stop(startTime + 1.6)
  // 噪声层
  noiseHit(startTime, 0.12, volume * 0.8, dest)
}

// ===== 失谐音（用于负面事件） =====

function discord(
  freqs: number[], startTime: number, volume: number, dest: AudioNode, duration: number = 0.35
): void {
  freqs.forEach((f, i) => {
    tone(f, 'sawtooth', startTime + i * 0.02, duration, volume * (0.7 - i * 0.15), dest, 0.05)
  })
}

// ===== 公开 SFX API =====

const P = { C2: 65, D2: 73, E2: 82, G2: 98, A2: 110, C3: 131, D3: 147, E3: 165, F3: 175, G3: 196, A3: 220, C4: 262, D4: 294, E4: 330, F4: 349, G4: 392, A4: 440, C5: 523, D5: 587, E5: 659, G5: 784, A5: 880, C6: 1047, D6: 1175 }

/** 疆土获得 — 凯旋号角 */
export function sfxTerritoryGain(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 鼓点起步
  noiseHit(t, 0.1, 0.12, dest)
  noiseHit(t + 0.15, 0.08, 0.1, dest)
  // 上行号角
  arpeggio([P.G3, P.C4, P.E4, P.G4, P.C5], t + 0.05, 0.08, 0.1, dest, 0.18)
  // 洪钟一响
  gongHit(P.C3, t + 0.3, 0.12, dest)
}

/** 疆土丢失 — 悲怆 */
export function sfxTerritoryLose(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 下行低音
  arpeggio([P.C5, P.G4, P.E4, P.C4, P.G3], t, 0.08, 0.06, dest, 0.1)
  // 低沉共鸣
  tone(P.G2, 'triangle', t + 0.1, 0.8, 0.05, dest, 0.5)
  // 微失谐
  discord([P.E4, P.D4], t + 0.2, 0.06, dest, 0.4)
}

/** 战斗大捷 — 擂鼓金鸣 */
export function sfxBattleVictory(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 战鼓三通
  noiseHit(t, 0.12, 0.15, dest)
  tone(P.C3, 'sine', t, 0.25, 0.1, dest, 0.02)
  noiseHit(t + 0.2, 0.1, 0.12, dest)
  tone(P.C3, 'sine', t + 0.2, 0.2, 0.08, dest, 0.02)
  noiseHit(t + 0.4, 0.08, 0.1, dest)
  // 金鸣号角
  arpeggio([P.C4, P.E4, P.G4, P.C5, P.E5], t + 0.25, 0.06, 0.1, dest, 0.15)
  // 洪钟
  gongHit(P.C3, t + 0.55, 0.15, dest)
}

/** 战斗兵败 — 沉郁 */
export function sfxBattleDefeat(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 沉闷鼓声渐弱
  tone(P.G2, 'sine', t, 0.18, 0.08, dest, 0.5)
  noiseHit(t, 0.08, 0.08, dest)
  noiseHit(t + 0.3, 0.06, 0.05, dest)
  // 下行失谐
  discord([P.E4, P.D4, P.A3], t + 0.1, 0.08, dest, 0.5)
  // 低频嗡鸣
  tone(P.D2, 'triangle', t + 0.2, 1.0, 0.04, dest, 0.6)
}

/** 外交缔约 — 钟磬盟誓 */
export function sfxDiplomacyTreaty(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 三声钟磬
  chime(P.D4, t, 0.08, dest, 0.4)
  chime(P.A4, t + 0.12, 0.07, dest, 0.35)
  chime(P.D5, t + 0.24, 0.06, dest, 0.5)
  // 共鸣
  tone(P.D3, 'triangle', t + 0.05, 1.5, 0.04, dest, 1.0)
}

/** 外交破裂 — 断弦 */
export function sfxDiplomacyBreak(): void {
  const dest = getMasterGain()
  const t = audioNow()
  discord([P.D5, P.A4, P.D4], t, 0.1, dest, 0.5)
  tone(P.D3, 'sawtooth', t + 0.05, 0.3, 0.04, dest, 0.2)
  noiseHit(t + 0.05, 0.04, 0.06, dest)
}

/** 回合推进开始 — 鼓动乾坤 */
export function sfxTurnAdvance(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 三通战鼓
  noiseHit(t, 0.1, 0.14, dest)
  tone(P.G2, 'sine', t, 0.2, 0.09, dest, 0.02)
  noiseHit(t + 0.2, 0.09, 0.11, dest)
  tone(P.G2, 'sine', t + 0.2, 0.18, 0.07, dest, 0.02)
  noiseHit(t + 0.4, 0.08, 0.09, dest)
  // 上行唤起
  arpeggio([P.G3, P.C4, P.E4, P.G4], t + 0.15, 0.07, 0.08, dest, 0.12)
  // 锣声
  gongHit(P.C3, t + 0.5, 0.1, dest)
}

/** 回合大事揭晓 — 卷轴展开 */
export function sfxTurnSummary(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 风铃散落
  const notes = [P.E5, P.G5, P.A5, P.C6, P.D6]
  for (let i = 0; i < notes.length; i++) {
    setTimeout(() => {
      chime(notes[i], audioNow(), 0.04, dest, 0.2)
    }, i * 70 + Math.random() * 40)
  }
  // 低沉共鸣
  tone(P.E3, 'triangle', t, 1.5, 0.04, dest, 1.0)
}

/** 叛军出现 — 警讯 */
export function sfxRebellion(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 急促鼓点
  for (let i = 0; i < 5; i++) {
    noiseHit(t + i * 0.1, 0.04, 0.08 - i * 0.01, dest)
  }
  // 失谐警告
  discord([P.D4, P.A3], t + 0.1, 0.09, dest, 0.4)
  tone(P.D3, 'triangle', t + 0.2, 0.6, 0.05, dest, 0.4)
}

/** 灾害降临 — 不祥之兆 */
export function sfxDisaster(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 低沉嗡鸣渐起
  tone(P.D2, 'triangle', t, 1.2, 0.06, dest, 0.8)
  // 风声
  const ctx = getGameAudioContext()
  for (let i = 0; i < 3; i++) {
    setTimeout(() => {
      const osc = ctx.createOscillator()
      const g = ctx.createGain()
      osc.type = 'sawtooth'
      const f = 300 + Math.random() * 200
      osc.frequency.setValueAtTime(f, audioNow())
      g.gain.setValueAtTime(0.02, audioNow())
      g.gain.exponentialRampToValueAtTime(0.001, audioNow() + 0.4)
      osc.connect(g)
      g.connect(dest)
      osc.start()
      osc.stop(audioNow() + 0.5)
    }, i * 150)
  }
  // 失谐
  discord([P.A3, P.D4, P.A4], t + 0.3, 0.08, dest, 0.6)
}

/** 结局胜利 */
export function sfxEndingVictory(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 洪钟大吕
  gongHit(P.C3, t, 0.18, dest)
  setTimeout(() => gongHit(P.C3, audioNow(), 0.12, dest), 800)
  // 辉煌泛音
  arpeggio([P.C4, P.E4, P.G4, P.C5, P.E5, P.G5], t + 0.2, 0.1, 0.1, dest, 0.2)
  setTimeout(() => {
    arpeggio([P.C5, P.E5, P.G5, P.C6], audioNow(), 0.08, 0.08, getMasterGain(), 0.18)
  }, 1500)
  // 长鸣低音
  tone(P.C2, 'triangle', t + 0.1, 3.0, 0.05, dest, 2.5)
}

/** 结局失败 */
export function sfxEndingDefeat(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 沉钟
  gongHit(P.D3, t, 0.1, dest)
  // 缓慢下行
  arpeggio([P.D5, P.A4, P.F4, P.D4, P.A3], t + 0.3, 0.15, 0.06, dest, 0.2)
  // 低频沉鸣
  tone(P.D2, 'triangle', t + 0.1, 3.0, 0.05, dest, 2.5)
  // 微失谐
  setTimeout(() => {
    discord([P.D4, P.A3], audioNow(), 0.05, dest, 0.6)
  }, 2000)
}

/** 宣战 */
export function sfxWarDeclaration(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 隆隆战鼓
  for (let i = 0; i < 3; i++) {
    noiseHit(t + i * 0.25, 0.12, 0.14 - i * 0.03, dest)
    tone(P.G2 - i * 10, 'sine', t + i * 0.25, 0.25, 0.09 - i * 0.02, dest, 0.02)
  }
  // 号角
  arpeggio([P.G3, P.C4, P.E4, P.G4, P.C5], t + 0.3, 0.06, 0.1, dest, 0.15)
  gongHit(P.C3, t + 0.6, 0.12, dest)
}

/** 和谈成功 */
export function sfxPeaceTreaty(): void {
  const dest = getMasterGain()
  const t = audioNow()
  // 平和钟声
  chime(P.E4, t, 0.07, dest, 0.4)
  chime(P.G4, t + 0.15, 0.06, dest, 0.4)
  chime(P.C5, t + 0.3, 0.05, dest, 0.5)
  // 共鸣
  tone(P.E3, 'triangle', t, 1.5, 0.04, dest, 1.0)
}
