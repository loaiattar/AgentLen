import path from 'node:path'
import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

const dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, dirname, '')
  const apiProxyTarget = env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000'
  // Read here, by the dev proxy, and nowhere else: without the VITE_ prefix
  // Vite never exposes it to client code, so the browser never holds it (#149).
  const apiKey = env.API_KEY ?? ''
  if (command === 'serve' && !apiKey) {
    console.warn('API_KEY is not set: the /api proxy sends no X-API-Key and the API will answer 401.')
  }

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
          // Lower-case, like Node's incoming header names, so it overwrites an
          // `x-api-key` a client sends instead of travelling next to it.
          ...(apiKey ? { headers: { 'x-api-key': apiKey } } : {}),
        },
      },
    },
  }
})
