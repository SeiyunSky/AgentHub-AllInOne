import { http } from './http'

export const skillsApi = {
  list(): Promise<any[]> {
    return http.get('/skills')
  },

  get(id: string): Promise<any> {
    return http.get(`/skills/${id}`)
  },

  create(data: any): Promise<any> {
    return http.post('/skills', data)
  },

  update(id: string, data: any): Promise<any> {
    return http.patch(`/skills/${id}`, data)
  },
}
