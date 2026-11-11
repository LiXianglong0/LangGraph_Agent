import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发时把 /api 代理到 FastAPI，避免跨域调试麻烦
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // 与 FastAPI 默认端口一致（8000 常被其它项目占用）
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  // history 路由刷新时回退到 index.html
  preview: {
    port: 5173,
  },
})