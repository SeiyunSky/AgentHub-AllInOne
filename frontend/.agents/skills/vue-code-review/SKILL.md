---
name: vue-code-review
description: Vue 前端代码审查清单。当用户要求对 Vue/前端代码进行 code review、代码审查、质量检查时触发。覆盖正确性、性能、组件设计、TypeScript、Pinia、安全和可维护性七个维度。
---

# Vue 前端代码审查

当用户请求对 Vue 代码进行 review 时，按以下七个维度逐一审查，对每个发现的问题给出：**问题描述 + 风险等级（高/中/低）+ 修改建议或示例代码**。

## When to Use This Skill

- 用户说"帮我 review 这段代码"、"code review"、"审查代码"、"检查代码质量"
- 用户提交了 Vue 组件、composable、Pinia store、或前端模块代码
- 用户问"这段代码有没有问题"、"这样写对吗"

## How to Perform the Review

### Step 1: 快速扫描结构

先整体看代码结构，确认：
- 是否使用 `<script setup>` + Composition API（项目标准）
- 文件长度是否合理（>300 行考虑拆分）
- 代码组织顺序：`<script setup>` / `<template>` / `<style>`

### Step 2: 按维度逐项检查

**维度 1 — 正确性 & Bug（优先检查）**

| 检查项 | 风险 |
|--------|------|
| `reactive`/`ref` 解构是否丢失响应式（如 `const { x } = reactive(...)`） | 高 |
| `onMounted`/`onUnmounted` 是否配对（事件监听、定时器、WebSocket） | 高 |
| `watch`/`watchEffect` 中异步操作是否有竞态风险，是否用 `AbortController` 或标志位 | 高 |
| `v-for` 的 `key` 是否稳定且唯一，是否用 `index` 做 key | 中 |
| 空值/`undefined` 是否妥善处理，是否缺失可选链 | 中 |

**维度 2 — 性能**

| 检查项 | 风险 |
|--------|------|
| Props 是否传递内联对象/数组（每次渲染新引用触发子组件重渲染） | 中 |
| 昂贵计算是否用 `computed` 而非方法调用；`computed` 是否有副作用 | 中 |
| 长列表是否使用虚拟滚动（如 `vue-virtual-scroller`） | 中 |
| 是否对大对象使用 `deep: true`，能否改为精确监听路径 | 中 |
| 图片是否懒加载，组件是否异步加载（`defineAsyncComponent`） | 低 |
| 闭包/定时器/事件监听是否在组件卸载时清理（内存泄漏） | 高 |

**维度 3 — 组件设计 & 架构**

| 检查项 | 风险 |
|--------|------|
| 组件是否承担过多职责，是否应拆分 | 中 |
| Props 是否有完整 TypeScript 类型、默认值、`required`/`validator` | 中 |
| `emit` 是否用 `defineEmits` 声明，事件名是否 kebab-case | 低 |
| 跨层级通信是否用 `provide/inject`，全局状态是否用 Pinia | 中 |
| 是否有重复逻辑可提取为 `useXxx` composable | 低 |
| 硬编码内容是否应改用 `slot` | 低 |

**维度 4 — TypeScript 类型安全**

| 检查项 | 风险 |
|--------|------|
| 是否有 `any` 可替换为具体类型 | 中 |
| `as` 断言是否可用类型守卫替代 | 中 |
| Props 是否用 `defineProps<T>()` 泛型声明 | 低 |
| API 返回值是否有类型定义，错误响应类型是否处理 | 中 |
| 是否可用 `Partial`/`Pick`/`Omit`/`Record` 简化类型定义 | 低 |

**维度 5 — 状态管理 Pinia**

| 检查项 | 风险 |
|--------|------|
| Store 是否按领域拆分，单个 store 是否过大 | 低 |
| 组件是否通过 action 修改状态，而非直接赋值 | 高 |
| Action 中异步操作是否有 `try/catch`，错误是否妥善处理 | 高 |
| 多个 store 之间是否有循环依赖 | 高 |
| 持久化敏感数据（token、密码等）是否排除在 `pinia-plugin-persistedstate` 之外 | 高 |

**维度 6 — 安全 & 数据校验**

| 检查项 | 风险 |
|--------|------|
| 是否使用 `v-html`，内容是否经过 sanitize | 高 |
| 用户输入是否前后端都做了校验 | 高 |
| Token 存储位置是否安全，是否在请求拦截器统一处理 | 高 |
| 是否有密码/密钥硬编码或暴露在客户端 | 高 |
| 动态跳转是否校验目标 URL，防止 open redirect | 中 |
| 是否有已知漏洞的第三方依赖 | 中 |

**维度 7 — 可维护性 & 规范**

| 检查项 | 风险 |
|--------|------|
| 组件名是否 PascalCase，变量/函数是否 camelCase，常量是否 SCREAMING_SNAKE_CASE | 低 |
| 是否有魔法数字/字符串应提取为常量或枚举 | 低 |
| 重复逻辑是否应提取为公共函数或 composable | 低 |
| 复杂逻辑是否有注释，注释是否准确有价值 | 低 |

### Step 3: 输出格式

按如下格式汇总结果：

```
## Code Review 结果

### 🔴 高风险问题
- [文件/行号] 问题描述
  建议：...

### 🟡 中风险问题
- [文件/行号] 问题描述
  建议：...

### 🟢 低风险 / 优化建议
- [文件/行号] 问题描述
  建议：...

### ✅ 总结
整体质量评价（1-2 句），主要关注点。
```

如果代码质量良好，明确说明并指出亮点。
