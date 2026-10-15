import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'
const storageKey = 'woobe.theme'
const mediaQuery = '(prefers-color-scheme: dark)'
const validPreference = (value: string | null): ThemePreference => value === 'light' || value === 'dark' ? value : 'system'

function readPreference(): ThemePreference {
  try { return validPreference(localStorage.getItem(storageKey)) } catch { return 'system' }
}

const ThemeContext = createContext<{
  themePreference: ThemePreference
  resolvedTheme: 'light' | 'dark'
  setThemePreference: (preference: ThemePreference) => void
} | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themePreference, setPreference] = useState(readPreference)
  const [systemDark, setSystemDark] = useState(() => window.matchMedia(mediaQuery).matches)
  const resolvedTheme = themePreference === 'system' ? systemDark ? 'dark' : 'light' : themePreference

  useEffect(() => {
    const media = window.matchMedia(mediaQuery)
    const onSystemChange = () => setSystemDark(media.matches)
    const onStorage = (event: StorageEvent) => {
      if (event.key === storageKey || event.key === null) setPreference(validPreference(event.newValue))
    }
    onSystemChange()
    media.addEventListener('change', onSystemChange)
    window.addEventListener('storage', onStorage)
    return () => {
      media.removeEventListener('change', onSystemChange)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', resolvedTheme === 'dark' ? '#191a17' : '#efede8')
  }, [resolvedTheme])

  const setThemePreference = (preference: ThemePreference) => {
    setPreference(preference)
    try { localStorage.setItem(storageKey, preference) } catch { /* Keep the in-memory choice. */ }
  }

  return <ThemeContext.Provider value={{ themePreference, resolvedTheme, setThemePreference }}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const theme = useContext(ThemeContext)
  if (!theme) throw new Error('useTheme requires ThemeProvider')
  return theme
}
