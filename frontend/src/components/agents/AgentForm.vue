<template>
  <div class="overflow-y-auto custom-scrollbar h-full">
    <div class="py-8 px-8 pr-12 space-y-6">

      <!-- Agent Identity: Avatar + Name -->
      <section class="flex items-center gap-4">
        <div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center shrink-0">
          <el-icon :size="24" class="text-brand"><User /></el-icon>
        </div>
        <div class="flex-1 min-w-0">
          <el-input
            v-model="draft.name"
            placeholder="Agent Name"
            size="large"
            class="borderless-input"
            input-style="padding: 0; font-size: 28px; font-weight: 600;"
          />
        </div>
      </section>

      <!-- Description -->
      <section>
        <h3 class="text-[12px] font-semibold text-on-surface-variant uppercase tracking-widest mb-3">Description</h3>
        <el-input
          v-model="draft.description"
          type="textarea"
          :rows="2"
          placeholder="Brief description of what this agent does..."
          resize="none"
          input-style="padding: 12px 16px; font-size: 13px; resize: none; line-height: 1.5;"
        />
      </section>

      <!-- Agent Platform -->
      <section>
        <h3 class="text-[12px] font-semibold text-on-surface-variant uppercase tracking-widest mb-3">Platform</h3>
        <el-select v-model="draft.type" class="!w-[280px]">
          <el-option label="Claude" value="claude">
            <span class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-amber-400"></span>
              Claude
            </span>
          </el-option>
          <el-option label="Codex" value="codex">
            <span class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
              Codex
            </span>
          </el-option>
          <el-option label="OpenCode" value="opencode">
            <span class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-blue-400"></span>
              OpenCode
            </span>
          </el-option>
          <el-option label="Custom" value="custom">
            <span class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-purple-400"></span>
              Custom
            </span>
          </el-option>
        </el-select>
      </section>

      <!-- Skills: Add button first, then active skills as tags -->
      <section>
        <h3 class="text-[12px] font-semibold text-on-surface-variant uppercase tracking-widest mb-3">Skills</h3>
        <div class="flex flex-wrap items-center gap-2">
          <!-- Add skill button with popup -->
          <el-popover
            trigger="click"
            placement="bottom-start"
            :width="280"
            :show-arrow="false"
            :offset="4"
            popper-class="skill-dropdown-popper"
          >
            <template #reference>
              <button
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium text-brand border border-brand bg-brand-light/30 hover:bg-brand-light/50 transition-all"
              >
                <el-icon :size="14"><Plus /></el-icon>
                Add Skill
              </button>
            </template>
            <!-- Checkbox list in popup -->
            <div class="py-2">
              <div
                v-for="skill in allSkills"
                :key="skill.key"
                class="flex items-center gap-3 px-3 py-2.5 text-[13px] cursor-pointer hover:bg-brand-light/30 rounded-lg mx-1 transition-colors"
                @click="toggleSkill(skill.key)"
              >
                <div
                  class="w-5 h-5 rounded-md flex items-center justify-center transition-all shrink-0"
                  :class="draft.capabilities[skill.key]
                    ? 'bg-brand text-white'
                    : 'bg-surface-container text-on-surface-variant'"
                >
                  <el-icon :size="12"><component :is="draft.capabilities[skill.key] ? Select : skill.icon" /></el-icon>
                </div>
                <span class="font-medium" :class="draft.capabilities[skill.key] ? 'text-brand' : 'text-on-surface'">
                  {{ skill.label }}
                </span>
              </div>
            </div>
          </el-popover>
          <!-- Active skills as tags -->
          <div
            v-for="skill in activeSkills"
            :key="skill.key"
            class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium bg-surface-container text-on-surface border border-outline-variant"
          >
            <el-icon :size="14"><component :is="skill.icon" /></el-icon>
            {{ skill.label }}
            <button
              class="w-4 h-4 rounded-md flex items-center justify-center hover:bg-on-surface/10 transition-colors"
              @click="toggleSkill(skill.key)"
            >
              <el-icon :size="10"><Close /></el-icon>
            </button>
          </div>
        </div>
      </section>

      <!-- System Prompt: directly editable, no Edit/Preview toggle -->
      <section>
        <h3 class="text-[12px] font-semibold text-on-surface-variant uppercase tracking-widest mb-3">System Prompt</h3>
        <el-input
          v-model="draft.systemPrompt"
          type="textarea"
          :rows="12"
          resize="none"
          placeholder="### Goals&#10;Define what the agent should accomplish...&#10;&#10;### Skills&#10;List the agent's core capabilities...&#10;&#10;### Workflow&#10;Describe how the agent should work...&#10;&#10;### Constraints&#10;Set boundaries and limitations..."
          input-style="padding: 16px; font-size: 13px; font-family: 'JetBrains Mono', 'Fira Code', monospace; line-height: 1.7; resize: none;"
        />
      </section>

      <!-- Tags: embedded inline input -->
      <section>
        <h3 class="text-[12px] font-semibold text-on-surface-variant uppercase tracking-widest mb-3">Tags</h3>
        <div class="flex flex-wrap items-center gap-1.5 p-2 rounded-xl border border-outline-variant bg-white min-h-[40px]">
          <span
            v-for="tag in draft.tags"
            :key="tag"
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[12px] font-medium bg-brand-light text-brand"
          >
            {{ tag }}
            <button
              class="w-3.5 h-3.5 rounded-full flex items-center justify-center hover:bg-brand/20 transition-colors"
              @click="removeTag(tag)"
            >
              <el-icon :size="8"><Close /></el-icon>
            </button>
          </span>
          <input
            v-model="tagInput"
            type="text"
            placeholder="Add tag..."
            class="flex-1 min-w-[100px] px-2 py-1 text-[13px] outline-none bg-transparent"
            @keyup.enter="addTag"
            @blur="addTag"
          />
        </div>
      </section>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { AgentDraft, AgentCapabilities } from '@/types/agent'
