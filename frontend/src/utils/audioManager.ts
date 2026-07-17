/**
 * 古风音频管理器
 * 
 * 管理：
 * - 乱世古风 BGM 播放（循环、淡入淡出）
 * - 角色 AI 配音播放（势力选择独白、事件语音）
 * - 音效控制（点击、切换等）
 * - UI 交互音效集成（五声音阶合成）
 * - 音量管理
 * - 后端 AI 语音生成（edge-tts）集成
 */
import axios from 'axios'
import { setUiSfxOptions } from './uiSfx'

export interface AudioTrack {
  id: string
  src: string
  type: 'bgm' | 'voice' | 'sfx'
  volume?: number
}

// 内置BGM列表（用户可替换 public/data/map/bgm/ 下的文件）
const DEFAULT_BGM: AudioTrack[] = [
  { id: 'main_menu', src: '/data/map/bgm/main_menu.mp4', type: 'bgm', volume: 0.45 },
  { id: 'gameplay', src: '/data/map/bgm/gameplay.mp4', type: 'bgm', volume: 0.4 },
  { id: 'main_theme', src: '/data/map/bgm/main_theme.wav', type: 'bgm', volume: 0.4 },
  { id: 'war_drums', src: '/data/map/bgm/war_drums.wav', type: 'bgm', volume: 0.35 },
  { id: 'court_music', src: '/data/map/bgm/court_music.wav', type: 'bgm', volume: 0.3 },
]

// 势力 AI 配音映射 (V3.0 九大势力 · edge-tts 生成)
const FACTION_VOICE_MAP: Record<string, string> = {
  faction_yuan: '/data/map/voice/faction_yuan_intro.mp3',
  faction_zhuyuanzhang: '/data/map/voice/faction_zhuyuanzhang_intro.mp3',
  faction_chenyouliang: '/data/map/voice/faction_chenyouliang_intro.mp3',
  faction_zhangshicheng: '/data/map/voice/faction_zhangshicheng_intro.mp3',
  faction_fangguozhen: '/data/map/voice/faction_fangguozhen_intro.mp3',
  faction_xushouhui: '/data/map/voice/faction_xushouhui_intro.mp3',
  faction_mingyuzhen: '/data/map/voice/faction_mingyuzhen_intro.mp3',
  faction_wangbaobao: '/data/map/voice/faction_wangbaobao_intro.mp3',
  faction_mobei: '/data/map/voice/faction_mobei_intro.mp3',
}

// 音色配置缓存（V4.0 双提供商：edge-tts + ElevenLabs）
interface VoiceInfo {
  role: string
  voice_edge: string       // edge-tts 音色名
  rate: string
  pitch: string
  desc: string
  text: string
  // ElevenLabs 扩展字段
  voice_elevenlabs?: string
  eleven_stability?: number
  eleven_similarity?: number
  eleven_style?: number
}

export class AudioManager {
  private _bgmPlayer: HTMLAudioElement | null = null
  private _voicePlayer: HTMLAudioElement | null = null
  private _sfxPlayers: HTMLAudioElement[] = []
  private _masterVolume: number = 0.7
  private _bgmVolume: number = 0.5
  private _voiceVolume: number = 0.8
  private _sfxVolume: number = 0.6
  private _isMuted: boolean = false
  private _currentBgmId: string | null = null
  private _bgmTracks: AudioTrack[] = [...DEFAULT_BGM]
  private _fadeInterval: number | null = null
  private _voiceConfigCache: Record<string, VoiceInfo> = {}
  private _voicePreloadMap: Map<string, HTMLAudioElement> = new Map()
  private _generatingFactions: Set<string> = new Set()
  private _userInteracted: boolean = false
  private _interactionUnlocked: boolean = false
  private _pendingBgmId: string | null = null
  private _pendingBgmFadeIn: number = 2.0

  get masterVolume() { return this._masterVolume }
  get isMuted() { return this._isMuted }

