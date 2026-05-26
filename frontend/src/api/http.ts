import axios from 'axios'
import type { AxiosResponse } from 'axios'

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

// Response interceptor: unwrap data, normalize errors
http.interceptors.response.use(
  (res: AxiosResponse) => res.data,
  (error) => {
    const message = error.response?.data?.detail ?? error.message ?? 'Unknown error'
    return Promise.reject(new Error(message))
  },
)

export { http }
