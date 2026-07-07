<template>
  <div class="py-8 px-8 pr-12 space-y-5 custom-scrollbar" :class="{ 'opacity-70': readonly }">

      <!-- Agent Identity: Avatar + Name -->
      <section class="flex items-center gap-4">
        <div class="w-14 h-14 rounded-2xl from-brand-light to-brand-subtle flex items-center justify-center shrink-0 border border-brand/20 shadow-soft overflow-hidden">
          <img v-if="draft.avatar" :src="draft.avatar" :alt="draft.name" class="w-full h-full object-cover" />
          <img v-else :src="getAgentTypeIcon(draft.type)" :alt="draft.type" class="w-8 h-8 object-contain" />
        </div>
        <div class="flex-1 min-w-0">
          <el-input
            v-model="draft.name"
            :placeholder="t('agentForm.namePlaceholder')"
            size="large"
            class="borderless-input"
            input-style="padding: 0; font-size: 28px; font-weight: 600;"
            :disabled="readonly"
          />
          <p v-if="!draft.name" class="text-[11px] text-on-surface-variant mt-1">{{ t('agentForm.nameHelper') }}</p>
        </div>
      </section>

      <!-- Description -->
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><Document /></el-icon>
          {{ t('agentForm.descriptionLabel') }}
        </h3>
        <el-input
          v-model="draft.description"
          type="textarea"
          :rows="2"
          :placeholder="t('agentForm.descriptionPlaceholder')"
          resize="none"
          input-style="height: 96px; font-size: 13px; resize: none; line-height: 1.5;"
          :disabled="readonly"
        />
      </section>

      <!-- Platform: Visual card selector -->
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><SetUp /></el-icon>
          {{ t('agentForm.platformLabel') }}
        </h3>
        <div class="grid grid-cols-2 gap-3">
          <button
            v-for="p in platformOptions"
            :key="p.value"
            class="relative flex items-center gap-3 px-4 py-3 rounded-xl border-2 cursor-pointer transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-60 text-left"
            :class="draft.type === p.value
              ? 'border-brand bg-brand-light/30 shadow-soft'
              : 'border-outline-variant bg-white hover:border-brand/40 hover:bg-brand-light/10'"
            :disabled="readonly"
            @click="draft.type = p.value"
          >
            <div class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" :class="p.bgClass">
              <img :src="p.iconSrc" :alt="p.label" class="w-6 h-6 object-contain" />
            </div>
            <div class="flex-1 min-w-0">
              <span class="block text-[12px] font-semibold" :class="draft.type === p.value ? 'text-brand' : 'text-on-surface'">
                {{ p.label }}
              </span>
              <span v-if="p.desc" class="block text-[10px] text-on-surface-variant leading-tight mt-0.5">{{ p.desc }}</span>
            </div>
            <!-- Check indicator -->
            <div
              v-if="draft.type === p.value"
              class="w-4 h-4 rounded-full flex items-center justify-center shrink-0 bg-brand"
            >
              <el-icon :size="10" class="text-white"><Select /></el-icon>
            </div>
          </button>
        </div>
      </section>

      <!-- Skills: capabilities (fixed) + API skills, single picker -->
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><SetUp /></el-icon>
          {{ t('agentForm.skillsLabel') }}
        </h3>

        <!-- Selected tags: capabilities + API skills -->
        <div v-if="selectedSkills.length > 0 || draft.skillIds.length > 0" class="flex flex-wrap gap-1.5 mb-2">
          <div
            v-for="skill in activeSkillDefs"
            :key="skill.key"
            class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[12px] font-medium border"
            :class="skill.tagClass"
          >
            <el-icon :size="12"><component :is="skill.icon" /></el-icon>
            {{ skill.label }}
            <button
              class="w-4 h-4 rounded-md flex items-center justify-center hover:bg-black/10 transition-colors disabled:cursor-not-allowed"
              :disabled="readonly"
              @click="removeSkill(skill.key)"
            >
              <el-icon :size="8"><Close /></el-icon>
            </button>
          </div>
          <div
            v-for="skill in selectedApiSkills"
            :key="skill.id"
            class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[12px] font-medium border bg-indigo-50 text-indigo-700 border-indigo-200/60"
          >
            <el-icon :size="12"><Promotion /></el-icon>
            {{ skill.displayName || skill.name }}
            <button
              class="w-4 h-4 rounded-md flex items-center justify-center hover:bg-black/10 transition-colors disabled:cursor-not-allowed"
              :disabled="readonly"
              @click="removeApiSkill(skill.id)"
            >
              <el-icon :size="8"><Close /></el-icon>
            </button>
          </div>
        </div>

        <!-- Single picker popover -->
        <el-popover
          trigger="click"
          placement="bottom-start"
          :width="280"
          :show-arrow="false"
          :offset="4"
          popper-class="skill-picker-popper"
        >
          <template #reference>
            <button class="flex items-center gap-1.5 px-3 py-2 rounded-xl text-[13px] font-medium border border-outline-variant bg-white hover:border-brand hover:bg-brand-light/20 transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-60" :disabled="readonly">
              <el-icon :size="14"><Plus /></el-icon>
              {{ totalSelected > 0 ? t('agentForm.addMoreSkills') : t('agentForm.selectSkills') }}
            </button>
          </template>

          <div class="py-1.5 max-h-[320px] overflow-y-auto custom-scrollbar">
            <!-- Capabilities group -->
            <p class="px-3 pt-1 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">{{ t('agentForm.capabilitiesGroup') }}</p>
            <div
              v-for="skill in allSkills"
              :key="skill.key"
              class="flex items-center gap-3 px-3 py-2.5 text-[13px] cursor-pointer hover:bg-brand-light/30 rounded-lg mx-1 transition-colors"
              @click="toggleSkillSelection(skill.key)"
            >
              <div
                class="w-5 h-5 rounded-md flex items-center justify-center transition-all shrink-0"
                :class="props.draft.capabilities[skill.key]
                  ? 'bg-brand text-white'
                  : 'bg-surface-container text-on-surface-variant'"
              >
                <el-icon :size="12"><component :is="props.draft.capabilities[skill.key] ? Select : skill.icon" /></el-icon>
              </div>
              <span class="font-medium" :class="props.draft.capabilities[skill.key] ? 'text-brand' : 'text-on-surface'">
                {{ skill.label }}
              </span>
            </div>

            <!-- Divider -->
            <div class="my-1.5 mx-3 border-t border-outline-variant/60" />

            <!-- API Skills group -->
            <p class="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">{{ t('agentForm.skillsGroup') }}</p>
            <div v-if="skillsStore.isLoading" class="px-3 py-2 text-[13px] text-on-surface-variant">{{ t('agentForm.loadingSkills') }}</div>
            <div v-else-if="skillsStore.skills.length === 0" class="px-3 py-2 text-[13px] text-on-surface-variant">{{ t('agentForm.noSkillsAvailable') }}</div>
            <div
              v-else
              v-for="skill in skillsStore.skills"
              :key="skill.id"
              class="flex items-center gap-3 px-3 py-2.5 text-[13px] cursor-pointer hover:bg-brand-light/30 rounded-lg mx-1 transition-colors"
              @click="toggleApiSkill(skill.id)"
            >
              <div
                class="w-5 h-5 rounded-md flex items-center justify-center transition-all shrink-0"
                :class="draft.skillIds.includes(skill.id)
                  ? 'bg-brand text-white'
                  : 'bg-surface-container text-on-surface-variant'"
              >
                <el-icon :size="12"><Select v-if="draft.skillIds.includes(skill.id)" /><Promotion v-else /></el-icon>
              </div>
              <div class="flex-1 min-w-0">
                <p class="font-medium truncate" :class="draft.skillIds.includes(skill.id) ? 'text-brand' : 'text-on-surface'">
                  {{ skill.displayName || skill.name }}
                </p>
                <p v-if="skill.description" class="text-[11px] text-on-surface-variant truncate">{{ skill.description }}</p>
              </div>
            </div>
          </div>
        </el-popover>
      </section>

      <!-- MCP Servers -->
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><Connection /></el-icon>
          {{ t('agentForm.mcpServersLabel') }}
        </h3>

        <div v-if="selectedMcpServers.length > 0" class="flex flex-wrap gap-1.5 mb-2">
          <div
            v-for="server in selectedMcpServers"
            :key="server.id"
            class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[12px] font-medium border"
            :class="server.transport === 'stdio' ? 'bg-emerald-50 text-emerald-700 border-emerald-200/60' : 'bg-blue-50 text-blue-700 border-blue-200/60'"
          >
            <el-icon :size="12"><Monitor v-if="server.transport === 'stdio'" /><Connection v-else /></el-icon>
            {{ server.name }}
            <button
              class="w-4 h-4 rounded-md flex items-center justify-center hover:bg-black/10 transition-colors disabled:cursor-not-allowed"
              :disabled="readonly"
              @click="removeMcpServer(server.id)"
            >
              <el-icon :size="8"><Close /></el-icon>
            </button>
          </div>
        </div>

        <!-- Picker popover -->
        <el-popover
          trigger="click"
          placement="bottom-start"
          :width="300"
          :show-arrow="false"
          :offset="4"
          popper-class="skill-picker-popper"
        >
          <template #reference>
            <button
              class="flex items-center gap-1.5 px-3 py-2 rounded-xl text-[13px] font-medium border border-outline-variant bg-white hover:border-brand hover:bg-brand-light/20 transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="readonly"
            >
              <el-icon :size="14"><Plus /></el-icon>
              {{ draft.mcpServerIds.length > 0 ? t('agentForm.addMoreMcpServers') : t('agentForm.selectMcpServers') }}
            </button>
          </template>
          <div class="py-1.5 max-h-[320px] overflow-y-auto custom-scrollbar">
            <div v-if="mcpServersStore.isLoading" class="px-3 py-2 text-[13px] text-on-surface-variant">{{ t('agentForm.loadingMcpServers') }}</div>
            <div v-else-if="mcpServersStore.servers.length === 0" class="px-3 py-2 text-[13px] text-on-surface-variant">{{ t('agentForm.noMcpServersAvailable') }}</div>
            <div
              v-else
              v-for="server in mcpServersStore.servers"
              :key="server.id"
              class="flex items-center gap-3 px-3 py-2.5 text-[13px] cursor-pointer hover:bg-brand-light/30 rounded-lg mx-1 transition-colors"
              @click="toggleMcpServer(server.id)"
            >
              <div
                class="w-5 h-5 rounded-md flex items-center justify-center transition-all shrink-0"
                :class="draft.mcpServerIds.includes(server.id)
                  ? 'bg-brand text-white'
                  : 'bg-surface-container text-on-surface-variant'"
              >
                <el-icon :size="12"><Select v-if="draft.mcpServerIds.includes(server.id)" /><Connection v-else /></el-icon>
              </div>
              <div class="flex-1 min-w-0">
                <p class="font-medium truncate" :class="draft.mcpServerIds.includes(server.id) ? 'text-brand' : 'text-on-surface'">
                  {{ server.name }}
                </p>
                <p v-if="server.description" class="text-[11px] text-on-surface-variant truncate">{{ server.description }}</p>
                <p v-else class="text-[11px] text-on-surface-variant truncate">{{ server.transport }} · {{ server.transport === 'stdio' ? server.command : server.url }}</p>
              </div>
            </div>
          </div>
        </el-popover>
      </section>

      <!-- System Prompt: Code container -->
      <section class="form-section !p-0 overflow-hidden">
        <div class="code-container-header">
          <el-icon :size="12"><Document /></el-icon>
          {{ t('agentForm.systemPromptLabel') }}
          <span class="ml-auto text-[10px] opacity-60">{{ t('agentForm.markdownSupported') }}</span>
        </div>
        <div class="code-container">
          <el-input
            v-model="draft.systemPrompt"
            type="textarea"
            :rows="12"
            resize="none"
            :placeholder="t('agentForm.systemPromptPlaceholder')"
            input-style="font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace; line-height: 1.7; resize: none; border: none; box-shadow: none; background: transparent;"
            :disabled="readonly"
          />
        </div>
      </section>

      <!-- Tags: Enhanced input -->
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><PriceTag /></el-icon>
          {{ t('agentForm.tagsLabel') }}
        </h3>
        <div class="flex flex-wrap items-center gap-1.5 p-3 rounded-xl border border-outline-variant bg-white min-h-[44px] focus-within:border-brand focus-within:shadow-[0_0_0_3px_rgba(59,130,246,0.08)] transition-all">
          <span
            v-for="tag in draft.tags"
            :key="tag"
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[12px] font-medium bg-brand-light text-brand border border-brand/10"
          >
            {{ tag }}
            <button
              class="w-4 h-4 rounded-md flex items-center justify-center hover:bg-brand/20 transition-colors disabled:cursor-not-allowed"
              :disabled="readonly"
              @click="removeTag(tag)"
            >
              <el-icon :size="8"><Close /></el-icon>
            </button>
          </span>
          <input
            v-model="tagInput"
            type="text"
            :placeholder="t('agentForm.addTagPlaceholder')"
            class="flex-1 min-w-[100px] px-2 py-1 text-[13px] outline-none bg-transparent disabled:cursor-not-allowed"
            :disabled="readonly"
            @keyup.enter="addTag"
            @blur="addTag"
          />
        </div>
        <p class="text-[11px] text-on-surface-variant mt-2">{{ t('agentForm.addTagHelper') }}</p>
      </section>

      <!-- Visibility -->
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><View /></el-icon>
          {{ t('agentForm.visibilityLabel') }}
        </h3>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-[13px] font-medium text-on-surface">{{ t('agentForm.publicAgent') }}</p>
            <p class="text-[12px] text-on-surface-variant">{{ t('agentForm.publicAgentDesc') }}</p>
          </div>
          <el-switch v-model="draft.isPublic" :disabled="readonly" />
        </div>
      </section>

      <!-- Status -->
      <section v-if="editMode">
        <h3 class="section-heading">
          <el-icon :size="14"><CircleCheck /></el-icon>
          {{ t('agentForm.statusLabel') }}
        </h3>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-[13px] font-medium text-on-surface">{{ t('agentForm.activeLabel') }}</p>
            <p class="text-[12px] text-on-surface-variant">{{ t('agentForm.disabledAgentDesc') }}</p>
          </div>
          <el-switch v-model="draft.isActive" :disabled="readonly" />
        </div>
      </section>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AgentDraft, AgentCapabilities, AgentType } from '@/types/agent'
