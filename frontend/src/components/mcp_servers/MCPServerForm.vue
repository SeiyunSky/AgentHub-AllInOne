<template>
  <div class="py-8 px-8 pr-12 space-y-5 custom-scrollbar" :class="{ 'opacity-70': readonly }">

    <!-- Identity: Name -->
    <section class="flex items-center gap-4">
      <div
        class="w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 border shadow-soft"
        :class="draft.transport === 'stdio' ? 'bg-emerald-50 border-emerald-200/60' : 'bg-blue-50 border-blue-200/60'"
      >
        <el-icon :size="24" :class="draft.transport === 'stdio' ? 'text-emerald-600' : 'text-blue-600'">
          <Monitor v-if="draft.transport === 'stdio'" /><Connection v-else />
        </el-icon>
      </div>
      <div class="flex-1 min-w-0">
        <el-input
          v-model="draft.name"
          :placeholder="t('mcpServerForm.namePlaceholder')"
          size="large"
          class="borderless-input"
          input-style="padding: 0; font-size: 28px; font-weight: 600; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
          :disabled="readonly"
        />
      </div>
    </section>

    <!-- Description -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><Document /></el-icon>
        {{ t('mcpServerForm.descriptionLabel') }}
      </h3>
      <el-input
        v-model="draft.description"
        type="textarea"
        :rows="2"
        :placeholder="t('mcpServerForm.descriptionPlaceholder')"
        input-style="height: 96px; font-size: 13px; resize: none; line-height: 1.5;"
        resize="none"
        :disabled="readonly"
      />
    </section>

    <!-- Transport -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><SetUp /></el-icon>
        {{ t('mcpServerForm.transportLabel') }}
      </h3>
      <el-radio-group v-model="draft.transport" :disabled="readonly">
        <el-radio-button value="stdio">stdio</el-radio-button>
        <el-radio-button value="sse">SSE</el-radio-button>
        <el-radio-button value="streamable_http">Streamable HTTP</el-radio-button>
      </el-radio-group>
    </section>

    <!-- stdio fields -->
    <template v-if="draft.transport === 'stdio'">
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><Promotion /></el-icon>
          {{ t('mcpServerForm.commandLabel') }}
        </h3>
        <el-input
          v-model="draft.command"
          :placeholder="t('mcpServerForm.commandPlaceholder')"
          input-style="font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
          :disabled="readonly"
        />
      </section>

      <!-- Args -->
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><List /></el-icon>
          {{ t('mcpServerForm.argsLabel') }}
        </h3>
        <div class="space-y-1.5">
          <div v-for="(_, idx) in displayArgs" :key="idx" class="flex gap-2 items-center">
            <el-input
              v-model="displayArgs[idx]"
              :placeholder="idx === displayArgs.length - 1 ? t('mcpServerForm.addArg') : ''"
              input-style="font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
              :disabled="readonly"
              @input="onArgInput(idx)"
              @blur="onArgBlur(idx)"
            />
            <button
              v-if="displayArgs[idx]"
              class="shrink-0 text-on-surface-variant hover:text-red-500 transition-colors disabled:cursor-not-allowed"
              :disabled="readonly"
              @click="removeArg(idx)"
            >
              <el-icon :size="12"><Close /></el-icon>
            </button>
            <!-- placeholder for alignment when no × button -->
            <span v-else class="w-3 shrink-0" />
          </div>
        </div>
      </section>

      <!-- Env -->
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><Key /></el-icon>
          {{ t('mcpServerForm.envLabel') }}
        </h3>
        <div class="space-y-1.5">
          <div v-for="(row, idx) in displayEnv" :key="idx" class="flex gap-2 items-center">
            <el-input
              v-model="row.key"
              :placeholder="idx === displayEnv.length - 1 ? t('mcpServerForm.addEnvVar') : 'KEY'"
              class="flex-1"
              input-style="font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
              :disabled="readonly"
              @input="onEnvKeyInput(idx)"
              @blur="onEnvKeyBlur(idx)"
            />
            <el-input
              v-model="row.value"
              placeholder="VALUE"
              class="flex-1"
              input-style="font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
              :disabled="readonly"
              @input="onEnvValueInput(idx)"
            />
            <button
              v-if="row.key || row.value"
              class="shrink-0 text-on-surface-variant hover:text-red-500 transition-colors disabled:cursor-not-allowed"
              :disabled="readonly"
              @click="removeEnvRow(idx)"
            >
              <el-icon :size="12"><Close /></el-icon>
            </button>
            <span v-else class="w-3 shrink-0" />
          </div>
        </div>
      </section>
    </template>

    <!-- SSE / Streamable HTTP fields -->
    <template v-if="draft.transport === 'sse' || draft.transport === 'streamable_http'">
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><Link /></el-icon>
          {{ t('mcpServerForm.urlLabel') }}
        </h3>
        <el-input
          v-model="draft.url"
          :placeholder="t('mcpServerForm.urlPlaceholder')"
          :disabled="readonly"
          input-style="font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
        />
      </section>

      <!-- Headers -->
      <section>
        <h3 class="section-heading">
          <el-icon :size="14"><Key /></el-icon>
          {{ t('mcpServerForm.headersLabel') }}
        </h3>
        <div class="space-y-1.5">
          <div v-for="(row, idx) in displayHeaders" :key="idx" class="flex gap-2 items-center">
            <el-input
              v-model="row.key"
              :placeholder="idx === displayHeaders.length - 1 ? t('mcpServerForm.addHeader') : t('mcpServerForm.headerKeyPlaceholder')"
              class="w-[40%]"
              input-style="font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
              :disabled="readonly"
              @input="onHeaderKeyInput(idx)"
              @blur="onHeaderKeyBlur(idx)"
            />
            <el-input
              v-model="row.value"
              :placeholder="t('mcpServerForm.headerValuePlaceholder')"
              class="wf"
              input-style="font-size: 13px; font-family: 'Consolas', 'SF Mono', ui-monospace, monospace;"
              :disabled="readonly"
              @input="onHeaderValueInput(idx)"
            />
            <button
              v-if="row.key || row.value"
              class="shrink-0 text-on-surface-variant hover:text-red-500 transition-colors disabled:cursor-not-allowed"
              :disabled="readonly"
              @click="removeHeaderRow(idx)"
            >
              <el-icon :size="12"><Close /></el-icon>
            </button>
            <span v-else class="w-3 shrink-0" />
          </div>
        </div>
      </section>
    </template>

    <!-- Visibility -->
    <section>
      <h3 class="section-heading">
        <el-icon :size="14"><View /></el-icon>
        {{ t('mcpServerForm.visibilityLabel') }}
      </h3>
      <div class="flex items-center justify-between">
        <div>
          <p class="text-[13px] font-medium text-on-surface">{{ t('mcpServerForm.publicServer') }}</p>
          <p class="text-[12px] text-on-surface-variant">{{ t('mcpServerForm.publicServerDesc') }}</p>
        </div>
        <el-switch v-model="draft.isPublic" :disabled="readonly" />
      </div>
    </section>

    <!-- Status -->
    <section v-if="editMode">
      <h3 class="section-heading">
        <el-icon :size="14"><CircleCheck /></el-icon>
        {{ t('mcpServerForm.statusLabel') }}
      </h3>
      <div class="flex items-center justify-between">
        <div>
          <p class="text-[13px] font-medium text-on-surface">{{ t('mcpServerForm.activeLabel') }}</p>
          <p class="text-[12px] text-on-surface-variant">{{ t('mcpServerForm.disabledServerDesc') }}</p>
        </div>
        <el-switch v-model="draft.isActive" :disabled="readonly" />
      </div>
    </section>

  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Monitor, Connection, Document, SetUp, Promotion, List, Close, Key, Link, View, CircleCheck } from '@element-plus/icons-vue'
