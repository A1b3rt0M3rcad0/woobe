export interface WoobeRuntimeConfig {
  apiUrl?: string
  chatEmbedUrl?: string
}

declare global {
  interface Window {
    __WOOBE_CONFIG__?: WoobeRuntimeConfig
  }
}

function resolveHttpUrl(value: string | undefined, label: string): string {
  const configured = value?.trim()
  if (!configured) {
    throw new Error(`${label} must be configured with an absolute HTTP(S) URL`)
  }

  try {
    const url = new URL(configured)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      throw new Error('Invalid URL protocol')
    }
    return url.toString().replace(/\/+$/, '')
  } catch {
    throw new Error(`${label} must be an absolute HTTP(S) URL. Received: ${configured}`)
  }
}

function runtimeValue(key: keyof WoobeRuntimeConfig, buildValue: string | undefined): string | undefined {
  if (typeof window !== 'undefined') {
    const value = window.__WOOBE_CONFIG__?.[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return buildValue
}

export function resolveRuntimeApiUrl(): string {
  return resolveHttpUrl(runtimeValue('apiUrl', import.meta.env.VITE_API_URL), 'Woobe API URL')
}

export function resolveRuntimeChatEmbedUrl(): string {
  return resolveHttpUrl(
    runtimeValue('chatEmbedUrl', import.meta.env.VITE_CHAT_EMBED_URL),
    'Woobe ChatSurface URL',
  )
}

export const RUNTIME_API_URL = resolveRuntimeApiUrl()
export const RUNTIME_CHAT_EMBED_URL = resolveRuntimeChatEmbedUrl()
export const RUNTIME_CHAT_EMBED_ORIGIN = new URL(RUNTIME_CHAT_EMBED_URL).origin
