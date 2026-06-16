<template>
  <div class="audit-view">
  <el-card>
    <h3>📋 API Audit Log</h3>
    <p style="color:var(--el-text-color-secondary);margin-bottom:12px">Recent API requests</p>
    <el-table :data="logs" stripe size="small" v-loading="loading">
      <el-table-column label="Time" width="200">
        <template #default="{ row }">{{ new Date(row.timestamp * 1000).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="Method" width="100">
        <template #default="{ row }">
          <el-tag :type="methodType(row.method)" size="small">{{ row.method }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="path" label="Path" min-width="200">
        <template #default="{ row }"><code>{{ row.path }}</code></template>
      </el-table-column>
      <el-table-column prop="bot_id" label="Bot" width="130" />
      <el-table-column prop="source_ip" label="IP" width="120" />
      <el-table-column label="Status" width="100">
        <template #default="{ row }">
          <span :style="{ color: row.status >= 400 ? '#ef4444' : '#10b981', fontWeight: 'bold' }">{{ row.status }}</span>
        </template>
      </el-table-column>
      <el-table-column label="Latency" width="100">
        <template #default="{ row }">{{ row.duration_ms }}ms</template>
      </el-table-column>
    </el-table>
  </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useApi } from '../composables/useApi'

const { api } = useApi()
const logs = ref([])
const loading = ref(false)
let timer = null

function methodType(m) {
  const map = { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger' }
  return map[m] || 'info'
}

async function refresh() {
  try { logs.value = await api('/api/audit?limit=200') } catch {}
}

onMounted(() => { refresh(); timer = setInterval(refresh, 15000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.audit-view { height: 100%; overflow-y: auto; padding-bottom: 20px; }
</style>
