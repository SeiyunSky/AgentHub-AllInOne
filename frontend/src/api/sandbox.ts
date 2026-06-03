import { http } from './http'
import type { SandboxFileNode } from '@/types/sandbox'

// 后端字段是 snake_case (is_dir, mime_type),此处统一转 camelCase 给前端用
interface RawSandboxFileNode {
  name: string
  path: string
  size: number
  mtime: number
  is_dir: boolean
}

interface RawReadFileResp {
  content: string
  mime_type: string
  size: number
}

export interface SandboxUploadedFile {
  name: string
  path: string
  size: number
}

export const sandboxApi = {
  async list(convId: string): Promise<SandboxFileNode[]> {
    const res = await http.get<unknown, { files: RawSandboxFileNode[] }>(
      `/sandbox/${convId}/files`,
    )
    return (res.files ?? []).map(f => ({
      name: f.name,
      path: f.path,
      size: f.size,
      mtime: f.mtime,
      isDir: f.is_dir,
    }))
  },

  read(convId: string, path: string): Promise<RawReadFileResp> {
    return http.get(`/sandbox/${convId}/files/raw`, { params: { path } })
  },

  save(convId: string, path: string, content: string): Promise<{ size: number }> {
    return http.put(`/sandbox/${convId}/files/raw`, { path, content })
  },

  // 直接拼 URL 给 <a download>:axios 拦截器会拆 envelope,
  // 但下载端点返回的是 StreamingResponse,需要浏览器原生处理 Content-Disposition
  downloadUrl(convId: string, path: string): string {
    return `/api/v1/sandbox/${convId}/files/download?path=${encodeURIComponent(path)}`
  },

  // 上传文件到当前会话沙箱根目录,Agent 立即能用 read_file 读到
  upload(convId: string, files: File[]): Promise<{ files: SandboxUploadedFile[] }> {
    const form = new FormData()
    for (const f of files) form.append('files', f)
    return http.post(`/sandbox/${convId}/files/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

