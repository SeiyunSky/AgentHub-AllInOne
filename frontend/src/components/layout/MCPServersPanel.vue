<template>
  <PanelContainer :title="t('mcpServersPanel.title')" :icon="Connection" variant="brand">

    <div class="p-6 overflow-y-auto h-full custom-scrollbar">

      <!-- Filter Bar -->
      <div class="flex items-center gap-1.5 flex-wrap mb-5">
        <button
          v-for="f in filterOptions"
          :key="f.value"
          class="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all cursor-pointer whitespace-nowrap"
          :class="activeFilter === f.value
            ? 'bg-brand text-white shadow-soft'
            : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'"
          @click="activeFilter = f.value"
        >
          {{ f.label }}
        </button>
      </div>

      <!-- Empty state (no servers at all) -->
      <div
        v-if="!mcpServersStore.isLoading && filteredServers.length === 0 && mcpServersStore.servers.length === 0"
        class="flex flex-col items-center justify-center h-full min-h-[400px] fade-in-up"
      >
        <div class="w-20 h-20 rounded-3xl bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center mb-5 shadow-soft">
          <el-icon :size="36" class="text-brand"><Connection /></el-icon>
        </div>
        <h3 class="text-[16px] font-semibold text-on-surface mb-1.5">{{ t('mcpServersPanel.emptyTitle') }}</h3>
        <p class="text-[13px] text-on-surface-variant mb-5 text-center max-w-[260px]">
          {{ t('mcpServersPanel.emptyDesc') }}
        </p>
        <button class="btn-create" @click="router.push({ name: 'mcp-server-create' })">
          <el-icon :size="14"><Plus /></el-icon>
          {{ t('mcpServersPanel.createServer') }}
        </button>
      </div>

      <!-- No results (has servers but filtered to none) -->
      <div
        v-else-if="!mcpServersStore.isLoading && filteredServers.length === 0 && mcpServersStore.servers.length > 0"
        class="flex flex-col items-center justify-center h-64 text-on-surface-variant fade-in-up"
      >
        <el-icon :size="32" class="opacity-30 mb-3"><Search /></el-icon>
        <p class="text-[13px]">{{ t('mcpServersPanel.noMatch') }}</p>
      </div>

      <!-- Loading skeleton -->
      <div v-else-if="mcpServersStore.isLoading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        <div v-for="n in 6" :key="n" class="premium-card p-5 space-y-4">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-surface-container-high shimmer"></div>
            <div class="flex-1 space-y-2">
              <div class="h-3.5 rounded-md bg-surface-container-high shimmer w-3/5"></div>
              <div class="h-2.5 rounded-md bg-surface-container-high shimmer w-2/5"></div>
            </div>
          </div>
          <div class="space-y-2">
            <div class="h-3 rounded-md bg-surface-container-high shimmer w-full"></div>
            <div class="h-3 rounded-md bg-surface-container-high shimmer w-4/5"></div>
          </div>
          <div class="flex gap-2 pt-3 border-t border-outline-variant">
            <div class="h-5 w-14 rounded-full bg-surface-container-high shimmer"></div>
          </div>
        </div>
      </div>

      <!-- Server cards grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        <div
          v-for="server in filteredServers"
          :key="server.id"
          class="premium-card overflow-hidden cursor-pointer hover:-translate-y-0.5"
          @click="router.push({ name: 'mcp-server-edit', params: { mcpServerId: server.id } })"
        >
          <!-- Transport accent strip -->
          <div
            class="h-1"
            :class="server.transport === 'stdio'
              ? 'bg-gradient-to-r from-emerald-300 to-emerald-500'
              : server.transport === 'streamable_http'
                ? 'bg-gradient-to-r from-violet-300 to-violet-500'
                : 'bg-gradient-to-r from-blue-300 to-blue-500'"
          ></div>

          <div class="p-5">
            <div class="flex items-start gap-3 mb-3">
              <div
                class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border"
                :class="server.transport === 'stdio'
                  ? 'bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200/60 text-emerald-600'
                  : server.transport === 'streamable_http'
                    ? 'bg-gradient-to-br from-violet-50 to-violet-100 border-violet-200/60 text-violet-600'
                    : 'bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200/60 text-blue-600'"
              >
                <el-icon :size="18"><Monitor v-if="server.transport === 'stdio'" /><Connection v-else /></el-icon>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-[14px] font-semibold text-on-surface truncate">{{ server.name }}</p>
                <p class="text-[11px] text-on-surface-variant truncate">{{ server.description || t('mcpServersPanel.noDescription') }}</p>
              </div>
              <div
                class="shrink-0 mt-1.5"
                :class="server.isActive ? 'status-dot-active agent-pulse' : 'status-dot-inactive'"
                :title="server.isActive ? t('mcpServersPanel.tooltipActive') : t('mcpServersPanel.tooltipInactive')"
              ></div>
            </div>

            <div class="flex items-center justify-between">
              <span
                class="px-2 py-0.5 rounded-full text-[10px] font-medium"
                :class="server.transport === 'stdio'
                  ? 'bg-emerald-50 text-emerald-700'
                  : server.transport === 'streamable_http'
                    ? 'bg-violet-50 text-violet-700'
                    : 'bg-blue-50 text-blue-700'"
              >
                {{ server.transport }}
              </span>
              <span class="text-[11px] font-mono text-on-surface-variant truncate max-w-[120px]">
                {{ server.transport === 'stdio' ? server.command : server.url }}
              </span>
            </div>

            <!-- SAP OIDC 授权状态 + 按钮 -->
            <div
              v-if="isSapOidcServer(server.id)"
              class="mt-3 pt-3 border-t border-outline-variant flex items-center justify-between"
              @click.stop
            >
              <span
                class="text-[11px] flex items-center gap-1"
                :class="authStatuses[server.id]?.authorized ? 'text-emerald-600' : 'text-amber-600'"
              >
                <span
                  class="w-1.5 h-1.5 rounded-full"
                  :class="authStatuses[server.id]?.authorized ? 'bg-emerald-500' : 'bg-amber-500'"
                ></span>
                {{ authStatuses[server.id]?.authorized ? t('mcpServersPanel.sapAuthorized') : t('mcpServersPanel.sapNeedAuth') }}
              </span>
              <button
                class="text-[11px] px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
                :class="authingServer === server.id
                  ? 'bg-surface-container text-on-surface-variant cursor-wait'
                  : 'bg-brand-light text-brand hover:bg-brand/20'"
                :disabled="authingServer === server.id"
                @click.stop="authorizeServer(server.id)"
              >
                {{ authingServer === server.id ? t('mcpServersPanel.authorizing') : t('mcpServersPanel.authorize') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Connection, Monitor, Plus, Search } from '@element-plus/icons-vue'
import { useMCPServersStore } from '@/stores/mcp_servers'
import { mcpAuthApi, isSapOidcServer } from '@/api/mcp_auth'
import PanelContainer from '@/components/layout/PanelContainer.vue'

const { t } = useI18n()
const router = useRouter()
const mcpServersStore = useMCPServersStore()

const activeFilter = ref('all')

const filterOptions = computed(() => [
  { label: t('mcpServersPanel.filterAll'), value: 'all' },
  { label: t('mcpServersPanel.filterActive'), value: 'active' },
  { label: 'stdio', value: 'stdio' },
  { label: 'SSE', value: 'sse' },
  { label: 'Streamable HTTP', value: 'streamable_http' },
])

const filteredServers = computed(() => {
  const servers = mcpServersStore.servers
  if (activeFilter.value === 'active') return servers.filter(s => s.isActive)
  if (activeFilter.value === 'stdio') return servers.filter(s => s.transport === 'stdio')
  if (activeFilter.value === 'sse') return servers.filter(s => s.transport === 'sse')
  if (activeFilter.value === 'streamable_http') return servers.filter(s => s.transport === 'streamable_http')
  return servers
})

onMounted(async () => {
  if (mcpServersStore.servers.length === 0) {
    await mcpServersStore.loadServers()
  }
  // 加载 SAP OIDC 服务器的授权状态
  await refreshAllAuthStatuses()
})

// ── SAP OIDC 授权状态管理 ──

const authStatuses = ref<Record<string, { authorized: boolean; expires_at?: string | null }>>({})
const authingServer = ref<string | null>(null)

async function refreshAllAuthStatuses() {
  const sapServers = mcpServersStore.servers.filter(s => isSapOidcServer(s.id))
  for (const srv of sapServers) {
    try {
      const status = await mcpAuthApi.status(srv.id)
      authStatuses.value[srv.id] = { authorized: status.authorized, expires_at: status.expires_at }
    } catch {
      authStatuses.value[srv.id] = { authorized: false }
    }
  }
}

async function authorizeServer(serverId: string) {
  authingServer.value = serverId
  let pollingStarted = false
  try {
    const res = await mcpAuthApi.start(serverId)
    if (res.status === 'authorized') {
      authStatuses.value[serverId] = { authorized: true }
      ElMessage.success(t('mcpServersPanel.authSuccess'))
      return
    }
    if (res.auth_url) {
      window.open(res.auth_url, '_blank')
      pollingStarted = true

      // Poll authorization status every 3s, up to 1 minute
      let retries = 0
      const poll = setInterval(async () => {
        retries++
        if (retries > 20) {
          clearInterval(poll)
          if (authingServer.value === serverId) authingServer.value = null
          return
        }
        try {
          const status = await mcpAuthApi.status(serverId)
          if (status.authorized) {
            clearInterval(poll)
            authStatuses.value[serverId] = { authorized: true, expires_at: status.expires_at }
            ElMessage.success(t('mcpServersPanel.authSuccess'))
            authingServer.value = null
          }
        } catch {
          // ignore polling errors, keep retrying
        }
      }, 3000)
      return
    }
    ElMessage.error(res.message || t('mcpServersPanel.authFailed'))
  } catch {
    ElMessage.error(t('mcpServersPanel.authFailed'))
  } finally {
    // Don't clear authingServer if polling started — the poll interval manages it
    if (!pollingStarted && authingServer.value === serverId) authingServer.value = null
  }
}
</script>
