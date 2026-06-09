import axios from 'axios'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type { ApiResponse } from '@/types/api'

const BASE_URL = '/api/v1'

const http = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// localStorage key (与 stores/auth.ts 保持一致;不直接 import store,避免循环依赖)
const LS_ACCESS = 'auth.access_token'
const LS_REFRESH = 'auth.refresh_token'

// /auth/login /auth/refresh /auth/register 不需要 token,也不应触发 refresh 流程
// /auth/oauth/ 下的所有路径同理(OAuth 回调由后端直接重定向,不走 Axios)
const SKIP_AUTH_PATHS = ['/auth/login', '/auth/refresh', '/auth/register', '/auth/oauth/']

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

// ---------------- Response: 拆 envelope + 401 清除会话 ----------------
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
    const config = error.config as InternalAxiosRequestConfig

    // 401 且不是 auth 端点本身:直接清除本地会话并通知应用层跳登录
    if (status === 401 && config && !isSkipAuthUrl(config.url)) {
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
