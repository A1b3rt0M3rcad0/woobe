import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const API_TARGET = process.env.PROXY_API_URL || process.env.VITE_API_URL || 'http://localhost:8000'

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
      '/identity': API_TARGET,
      '/core': API_TARGET,
      '/ai': API_TARGET,
      '/knowledge': API_TARGET,
      '/runtime': API_TARGET,
      '/tools': API_TARGET,
      '/metering': API_TARGET,
      '/billing': API_TARGET,
      '/observability': API_TARGET,
      '/health': API_TARGET,
    },
  },
})
