import { http } from './http'

export const filesApi = {
  upload(files: File[]): Promise<{ paths: string[] }> {
    const form = new FormData()
    for (const file of files) {
      form.append('files', file)
    }
    return http.post('/files/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  getContent(filePath: string): Promise<{ content: string }> {
    return http.get('/files/content', { params: { filePath } })
  },

  saveContent(filePath: string, content: string): Promise<{ success: boolean }> {
    return http.put('/files/content', { filePath, content })
  },
}
