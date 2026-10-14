import { useTheme, type ThemePreference } from './ThemeProvider'

/** Native select keeps all three choices explicit and works with keyboard/touch. */
export function ThemeSelect() {
  const { themePreference, setThemePreference } = useTheme()
  return (
    <label className="woobe-theme-select inline-flex shrink-0 items-center">
      <span className="sr-only">Theme</span>
      <select
        aria-label="Theme"
        value={themePreference}
        onChange={(event) => setThemePreference(event.target.value as ThemePreference)}
        className="h-control-sm max-w-full rounded-control border border-control-border bg-surface px-ui-sm font-sans text-chrome-label text-foreground hover:bg-control"
      >
        <option value="light">Light</option>
        <option value="dark">Dark</option>
        <option value="system">System</option>
      </select>
    </label>
  )
}