import type { MCPServerDraft } from '@/types/mcp_server'

const { t } = useI18n()

const props = defineProps<{
  draft: MCPServerDraft
  editMode: boolean
  readonly?: boolean
}>()

// ── Display state ──────────────────────────────────────────────────────────────

type KVRow = { key: string; value: string }

const displayArgs = ref<string[]>([])
const displayEnv = ref<KVRow[]>([])
const displayHeaders = ref<KVRow[]>([])

watch(
  () => props.draft,
  (draft) => {
    displayArgs.value = [...draft.args, '']
    displayEnv.value = [
      ...Object.entries(draft.env).map(([key, value]) => ({ key, value })),
      { key: '', value: '' },
    ]
    displayHeaders.value = [
      ...Object.entries(draft.headers).map(([key, value]) => ({ key, value })),
      { key: '', value: '' },
    ]
  },
  { immediate: true },
)

// ── Sync helpers ───────────────────────────────────────────────────────────────

function syncArgs() {
  const vals = displayArgs.value.filter((s) => s.trim())
  props.draft.args.splice(0, props.draft.args.length, ...vals)
}

function syncEnv() {
  for (const k of Object.keys(props.draft.env)) delete props.draft.env[k]
  for (const row of displayEnv.value)
    if (row.key.trim()) props.draft.env[row.key] = row.value
}

