import { http } from './http'

export interface SquadAgent {
  id: string
  name: string
  description?: string
  type?: string
  avatar_url?: string
}

export interface Squad {
  id: string
  name: string
  description: string
  icon: string
  agent_ids: string[]
  agents: SquadAgent[]
}

export const squadsApi = {
  list(): Promise<Squad[]> {
    return http.get('/squads')
  },
}
