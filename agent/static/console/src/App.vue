<template>
  <div class="app-layout">
    <el-menu
      :default-active="activeTab"
      class="app-nav"
      @select="handleTabSelect"
    >
      <div class="nav-title">Zowsup Console</div>
      <el-menu-item index="escalations">
        <el-icon><WarningFilled /></el-icon>
        <span>Escalations</span>
      </el-menu-item>
      <el-menu-item index="conversations">
        <el-icon><ChatDotRound /></el-icon>
        <span>Conversations</span>
      </el-menu-item>
      <el-menu-item index="plugins">
        <el-icon><SetUp /></el-icon>
        <span>Plugins</span>
      </el-menu-item>
      <el-menu-item index="bots">
        <el-icon><Monitor /></el-icon>
        <span>Bots</span>
      </el-menu-item>
      <el-menu-item index="audit">
        <el-icon><Document /></el-icon>
        <span>Audit</span>
      </el-menu-item>
      <el-menu-item v-if="showCluster" index="cluster">
        <el-icon><Connection /></el-icon>
        <span>Cluster</span>
      </el-menu-item>
    </el-menu>

    <div class="app-main">
      <EscalationsTab v-if="activeTab === 'escalations'" />
      <ConversationsTab v-if="activeTab === 'conversations'" />
      <PluginsTab v-if="activeTab === 'plugins'" />
      <BotsTab v-if="activeTab === 'bots'" />
      <AuditTab v-if="activeTab === 'audit'" />
      <ClusterTab v-if="activeTab === 'cluster' && showCluster" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  WarningFilled, ChatDotRound, SetUp, Monitor, Document, Connection
} from '@element-plus/icons-vue'
import EscalationsTab from './views/EscalationsTab.vue'
import ConversationsTab from './views/ConversationsTab.vue'
import PluginsTab from './views/PluginsTab.vue'
import BotsTab from './views/BotsTab.vue'
import AuditTab from './views/AuditTab.vue'
import ClusterTab from './views/ClusterTab.vue'

const activeTab = ref('escalations')
const showCluster = ref(false)

function handleTabSelect(index) {
  activeTab.value = index
}

onMounted(async () => {
  try {
    const r = await fetch('/api/cluster/agents')
    if (r.ok || r.status === 403) showCluster.value = true
  } catch { /* standalone */ }
})
</script>

<style>
.app-layout { display: flex; height: 100%; }
.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 24px;
  background: var(--zs-bg);
}
.app-main > :deep(div) {
  flex: 1;
  min-height: 0;
}
</style>