  /**
   * 初始化音频管理器，绑定用户交互以解锁浏览器自动播放限制
   * 应在应用入口处尽早调用（如 main.ts 或 App.vue onMounted）
   */
  init() {
    if (this._interactionUnlocked) return
    this._interactionUnlocked = true

    const unlock = () => {
      this._userInteracted = true
      // 解锁后尝试播放之前因 NotAllowedError 搁置的 BGM
      if (this._pendingBgmId) {
        const id = this._pendingBgmId
        const fi = this._pendingBgmFadeIn
        this._pendingBgmId = null
        this.playBgm(id, fi)
      }
    }

    const events = ['click', 'touchstart', 'keydown', 'mousedown'] as const
    const handler = () => {
      unlock()
      for (const evt of events) {
        document.removeEventListener(evt, handler, true)
      }
    }
    for (const evt of events) {
      document.addEventListener(evt, handler, true)
    }
  }

  /** 设置主音量 */
  setMasterVolume(v: number) {
    this._masterVolume = Math.max(0, Math.min(1, v))
    this._applyVolume()
    // 同步 UI 音效音量
    setUiSfxOptions({ masterVolume: this._masterVolume })
  }

  /** 设置BGM音量 */
  setBgmVolume(v: number) {
    this._bgmVolume = Math.max(0, Math.min(1, v))
    this._applyVolume()
  }

  /** 获取BGM音量 */
  getBgmVolume(): number { return this._bgmVolume }

  /** 设置音效音量 */
  setSfxVolume(v: number) {
    this._sfxVolume = Math.max(0, Math.min(1, v))
    // 更新正在播放的音效
    for (const p of this._sfxPlayers) {
      p.volume = this._sfxVolume * (this._isMuted ? 0 : this._masterVolume)
    }
  }

  /** 获取音效音量 */
  getSfxVolume(): number { return this._sfxVolume }

  /** 设置配音音量 */
  setVoiceVolume(v: number) {
    this._voiceVolume = Math.max(0, Math.min(1, v))
    this._applyVolume()
  }

  /** 获取配音音量 */
  getVoiceVolume(): number { return this._voiceVolume }

  /** 设置BGM静音状态 */
  setBgmMuted(muted: boolean) {
    if (muted) {
      this.pauseBgm()
    } else {
      this.resumeBgm()
    }
  }

  /** 设置音效静音状态 */
  setSfxMuted(muted: boolean) {
    setUiSfxOptions({ muted })
  }

  /** 静音切换 */
  toggleMute(): boolean {
    this._isMuted = !this._isMuted
    this._applyVolume()
    // 同步 UI 音效静音状态
    setUiSfxOptions({ muted: this._isMuted })
    return this._isMuted
  }

  /** 设置全局静音 */
  setMuted(muted: boolean) {
    this._isMuted = muted
    this._applyVolume()
    setUiSfxOptions({ muted: this._isMuted })
  }

  /** 注册自定义BGM */
  registerBgm(tracks: AudioTrack[]) {
    this._bgmTracks = tracks
  }

  /** 
   * 播放BGM（支持淡入）
   * @param bgmId BGM ID，不传则随机播放
   * @param fadeIn 淡入时长（秒）
   */
  playBgm(bgmId?: string, fadeIn: number = 2.0) {
    const track = bgmId
      ? this._bgmTracks.find(t => t.id === bgmId)
      : this._bgmTracks[Math.floor(Math.random() * this._bgmTracks.length)]

    if (!track) return

    // 如果是同一首BGM且正在播放，跳过
    if (this._currentBgmId === track.id && this._bgmPlayer && !this._bgmPlayer.paused) {
      return
    }

    // 静音状态下不播放
    if (this._isMuted) return

    // 用户尚未交互 → 暂存待交互后播放，避免浏览器 NotAllowedError 警告
    if (!this._userInteracted) {
      this._pendingBgmId = track.id
      this._pendingBgmFadeIn = fadeIn
      return
    }

    // 淡出并销毁旧BGM播放器，防止内存泄漏
    if (this._bgmPlayer && !this._bgmPlayer.paused) {
      this._fadeOutAndStop(this._bgmPlayer, 1.0)
    } else if (this._bgmPlayer) {
      // 暂停的旧播放器也清理掉引用，帮助GC回收
      this._bgmPlayer.src = ''
      this._bgmPlayer.load()
    }

    // 创建新播放器
    const player = new Audio(track.src)
    player.loop = true
    player.preload = 'auto'
    player.volume = 0

    player.play().then(() => {
      this._bgmPlayer = player
      this._currentBgmId = track.id
      // 淡入
      this._fadeTo(player, (track.volume || this._bgmVolume) * (this._isMuted ? 0 : this._masterVolume), fadeIn)
    }).catch(err => {
      // 浏览器自动播放策略限制 → 暂存，等用户交互后重试
      if (err.name === 'NotAllowedError') {
        this._pendingBgmId = track.id
        this._pendingBgmFadeIn = fadeIn
        return
      }
      // 音频文件不存在或格式不支持
      if (err.name === 'NotSupportedError') {
        console.warn(`[AudioManager] BGM资源不可用: ${track.src}`, err)
        return
      }
      console.warn('[AudioManager] BGM播放失败:', err)
    })
  }

