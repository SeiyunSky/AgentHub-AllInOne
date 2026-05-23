<template>
  <div class="border-t border-outline-variant px-4 py-3 bg-white">
    <div class="flex items-end gap-3">
      <!-- Input container -->
      <div class="flex-1 relative">
        <textarea
          class="w-full min-h-[48px] max-h-[200px] px-4 py-3 bg-surface border border-outline-variant rounded-xl text-[13px] text-on-surface placeholder-on-surface-variant/60 outline-none resize-none focus:border-brand focus:shadow-glow transition-all duration-200 leading-relaxed pr-10"
          placeholder="Ask Nexus anything..."
          rows="1"
        ></textarea>
        <!-- Inline action buttons (left side) -->
        <div class="absolute left-3 bottom-3 flex items-center gap-1">
          <button class="w-7 h-7 rounded-md flex items-center justify-center text-on-surface-variant/60 hover:text-on-surface-variant hover:bg-white transition-colors">
            <el-icon :size="16"><Plus /></el-icon>
          </button>
          <button class="w-7 h-7 rounded-md flex items-center justify-center text-on-surface-variant/60 hover:text-on-surface-variant hover:bg-white transition-colors">
            <el-icon :size="16"><Paperclip /></el-icon>
          </button>
        </div>
      </div>

      <!-- Send button -->
      <button
        class="w-10 h-10 rounded-xl bg-slate-700 flex items-center justify-center text-white shadow-soft hover:bg-slate-600 hover:shadow-float active:scale-95 transition-all duration-200"
      >
        <el-icon :size="20"><Promotion /></el-icon>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Plus, Paperclip, Promotion } from '@element-plus/icons-vue'
</script>