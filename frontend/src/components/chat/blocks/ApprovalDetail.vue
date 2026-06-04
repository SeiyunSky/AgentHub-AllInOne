<template>
  <div class="space-y-2">
    <!-- create_file: path + size + 折叠的 content -->
    <template v-if="action === 'create_file' && parsed">
      <div class="flex items-center gap-2 flex-wrap text-[12px]">
        <el-icon :size="13" class="text-emerald-600"><Document /></el-icon>
        <span class="font-mono text-on-surface font-medium">{{ parsed.path }}</span>
        <span class="text-on-surface-variant/60">·</span>
        <span class="text-[11px] text-on-surface-variant font-mono">{{ formatBytes(contentBytes) }}</span>
        <span v-if="lang" class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-400/15 text-sky-600">{{ lang }}</span>
        <span v-if="lineCount" class="text-[10px] text-on-surface-variant/50 ml-auto">{{ lineCount }} lines</span>
      </div>

      <div class="rounded-lg border border-outline-variant bg-[#f6f8fa] overflow-hidden">
        <div
          class="flex items-center gap-1.5 px-2 py-1 cursor-pointer select-none hover:bg-black/[0.02]"
          @click="expandedContent = !expandedContent"
        >
          <el-icon :size="12" class="text-on-surface-variant transition-transform" :class="{ 'rotate-90': expandedContent }">
            <ArrowRight />
          </el-icon>
          <span class="text-[11px] text-on-surface-variant">{{ expandedContent ? 'Hide content' : 'Show content' }}</span>
        </div>
        <pre v-if="expandedContent" class="text-[11px] font-mono px-3 py-2 overflow-x-auto leading-relaxed max-h-[320px] overflow-y-auto whitespace-pre"><code>{{ parsed.content }}</code></pre>
      </div>
    </template>

    <!-- edit_file: path + 双块 old/new 对比 -->
    <template v-else-if="action === 'edit_file' && parsed">
      <div class="flex items-center gap-2 flex-wrap text-[12px]">
        <el-icon :size="13" class="text-amber-600"><Edit /></el-icon>
        <span class="font-mono text-on-surface font-medium">{{ parsed.path }}</span>
        <span v-if="lang" class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-400/15 text-sky-600">{{ lang }}</span>
      </div>

      <div class="rounded-lg border border-outline-variant overflow-hidden">
        <div
          class="flex items-center gap-1.5 px-2 py-1 bg-[#f6f8fa] cursor-pointer select-none hover:bg-black/[0.02]"
          @click="expandedContent = !expandedContent"
        >
          <el-icon :size="12" class="text-on-surface-variant transition-transform" :class="{ 'rotate-90': expandedContent }">
            <ArrowRight />
          </el-icon>
          <span class="text-[11px] text-on-surface-variant">{{ expandedContent ? 'Hide diff' : 'Show diff' }}</span>
        </div>
        <div v-if="expandedContent" class="bg-white">
          <div class="px-3 py-1 text-[10px] font-mono text-red-600 bg-red-50 border-b border-red-100">- old</div>
          <pre class="text-[11px] font-mono px-3 py-2 overflow-x-auto leading-relaxed max-h-[200px] overflow-y-auto whitespace-pre bg-red-50/30 text-red-900"><code>{{ parsed.old_text }}</code></pre>
          <div class="px-3 py-1 text-[10px] font-mono text-emerald-600 bg-emerald-50 border-b border-t border-emerald-100">+ new</div>
          <pre class="text-[11px] font-mono px-3 py-2 overflow-x-auto leading-relaxed max-h-[200px] overflow-y-auto whitespace-pre bg-emerald-50/30 text-emerald-900"><code>{{ parsed.new_text }}</code></pre>
        </div>
      </div>
    </template>

    <!-- 其他工具 / 解析失败:兜底显示原文(可折叠) -->
    <template v-else>
      <div class="rounded-lg border border-outline-variant bg-[#f6f8fa] overflow-hidden">
        <div
          class="flex items-center gap-1.5 px-2 py-1 cursor-pointer select-none hover:bg-black/[0.02]"
          @click="expandedContent = !expandedContent"
        >
          <el-icon :size="12" class="text-on-surface-variant transition-transform" :class="{ 'rotate-90': expandedContent }">
            <ArrowRight />
          </el-icon>
          <span class="text-[11px] text-on-surface-variant">
            {{ expandedContent ? 'Hide details' : `Show details (${formatBytes(rawBytes)})` }}
          </span>
        </div>
        <pre v-if="expandedContent" class="text-[11px] font-mono px-3 py-2 overflow-x-auto leading-relaxed max-h-[320px] overflow-y-auto whitespace-pre-wrap break-all">{{ rawDetail }}</pre>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Document, Edit, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps<{
  action: string
  detail: string
}>()

// approval 详情默认折叠,避免几十 KB content 直接撑满消息流
const expandedContent = ref(false)

// 后端 detail 现在是 JSON 字符串(tool_input 的序列化结果),解析失败兜底原文展示
const parsed = computed<Record<string, string> | null>(() => {
  try {
    const obj = JSON.parse(props.detail)
    if (obj && typeof obj === 'object') return obj as Record<string, string>
  } catch { /* not JSON */ }
  return null
})

const rawDetail = computed(() => {
  if (!parsed.value) return props.detail
  // 已结构化但走到兜底分支(非 create_file/edit_file)时美化 JSON
  try { return JSON.stringify(parsed.value, null, 2) } catch { return props.detail }
})

const contentBytes = computed(() => {
  const c = parsed.value?.content ?? ''
  return new Blob([c]).size
})

const rawBytes = computed(() => new Blob([rawDetail.value]).size)

const lineCount = computed(() => {
  const c = parsed.value?.content
  if (!c) return 0
  return c.split('\n').length
})

const lang = computed(() => {
  const path = parsed.value?.path
  if (!path) return ''
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  const map: Record<string, string> = {
    ts: 'TypeScript', tsx: 'TSX', js: 'JavaScript', jsx: 'JSX',
    py: 'Python', go: 'Go', rs: 'Rust', java: 'Java',
    html: 'HTML', css: 'CSS', scss: 'SCSS',
    json: 'JSON', yaml: 'YAML', yml: 'YAML', md: 'Markdown',
    sh: 'Shell', sql: 'SQL', vue: 'Vue', xml: 'XML',
  }
  return map[ext] ?? ext.toUpperCase()
})

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
</script>
