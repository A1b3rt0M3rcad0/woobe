/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  envDir: path.resolve(__dirname, '..'),
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@woobe/runtime-client': path.resolve(
        __dirname,
        '../woobe-runtime-client/src/index.ts',
      ),
      '@woobe/ui': path.resolve(__dirname, '../woobe-ui/src/index.ts'),
      react: path.resolve(__dirname, './node_modules/react'),
      'react-dom': path.resolve(__dirname, './node_modules/react-dom'),
      'tailwind-merge': path.resolve(__dirname, './node_modules/tailwind-merge'),
    },
    dedupe: ['react', 'react-dom'],
  },
  server: {
    port: 5173,
  },
  test: {
    globals: true,
    environment: 'node',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
})
