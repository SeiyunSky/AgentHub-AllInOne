import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sandboxApi } from '@/api/sandbox'
import type { SandboxFileNode } from '@/types/sandbox'

export const useSandboxFilesStore = defineStore('sandboxFiles', () => {
  // 按 convId 缓存:每个会话的沙箱文件列表
  const filesByConv = ref<Map<string, SandboxFileNode[]>>(new Map())
  const loadingByConv = ref<Map<string, boolean>>(new Map())
  const errorByConv = ref<Map<string, string>>(new Map())

  // SSE 触发 loadFiles 时的 debounce 计时器(每个 conv 一个)
  const debounceTimers = new Map<string, ReturnType<typeof setTimeout>>()

  function getFiles(convId: string): SandboxFileNode[] {
    return filesByConv.value.get(convId) ?? []
  }

  function isLoading(convId: string): boolean {
    return loadingByConv.value.get(convId) ?? false
  }

  function getError(convId: string): string | undefined {
    return errorByConv.value.get(convId)
  }

  async function loadFiles(convId: string): Promise<void> {
    if (!convId) return
    loadingByConv.value.set(convId, true)
    errorByConv.value.delete(convId)
    try {
      const files = await sandboxApi.list(convId)
      filesByConv.value.set(convId, files)
      // 触发响应式更新(Map mutation 不会自动通知)
      filesByConv.value = new Map(filesByConv.value)
    } catch (e) {
      errorByConv.value.set(convId, String(e))
    } finally {
      loadingByConv.value.set(convId, false)
      loadingByConv.value = new Map(loadingByConv.value)
    }
  }

  /** SSE 收到写文件事件后调:延后 500ms 刷新,合并连续多次写文件触发 */
  function loadFilesDebounced(convId: string, delay = 500): void {
    if (!convId) return
    const existing = debounceTimers.get(convId)
    if (existing) clearTimeout(existing)
    const t = setTimeout(() => {
      debounceTimers.delete(convId)
      void loadFiles(convId)
    }, delay)
    debounceTimers.set(convId, t)
  }

  return {
    filesByConv,
    loadingByConv,
    errorByConv,
    getFiles,
    isLoading,
    getError,
    loadFiles,
    loadFilesDebounced,
  }
})
