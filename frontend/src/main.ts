import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './styles/main.css'
import { UiAudioPlugin } from './utils/uiAudioPlugin'
import { initUiSfx } from './utils/uiSfx'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(UiAudioPlugin)
app.mount('#app')

// 预初始化 UI 音效 AudioContext（用户首次交互时激活）
document.addEventListener('click', () => initUiSfx(), { once: true })
document.addEventListener('keydown', () => initUiSfx(), { once: true })
