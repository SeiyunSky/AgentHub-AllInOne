export interface Skill {
  id: string
  name: string
  displayName?: string
  description?: string
  category?: string
  authorId: string
  isPublic: boolean
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface SkillWithContent extends Skill {
  content: string
}

export interface SkillCreate {
  name: string
  displayName?: string
  description?: string
  category?: string
  content: string
  isPublic: boolean
}

export interface SkillUpdate {
  displayName?: string
  description?: string
  category?: string
  content?: string
  isPublic?: boolean
  isActive?: boolean
}
