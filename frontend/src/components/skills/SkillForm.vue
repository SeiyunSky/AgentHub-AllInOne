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
          :placeholder="t('skillForm.namePlaceholder')"
          size="large"
          class="borderless-input"
          input-style="padding: 0; font-size: 28px; font-weight: 600; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
          :disabled="editMode || readonly"
        />
        <p v-if="!draft.name" class="text-[11px] text-on-surface-variant mt-1">
          {{ t('skillForm.nameHelper') }}
        </p>
      </div>
    </section>

    <!-- Display Name -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><EditPen /></el-icon>
        {{ t('skillForm.displayNameLabel') }}
      </h3>
      <el-input
        v-model="draft.displayName"
        :placeholder="t('skillForm.displayNamePlaceholder')"
        :disabled="readonly"
      />
    </section>

    <!-- Description -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><Document /></el-icon>
        {{ t('skillForm.descriptionLabel') }}
      </h3>
      <el-input
        v-model="draft.description"
        type="textarea"
        :rows="2"
        :placeholder="t('skillForm.descriptionPlaceholder')"
        resize="none"
        input-style="height: 96px; font-size: 13px; resize: none; line-height: 1.5;"
        :disabled="readonly"
      />
    </section>

    <!-- Category -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><PriceTag /></el-icon>
        {{ t('skillForm.categoryLabel') }}
      </h3>
      <el-select
        v-model="draft.category"
        :placeholder="t('skillForm.selectCategory')"
        clearable
        style="width: 100%;"
        :disabled="readonly"
      >
        <el-option
          v-for="cat in categoryOptions"
          :key="cat.value"
          :label="cat.label"
          :value="cat.value"
        />
      </el-select>
    </section>

    <!-- Content: Code container -->
    <section class="form-section !p-0 overflow-hidden">
      <div class="code-container-header">
        <el-icon :size="12"><Document /></el-icon>
        {{ t('skillForm.contentLabel') }}
        <span class="ml-auto text-[10px] opacity-60">{{ t('skillForm.markdownSupported') }}</span>
      </div>
      <div class="code-container">
        <el-input
          v-model="draft.content"
          type="textarea"
          :rows="14"
          resize="none"
          :placeholder="t('skillForm.contentPlaceholder')"
          input-style="font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace; line-height: 1.7; resize: none; border: none; box-shadow: none; background: transparent;"
          :disabled="readonly"
        />
      </div>
    </section>

    <!-- Visibility -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><View /></el-icon>
        {{ t('skillForm.visibilityLabel') }}
      </h3>
      <div class="flex items-center justify-between">
        <div>
          <p class="text-[13px] font-medium text-on-surface">{{ t('skillForm.publicSkill') }}</p>
          <p class="text-[12px] text-on-surface-variant">{{ t('skillForm.publicSkillDesc') }}</p>
        </div>
        <el-switch v-model="draft.isPublic" :disabled="readonly" />
      </div>
    </section>

    <!-- Status -->
    <section v-if="editMode">
      <h3 class="section-heading">
        <el-icon :size="14"><CircleCheck /></el-icon>
        {{ t('skillForm.statusLabel') }}
      </h3>
      <div class="flex items-center justify-between">
        <div>
          <p class="text-[13px] font-medium text-on-surface">{{ t('skillForm.activeLabel') }}</p>
          <p class="text-[12px] text-on-surface-variant">{{ t('skillForm.disabledSkillDesc') }}</p>
        </div>
        <el-switch v-model="draft.isActive" :disabled="readonly" />
      </div>
    </section>

  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MagicStick, EditPen, Document, PriceTag, View, CircleCheck } from '@element-plus/icons-vue'
import type { SkillDraft } from '@/types/skill'

const { t } = useI18n()

defineProps<{
  draft: SkillDraft
  editMode: boolean
  readonly?: boolean
}>()

const categoryOptions = computed(() => [
  { value: '代码', label: t('skillForm.categoryCode') },
  { value: '安全', label: t('skillForm.categorySecurity') },
  { value: '领域知识', label: t('skillForm.categoryDomainKnowledge') },
  { value: '通用', label: t('skillForm.categoryGeneral') },
])
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
