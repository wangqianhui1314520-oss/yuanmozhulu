/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, any>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_BASE: string
  readonly VITE_API_TARGET: string
  readonly VITE_BASE_URL: string
  readonly VITE_GAME_TITLE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