import type { Component } from 'vue'
import { Close, Document, SetUp, Picture, Cpu, Select, PriceTag, View, Plus, CircleCheck, Promotion, Connection, Monitor } from '@element-plus/icons-vue'
import { getAgentTypeIcon } from '@/utils/agentIcons'
import { useSkillsStore } from '@/stores/skills'
import { useMCPServersStore } from '@/stores/mcp_servers'

const { t } = useI18n()

const props = defineProps<{
  draft: AgentDraft
  editMode?: boolean
  readonly?: boolean
}>()

const skillsStore = useSkillsStore()
const mcpServersStore = useMCPServersStore()

onMounted(() => {
  skillsStore.loadSkills()
  mcpServersStore.loadServers()
})

const tagInput = ref('')

interface SkillDef {
  key: keyof AgentCapabilities
  label: string
  icon: Component
  tagClass: string
}

const allSkills = computed<SkillDef[]>(() => [
  { key: 'supportsCode', label: t('agentForm.skillCodeExecution'), icon: Cpu, tagClass: 'bg-emerald-50 text-emerald-700 border-emerald-200/60' },
  { key: 'supportsDiff', label: t('agentForm.skillDiffReview'), icon: Document, tagClass: 'bg-blue-50 text-blue-700 border-blue-200/60' },
  { key: 'supportsApproval', label: t('agentForm.skillApprovalFlow'), icon: SetUp, tagClass: 'bg-amber-50 text-amber-700 border-amber-200/60' },
  { key: 'supportsImage', label: t('agentForm.skillImageProcessing'), icon: Picture, tagClass: 'bg-purple-50 text-purple-700 border-purple-200/60' },
])

