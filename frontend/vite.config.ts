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
    build: {
      // Lowered, not raised. The single 514 kB bundle sat just above Vite's
      // 500 kB default, so the warning had become background noise. The entry
      // chunk is ~370 kB once the routes are split; 400 leaves room to breathe
      // and trips again well before the old size comes back.
      chunkSizeWarningLimit: 400,
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
