import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 一次部署事件 — 由 deploy_app 工具的 tool_use block_stop 事件触发追加。
 *
 * 同一会话多次部署累积成历史(用户改 bug 后重新部署),
 * 最新的 active 设为 true,旧的 active 设为 false 但保留可见。
 */
export interface Deployment {
  id: string                       // tool_use block_id (LLM 给的 call.id)
  conversationId: string
  url: string                      // /preview/{conv_id}/
  entryPoint: string               // app.py / main.py
  status: 'running' | 'error'
  active: boolean                  // 是否最新成功部署(同会话只会有一个 active)
  startedAt: number                // epoch ms
  logs?: string
  errorMessage?: string
}

export const useDeploymentsStore = defineStore('deployments', () => {
  // per-conversation 部署历史(末尾是最新)
  const byConv = ref<Map<string, Deployment[]>>(new Map())

  function getDeployments(convId: string): Deployment[] {
    return byConv.value.get(convId) ?? []
  }

  /** 当前活跃部署(最新一次 status=running 且 active=true 的) */
  function getActive(convId: string): Deployment | null {
    const list = getDeployments(convId)
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].active && list[i].status === 'running') return list[i]
    }
    return null
  }

  /** 总数(用于 tab badge) */
  function getCount(convId: string): number {
    return getDeployments(convId).length
  }

  function addDeployment(d: Deployment) {
    const list = [...getDeployments(d.conversationId)]
    // 同会话之前的 active 清掉
    for (const old of list) old.active = false
    list.push(d)
    byConv.value.set(d.conversationId, list)
    // 触发响应式重建
    byConv.value = new Map(byConv.value)
  }

  function clear(convId: string) {
    byConv.value.delete(convId)
    byConv.value = new Map(byConv.value)
  }

  return {
    byConv,
    getDeployments,
    getActive,
    getCount,
    addDeployment,
    clear,
  }
})
