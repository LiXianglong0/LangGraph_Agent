<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import mermaid from 'mermaid'

const props = defineProps({
  code: { type: String, required: true },
})

const host = ref(null)
const err = ref('')
let renderSeq = 0

mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'loose',
  theme: 'neutral',
  flowchart: { curve: 'basis', htmlLabels: true },
})

async function render() {
  err.value = ''
  await nextTick()
  if (!host.value || !props.code?.trim()) return
  const id = `mmd-${Date.now()}-${++renderSeq}`
  try {
    const { svg } = await mermaid.render(id, props.code.trim())
    host.value.innerHTML = svg
  } catch (e) {
    err.value = e?.message || String(e)
    host.value.innerHTML = ''
  }
}

watch(() => props.code, render, { immediate: true })

onBeforeUnmount(() => {
  if (host.value) host.value.innerHTML = ''
})
</script>

<template>
  <div class="mermaid-wrap">
    <div v-if="err" class="mermaid-err">流程图渲染失败：{{ err }}</div>
    <div ref="host" class="mermaid-host" aria-label="Agent 流程图" />
  </div>
</template>
