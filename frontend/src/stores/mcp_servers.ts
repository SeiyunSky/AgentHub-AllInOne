import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MCPServer } from '@/types/mcp_server'
import { mcpServersApi, type MCPServerResponse } from '@/api/mcp_servers'

function mapMCPServerResponse(s: MCPServerResponse): MCPServer {
  return {
    id: s.id,
    name: s.name,
    description: s.description,
    transport: s.transport,
    command: s.command,
    args: s.args ?? [],
    env: s.env ?? {},
    url: s.url,
    headers: s.headers ?? {},
    authorId: s.author_id,
    isPublic: s.is_public,
    isActive: s.is_active,
    createdAt: s.created_at,
    updatedAt: s.updated_at,
  }
}

export const useMCPServersStore = defineStore('mcpServers', () => {
  const servers = ref<MCPServer[]>([])
  const isLoading = ref(false)

  let loadPromise: Promise<void> | null = null

  async function loadServers() {
    if (loadPromise) return loadPromise
    loadPromise = (async () => {
      isLoading.value = true
      try {
        const data = await mcpServersApi.list()
        servers.value = data.map(mapMCPServerResponse)
      } finally {
        isLoading.value = false
        loadPromise = null
      }
    })()
    return loadPromise
  }

  function upsertServer(raw: MCPServerResponse) {
    const server = mapMCPServerResponse(raw)
    const idx = servers.value.findIndex(s => s.id === server.id)
    if (idx >= 0) {
      servers.value.splice(idx, 1, server)
    } else {
      servers.value.unshift(server)
    }
  }

  function removeServer(id: string) {
    const idx = servers.value.findIndex(s => s.id === id)
    if (idx >= 0) servers.value.splice(idx, 1)
  }

  return {
    servers,
    isLoading,
    loadServers,
    upsertServer,
    removeServer,
  }
})
