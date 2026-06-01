import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Skill } from '@/types/skill'
import { skillsApi, type SkillResponse } from '@/api/skills'

function mapSkillResponse(s: SkillResponse): Skill {
  return {
    id: s.id,
    name: s.name,
    displayName: s.display_name,
    description: s.description,
    category: s.category,
    authorId: s.author_id,
    isPublic: s.is_public,
    isActive: s.is_active,
    createdAt: s.created_at,
    updatedAt: s.updated_at,
  }
}

export const useSkillsStore = defineStore('skills', () => {
  const skills = ref<Skill[]>([])
  const isLoading = ref(false)

  let loadPromise: Promise<void> | null = null

  async function loadSkills() {
    if (loadPromise) return loadPromise
    loadPromise = (async () => {
      isLoading.value = true
      try {
        const data = await skillsApi.list()
        skills.value = data.map(mapSkillResponse)
      } finally {
        isLoading.value = false
        loadPromise = null
      }
    })()
    return loadPromise
  }

  function removeSkill(id: string) {
    const idx = skills.value.findIndex(s => s.id === id)
    if (idx >= 0) skills.value.splice(idx, 1)
  }

  return {
    skills,
    isLoading,
    loadSkills,
    removeSkill,
  }
})
