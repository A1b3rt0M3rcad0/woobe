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
      '@codemirror/lang-json': path.resolve(__dirname, './node_modules/@codemirror/lang-json'),
      '@codemirror/language': path.resolve(__dirname, './node_modules/@codemirror/language'),
      '@codemirror/state': path.resolve(__dirname, './node_modules/@codemirror/state'),
      '@codemirror/view': path.resolve(__dirname, './node_modules/@codemirror/view'),
      '@lezer/highlight': path.resolve(__dirname, './node_modules/@lezer/highlight'),
      '@uiw/react-codemirror': path.resolve(__dirname, './node_modules/@uiw/react-codemirror'),
      react: path.resolve(__dirname, './node_modules/react'),
      'react-dom': path.resolve(__dirname, './node_modules/react-dom'),
      'lucide-react': path.resolve(__dirname, './node_modules/lucide-react'),
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
