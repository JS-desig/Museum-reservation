import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 后端API统一前缀, 避免与前端路由冲突
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
