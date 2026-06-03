<template>
  <div class="flex flex-col h-full bg-surface">
    <!-- Toolbar -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-outline-variant bg-white">
      <span class="text-[11px] uppercase font-semibold tracking-widest text-on-surface-variant">
        Sandbox · {{ files.length }} {{ files.length === 1 ? 'file' : 'files' }}
      </span>
      <div class="flex-1" />
      <button
        class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors disabled:opacity-50"
        :disabled="loading"
        :title="loading ? 'Loading...' : 'Refresh'"
        @click="refresh"
      >
        <el-icon :size="14" :class="{ 'animate-spin': loading }">
          <Refresh />
        </el-icon>
      </button>
    </div>

    <!-- Body -->
    <div class="flex-1 overflow-y-auto custom-scrollbar px-4 py-4 space-y-2">
      <!-- No conversation -->
      <div v-if="!convId" class="flex flex-col items-center justify-center h-full text-on-surface-variant text-center px-6 py-12">
        <div class="w-14 h-14 rounded-2xl bg-surface-container flex items-center justify-center mb-4 border border-outline-variant">
          <el-icon :size="28"><FolderOpened /></el-icon>
        </div>
        <p class="text-[13px] font-medium text-on-surface mb-1">No conversation selected</p>
      </div>

      <!-- Error -->
      <div v-else-if="errorMsg" class="flex flex-col items-center justify-center h-full text-on-surface-variant text-center px-6 py-12">
        <div class="w-14 h-14 rounded-2xl bg-error-light flex items-center justify-center mb-4">
          <el-icon :size="28" class="text-error"><WarningFilled /></el-icon>
        </div>
        <p class="text-[13px] font-medium text-error mb-1">Failed to load files</p>
        <p class="text-[11px] text-on-surface-variant max-w-xs">{{ errorMsg }}</p>
      </div>

      <!-- Empty -->
      <div v-else-if="!loading && files.length === 0" class="flex flex-col items-center justify-center h-full text-on-surface-variant text-center px-6 py-12">
        <div class="w-14 h-14 rounded-2xl bg-surface-container flex items-center justify-center mb-4 border border-outline-variant">
          <el-icon :size="28"><FolderOpened /></el-icon>
        </div>
        <p class="text-[13px] font-medium text-on-surface mb-1">No files yet</p>
        <p class="text-[11px] text-on-surface-variant max-w-xs">
          When the agent creates a file in this conversation, it will appear here.
        </p>
      </div>

      <!-- File list -->
      <template v-else>
        <div
          v-for="file in files"
          :key="file.path"
          class="group p-3 rounded-xl bg-white border cursor-pointer transition-all duration-200 hover-lift"
          :class="isActive(file)
            ? 'border-brand bg-brand-light/30'
            : 'border-outline-variant hover:border-brand/40'"
          @click="handleClick(file)"
        >
          <div class="flex items-center gap-3">
            <!-- Icon -->
            <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" :class="iconBgClass(file)">
              <el-icon :size="16" :class="iconColorClass(file)">
                <component :is="iconFor(file)" />
              </el-icon>
            </div>

            <!-- Name + meta -->
            <div class="flex-1 min-w-0">
              <div class="text-[13px] font-medium text-on-surface truncate">{{ file.path }}</div>
              <div class="text-[10px] text-on-surface-variant flex items-center gap-2 mt-0.5">
                <span>{{ formatSize(file.size) }}</span>
                <span>·</span>
                <span>{{ formatTime(file.mtime) }}</span>
              </div>
            </div>

            <!-- Actions (hover) -->
            <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                v-if="isPreviewable(file)"
                class="w-7 h-7 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-brand-light hover:text-brand transition-colors"
                title="Preview"
                @click.stop="handlePreview(file)"
              >
                <el-icon :size="14"><View /></el-icon>
              </button>
              <button
                class="w-7 h-7 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
                title="Edit"
                @click.stop="handleEdit(file)"
              >
                <el-icon :size="14"><Edit /></el-icon>
              </button>
              <button
                class="w-7 h-7 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
                title="Download"
                @click.stop="handleDownload(file)"
              >
                <el-icon :size="14"><Download /></el-icon>
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import {
  Refresh,
  View,
  Edit,
  Download,
  Document,
  Picture,
  Folder,
  FolderOpened,
  WarningFilled,
} from '@element-plus/icons-vue'
import { useConversationsStore } from '@/stores/conversations'
import { useSandboxFilesStore } from '@/stores/sandboxFiles'
import { useArtifactPreview } from '@/composables/useArtifactPreview'
import { sandboxApi } from '@/api/sandbox'
import type { SandboxFileNode } from '@/types/sandbox'
import type { ArtifactItem, ArtifactKind } from '@/types/artifact'

const conversationsStore = useConversationsStore()
const filesStore = useSandboxFilesStore()
const { openArtifact, activeArtifact } = useArtifactPreview()

