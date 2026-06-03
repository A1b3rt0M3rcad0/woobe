import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#020817',
        surface: '#0f1729',
        border: '#1e293b',
        primary: {
          DEFAULT: '#3b82f6',
          hover: '#2563eb',
          light: '#93c5fd',
        },
        muted: {
          DEFAULT: '#64748b',
          foreground: '#94a3b8',
        },
        accent: {
          DEFAULT: '#1e293b',
          foreground: '#f8fafc',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
