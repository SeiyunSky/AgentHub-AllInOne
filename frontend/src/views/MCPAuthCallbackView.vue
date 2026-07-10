<template>
  <div class="flex flex-col items-center justify-center h-screen gap-3">
    <div v-if="success" class="flex flex-col items-center gap-2 text-emerald-600">
      <el-icon :size="48"><CircleCheck /></el-icon>
      <p class="text-[15px] font-semibold">授权成功</p>
      <p class="text-[12px] text-on-surface-variant">此页面将自动关闭</p>
    </div>
    <div v-else class="flex flex-col items-center gap-2 text-on-surface-variant">
      <el-icon :size="48" class="animate-spin"><Loading /></el-icon>
      <p class="text-[14px]">正在处理授权...</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { CircleCheck, Loading } from '@element-plus/icons-vue'

const success = ref(false)

onMounted(() => {
  if (window.opener) {
    window.opener.postMessage({ type: 'mcp-auth-success' }, '*')
    success.value = true
    setTimeout(() => window.close(), 1500)
  } else {
    // 不是弹窗打开的（例如直接访问），简单展示成功
    success.value = true
  }
})
</script>
