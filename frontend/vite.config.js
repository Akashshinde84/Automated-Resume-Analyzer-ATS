import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  if (process.env.VERCEL_ENV === 'production') {
    const url = new URL(env.VITE_API_BASE_URL || '')
    if (
      url.protocol !== 'https:' ||
      url.username ||
      url.password ||
      url.pathname !== '/' ||
      url.search ||
      url.hash ||
      ['localhost', '127.0.0.1'].includes(url.hostname)
    )
      throw new Error(
        'Production VITE_API_BASE_URL must be an HTTPS API origin',
      )
  }
  return {
    plugins: [react(), tailwindcss()],
    server: { port: 5173, strictPort: true },
  }
})