function syncHeaders() {
  for (const k of Object.keys(props.draft.headers)) delete props.draft.headers[k]
  for (const row of displayHeaders.value)
    if (row.key.trim()) props.draft.headers[row.key] = row.value
}

// ── Args ───────────────────────────────────────────────────────────────────────

function onArgInput(idx: number) {
  if (idx === displayArgs.value.length - 1 && displayArgs.value[idx])
    displayArgs.value.push('')
  syncArgs()
}

function onArgBlur(idx: number) {
  if (idx < displayArgs.value.length - 1 && !displayArgs.value[idx].trim()) {
    displayArgs.value.splice(idx, 1)
    syncArgs()
  }
}

function removeArg(idx: number) {
  displayArgs.value.splice(idx, 1)
  if (!displayArgs.value.length) displayArgs.value.push('')
  syncArgs()
}

// ── Env ────────────────────────────────────────────────────────────────────────

function onEnvKeyInput(idx: number) {
  if (idx === displayEnv.value.length - 1 && displayEnv.value[idx].key)
    displayEnv.value.push({ key: '', value: '' })
  syncEnv()
}

function onEnvKeyBlur(idx: number) {
  const row = displayEnv.value[idx]
  if (idx < displayEnv.value.length - 1 && !row.key && !row.value) {
    displayEnv.value.splice(idx, 1)
    syncEnv()
  }
}

function onEnvValueInput(_idx: number) {
  syncEnv()
}

function removeEnvRow(idx: number) {
  displayEnv.value.splice(idx, 1)
  if (!displayEnv.value.length) displayEnv.value.push({ key: '', value: '' })
  syncEnv()
}

// ── Headers ────────────────────────────────────────────────────────────────────

function onHeaderKeyInput(idx: number) {
  if (idx === displayHeaders.value.length - 1 && displayHeaders.value[idx].key)
    displayHeaders.value.push({ key: '', value: '' })
  syncHeaders()
}

function onHeaderKeyBlur(idx: number) {
  const row = displayHeaders.value[idx]
  if (idx < displayHeaders.value.length - 1 && !row.key && !row.value) {
    displayHeaders.value.splice(idx, 1)
    syncHeaders()
  }
}

function onHeaderValueInput(_idx: number) {
  syncHeaders()
}

function removeHeaderRow(idx: number) {
  displayHeaders.value.splice(idx, 1)
  if (!displayHeaders.value.length) displayHeaders.value.push({ key: '', value: '' })
  syncHeaders()
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
