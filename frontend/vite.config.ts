/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rolldownOptions: {
      output: {
        // Libraries change less often than Finalarr itself: a separate chunk stays cached
        // across updates and keeps the app chunk small.
        codeSplitting: { groups: [{ name: 'vendor', test: /node_modules/ }] },
      },
    },
  },
  server: {
    proxy: { '/api': 'http://localhost:5790', '/health': 'http://localhost:5790' },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    coverage: { include: ['src/lib/**', 'src/components/**'], thresholds: { lines: 80 } },
  },
})
