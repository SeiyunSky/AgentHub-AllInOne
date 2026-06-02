import { http } from './http'
import type { SkillCreate, SkillUpdate } from '@/types/skill'

/** Snake-case response from GET /skills (list, no content) */
export interface SkillResponse {
  id: string
  name: string
  display_name?: string
  description?: string
  category?: string
  author_id: string
  is_public: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

/** Snake-case response from GET/POST/PATCH /skills/:id (with content) */
export interface SkillWithContentResponse extends SkillResponse {
  content: string
}

export const skillsApi = {
  list(): Promise<SkillResponse[]> {
    return http.get('/skills')
  },

  get(id: string): Promise<SkillWithContentResponse> {
    return http.get(`/skills/${id}`)
  },

  create(data: SkillCreate): Promise<SkillWithContentResponse> {
    return http.post('/skills', data)
  },

  update(id: string, data: SkillUpdate): Promise<SkillWithContentResponse> {
    return http.patch(`/skills/${id}`, data)
  },

  remove(id: string): Promise<void> {
    return http.delete(`/skills/${id}`)
  },
}
