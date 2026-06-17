<template>
  <div class="cluster-view">
    <!-- Agent list -->
    <el-card v-if="!detailId">
      <template #header>
        <div class="card-row">
          <span>🖥 Cluster</span>
          <span class="sub">{{onlineCnt}}/{{agents.length}} agents online</span>
          <el-button size="small" @click="load">Refresh</el-button>
        </div>
      </template>
      <el-table :data="agents" stripe size="small" v-loading="loading" @row-click="openDetail">
        <el-table-column prop="agent_id" label="Agent ID" width="200"/>
        <el-table-column label="Status" width="120">
          <template #default="{row}"><el-tag :type="row.status==='online'?'success':'danger'" size="small">{{row.status}}</el-tag></template>
        </el-table-column>
        <el-table-column prop="url" label="URL" min-width="200"/>
        <el-table-column label="Bots" width="100"><template #default="{row}">{{row.bot_count||0}}</template></el-table-column>
        <el-table-column label="" width="80"><template #default="{row}"><el-button type="primary" size="small">View</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <!-- Agent detail -->
    <el-card v-else>
      <div class="card-row"><span>🖥 {{detailId}}</span><el-tag :type="agent.status==='online'?'success':'danger'" size="small">{{agent.status}}</el-tag><el-button size="small" @click="back">← Back</el-button></div>
      <div class="sub" style="margin:6px 0">URL: {{agent.url}} · Bots: {{(agent.bots||[]).length}}</div>
      <el-table :data="agentBots" stripe size="small" v-loading="dloading">
        <el-table-column prop="bot_id" label="Bot ID" min-width="130"><template #default="{row}"><b>{{row.bot_id}}</b></template></el-table-column>
        <el-table-column prop="agent_id" label="Agent" width="120" />
        <el-table-column label="Status" width="120"><template #default="{row}"><el-tag :type="row.status==='RUNNING'?'success':'warning'" size="small">{{row.status}}</el-tag></template></el-table-column>
        <el-table-column prop="env" label="Env" width="120"/>
        <el-table-column label="Uptime" width="120"><template #default="{row}">{{row.uptime_seconds?Math.floor(row.uptime_seconds/60)+'m':'—'}}</template></el-table-column>
        <el-table-column label="Migrate" width="250">
          <template #default="{row}">
            <el-select v-model="migTargets[row.bot_id]" size="small" style="width:130px" placeholder="Target Agent">
              <el-option v-for="a in otherAgents" :key="a.agent_id" :value="a.agent_id" :label="`${a.agent_id} (${a.bot_count||0})`"/>
            </el-select>
            <el-button size="small" style="margin-left:4px" @click="migrateBot(row.bot_id)">→</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useApi } from '../composables/useApi'
const { api } = useApi()

const agents=ref([]),loading=ref(false),detailId=ref(''),agent=ref({}),agentBots=ref([]),dloading=ref(false),migTargets=ref({})
const onlineCnt=computed(()=>agents.value.filter(a=>a.status==='online').length)
const otherAgents=computed(()=>agents.value.filter(a=>a.agent_id!==detailId.value&&a.status==='online'))

async function load(){loading.value=true;try{agents.value=await api('/api/cluster/agents')}catch{agents.value=[]}loading.value=false}
function back(){detailId.value='';agent.value={};agentBots.value=[]}

async function openDetail(row){
  detailId.value=row.agent_id
  dloading.value=true
  try{
    const [list, allAgents] = await Promise.all([
      api('/api/listbot').catch(()=>[]),
      api('/api/cluster/agents').catch(()=>[]),
    ])
    agents.value=allAgents
    agent.value=allAgents.find(a=>a.agent_id===detailId.value)||{}
    agentBots.value=(list||[]).filter(b=>b.agent_id===detailId.value)
  }catch{}
  dloading.value=false
}

async function migrateBot(botId){
  const target=migTargets.value[botId]
  if(!target)return
  try{
    await api('/api/cluster/migrate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bot_id:botId,target_agent:target})})
    ElMessage.success('Migrated!')
    openDetail({agent_id:detailId.value})
  }catch{}
}

onMounted(load)
</script>

<style scoped>
.cluster-view{height:100%;overflow-y:auto;padding-bottom:20px}
.card-row{display:flex;align-items:center;gap:12px}.sub{font-size:12px;color:var(--el-text-color-secondary)}
</style>
