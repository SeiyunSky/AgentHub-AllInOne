import { http } from './http'

export const artifactsApi = {
  applyDiff(
    messageId: string,
    editedCode?: string,
  ): Promise<{ success: boolean; applied_files: string[] }> {
    return http.post('/artifacts/diff/apply', {
      message_id: messageId,
      ...(editedCode !== undefined && { edited_code: editedCode }),
    })
  },
}
