<template>
  <span class="inline-block w-1.5 h-4 bg-slate-700 animate-blink align-text-bottom"></span>
</template>

<style scoped>
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.animate-blink {
  animation: blink 1s step-end infinite;
}
</style>