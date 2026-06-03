import axios from 'axios'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type { ApiResponse } from '@/types/api'

const BASE_URL = '/api/v1'

const http = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 裸 axios:用于 refresh 时不再走拦截器,避免递归。
const rawAxios = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// localStorage key (与 stores/auth.ts 保持一致;不直接 import store,避免循环依赖)
const LS_ACCESS = 'auth.access_token'
const LS_REFRESH = 'auth.refresh_token'

// /auth/login /auth/refresh /auth/register 不需要 token,也不应触发 refresh 流程
const SKIP_AUTH_PATHS = ['/auth/login', '/auth/refresh', '/auth/register']

function isSkipAuthUrl(url?: string): boolean {
  if (!url) return false
  return SKIP_AUTH_PATHS.some(p => url.includes(p))
}

// 通过事件解耦:401 不可恢复时通知应用层跳登录页(由 main.ts 监听)
function emitAuthExpired() {
  window.dispatchEvent(new CustomEvent('auth:expired'))
}

// ---------------- Request: 注入 Bearer ----------------
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(LS_ACCESS)
  if (token && !isSkipAuthUrl(config.url)) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

// ---------------- Refresh 单飞 (并发 401 共用一次 refresh) ----------------
let refreshing: Promise<string | null> | null = null

async function tryRefresh(): Promise<string | null> {
  const refreshToken = localStorage.getItem(LS_REFRESH)
  if (!refreshToken) return null
  try {
    const resp = await rawAxios.post<ApiResponse<{ access_token: string; refresh_token: string }>>(
      '/auth/refresh',
      { refresh_token: refreshToken },
    )
    const envelope = resp.data
    if (!envelope || envelope.code !== 200 || !envelope.data) return null
    const newAccess = envelope.data.access_token
    localStorage.setItem(LS_ACCESS, newAccess)
    // refresh_token 沿用原值,后端不会轮换;但若返回了新值就更新
    if (envelope.data.refresh_token) {
      localStorage.setItem(LS_REFRESH, envelope.data.refresh_token)
    }
    return newAccess
  } catch {
    return null
  }
}

// ---------------- Response: 拆 envelope + 401 自动 refresh ----------------
http.interceptors.response.use(
  (res: AxiosResponse<ApiResponse<unknown>>) => {
    const envelope = res.data
    if (envelope && envelope.code !== undefined && envelope.code !== 200 && envelope.code !== 201 && envelope.code !== 204) {
      return Promise.reject(new Error(envelope.message || `Error ${envelope.code}`))
    }
    return envelope?.data ?? envelope
  },
  async (error) => {
    const status = error.response?.status
    const config = error.config as InternalAxiosRequestConfig & { _retried?: boolean }

    // 401 且不是 auth 端点本身,尝试用 refresh token 续期一次
    if (
      status === 401 &&
      config &&
      !config._retried &&
      !isSkipAuthUrl(config.url)
    ) {
      config._retried = true

      // 单飞:并发 401 共享同一次 refresh 请求
      if (!refreshing) {
        refreshing = tryRefresh().finally(() => {
          refreshing = null
        })
      }
      const newAccess = await refreshing

      if (newAccess) {
        config.headers = config.headers ?? {}
        // 兼容两种 headers 形态
        if (typeof (config.headers as { set?: unknown }).set === 'function') {
          (config.headers as unknown as { set: (k: string, v: string) => void })
            .set('Authorization', `Bearer ${newAccess}`)
        } else {
          (config.headers as Record<string, string>)['Authorization'] = `Bearer ${newAccess}`
        }
        return http.request(config)
      }

      // refresh 也失败:清状态 + 通知应用层跳登录
      localStorage.removeItem(LS_ACCESS)
      localStorage.removeItem(LS_REFRESH)
      localStorage.removeItem('auth.user')
      emitAuthExpired()
    }

    const data = error.response?.data
    const message = data?.message ?? data?.detail ?? error.message ?? 'Unknown error'
    return Promise.reject(new Error(message))
  },
)

export { http }
