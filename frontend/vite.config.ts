import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// DEV_API_PROXY_TARGET lets docker-compose point this at the backend
// container's service name (e.g. http://backend:5001) instead of
// 127.0.0.1, since containers don't share a loopback interface. Unset for
// normal local dev — defaults to the same target as before.
const proxyTarget = process.env.DEV_API_PROXY_TARGET ?? 'http://127.0.0.1:5001'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // 0.0.0.0 so the dev server is reachable from outside a container;
    // still reachable via 127.0.0.1 for normal (non-Docker) local dev.
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
      '/health': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})
