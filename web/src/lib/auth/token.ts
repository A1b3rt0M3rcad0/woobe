const TOKEN_KEY = 'projectrai_token'

type TokenListener = (token: string | null) => void
const listeners = new Set<TokenListener>()

function notify(token: string | null): void {
  for (const listener of listeners) listener(token)
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  notify(token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  notify(null)
}

export function subscribeToken(listener: TokenListener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
