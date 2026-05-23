<template>
  <div class="border-t border-outline-variant p-4 bg-white">
    <div class="flex items-end gap-2">
      <!-- Input area -->
      <div class="flex-1 relative">
        <div class="flex items-center gap-1.5 mb-2">
          <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
            <el-icon :size="18"><Plus /></el-icon>
          </button>
          <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
            <el-icon :size="18"><Paperclip /></el-icon>
          </button>
        </div>
        <textarea
          class="w-full min-h-[56px] max-h-[200px] p-3.5 bg-surface border border-outline-variant rounded-xl text-[13px] text-on-surface placeholder-on-surface-variant/60 outline-none resize-none focus:border-brand focus:shadow-glow transition-all duration-200 leading-relaxed"
          placeholder="Ask Nexus anything..."
          rows="2"
        ></textarea>
      </div>

      <!-- Action buttons column -->
      <div class="flex flex-col gap-2 pb-1">
        <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
          <el-icon :size="18"><Microphone /></el-icon>
        </button>
        <button
          class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center text-white shadow-soft hover:shadow-glow hover:scale-105 active:scale-95 transition-all duration-200"
        >
          <el-icon :size="18"><Promotion /></el-icon>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Plus, Paperclip, Microphone, Promotion } from '@element-plus/icons-vue'
</script>