  /**
   * 加载音色配置缓存（从后端获取）
   */
  async loadVoiceConfigs(): Promise<Record<string, VoiceInfo>> {
    if (Object.keys(this._voiceConfigCache).length > 0) return this._voiceConfigCache
    try {
      const { data: resp } = await axios.get('/api/audio/voice-config', { timeout: 5000 })
      // 后端统一返回 { code: 200, data: {...} } 格式
      if (resp && (resp.code === 200 || resp.code === 0) && resp.data) {
        this._voiceConfigCache = resp.data
      }
    } catch (e) {
      console.warn('[AudioManager] 音色配置加载失败:', e)
    }
    return this._voiceConfigCache
  }

  /**
   * 获取势力的音色信息
   */
  getVoiceInfo(factionId: string): VoiceInfo | null {
    return this._voiceConfigCache[factionId] || null
  }

  /**
   * 预加载势力 AI 配音（后台静默加载）
   */
  preloadFactionVoice(factionId: string) {
    const src = FACTION_VOICE_MAP[factionId]
    if (!src || this._voicePreloadMap.has(factionId)) return
    const audio = new Audio(src)
    audio.preload = 'auto'
    audio.load()
    this._voicePreloadMap.set(factionId, audio)
  }

  /**
   * 预加载所有九大势力配音
   */
  preloadAllFactionVoices() {
    for (const factionId of Object.keys(FACTION_VOICE_MAP)) {
      this.preloadFactionVoice(factionId)
    }
  }

  /**
   * 请求后端生成势力的 AI 配音（通过 edge-tts）
   * 返回生成后的音频 Blob URL 或 null
   */
  async _requestVoiceGeneration(factionId: string): Promise<string | null> {
    if (this._generatingFactions.has(factionId)) return null
    this._generatingFactions.add(factionId)
    try {
      const { data: resp } = await axios.post('/api/audio/generate-voice', { faction_id: factionId }, { timeout: 30000 })
      // 后端统一返回 { code: 200/0, data: {...} } 格式
      if (resp && (resp.code === 200 || resp.code === 0) && resp.data?.generated) {
        if (import.meta.env.DEV) console.log(`[AudioManager] AI配音生成成功: ${factionId}`)
        // 生成了就返回文件路径
        return FACTION_VOICE_MAP[factionId] || null
      }
      return null
    } catch (e) {
      console.warn(`[AudioManager] AI配音生成失败: ${factionId}`, e)
      return null
    } finally {
      this._generatingFactions.delete(factionId)
    }
  }

