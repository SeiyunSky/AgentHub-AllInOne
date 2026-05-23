<template>
  <div class="px-4 h-14 border-b border-outline-variant flex justify-between items-center shrink-0 bg-white">
    <div class="flex flex-col">
      <h2 class="text-sm font-semibold text-on-surface">{{ title }}</h2>
      <p class="text-[11px] text-on-surface-variant flex items-center gap-1.5">
        <span class="w-1.5 h-1.5 bg-success rounded-full shadow-sm shadow-success/50"></span>
        {{ status }}
      </p>
    </div>
    <div class="flex items-center gap-1">
      <el-button circle text size="small" class="!text-on-surface-variant hover:!bg-surface-container">
        <el-icon :size="16"><MoreFilled /></el-icon>
      </el-button>
      <el-button circle text size="small" class="!text-on-surface-variant hover:!bg-surface-container" @click="uiStore.rightPanelVisible = !uiStore.rightPanelVisible">
        <el-icon :size="16">
          <ArrowRight v-if="uiStore.rightPanelVisible" />
          <ArrowLeft v-else />
        </el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useUIStore } from '@/stores/ui'
import { MoreFilled, ArrowRight, ArrowLeft } from '@element-plus/icons-vue'

const uiStore = useUIStore()

const title = 'Active Thread'
const status = '3 agents listening'
</script>