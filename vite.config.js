import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  build: {
    // TEMPORAL: sourcemaps + dev React para diagnosticar error #130 minificado.
    // Quitar después de fix (el bundle pesa ~3x más así).
    sourcemap: true,
    minify: false,
  },
  define: {
    // React dev build → mensajes de error completos en producción.
    'process.env.NODE_ENV': JSON.stringify('development'),
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://yokochat.vercel.app',
        changeOrigin: true,
        secure: true,
      },
    },
  },
})
