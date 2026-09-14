import type { Config } from 'tailwindcss'
import woobeTailwindPreset from '../woobe-ui/tailwind.preset'

export default {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
    '../woobe-ui/src/**/*.{ts,tsx}',
  ],
  darkMode: 'class',
  presets: [woobeTailwindPreset],
  theme: {
    extend: {},
  },
  plugins: [],
} satisfies Config