const selectedSkills = computed(() =>
  allSkills.value.filter(s => props.draft.capabilities[s.key]).map(s => s.key),
)

const activeSkillDefs = computed(() =>
  allSkills.value.filter(s => props.draft.capabilities[s.key]),
)

const totalSelected = computed(() =>
  selectedSkills.value.length + props.draft.skillIds.length,
)

function toggleSkillSelection(key: keyof AgentCapabilities) {
  props.draft.capabilities[key] = !props.draft.capabilities[key]
}

function removeSkill(key: keyof AgentCapabilities) {
  props.draft.capabilities[key] = false
}

interface PlatformOption {
  value: AgentType
  label: string
  desc?: string
  iconSrc: string
  bgClass: string
  iconClass: string
}

const platformOptions: PlatformOption[] = [
  { value: 'claude', label: t('agentForm.platformClaudeLabel'), desc: t('agentForm.platformClaudeDesc'), iconSrc: getAgentTypeIcon('claude'), bgClass: '', iconClass: 'text-amber-600' },
  { value: 'anthropic_sdk', label: t('agentForm.platformAnthropicSdkLabel'), desc: t('agentForm.platformAnthropicSdkDesc'), iconSrc: getAgentTypeIcon('anthropic_sdk'), bgClass: '', iconClass: 'text-amber-600' },
  { value: 'codex', label: 'Codex', iconSrc: getAgentTypeIcon('codex'), bgClass: '', iconClass: 'text-teal-600' },
  { value: 'opencode', label: 'OpenCode', iconSrc: getAgentTypeIcon('opencode'), bgClass: '', iconClass: 'text-slate-600' },
]


