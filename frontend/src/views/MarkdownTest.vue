<template>
  <div class="p-8 max-w-4xl mx-auto">
    <h1 class="text-2xl font-bold mb-4">Markdown Render Test</h1>

    <div class="grid grid-cols-2 gap-8">
      <!-- Input -->
      <div>
        <h2 class="text-lg font-semibold mb-2">Input (Raw Text)</h2>
        <textarea
          v-model="input"
          class="w-full h-64 p-4 border border-gray-300 rounded-lg text-sm font-mono"
          placeholder="Type markdown here..."
        ></textarea>
      </div>

      <!-- Output -->
      <div>
        <h2 class="text-lg font-semibold mb-2">Output (Rendered HTML)</h2>
        <div class="bg-white border border-gray-300 rounded-lg p-4 min-h-64">
          <div class="markdown-body" v-html="rendered"></div>
        </div>
      </div>
    </div>

    <!-- Raw HTML output -->
    <div class="mt-8">
      <h2 class="text-lg font-semibold mb-2">Raw HTML Output</h2>
      <pre class="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto">{{ rendered }}</pre>
    </div>

    <!-- Preset buttons -->
    <div class="mt-4 flex gap-2">
      <button
        v-for="preset in presets"
        :key="preset.label"
        class="px-3 py-1.5 bg-brand text-white rounded-lg text-sm cursor-pointer hover:bg-brand-dark"
        @click="input = preset.text"
      >
        {{ preset.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const input = ref("List:\n- aaa\n- bbb\n\n**Bold** and *italic*\n`inline code`\n\n[link](https://example.com)\n\n1. First\n2. Second\n\n> blockquote\n\ncode block:\n\n```python\ndef hello():\n    print('Hello')\n```")

const rendered = computed(() => renderMarkdown(input.value))

const presets = [
  {
    label: 'List Test',
    text: "List:\n- aaa\n- bbb\n\nSeparate list:\n\n- item 1\n- item 2",
  },
  {
    label: 'Full Demo',
    text: "# Heading\n\n**bold** *italic* `code`\n\n- bullet 1\n- bullet 2\n\n1. number 1\n2. number 2\n\n> quote\n\n```js\nconsole.log('test')\n```",
  },
  {
    label: 'Empty',
    text: '',
  },
]
</script>