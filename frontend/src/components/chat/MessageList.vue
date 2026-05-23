<template>
  <div class="px-5 py-6 space-y-5">
    <!-- Agent message -->
    <div class="flex gap-3 message-enter">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center shrink-0 border border-brand/20 ring-2 ring-brand/10">
        <el-icon class="text-brand" :size="16"><User /></el-icon>
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1.5">
          <span class="text-[12px] font-semibold text-on-surface">Orchestrator</span>
          <span class="text-[10px] bg-brand-light text-brand font-semibold px-2 py-0.5 rounded-md uppercase">Host</span>
          <span class="text-[10px] text-on-surface-variant">2m ago</span>
        </div>
        <div class="p-4 bg-white border border-outline-variant rounded-2xl rounded-tl-md shadow-soft">
          <p class="text-[13px] leading-relaxed text-on-surface">I'll analyze the sales data and coordinate with the team. Let me dispatch tasks to the relevant agents.</p>
        </div>
      </div>
    </div>

    <!-- User message -->
    <div class="flex gap-3 justify-end message-enter">
      <div class="max-w-[70%]">
        <div class="p-4 bg-gradient-to-br from-brand to-brand-dark text-white rounded-2xl rounded-tr-md shadow-soft">
          <p class="text-[13px] leading-relaxed">Can you help me process the Q4 sales data and generate a summary report?</p>
        </div>
      </div>
      <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-soft">U</div>
    </div>

    <!-- Agent message with processing status -->
    <div class="flex gap-3 message-enter">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-warning-light to-amber-100 flex items-center justify-center shrink-0 border border-warning/20 ring-2 ring-warning/10">
        <el-icon class="text-amber-600" :size="16"><User /></el-icon>
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1.5">
          <span class="text-[12px] font-semibold text-on-surface">Data Analyst</span>
          <span class="text-[10px] bg-warning-light text-amber-700 font-semibold px-2 py-0.5 rounded-md uppercase">Processing</span>
          <span class="text-[10px] text-on-surface-variant">just now</span>
        </div>
        <div class="p-4 bg-white border border-outline-variant rounded-2xl rounded-tl-md shadow-soft">
          <p class="text-[13px] leading-relaxed text-on-surface">Found 3 CSV files in the target directory. Processing records...</p>
          <!-- Code block -->
          <div class="mt-3 rounded-xl overflow-hidden border border-neutral-800">
            <div class="bg-neutral-900 px-3 py-1.5 flex items-center gap-2 border-b border-neutral-800">
              <div class="flex gap-1.5">
                <span class="w-2.5 h-2.5 rounded-full bg-red-500/80"></span>
                <span class="w-2.5 h-2.5 rounded-full bg-yellow-500/80"></span>
                <span class="w-2.5 h-2.5 rounded-full bg-green-500/80"></span>
              </div>
              <span class="text-[10px] text-neutral-500 font-mono ml-1">sales_q4.csv</span>
            </div>
            <div class="p-3 bg-neutral-900/95 text-xs font-mono leading-relaxed">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-neutral-500 select-none">1</span>
                <span class="text-neutral-400">sales_q4.csv</span>
                <span class="text-success">+142 -3</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-neutral-500 select-none">2</span>
                <span class="text-sky-400">import</span>
                <span class="text-amber-300">pandas</span>
                <span class="text-sky-400">as</span>
                <span class="text-amber-300">pd</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-neutral-500 select-none">3</span>
                <span class="text-amber-300">df</span>
                <span class="text-neutral-400">=</span>
                <span class="text-amber-300">pd</span>
                <span class="text-neutral-400">.</span>
                <span class="text-blue-400">read_csv</span>
                <span class="text-neutral-400">(</span>
                <span class="text-emerald-400">'sales_q4.csv'</span>
                <span class="text-neutral-400">)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Typing indicator -->
    <div class="flex gap-3 message-enter">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center shrink-0 border border-brand/20">
        <el-icon class="text-brand" :size="16"><User /></el-icon>
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1.5">
          <span class="text-[12px] font-semibold text-on-surface">Orchestrator</span>
          <span class="text-[10px] text-on-surface-variant">typing</span>
        </div>
        <div class="p-4 bg-white border border-outline-variant rounded-2xl rounded-tl-md shadow-soft inline-flex items-center gap-1.5">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { User } from '@element-plus/icons-vue'
</script>