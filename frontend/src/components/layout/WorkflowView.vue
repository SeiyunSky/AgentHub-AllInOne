<template>
  <div class="flex-1 node-connector relative overflow-hidden px-5 py-6">
    <!-- Workflow visualization -->
    <div class="flex flex-col items-center gap-6">
      <!-- Node 1: Completed -->
      <div class="bg-white border border-success/30 rounded-2xl p-4 w-64 shadow-soft">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-success-light flex items-center justify-center border border-success/20">
            <el-icon class="text-success" :size="18"><Download /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">Fetch Data</p>
            <p class="text-[11px] text-success font-medium">COMPLETED</p>
          </div>
          <span class="text-[11px] text-on-surface-variant font-mono">2.4s</span>
        </div>
      </div>

      <!-- Connector -->
      <div class="flex flex-col items-center gap-1">
        <div class="w-0.5 h-4 bg-success rounded-full"></div>
        <div class="w-2 h-2 bg-success rounded-full shadow-sm shadow-success/50"></div>
        <div class="w-0.5 h-4 bg-outline-variant rounded-full"></div>
      </div>

      <!-- Node 2: Running -->
      <div class="bg-white border-2 border-brand rounded-2xl p-4 w-64 shadow-card agent-pulse">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-brand-light flex items-center justify-center border border-brand/20">
            <el-icon class="text-brand" :size="18"><RefreshRight /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">Process CSV</p>
            <p class="text-[11px] text-brand font-medium">RUNNING</p>
          </div>
        </div>
        <div class="mt-3">
          <div class="h-1.5 bg-surface-container rounded-full overflow-hidden">
            <div class="h-full progress-fill rounded-full" style="width: 66%"></div>
          </div>
          <p class="text-[11px] text-on-surface-variant mt-1.5 font-medium">Data Analyst • 2/3 records</p>
        </div>
      </div>

      <!-- Connector -->
      <div class="flex flex-col items-center gap-1">
        <div class="w-0.5 h-4 bg-outline-variant rounded-full"></div>
        <div class="w-2 h-2 bg-outline-variant rounded-full"></div>
        <div class="w-0.5 h-4 bg-outline-variant rounded-full"></div>
      </div>

      <!-- Node 3: Pending -->
      <div class="bg-white border border-outline-variant rounded-2xl p-4 w-64 shadow-soft opacity-50">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-surface-container flex items-center justify-center border border-outline-variant">
            <el-icon class="text-on-surface-variant" :size="18"><Upload /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">Upload Results</p>
            <p class="text-[11px] text-on-surface-variant font-medium">PENDING</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Download, RefreshRight, Upload } from '@element-plus/icons-vue'
</script>