import path from 'node:path'
import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

const dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, dirname, '')
  const apiProxyTarget = env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

  return {
    plugins: [
      tanstackRouter({
        routesDirectory: './src/app/router/routes',
        generatedRouteTree: './src/app/router/routeTree.gen.ts',
        target: 'react',
      }),
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(dirname, './src'),
      },
    },
    server: {
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
