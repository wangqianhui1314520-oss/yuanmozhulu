import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  // CloudStudio / 生产部署：API 由 Nginx 反向代理到同源 /api/
  // 开发模式：Vite 代理到本地 Python 后端
  const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8800'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    // 生产环境基础路径（CloudStudio 部署时可设为 '/' 或 CDN 路径）
    base: process.env.VITE_BASE_URL || '/',
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      // 图片资源内联阈值（小于 4KB 的图片内联为 base64）
      assetsInlineLimit: 4096,
      rollupOptions: {
        output: {
          // 将图片资源分类存放
          assetFileNames: (assetInfo) => {
            if (assetInfo.name && /\.(png|jpe?g|gif|webp|svg)$/i.test(assetInfo.name)) {
              return 'assets/images/[name]-[hash][extname]'
            }
            return 'assets/[name]-[hash][extname]'
          },
        },
      },
    },
  }
})