const convId = computed(() => conversationsStore.currentId ?? '')
const files = computed(() => filesStore.getFiles(convId.value).filter(f => !f.isDir))
const loading = computed(() => filesStore.isLoading(convId.value))
const errorMsg = computed(() => filesStore.getError(convId.value))

function refresh() {
  if (convId.value) void filesStore.loadFiles(convId.value)
}

onMounted(() => {
  if (convId.value) void filesStore.loadFiles(convId.value)
})

watch(convId, (newId) => {
  if (newId) void filesStore.loadFiles(newId)
})

// ----------- 文件类型判断 -----------

function extOf(file: SandboxFileNode): string {
  const idx = file.name.lastIndexOf('.')
  return idx === -1 ? '' : file.name.slice(idx + 1).toLowerCase()
}

// 二进制类型黑名单:除此之外都能预览(文本不识别也走 plaintext 兜底)
const BIN_EXTS = new Set([
  'exe', 'dll', 'so', 'dylib', 'bin', 'class',
  'zip', 'tar', 'gz', 'tgz', 'bz2', '7z', 'rar', 'xz',
  'pdf', 'docx', 'xlsx', 'pptx', 'odt', 'ods',
  'mp3', 'mp4', 'mov', 'avi', 'wav', 'flac', 'ogg', 'webm', 'mkv',
  'ttf', 'otf', 'woff', 'woff2', 'eot',
])

function isPreviewable(file: SandboxFileNode): boolean {
  const e = extOf(file)
  if (BIN_EXTS.has(e)) return false
  return true
}

function iconFor(file: SandboxFileNode) {
  const e = extOf(file)
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico'].includes(e)) return Picture
  if (file.isDir) return Folder
  return Document
}

function iconBgClass(file: SandboxFileNode): string {
  const e = extOf(file)
  if (e === 'html') return 'bg-orange-50'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(e)) return 'bg-violet-50'
  if (['md', 'txt'].includes(e)) return 'bg-blue-50'
  if (['py', 'js', 'ts', 'tsx', 'vue'].includes(e)) return 'bg-emerald-50'
  return 'bg-surface-container'
}

function iconColorClass(file: SandboxFileNode): string {
  const e = extOf(file)
  if (e === 'html') return 'text-orange-500'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(e)) return 'text-violet-500'
  if (['md', 'txt'].includes(e)) return 'text-blue-500'
  if (['py', 'js', 'ts', 'tsx', 'vue'].includes(e)) return 'text-emerald-500'
  return 'text-on-surface-variant'
}

// ----------- 格式化 -----------

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(mtime: number): string {
  const d = new Date(mtime * 1000)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) {
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString()
}

// ----------- 预览 / 编辑 / 下载 -----------

function buildArtifactItem(file: SandboxFileNode): ArtifactItem {
  const e = extOf(file)
  // mimeType 主要用于 useArtifactPreview 的 fallback 路径(name/path 没扩展名时);
  // 沙箱文件总有 path,所以这里给个粗略 mimeType 即可
  let mimeType: ArtifactKind | undefined
  if (e === 'html' || e === 'htm') mimeType = 'text/html'
  else if (e === 'svg') mimeType = 'image/svg+xml'
  else if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico'].includes(e)) mimeType = 'image/*'
  else if (e === 'json') mimeType = 'application/json'
  else mimeType = 'text/plain'

  return {
    name: file.name,
    type: e || 'text',
    mimeType,
    convId: convId.value,
    path: file.path,
    // preview 字段留空,让 useArtifactPreview.loadFileContent 自己拉
  }
}

function isActive(file: SandboxFileNode): boolean {
  const a = activeArtifact.value
  return !!a && a.item.convId === convId.value && a.item.path === file.path
}

function handleClick(file: SandboxFileNode) {
  // 行体点击 = Preview 默认行为
  handlePreview(file)
}

function handlePreview(file: SandboxFileNode) {
  openArtifact('', buildArtifactItem(file), 0)
}

function handleEdit(file: SandboxFileNode) {
  openArtifact('', buildArtifactItem(file), 0)
  // 切到 edit 模式由 RightPanel 头部按钮控制,这里先打开预览;
  // 用户想直接进 edit 可点 Edit toggle
}

async function handleDownload(file: SandboxFileNode) {
  // axios 拦截器处理认证;直接 fetch + blob 触发浏览器下载
  // (因为 <a href> 不会自动带 Authorization header)
  const url = sandboxApi.downloadUrl(convId.value, file.path)
  const token = localStorage.getItem('auth.access_token')
  try {
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) {
      console.error('[Sandbox] download failed', res.status)
      return
    }
    const blob = await res.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = file.name
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  } catch (e) {
    console.error('[Sandbox] download error', e)
  }
}
</script>

<style scoped>
.hover-lift {
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.hover-lift:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
</style>
