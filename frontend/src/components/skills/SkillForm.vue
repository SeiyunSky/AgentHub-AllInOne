<template>
  <div class="py-8 px-8 pr-12 space-y-5 custom-scrollbar" :class="{ 'opacity-70': readonly }">

    <!-- Skill Identity: Name + Display Name -->
    <section class="flex items-center gap-4">
      <div class="w-14 h-14 rounded-2xl from-brand-light to-brand-subtle flex items-center justify-center shrink-0 border border-brand/20 shadow-soft">
        <el-icon class="text-brand" :size="24"><MagicStick /></el-icon>
      </div>
      <div class="flex-1 min-w-0">
        <el-input
          v-model="draft.name"
          placeholder="skill-name"
          size="large"
          class="borderless-input"
          input-style="padding: 0; font-size: 28px; font-weight: 600; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
          :disabled="editMode || readonly"
        />
        <p v-if="!draft.name" class="text-[11px] text-on-surface-variant mt-1">
          English identifier (lowercase, numbers, hyphens, underscores)
        </p>
      </div>
    </section>

    <!-- Display Name -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><EditPen /></el-icon>
        Display Name
      </h3>
      <el-input
        v-model="draft.displayName"
        placeholder="中文名称（可选）"
        input-style="padding: 10px 16px; font-size: 13px;"
        :disabled="readonly"
      />
    </section>

    <!-- Description -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><Document /></el-icon>
        Description
      </h3>
      <el-input
        v-model="draft.description"
        type="textarea"
        :rows="2"
        placeholder="Brief description of what this skill does..."
        resize="none"
        input-style="padding: 12px 16px; font-size: 13px; resize: none; line-height: 1.5;"
        :disabled="readonly"
      />
    </section>

    <!-- Category -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><PriceTag /></el-icon>
        Category
      </h3>
      <el-select
        v-model="draft.category"
        placeholder="Select category"
        clearable
        style="width: 100%;"
        :disabled="readonly"
      >
        <el-option
          v-for="cat in categoryOptions"
          :key="cat"
          :label="cat"
          :value="cat"
        />
      </el-select>
    </section>

    <!-- Content: Code container -->
    <section class="form-section !p-0 overflow-hidden">
      <div class="code-container-header">
        <el-icon :size="12"><Document /></el-icon>
        Content
        <span class="ml-auto text-[10px] opacity-60">Markdown supported</span>
      </div>
      <div class="code-container">
        <el-input
          v-model="draft.content"
          type="textarea"
          :rows="14"
          resize="none"
          placeholder="### Overview&#10;Describe the skill's purpose and scope...&#10;&#10;### Instructions&#10;Step-by-step guidance for the agent...&#10;&#10;### Examples&#10;Provide example inputs and outputs...&#10;&#10;### Constraints&#10;Set boundaries and limitations..."
          input-style="padding: 16px; font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace; line-height: 1.7; resize: none; border: none; box-shadow: none; background: transparent;"
          :disabled="readonly"
        />
      </div>
    </section>

    <!-- Visibility -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><View /></el-icon>
        Visibility
      </h3>
      <div class="flex items-center justify-between">
        <div>
          <p class="text-[13px] font-medium text-on-surface">Public Skill</p>
          <p class="text-[12px] text-on-surface-variant">Allow other users to discover and use this skill</p>
        </div>
        <el-switch v-model="draft.isPublic" :disabled="readonly" />
      </div>
    </section>

    <!-- Status -->
    <section v-if="editMode">
      <h3 class="section-heading">
        <el-icon :size="14"><CircleCheck /></el-icon>
        Status
      </h3>
      <div class="flex items-center justify-between">
        <div>
          <p class="text-[13px] font-medium text-on-surface">Active</p>
          <p class="text-[12px] text-on-surface-variant">Disabled skills cannot be selected by agents</p>
        </div>
        <el-switch v-model="draft.isActive" :disabled="readonly" />
      </div>
    </section>

  </div>
</template>

<script setup lang="ts">
import { MagicStick, EditPen, Document, PriceTag, View, CircleCheck } from '@element-plus/icons-vue'
import type { SkillDraft } from '@/types/skill'

defineProps<{
  draft: SkillDraft
  editMode: boolean
  readonly?: boolean
}>()

const categoryOptions = ['代码', '安全', '领域知识', '通用']
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
