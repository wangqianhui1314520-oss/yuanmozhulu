import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './styles/main.css'
import './styles/gameSprites.css'
import { UiAudioPlugin } from './utils/uiAudioPlugin'
import { initUiSfx } from './utils/uiSfx'
import { audioManager } from './utils/audioManager'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(UiAudioPlugin)
app.mount('#app')

// 初始化音频管理器（绑定用户交互解锁浏览器自动播放限制）
audioManager.init()

// 预初始化 UI 音效 AudioContext（用户首次交互时激活）
document.addEventListener('click', () => initUiSfx(), { once: true })
document.addEventListener('keydown', () => initUiSfx(), { once: true })
