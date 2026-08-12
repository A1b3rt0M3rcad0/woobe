/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_CHAT_EMBED_URL?: string
  readonly VITE_WOOBE_EDITION?: 'community' | 'cloud'
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
