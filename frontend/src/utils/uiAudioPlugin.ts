/**
 * Vue3 全局 UI 音频插件
 *
 * 提供：
 * 1. v-audio 指令：自动为元素绑定音效（通过 data-audio 属性指定分类）
 * 2. 全局 $uiAudio 属性：可在模板中直接调用
 *
 * 用法：
 *   <!-- 指令方式 -->
 *   <button v-audio data-audio="btn_primary">确认</button>
 *   <button v-audio data-audio="btn_danger">删除</button>
 *   <div v-audio data-audio="panel_open" @click="openPanel">面板</div>
 *
 *   <!-- 通过 CSS class 自动推断 -->
 *   <button class="btn-primary" v-audio>启卷入世</button>     → btn_primary
 *   <button class="btn-gold" v-audio>颁布圣旨</button>         → edict_submit
 *   <button class="close-btn" v-audio>✕</button>               → panel_close
 *   <button class="icon-btn" v-audio>🔇</button>               → toggle_off / toggle_on
 *   <div class="tip-action-btn" v-audio data-action="march">    → action_march
 *   <button class="toggle-btn" v-audio>开关</button>            → toggle_on / toggle_off
 *   <div class="hdr-btn" v-audio data-audio="btn_nav">国策</div>
 *   <button class="cfg-danger" v-audio>重置</button>           → btn_danger
 *   <button class="speed-btn" v-audio>2x</button>              → tab_switch
 *   <button class="npc-tab" v-audio>谋臣</button>              → tab_switch
 *   <div class="filter-tag" v-audio>军事</div>                 → select
 *   <button class="modal-close" v-audio>✕</button>             → modal_close
 *
 *   <!-- 六边形地块 -->
 *   <div v-hex-audio data-hex-selected="true">地块</div>
 *
 *   <!-- 悬停 -->
 *   <div v-hover-audio>悬停我</div>
 */

import type { App, DirectiveBinding, ObjectDirective } from 'vue'
import { playUiSfx, type SfxCategory } from './uiSfx'

// CSS class → 音效分类 自动推断映射
const CLASS_SFX_MAP: Array<{ pattern: RegExp; sfx: SfxCategory }> = [
  { pattern: /btn-primary|btn-confirm/, sfx: 'btn_primary' },
  { pattern: /btn-gold/, sfx: 'edict_submit' },
  { pattern: /btn-danger|btn-delete|cfg-danger|cfg-reset/, sfx: 'btn_danger' },
  { pattern: /cfg-save/, sfx: 'btn_primary' },
  { pattern: /cfg-test/, sfx: 'btn_nav' },
  { pattern: /close-btn|fp-close|tip-close|panel-close|mp-close|replay-close|settings-close|rpl-close-btn/, sfx: 'panel_close' },
  { pattern: /icon-btn/, sfx: 'btn_secondary' },
  { pattern: /toggle-btn/, sfx: 'toggle_on' },
  { pattern: /hdr-btn|top-btn/, sfx: 'btn_nav' },
  { pattern: /speed-btn/, sfx: 'tab_switch' },
  { pattern: /npc-tab/, sfx: 'tab_switch' },
  { pattern: /filter-tag/, sfx: 'select' },
  { pattern: /modal-close|bio-close/, sfx: 'modal_close' },
  { pattern: /quick-btn|tip-quick-btn|mp-quick-btn/, sfx: 'btn_secondary' },
  { pattern: /empty-btn/, sfx: 'btn_secondary' },
  { pattern: /transport-btn/, sfx: 'tab_switch' },
  { pattern: /quick-amt-btn/, sfx: 'btn_secondary' },
  { pattern: /btn-sm|btn-small/, sfx: 'btn_secondary' },
  { pattern: /tab-btn/, sfx: 'tab_switch' },
  { pattern: /zoom-btn/, sfx: 'tab_switch' },
  { pattern: /ctx-menu-item/, sfx: 'btn_secondary' },
  { pattern: /btn-retry/, sfx: 'btn_danger' },
  { pattern: /btn-back/, sfx: 'btn_nav' },
  { pattern: /btn-enter/, sfx: 'btn_primary' },
  { pattern: /btn-voice/, sfx: 'btn_secondary' },
  { pattern: /advance-turn-btn/, sfx: 'turn_advance' },
  { pattern: /mp-btn-primary/, sfx: 'btn_primary' },
  { pattern: /mp-btn-secondary/, sfx: 'btn_secondary' },
  { pattern: /mtc-change-btn/, sfx: 'btn_secondary' },
  { pattern: /rpl-btn(?!-close)/, sfx: 'btn_secondary' },
  { pattern: /cfg-btn(?!-danger|reset)/, sfx: 'btn_secondary' },
  { pattern: /settings-tab/, sfx: 'tab_switch' },
]

