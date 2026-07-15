/**
 * Vue3 Composable：UI 交互音频
 *
 * 为所有前端 UI 交互提供即时的五声音阶合成音效。
 * 组件中调用即可播放对应音效，无需额外配置。
 *
 * 用法：
 *   const { click, panel, notify, action, hex, turn, tab, select, hover } = useUiAudio()
 *   click.primary()          // 主要按钮点击
 *   panel.open()             // 面板打开
 *   notify.success()         // 成功通知
 *   action.march()           // 出征操作
 *   turn.edict()             // 颁布圣旨
 *   hex.select()             // 地块选中
 *   tab.switch()             // 标签切换
 */

import { onMounted } from 'vue'
import {
  initUiSfx,
  playUiSfx,
  uiClick,
  uiPanel,
  uiNotify,
  uiAction,
  uiHex,
  uiTurn,
  setUiSfxOptions,
  type SfxCategory,
  type UiSfxOptions,
} from './uiSfx'

export interface UseUiAudioReturn {
  /** 按钮点击音效 */
  click: typeof uiClick
  /** 面板开合音效 */
  panel: typeof uiPanel
  /** 通知音效 */
  notify: typeof uiNotify
  /** 游戏操作音效 */
  action: typeof uiAction
  /** 六边形地块音效 */
  hex: typeof uiHex
  /** 回合/圣旨音效 */
  turn: typeof uiTurn
  /** 标签切换 */
  tab: { switch: () => void }
  /** 选择/取消 */
  select: { on: () => void; off: () => void }
  /** 悬停 */
  hover: () => void
  /** 弹窗 */
  modal: { open: () => void; close: () => void }
  /** 直接播放任意分类 */
  play: (category: SfxCategory) => void
  /** 更新配置 */
  configure: (opts: UiSfxOptions) => void
}

export function useUiAudio(muted?: () => boolean): UseUiAudioReturn {
  onMounted(() => {
    initUiSfx()
  })

  // 响应式静音
  if (muted) {
    // 初始设置
    setUiSfxOptions({ muted: muted() })
    // 依赖调用方传入 ref getter
  }

  return {
    click: uiClick,
    panel: uiPanel,
    notify: uiNotify,
    action: uiAction,
    hex: uiHex,
    turn: uiTurn,
    tab: { switch: () => playUiSfx('tab_switch') },
    select: {
      on: () => playUiSfx('select'),
      off: () => playUiSfx('deselect'),
    },
    hover: () => playUiSfx('hover'),
    modal: {
      open: () => playUiSfx('modal_open'),
      close: () => playUiSfx('modal_close'),
    },
    play: (category: SfxCategory) => playUiSfx(category),
    configure: (opts: UiSfxOptions) => setUiSfxOptions(opts),
  }
}
