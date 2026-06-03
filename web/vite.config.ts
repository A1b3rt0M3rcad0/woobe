import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/identity': 'http://localhost:8000',
      '/core': 'http://localhost:8000',
      '/ai': 'http://localhost:8000',
      '/knowledge': 'http://localhost:8000',
      '/runtime': 'http://localhost:8000',
      '/tools': 'http://localhost:8000',
      '/metering': 'http://localhost:8000',
      '/billing': 'http://localhost:8000',
      '/observability': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
