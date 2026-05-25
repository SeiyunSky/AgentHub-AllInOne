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

    <!-- Code mode (force show code) -->
    <div v-else-if="mode === 'code'" class="flex-1 overflow-auto p-4 bg-surface-container-low">
      <pre class="text-[12px] leading-relaxed font-mono text-on-surface" style="white-space: pre-wrap; word-wrap: break-word; margin: 0">{{ activeArtifact.item.preview }}</pre>
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
        <pre class="text-[12px] leading-relaxed font-mono text-on-surface" style="white-space: pre-wrap; word-wrap: break-word; margin: 0">{{ activeArtifact?.item.preview }}</pre>
      </div>
      <!-- Unknown -->
      <div v-else class="flex-1 flex items-center justify-center text-on-surface-variant">
        <p class="text-[13px]">No preview available for this artifact type.</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { View } from '@element-plus/icons-vue'
import { useArtifactPreview } from '@/composables/useArtifactPreview'

withDefaults(defineProps<{
  mode?: 'preview' | 'code'
}>(), {
  mode: 'preview',
})

const { activeArtifact, rendererType, sanitizedSvg, iframeSrcdoc } = useArtifactPreview()
</script>
