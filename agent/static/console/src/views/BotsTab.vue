<template>
  <div class="bots-view">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>🤖 Bots</span>
          <div class="header-info">
            <span v-if="health">Uptime: {{ uptime }} &middot; DB: {{ health.db_bot_count }} &middot; WS: {{ health.ws_connections }} &middot; Threads: {{ health.thread_count }}</span>
          </div>
          <div class="header-actions">
            <el-button size="small" @click="scanAccounts" :loading="scanning">🔍 Scan</el-button>
            <el-button size="small" @click="showImport = !showImport">{{ showImport ? '−' : '+' }} Import</el-button>
          </div>
        </div>
      </template>

      <!-- Import form -->
      <div v-if="showImport" class="import-form">
        <el-input v-model="importCsv" placeholder="6-Segment CSV: phone,cc,..." style="width:300px" size="small" />
        <el-select v-model="importEnv" size="small" style="width:130px">
          <el-option v-for="e in envs" :key="e" :value="e" :label="e" />
        </el-select>
        <el-button type="primary" size="small" @click="importBot">Import</el-button>
      </div>

      <!-- Filters -->
      <div class="filters">
        <el-input v-model="filterId" placeholder="Filter BotID..." size="small" style="width:160px" clearable />
        <el-select v-if="isCluster" v-model="filterAgent" size="small" style="width:160px" clearable placeholder="All Agents">
          <el-option v-for="a in agents" :key="a.agent_id" :value="a.agent_id" :label="a.agent_id" />
        </el-select>
        <el-button size="small" @click="refresh">Refresh</el-button>
      </div>

      <!-- Table -->
      <el-table :data="filteredBots" stripe size="small" v-loading="loading">
        <el-table-column prop="bot_id" label="Bot ID" min-width="130">
          <template #default="{ row }"><b>{{ row.bot_id }}</b></template>
        </el-table-column>
        <el-table-column v-if="isCluster" prop="agent_id" label="Agent" width="120" />
        <el-table-column prop="status" label="Status" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'RUNNING' ? 'success' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="env" label="Env" width="100" />
        <el-table-column label="Uptime" width="100">
          <template #default="{ row }">
            {{ row.uptime_seconds ? Math.floor(row.uptime_seconds / 60) + 'm' : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openLogs(row.bot_id)">📋</el-button>
            <el-button
              v-if="row.status === 'RUNNING'"
              type="danger" size="small"
              @click="controlBot(row.bot_id, 'stop')"
            >Stop</el-button>
            <el-button
              v-else
              type="primary" size="small"
              @click="controlBot(row.bot_id, 'start')"
            >Start</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Log Viewer Dialog -->
    <LogViewer ref="logViewer" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useApi } from '../composables/useApi'
import LogViewer from './LogViewer.vue'

const { api } = useApi()

const bots = ref([])
const health = ref(null)
const agents = ref([])
const loading = ref(false)
const scanning = ref(false)
const filterId = ref('')
const filterAgent = ref('')
const showImport = ref(false)
const importCsv = ref('')
const importEnv = ref('android')
const envs = ['android', 'smb_android', 'ios', 'smb_ios']
const logViewer = ref(null)
let refreshTimer = null

const isCluster = computed(() => bots.value.some(b => b.agent_id))
const uptime = computed(() => {
  if (!health.value) return ''
  const u = health.value.uptime_seconds || 0
  return `${Math.floor(u / 3600)}h ${Math.floor((u % 3600) / 60)}m`
})

const filteredBots = computed(() => {
  let list = bots.value
  if (isCluster.value && filterAgent.value) {
    list = list.filter(b => b.agent_id === filterAgent.value)
  }
  if (filterId.value) {
    const q = filterId.value.toLowerCase()
    list = list.filter(b => (b.bot_id || '').toLowerCase().includes(q))
  }
  return list
})

async function refresh() {
  try {
    const [b, h] = await Promise.all([
      api('/api/listbot').catch(() => []),
      api('/api/health').catch(() => null),
    ])
    bots.value = b || []
    health.value = h
    if (isCluster.value) {
      try { agents.value = await api('/api/cluster/agents') } catch {}
    }
  } catch {}
}

async function controlBot(id, action) {
  try {
    const endpoint = action === 'start' ? '/api/startbot' : '/api/stopbot'
    const body = action === 'start' ? { bot_ids: [id] } : { bot_ids: [id], mode: 'force' }
    await api(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    ElMessage.success(`Bot ${id} ${action}ed`)
  } catch { /* handled by api() */ }
  refresh()
}

async function scanAccounts() {
  scanning.value = true
  try {
    await api('/api/scan', { method: 'POST' })
    ElMessage.success('Scan complete')
  } catch {}
  scanning.value = false
  refresh()
}

async function importBot() {
  if (!importCsv.value.trim()) return
  try {
    await api('/api/importbot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accounts: [{ data: importCsv.value, env: importEnv.value }] }),
    })
    ElMessage.success('Imported')
    importCsv.value = ''
    showImport.value = false
  } catch {}
  refresh()
}

function openLogs(botId) {
  logViewer.value?.open(botId)
}

onMounted(() => {
  refresh()
  refreshTimer = setInterval(refresh, 15000)
})
onUnmounted(() => clearInterval(refreshTimer))
</script>

<style scoped>
.bots-view { height: 100%; overflow-y: auto; padding-bottom: 20px; }
.bots-view :deep(.el-card) { margin-bottom: 0; }
.card-header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.header-info { font-size: 12px; color: var(--el-text-color-secondary); flex: 1; }
.header-actions { display: flex; gap: 6px; }
.import-form { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
.filters { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
