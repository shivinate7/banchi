import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Port 5173 is not Vite's default acting by accident — CLAUDE.md and the Makefile's `dev`
// target both promise :5173, and scripts/views.txt points the screenshot runner there.
// strictPort so a busy port fails loudly instead of serving on 5174, where every one of
// those three would be quietly wrong.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
})
