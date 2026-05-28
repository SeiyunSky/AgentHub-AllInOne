import axios from 'axios'
import type { AxiosResponse } from 'axios'
import type { ApiResponse } from '@/types/api'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: inject X-User-Id (MVP auth)
http.interceptors.request.use((config) => {
  const userId = localStorage.getItem('user_id') || 'default'
  config.headers.set('X-User-Id', userId)
  return config
})

// Response interceptor: unwrap { code, message, data } envelope
http.interceptors.response.use(
  (res: AxiosResponse<ApiResponse<unknown>>) => {
    const envelope = res.data
    if (envelope && envelope.code !== undefined && envelope.code !== 200) {
      return Promise.reject(new Error(envelope.message || `Error ${envelope.code}`))
    }
    return envelope?.data ?? envelope
  },
  (error) => {
    const data = error.response?.data
    const message = data?.message ?? data?.detail ?? error.message ?? 'Unknown error'
    return Promise.reject(new Error(message))
  },
)

export { http }
