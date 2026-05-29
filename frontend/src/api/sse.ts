import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { SSEEvent } from '@/types/api'

export interface SSEOptions {
  onEvent: (event: SSEEvent) => void
  onError?: (error: Error) => void
  onClose?: () => void
}

export function connectSSE(url: string, options: SSEOptions): AbortController {
  const ctrl = new AbortController()
  const userId = localStorage.getItem('user_id') || 'default'

  fetchEventSource(url, {
    method: 'GET',
    headers: {
      'Accept': 'text/event-stream',
      'X-User-Id': userId,
    },
    signal: ctrl.signal,

    async onopen(response) {
      if (!response.ok) {
        throw new Error(`SSE connection failed: ${response.status}`)
      }
    },

    onmessage(ev) {
      try {
        const parsed = JSON.parse(ev.data) as SSEEvent
        options.onEvent(parsed)
      } catch {
        // ignore malformed JSON
      }
    },

    onerror(err) {
      options.onError?.(err instanceof Error ? err : new Error(String(err)))
      throw err // stop reconnecting
    },

    onclose() {
      options.onClose?.()
    },
  })

  return ctrl
}
