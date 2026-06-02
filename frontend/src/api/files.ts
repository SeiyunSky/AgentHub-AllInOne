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
}
