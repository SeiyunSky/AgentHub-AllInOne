<template>
  <div class="flex-1 bg-surface-elevated flex flex-col items-center justify-center">
    <div class="text-center px-6">
      <div class="w-14 h-14 rounded-2xl bg-surface-container flex items-center justify-center mx-auto mb-4 border border-outline-variant">
        <el-icon :size="28" class="text-on-surface-variant"><View /></el-icon>
      </div>
      <p class="text-[13px] font-medium text-on-surface mb-1">No artifact to preview</p>
      <p class="text-[11px] text-on-surface-variant max-w-xs">Select an artifact from the chat to preview it here. Supported: images, PDFs, code files, and more.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { View } from '@element-plus/icons-vue'
</script>