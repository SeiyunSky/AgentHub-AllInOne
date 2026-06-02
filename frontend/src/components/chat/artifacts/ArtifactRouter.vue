<template>
  <div class="w-full h-full flex flex-col">
    <!-- Empty state -->
    <div v-if="!activeArtifact" class="flex-1 flex items-center justify-center text-on-surface-variant">
      <div class="text-center px-6">
        <div class="w-14 h-14 rounded-2xl bg-surface-container flex items-center justify-center mx-auto mb-4 border border-outline-variant">
          <el-icon :size="28"><View /></el-icon>
        </div>
        <p class="text-[13px] font-medium text-on-surface mb-1">No artifact to preview</p>
        <p class="text-[11px] text-on-surface-variant max-w-xs">Select an artifact from the chat to preview it here.</p>
      </div>
    </div>

    <!-- Edit mode: Monaco editor -->
    <div v-else-if="mode === 'edit'" class="flex-1 flex flex-col min-h-0">
      <div v-if="isLoadingContent" class="flex-1 flex items-center justify-center text-on-surface-variant">
        <el-icon class="animate-spin mr-2"><Loading /></el-icon>
        <span class="text-[12px]">Loading...</span>
      </div>
      <VueMonacoEditor
        v-else
        :value="editContent ?? ''"
        :language="monacoLanguage"
        :theme="monacoTheme"
        class="flex-1"
        :options="monacoOptions"
        @change="setEditContent"
      />
      <div class="flex items-center justify-end gap-2 px-3 py-2 border-t border-outline-variant bg-surface-container">
        <span v-if="isSaving" class="text-[11px] text-on-surface-variant flex items-center gap-1">
          <el-icon class="animate-spin"><Loading /></el-icon>
          Saving...
        </span>
        <button
          class="px-3 py-1 rounded-md text-[12px] font-medium bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-50"
          :disabled="isSaving"
          @click="saveFileContent"
        >
          Save
        </button>
      </div>
    </div>

    <!-- Preview mode: renderer dispatch -->
    <template v-else>
      <!-- HTML iframe -->
      <iframe
        v-if="rendererType === 'iframe'"
        :srcdoc="iframeSrcdoc"
        sandbox="allow-scripts"
        class="flex-1 w-full h-full border-0 bg-white"
      />
      <!-- SVG -->
      <div
        v-else-if="rendererType === 'svg'"
        class="flex-1 flex items-center justify-center p-6 bg-surface-container-low"
        v-html="sanitizedSvg"
      />
      <!-- Image -->
      <div v-else-if="rendererType === 'image'" class="flex-1 flex items-center justify-center p-6 bg-surface-container-low">
        <img :src="activeArtifact?.item.preview" :alt="activeArtifact?.item.name" class="max-w-full max-h-full object-contain" />
      </div>
      <!-- Code fallback -->
      <div v-else-if="rendererType === 'code'" class="flex-1 overflow-auto p-4 bg-surface-container-low">
        <pre class="text-[12px] leading-relaxed font-mono text-on-surface" style="white-space: pre-wrap; word-wrap: break-word; margin: 0">{{ liveContent }}</pre>
      </div>
      <!-- Unknown -->
      <div v-else class="flex-1 flex items-center justify-center text-on-surface-variant">
        <p class="text-[13px]">No preview available for this artifact type.</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'
import { View, Loading } from '@element-plus/icons-vue'
import { useArtifactPreview } from '@/composables/useArtifactPreview'

withDefaults(defineProps<{
  mode?: 'preview' | 'edit'
}>(), {
  mode: 'preview',
})

const {
  activeArtifact,
  rendererType,
  sanitizedSvg,
  iframeSrcdoc,
  liveContent,
  isSaving,
  isLoadingContent,
  saveFileContent,
  editContent,
  setEditContent,
} = useArtifactPreview()

const monacoLanguage = computed(() => {
  const t = (activeArtifact.value?.item.mimeType ?? activeArtifact.value?.item.type ?? '').toLowerCase()
  if (t === 'text/html' || t === 'html') return 'html'
  if (t === 'image/svg+xml' || t === 'svg') return 'xml'
  if (t === 'application/json' || t === 'json') return 'json'
  if (t === 'python') return 'python'
  if (t === 'typescript') return 'typescript'
  if (t === 'javascript') return 'javascript'
  return 'plaintext'
})

const prefersDark = window.matchMedia('(prefers-color-scheme: dark)')
const monacoTheme = ref(prefersDark.matches ? 'vs-dark' : 'vs')

function onSchemeChange(e: MediaQueryListEvent) {
  monacoTheme.value = e.matches ? 'vs-dark' : 'vs'
}
onMounted(() => prefersDark.addEventListener('change', onSchemeChange))
onUnmounted(() => prefersDark.removeEventListener('change', onSchemeChange))

const monacoOptions = {
  minimap: { enabled: false },
  fontSize: 13,
  lineHeight: 20,
  scrollBeyondLastLine: false,
  wordWrap: 'on' as const,
  tabSize: 2,
}
</script>
