import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, proxy: { '/api': { target: process.env.VITE_API_TARGET || 'http://localhost:8000', changeOrigin: true } } },
  test: {
    environment: 'happy-dom',
    include: ['src/**/*.test.js'],
    setupFiles: ['./src/test-setup.js']
  }
})
