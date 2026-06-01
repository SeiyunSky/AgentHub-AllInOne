<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Skills Library</div>
    <div class="space-y-2">
      <!-- New Skill -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 border-2 border-dashed"
        :class="isSelected('new')
          ? 'border-brand bg-brand-light/40 text-brand'
          : 'border-outline-variant text-brand hover:border-brand/40 hover:bg-brand-light/20'"
        @click="router.push({ name: 'skill-create' })"
      >
        <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-brand-light">
          <el-icon :size="16" class="text-brand"><Plus /></el-icon>
        </div>
        <span class="text-[13px] font-medium">New Skill</span>
      </div>
      <!-- Skills list -->
      <div
        v-for="skill in skillsStore.skills"
        :key="skill.id"
        class="group p-3 rounded-xl bg-white border cursor-pointer transition-all duration-200 hover-lift"
        :class="isSelected(skill.id)
          ? 'border-brand bg-brand-light/30'
          : 'border-outline-variant hover:border-brand/40'"
        @click="router.push({ name: 'skill-edit', params: { skillId: skill.id } })"
      >
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-brand-light flex items-center justify-center shrink-0 border border-brand/20">
            <el-icon class="text-brand" :size="16"><MagicStick /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[14px] font-semibold text-on-surface truncate">{{ skill.displayName || skill.name }}</p>
            <p class="text-[11px] text-on-surface-variant truncate">{{ skill.description || 'No description' }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { MagicStick, Plus } from '@element-plus/icons-vue'
import { useSkillsStore } from '@/stores/skills'

const router = useRouter()
const route = useRoute()
const skillsStore = useSkillsStore()

const currentSkillId = computed(() => route.params.skillId as string | undefined)

function isSelected(skillId: string) {
  if (skillId === 'new') {
    return route.name === 'skill-create'
  }
  return route.name === 'skill-edit' && currentSkillId.value === skillId
}

onMounted(() => {
  skillsStore.loadSkills()
})
</script>
