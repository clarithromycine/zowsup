<template>
  <div class="plugins-view">
  <el-card v-if="!editName">
    <template #header><span>🧩 Plugins</span></template>
    <el-table :data="plugins" stripe size="small" v-loading="loading">
      <el-table-column prop="name" label="Name" width="140"/>
      <el-table-column prop="version" label="Version" width="100"/>
      <el-table-column label="Status" width="120">
        <template #default="{row}">
          <el-tag :type="row.enabled?'success':'info'" size="small">{{row.enabled?'Enabled':'Disabled'}}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="Description" min-width="200"/>
      <el-table-column label="Actions" width="180">
        <template #default="{row}">
          <el-switch v-model="row.enabled" size="small" @change="toggle(row)"/>
          <el-button size="small" style="margin-left:8px" @click="openEdit(row.name)">Edit</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card v-else>
    <div class="card-row"><span>🧩 {{editName}} Config</span><el-button size="small" @click="editName=''">← Back</el-button></div>
    <el-input v-model="configJson" type="textarea" :rows="12" style="font-family:monospace;font-size:12px;margin:10px 0"/>
    <el-button type="primary" @click="saveConfig">Save</el-button>
  </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useApi } from '../composables/useApi'
const { api } = useApi()
const plugins=ref([]),loading=ref(false),editName=ref(''),configJson=ref('')

async function load(){loading.value=true;try{plugins.value=await api('/api/plugin')}catch{plugins.value=[]}loading.value=false}
async function toggle(p){try{await api(`/api/plugin/${p.name}/enabled`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:p.enabled})});ElMessage.success(p.enabled?'Enabled':'Disabled')}catch{p.enabled=!p.enabled}}
async function openEdit(name){editName.value=name;try{const c=await api(`/api/plugin/${name}/config`);configJson.value=JSON.stringify(c,null,2)}catch{configJson.value='{}'}}
async function saveConfig(){try{await api(`/api/plugin/${editName.value}/config`,{method:'PUT',headers:{'Content-Type':'application/json'},body:configJson.value});ElMessage.success('Saved');editName.value='';load()}catch{}}
onMounted(load)
</script>

<style scoped>
.plugins-view { height: 100%; overflow-y: auto; padding-bottom: 20px; }
.card-row{display:flex;align-items:center;gap:12px}
</style>