  /**
   * 播放势力 AI 配音（优先使用 edge-tts 生成的 MP3，降级到 Web Speech API）
   * @param factionId 势力ID
   * @param voiceText 势力开场台词（作为 TTS 降级方案）
   * @param onEnd 播放结束回调
   * @returns 是否成功启动播放
   */
  async playFactionVoiceAI(factionId: string, voiceText?: string, onEnd?: () => void): Promise<boolean> {
    if (this._isMuted) return false

    const src = FACTION_VOICE_MAP[factionId]
    if (!src) {
      if (voiceText) this.speakText(voiceText, onEnd)
      return false
    }

    // 降低BGM音量（ducking）
    if (this._bgmPlayer) {
      this._fadeTo(this._bgmPlayer, this._bgmVolume * 0.2 * this._masterVolume, 0.5)
    }

    // 停止当前正在播放的配音
    this._stopVoice()

    const playAudio = (audioSrc: string): Promise<boolean> => {
      return new Promise((resolve) => {
        const player = new Audio(audioSrc)
        player.volume = this._voiceVolume * (this._isMuted ? 0 : this._masterVolume)
        player.preload = 'auto'

        player.oncanplaythrough = () => {
          player.play().then(() => {
            this._voicePlayer = player
            resolve(true)
          }).catch(() => {
            resolve(false)
          })
        }

        player.onerror = () => {
          resolve(false)
        }

        player.onended = () => {
          this._voicePlayer = null
          if (this._bgmPlayer) {
            this._fadeTo(this._bgmPlayer, this._bgmVolume * this._masterVolume, 1.0)
          }
          if (onEnd) onEnd()
        }

        // 超时保护
        setTimeout(() => {
          if (this._voicePlayer !== player && player.readyState < 3) {
            player.load() // 重试加载
          }
        }, 3000)
      })
    }

    // 优先尝试直接播放本地文件
    const played = await playAudio(src)
    if (played) return true

    // 本地文件不存在，从后端请求生成
    if (import.meta.env.DEV) console.log(`[AudioManager] 本地配音缺失，请求后端 AI 生成: ${factionId}`)
    const generatedSrc = await this._requestVoiceGeneration(factionId)
    if (generatedSrc) {
      const playedAfterGen = await playAudio(generatedSrc)
      if (playedAfterGen) return true
    }

    // 最终降级：Web Speech API
    if (voiceText) {
      this.speakText(voiceText, onEnd)
      return true
    }

    // BGM 恢复
    if (this._bgmPlayer) {
      this._fadeTo(this._bgmPlayer, this._bgmVolume * this._masterVolume, 1.0)
    }
    return false
  }

  /** 
   * 播放角色配音（兼容旧接口，直接播放本地 MP3）
   * @param factionId 势力ID
   * @param onEnd 播放结束回调
   */
  playFactionVoice(factionId: string, onEnd?: () => void): boolean {
    const src = FACTION_VOICE_MAP[factionId]
    if (!src) return false

    // 降低BGM音量（ducking）
    if (this._bgmPlayer) {
      this._fadeTo(this._bgmPlayer, this._bgmVolume * 0.2 * this._masterVolume, 0.5)
    }

    this._stopVoice()

    const player = new Audio(src)
    player.volume = this._voiceVolume * (this._isMuted ? 0 : this._masterVolume)
    player.preload = 'auto'

    player.play().then(() => {
      this._voicePlayer = player
    }).catch(err => {
      console.warn('[AudioManager] 配音播放失败:', err)
    })

    player.onended = () => {
      this._voicePlayer = null
      if (this._bgmPlayer) {
        this._fadeTo(this._bgmPlayer, this._bgmVolume * this._masterVolume, 1.0)
      }
      if (onEnd) onEnd()
    }

    return true
  }

  /**
   * 停止当前配音
   */
  stopVoice() {
    this._stopVoice()
    window.speechSynthesis?.cancel()
  }

  private _stopVoice() {
    if (this._voicePlayer) {
      this._voicePlayer.pause()
      this._voicePlayer.src = ''
      this._voicePlayer = null
    }
  }

  /** 
   * 播放TTS配音（降级方案）
   */
  speakText(text: string, onEnd?: () => void) {
    if (typeof window === 'undefined' || !window.speechSynthesis) return

    window.speechSynthesis.cancel()

    // 降低BGM音量
    if (this._bgmPlayer) {
      this._fadeTo(this._bgmPlayer, this._bgmVolume * 0.2 * this._masterVolume, 0.3)
    }

    const utter = new SpeechSynthesisUtterance(text)
    utter.lang = 'zh-CN'
    utter.rate = 0.85
    utter.pitch = 1.0
    utter.volume = this._voiceVolume * (this._isMuted ? 0 : 1)

    const voices = window.speechSynthesis.getVoices()
    const zhVoice = voices.find(v => v.lang.startsWith('zh') && v.name.includes('男'))
      || voices.find(v => v.lang.startsWith('zh'))
    if (zhVoice) utter.voice = zhVoice

    utter.onend = () => {
      if (this._bgmPlayer) {
        this._fadeTo(this._bgmPlayer, this._bgmVolume * this._masterVolume, 1.0)
      }
      if (onEnd) onEnd()
    }

    window.speechSynthesis.speak(utter)
  }

  /** 播放音效 */
  playSfx(src: string) {
    if (this._isMuted) return
    const player = new Audio(src)
    player.volume = this._sfxVolume * this._masterVolume
    player.play().catch(() => {})
    this._sfxPlayers.push(player)
    player.onended = () => {
      const idx = this._sfxPlayers.indexOf(player)
      if (idx >= 0) this._sfxPlayers.splice(idx, 1)
    }
    // 限制同时播放的音效数量
    if (this._sfxPlayers.length > 5) {
      const old = this._sfxPlayers.shift()
      if (old) { old.pause(); old.src = '' }
    }
  }

