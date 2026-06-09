<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">{{ t('mcpServersList.libraryTitle') }}</div>
    <div class="space-y-2">
      <!-- New MCP Server -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 border-2 border-dashed"
        :class="isSelected('new')
          ? 'border-brand bg-brand-light/40 text-brand'
          : 'border-outline-variant text-brand hover:border-brand/40 hover:bg-brand-light/20'"
        @click="router.push({ name: 'mcp-server-create' })"
      >
        <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-brand-light">
          <el-icon :size="16" class="text-brand"><Plus /></el-icon>
        </div>
        <span class="text-[13px] font-medium">{{ t('mcpServersList.newServer') }}</span>
      </div>
      <!-- Servers list -->
      <div
        v-for="server in mcpServersStore.servers"
        :key="server.id"
        class="group p-3 rounded-xl bg-white border cursor-pointer transition-all duration-200 hover-lift"
        :class="isSelected(server.id)
          ? 'border-brand bg-brand-light/30'
          : 'border-outline-variant hover:border-brand/40'"
        @click="router.push({ name: 'mcp-server-edit', params: { mcpServerId: server.id } })"
      >
        <div class="flex items-center gap-3">
          <div
            class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border"
            :class="server.transport === 'stdio'
              ? 'bg-emerald-50 border-emerald-200/60 text-emerald-600'
              : 'bg-blue-50 border-blue-200/60 text-blue-600'"
          >
            <el-icon :size="16"><Monitor v-if="server.transport === 'stdio'" /><Connection v-else /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[14px] font-semibold text-on-surface truncate">{{ server.name }}</p>
            <p class="text-[11px] text-on-surface-variant truncate">{{ server.description || t('mcpServersList.noDescription') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Monitor, Connection, Plus } from '@element-plus/icons-vue'
import { useMCPServersStore } from '@/stores/mcp_servers'

const router = useRouter()
const route = useRoute()
const mcpServersStore = useMCPServersStore()
const { t } = useI18n()

const currentServerId = computed(() => route.params.mcpServerId as string | undefined)

function isSelected(serverId: string) {
  if (serverId === 'new') {
    return route.name === 'mcp-server-create'
  }
  return route.name === 'mcp-server-edit' && currentServerId.value === serverId
}

onMounted(() => {
  mcpServersStore.loadServers()
})
</script>