import type { Ref, Component } from 'vue'
import { User, Plus, Close, Document, SetUp, Picture, Cpu, Select } from '@element-plus/icons-vue'

const props = defineProps<{
  draft: Ref<AgentDraft>
}>()

const draft = computed(() => props.draft.value)

const tagInput = ref('')

interface SkillDef {
  key: keyof AgentCapabilities
  label: string
  icon: Component
}

const allSkills: SkillDef[] = [
  { key: 'supportsCode', label: 'Code Execution', icon: Cpu },
  { key: 'supportsDiff', label: 'Diff Review', icon: Document },
  { key: 'supportsApproval', label: 'Approval Flow', icon: SetUp },
  { key: 'supportsImage', label: 'Image Processing', icon: Picture },
]

const activeSkills = computed(() =>
  allSkills.filter(s => draft.value.capabilities[s.key]),
)

function toggleSkill(key: keyof AgentCapabilities) {
  props.draft.value.capabilities[key] = !props.draft.value.capabilities[key]
}

function addTag() {
  const tag = tagInput.value.trim()
  if (tag && !draft.value.tags.includes(tag)) {
    props.draft.value.tags.push(tag)
    tagInput.value = ''
  }
}

function removeTag(tag: string) {
  const index = draft.value.tags.indexOf(tag)
  if (index > -1) props.draft.value.tags.splice(index, 1)
}
</script>

<style scoped>
.borderless-input :deep(.el-input__wrapper) {
  box-shadow: none;
  background: transparent;
}
.borderless-input :deep(.el-input__wrapper:hover) {
  box-shadow: none;
}
.borderless-input :deep(.el-input__wrapper:focus-within) {
  box-shadow: none;
}
</style>

<style>
.skill-dropdown-popper {
  border-radius: 12px !important;
  border: 1px solid var(--el-border-color-lighter) !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08), 0 1px 4px rgba(0, 0, 0, 0.04) !important;
  padding: 4px !important;
}
</style>