// data-action 属性 → 音效分类映射
const ACTION_SFX_MAP: Record<string, SfxCategory> = {
  march: 'action_march',
  recruit: 'action_recruit',
  build: 'action_build',
  tax: 'action_tax',
  spy: 'action_spy',
  develop: 'action_develop',
  fortify: 'action_build',
  relief: 'action_develop',
}

/** 从元素属性/class 推断音效分类 */
function inferSfx(el: HTMLElement): SfxCategory | null {
  const dataset = el.dataset

  // 1. 显式指定 data-audio
  if (dataset.audio) {
    return dataset.audio as SfxCategory
  }

  // 2. data-action 映射
  if (dataset.action && ACTION_SFX_MAP[dataset.action]) {
    return ACTION_SFX_MAP[dataset.action]
  }

  // 3. CSS class 推断
  const cls = el.className
  if (typeof cls === 'string') {
    for (const { pattern, sfx } of CLASS_SFX_MAP) {
      if (pattern.test(cls)) return sfx
    }
  }

  // 4. 通用 button 元素 — 默认 secondary
  if (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button') {
    return 'btn_secondary'
  }

  return null
}

// ─── v-audio 指令 ───

const audioDirective: ObjectDirective<HTMLElement> = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const sfx = inferSfx(el)
    if (!sfx) return

    const handler = () => playUiSfx(sfx)
    ;(el as any).__uiAudioHandler = handler
    el.addEventListener('click', handler)
  },

  updated(el: HTMLElement, binding: DirectiveBinding) {
    // data-audio 可能动态变化，重新绑定
    const oldHandler = (el as any).__uiAudioHandler
    const sfx = inferSfx(el)
    if (!sfx) {
      if (oldHandler) {
        el.removeEventListener('click', oldHandler)
        delete (el as any).__uiAudioHandler
      }
      return
    }

    const handler = () => playUiSfx(sfx)
    if (oldHandler) el.removeEventListener('click', oldHandler)
    ;(el as any).__uiAudioHandler = handler
    el.addEventListener('click', handler)
  },

  unmounted(el: HTMLElement) {
    const handler = (el as any).__uiAudioHandler
    if (handler) {
      el.removeEventListener('click', handler)
      delete (el as any).__uiAudioHandler
    }
  },
}

// ─── v-hover-audio 指令（悬停音效） ───

const hoverAudioDirective: ObjectDirective<HTMLElement> = {
  mounted(el: HTMLElement) {
    const handler = () => playUiSfx('hover')
    ;(el as any).__uiHoverHandler = handler
    el.addEventListener('mouseenter', handler)
  },
  unmounted(el: HTMLElement) {
    const handler = (el as any).__uiHoverHandler
    if (handler) {
      el.removeEventListener('mouseenter', handler)
      delete (el as any).__uiHoverHandler
    }
  },
}

// ─── v-hex-audio 指令（六边形地块选中音效） ───

const hexAudioDirective: ObjectDirective<HTMLElement> = {
  mounted(el: HTMLElement) {
    const observer = new MutationObserver(() => {
      const selected = el.dataset.hexSelected === 'true'
      playUiSfx(selected ? 'hex_select' : 'hex_deselect')
    })
    observer.observe(el, { attributes: true, attributeFilter: ['data-hex-selected'] })
    ;(el as any).__uiHexObserver = observer
  },
  unmounted(el: HTMLElement) {
    const observer = (el as any).__uiHexObserver
    if (observer) observer.disconnect()
  },
}

// ─── Vue 插件安装 ───

export const UiAudioPlugin = {
  install(app: App, _options?: {}) {
    app.directive('audio', audioDirective)
    app.directive('hover-audio', hoverAudioDirective)
    app.directive('hex-audio', hexAudioDirective)
  },
}

// ─── 重新导出 composable ───
export { useUiAudio } from './useUiAudio'
export type { UseUiAudioReturn } from './useUiAudio'
