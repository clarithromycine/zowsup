<template>
  <el-dialog
    v-model="visible"
    :title="'📋 ' + botId + ' Logs'"
    width="85%"
    top="5vh"
    destroy-on-close
    @closed="disconnect"
  >
    <div class="log-status">
      <el-tag :type="statusType" size="small">{{ statusText }}</el-tag>
      <span class="log-count">{{ lineCount }} lines</span>
      <el-switch
        v-model="autoScroll"
        active-text="Auto-scroll"
        size="small"
        style="margin-left: auto"
      />
    </div>
    <div ref="logBody" class="log-body" @scroll="onScroll">
      <div
        v-for="(line, i) in lines"
        :key="i"
        class="log-line"
        :class="{ 'log-error': isError(line), 'log-warn': isWarn(line) }"
      >{{ line }}</div>
      <div v-if="!lines.length" class="log-empty">Loading...</div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { useWebSocket } from '../composables/useWebSocket'

const visible = ref(false)
const botId = ref('')
const lines = ref([])
const lineCount = ref(0)
const autoScroll = ref(true)
const logBody = ref(null)
const { connect, close } = useWebSocket()

const statusMap = { 0: ['info', 'Connecting...'], 1: ['success', '● LIVE'], 2: ['warning', '● Disconnected'], 3: ['danger', '● Error'] }
const statusIdx = ref(0)
const statusType = computed(() => statusMap[statusIdx.value]?.[0] || 'info')
const statusText = computed(() => statusMap[statusIdx.value]?.[1] || '')

let _closing = false

function open(id) {
  botId.value = id
  lines.value = []
  lineCount.value = 0
  statusIdx.value = 0
  _closing = false
  visible.value = true
  loadHistory(id)
}

async function loadHistory(id) {
  try {
    const r = await fetch(`/api/bot/${encodeURIComponent(id)}/logs/recent?lines=200`)
    if (r.ok) {
      const data = await r.json()
      appendLines(data.lines || [], true)
    }
  } catch {}
  connectWs(id)
}

function connectWs(id) {
  statusIdx.value = 0
  const url = `/api/bot/${encodeURIComponent(id)}/logs?tail=0`
  connect(url, {
    onopen() { statusIdx.value = 1 },
    onmessage(e) { if (!_closing) appendLines([e.data], false) },
    onclose() { if (!_closing) statusIdx.value = 2 },
    onerror() { if (!_closing) statusIdx.value = 3 },
  })
}

function disconnect() {
  _closing = true
  close()
}

function appendLines(newLines, replace) {
  if (replace) lines.value = []
  lines.value.push(...newLines)
  lineCount.value = lines.value.length
  if (autoScroll.value) {
    nextTick(() => {
      if (logBody.value) logBody.value.scrollTop = logBody.value.scrollHeight
    })
  }
}

function onScroll() {
  if (!logBody.value) return
  const el = logBody.value
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 30
}

function isError(line) {
  const lc = line.toLowerCase()
  return lc.includes('| error') || lc.includes('traceback')
}
function isWarn(line) {
  return line.toLowerCase().includes('| warning')
}

defineExpose({ open })
</script>

<style scoped>
.log-status { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.log-count { font-size: 12px; color: var(--el-text-color-secondary); }
.log-body {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 12px 16px;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #c0c0c0;
  white-space: pre-wrap;
  word-break: break-all;
  height: 50vh;
  overflow-y: auto;
}
.log-body::-webkit-scrollbar { width: 6px; }
.log-body::-webkit-scrollbar-thumb { background: rgba(255,255,255,.15); border-radius: 3px; }
.log-line { padding: 1px 0; }
.log-error { color: #ef4444; }
.log-warn { color: #f59e0b; }
.log-empty { color: rgba(255,255,255,.3); }
</style>