function addTag() {
  const tag = tagInput.value.trim()
  if (tag && !props.draft.tags.includes(tag)) {
    props.draft.tags.push(tag)
    tagInput.value = ''
  }
}

function removeTag(tag: string) {
  const index = props.draft.tags.indexOf(tag)
  if (index > -1) props.draft.tags.splice(index, 1)
}

const selectedApiSkills = computed(() =>
  skillsStore.skills.filter(s => props.draft.skillIds.includes(s.id)),
)

function toggleApiSkill(id: string) {
  const idx = props.draft.skillIds.indexOf(id)
  if (idx >= 0) {
    props.draft.skillIds.splice(idx, 1)
  } else {
    props.draft.skillIds.push(id)
  }
}

function removeApiSkill(id: string) {
  const idx = props.draft.skillIds.indexOf(id)
  if (idx >= 0) props.draft.skillIds.splice(idx, 1)
}

// MCP Server picker
const selectedMcpServers = computed(() =>
  mcpServersStore.servers.filter(s => props.draft.mcpServerIds.includes(s.id)),
)

function toggleMcpServer(id: string) {
  const idx = props.draft.mcpServerIds.indexOf(id)
  if (idx >= 0) {
    props.draft.mcpServerIds.splice(idx, 1)
  } else {
    props.draft.mcpServerIds.push(id)
  }
}

function removeMcpServer(id: string) {
  const idx = props.draft.mcpServerIds.indexOf(id)
  if (idx >= 0) props.draft.mcpServerIds.splice(idx, 1)
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
.skill-picker-popper {
  border-radius: 12px !important;
  border: 1px solid var(--color-outline-variant) !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08), 0 1px 4px rgba(0, 0, 0, 0.04) !important;
  padding: 4px !important;
}
</style>
