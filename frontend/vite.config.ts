import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { viteMockServe } from 'vite-plugin-mock'
import { fileURLToPath, URL } from 'node:url'
import type { Connect } from 'vite'

const MOCK_AGENTS: Connect.SimpleHandleFunction = (_req, res) => {
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify([
    {
      id: 'agent-research-builtin',
      user_id: 'GUGA',
      name: '调研 Agent',
      description: '专业信息收集与结构化报告输出，适合市场调研、技术选型、资料汇总等任务',
      type: 'claude',
      capabilities: {},
      tags: [],
      is_public: true,
      is_active: true,
      skill_ids: [],
      created_at: '2026-05-01T00:00:00Z',
      updated_at: '2026-05-01T00:00:00Z',
    },
  ]))
}

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    viteMockServe({
      mockPath: 'mock',
      enable: true,
    }),
    {
      name: 'mock-agents',
      configureServer(server) {
        server.middlewares.use('/api/v1/agents', (req, res, next) => {
          if (req.method === 'GET') return MOCK_AGENTS(req, res)
          next()
        })
      },
    },
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
