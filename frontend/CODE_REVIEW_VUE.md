# Vue 前端代码审查清单

## 1. 正确性 & Bug

1. 响应式系统：是否存在 reactive/ref 解构丢失响应式、错误赋值导致响应式断裂
2. 生命周期：onMounted/onUnmounted 是否配对（事件监听、定时器、WebSocket 等）
3. 异步竞态：watch/watchEffect 中的异步操作是否有竞态风险，是否使用 AbortController 或标志位
4. 列表渲染：v-for 的 key 是否稳定且唯一，避免用 index 做 key
5. 边界情况：空值/undefined 是否被妥善处理，数组越界、可选链缺失

## 2. 性能

1. 不必要的重渲染：组件 props 是否传递了内联对象/数组（每次渲染都是新引用）
2. 计算缓存：昂贵计算是否用 computed 而非方法调用，computed 是否有副作用
3. 大数据渲染：长列表是否使用虚拟滚动，表格数据是否分页
4. watch deep：是否对大对象使用 deep: true，能否替换为精确监听路径
5. 资源加载：图片是否懒加载，组件是否异步加载（defineAsyncComponent）
6. 内存泄漏：闭包/定时器/事件监听是否在组件卸载时清理

## 3. 组件设计 & 架构

1. 单一职责：组件是否承担了过多职责，是否应该拆分
2. Props 定义：是否有完整的 TypeScript 类型/默认值/required/validator
3. 事件规范：emit 是否用 defineEmits 声明，事件名是否使用 kebab-case
4. 组件通信：父子通信是否用 props/emit，跨层级是否用 provide/inject，全局状态是否用 Pinia
5. 逻辑复用：是否有重复逻辑可以提取为 composable（useXxx）
6. 插槽使用：是否有硬编码的内容应该用 slot 替代
7. 组件 API：props 命名是否语义化，组件是否易用且灵活

## 4. TypeScript 类型安全

1. any 类型：是否有 any 可以替换为具体类型
2. 类型断言：as 断言是否可以用类型守卫（type guard）替代
3. Props 类型：是否使用 defineProps\<T\>() 泛型声明，而非运行时声明
4. API 类型：接口返回值是否有类型定义，是否处理了错误响应的类型
5. 泛型使用：是否合理使用泛型提升复用性
6. 工具类型：是否可使用 Partial/Pick/Omit/Record 等简化类型定义

## 5. 状态管理 Pinia

1. Store 拆分：是否按领域/功能拆分，单个 store 是否过大
2. 状态修改：组件是否通过 action 修改状态而非直接赋值
3. 异步处理：action 中的异步操作是否有 try/catch，错误是否妥善处理
4. Store 组合：多个 store 之间是否有循环依赖
5. 持久化：是否需要 pinia-plugin-persistedstate，敏感数据是否排除
6. 类型安全：state/getters/actions 是否有完整 TypeScript 类型

## 6. 安全 & 数据校验

1. XSS 风险：是否使用 v-html，内容是否经过 sanitize
2. 数据校验：用户输入是否在前后端都做了校验
3. 认证令牌：token 是否存储在合适位置，是否在请求拦截器中统一处理
4. 敏感数据：是否有密码/密钥等硬编码或暴露在客户端
5. URL 注入：动态跳转是否校验目标 URL，防止 open redirect
6. 第三方依赖：是否有已知漏洞的依赖

## 7. 可维护性 & 规范

1. 命名规范：组件是否 PascalCase，变量/函数是否 camelCase，常量是否 SCREAMING_SNAKE_CASE
2. 魔法值：是否有硬编码的数字/字符串应提取为常量或枚举
3. 代码重复：是否有重复逻辑应提取为公共函数或 composable
4. 注释质量：复杂逻辑是否有注释，注释是否准确且有价值
5. 文件结构：单文件组件是否按 \<script setup\> / \<template\> / \<style\> 顺序组织
6. 代码长度：单文件是否过长（>300 行建议拆分），单个函数是否过长