  /**
   * 渐隐 BGM（选完势力 → 过渡到加载/游戏界面前的消声）
   * @param duration 淡出时长（秒），默认 2.0
   */
  fadeOutBgm(duration: number = 2.0) {
    if (this._bgmPlayer && !this._bgmPlayer.paused) {
      this._fadeOutAndStop(this._bgmPlayer, duration)
      this._bgmPlayer = null
      this._currentBgmId = null
    }
  }

  /** 停止所有音频 */
  stopAll() {
    if (this._bgmPlayer) {
      this._bgmPlayer.pause()
      this._bgmPlayer.src = ''
      this._bgmPlayer = null
    }
    this._stopVoice()
    for (const p of this._sfxPlayers) {
      p.pause()
    }
    this._sfxPlayers = []
    if (this._fadeInterval) {
      clearInterval(this._fadeInterval)
      this._fadeInterval = null
    }
    this._currentBgmId = null
    window.speechSynthesis?.cancel()
  }

  /** 暂停BGM */
  pauseBgm() {
    if (this._bgmPlayer) this._bgmPlayer.pause()
  }

  /** 恢复BGM */
  resumeBgm() {
    if (this._bgmPlayer) this._bgmPlayer.play().catch(() => {})
  }

  /** 检查 BGM 是否正在播放 */
  isBgmPlaying(): boolean {
    return this._bgmPlayer !== null && !this._bgmPlayer.paused
  }

  /** 随机播放一首 BGM */
  playRandomBgm() {
    if (this._bgmTracks.length === 0) return
    const idx = Math.floor(Math.random() * this._bgmTracks.length)
    this.playBgm(this._bgmTracks[idx].id)
  }

  /** 获取当前 BGM 名称 */
  getCurrentBgmName(): string {
    if (!this._currentBgmId) return ''
    const track = this._bgmTracks.find(t => t.id === this._currentBgmId)
    const nameMap: Record<string, string> = {
      main_menu: '乱世序曲', gameplay: '逐鹿中原', main_theme: '山河颂', war_drums: '战鼓擂', court_music: '庙堂之音'
    }
    return nameMap[this._currentBgmId] || track?.id || this._currentBgmId
  }

  /** 获取当前 BGM ID */
  getCurrentBgmId(): string | null {
    return this._currentBgmId
  }

  /** 获取所有 BGM 曲目（含中文名） */
  getBgmTracks(): (AudioTrack & { name: string })[] {
    const nameMap: Record<string, string> = {
      main_menu: '乱世序曲', gameplay: '逐鹿中原', main_theme: '山河颂', war_drums: '战鼓擂', court_music: '庙堂之音'
    }
    return this._bgmTracks.map(t => ({ ...t, name: nameMap[t.id] || t.id }))
  }

  /** 销毁 */
  destroy() {
    this.stopAll()
    this._voicePreloadMap.clear()
    this._voiceConfigCache = {}
  }

  // ===== 内部方法 =====
  private _applyVolume() {
    const m = this._isMuted ? 0 : this._masterVolume
    if (this._bgmPlayer) this._bgmPlayer.volume = this._bgmVolume * m
    if (this._voicePlayer) this._voicePlayer.volume = this._voiceVolume * m
  }

  private _fadeTo(player: HTMLAudioElement, targetVol: number, duration: number) {
    if (this._fadeInterval) clearInterval(this._fadeInterval)
    const startVol = player.volume
    const startTime = Date.now()

    this._fadeInterval = window.setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000
      const progress = Math.min(1, elapsed / duration)
      player.volume = startVol + (targetVol - startVol) * progress
      if (progress >= 1 && this._fadeInterval) {
        clearInterval(this._fadeInterval)
        this._fadeInterval = null
      }
    }, 50)
  }

  private _fadeOutAndStop(player: HTMLAudioElement, duration: number) {
    this._fadeTo(player, 0, duration)
    setTimeout(() => {
      player.pause()
      player.src = ''
    }, duration * 1000 + 100)
  }
}

/** 全局音频管理器单例 */
export const audioManager = new AudioManager()
