<template>
  <div class="esc-view">
    <el-card v-if="!detailId">
      <template #header>
        <div class="card-row">
          <span>🟡 Escalations</span>
          <el-button-group size="small">
            <el-button v-for="s in statuses" :key="s" :type="filter===s?'primary':''" @click="filter=s">{{s}}</el-button>
          </el-button-group>
          <span class="sub">{{items.length}} items</span>
        </div>
      </template>
      <el-table :data="items" stripe size="small" v-loading="loading">
        <el-table-column label="Conv" min-width="180"><template #default="{row}"><b>{{row.bot_id}}</b><br><span class="sub">{{jid(row)}}</span></template></el-table-column>
        <el-table-column prop="reason" label="Reason" min-width="100"/>
        <el-table-column label="Priority" width="120"><template #default="{row}"><el-tag :type="row.priority==='high'?'danger':'info'" size="small">{{row.priority}}</el-tag></template></el-table-column>
        <el-table-column label="Status" width="90"><template #default="{row}"><el-tag :type="stype(row.status)" size="small">{{row.status}}</el-tag></template></el-table-column>
        <el-table-column label="When" width="200"><template #default="{row}">{{fmt(row.created_at)}}</template></el-table-column>
        <el-table-column width="100"><template #default="{row}"><el-button type="primary" size="small" @click="open(row.id)">View</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-card v-else>
      <div class="card-row"><span>Escalation #{{detailId}}</span><el-tag :type="stype(detail.status)" size="small">{{detail.status}}</el-tag><el-button size="small" @click="back">← Back</el-button></div>
      <div class="meta"><b>Bot:</b> {{detail.bot_id}} &nbsp; <b>Reason:</b> {{detail.reason}} &nbsp; <b>Priority:</b> {{detail.priority}}</div>
      <div class="msg-list" ref="mlist">
        <div v-for="m in msgs" :key="m.id" class="mb" :class="m.content_type==='SYSTEM'?'ms':m.direction==='incoming'?'mi':'mo'">
          <template v-if="m.content_type==='SYSTEM'">
            <span class="sys-msg">{{ m.content }}</span>
            <span class="sys-time">{{ fmt(m.created_at) }}</span>
          </template>
          <template v-else>
          <img v-if="m.content_type==='IMAGE'&&m.media_url" :src="media(m)" style="max-width:240px;max-height:240px;border-radius:8px;cursor:pointer" @click="window.open(media(m))"/>
          <div v-else>{{m.content}}</div>
          <div v-if="m.media_caption" class="mcap">{{m.media_caption}}</div>
          <div v-if="m.note" class="mnote">{{m.note}}</div>
          <div class="mm">{{m.direction}} · {{m.content_type||'TEXT'}} · {{fmt(m.created_at)}}<span v-if="m.direction==='outgoing'" class="mc" :class="ccls(m.status)">{{cico(m.status)}}</span></div>
          </template>
        </div>
      </div>
      <div class="act"><el-button v-if="detail.status==='pending'" type="primary" size="small" @click="claim">Claim</el-button><el-button v-if="detail.status==='claimed'" size="small" @click="unclaim">Unclaim</el-button><template v-if="detail.status==='claimed'||detail.status==='pending'"><el-input v-model="replyText" placeholder="Reply..." size="small" style="flex:1" @keyup.enter="reply"/><el-button type="primary" size="small" @click="reply">Reply</el-button></template><el-button v-if="detail.status!=='resolved'" type="success" size="small" @click="resolve">Resolve</el-button></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useApi } from '../composables/useApi'
import { useWebSocket } from '../composables/useWebSocket'
const { api } = useApi()
const { connect: wsConnect, close: wsClose } = useWebSocket()
const statuses=['pending','claimed','resolved']
const filter=ref('pending'),items=ref([]),loading=ref(false),detailId=ref(null),detail=ref({}),msgs=ref([]),replyText=ref('')
let timer=null
function jid(r){return r.conversation?r.conversation.jid:(r.conversation_id||'').split(':').slice(1).join(':')}
function fmt(t){return t?new Date(t*1000).toLocaleString():''}
function stype(s){return {pending:'warning',claimed:'primary',resolved:'success'}[s]||'info'}
function cico(s){const v=String(s||'').toUpperCase();const m={READ:'✓✓',DELIVERED:'✓✓',RECEIVED:'✓✓',SENT:'✓',SERVER_ACK:'✓',EXECUTED:'⏳',FAILED:'✗',ERROR:'✗','3':'✓','4':'✓✓','5':'✓✓','6':'✗'};return m[v]||'✓'}
function ccls(s){const v=String(s||'').toUpperCase();const m={READ:'read',DELIVERED:'delivered',RECEIVED:'delivered',SENT:'sent',SERVER_ACK:'sent',EXECUTED:'exec',FAILED:'failed',ERROR:'failed','3':'sent','4':'delivered','5':'read','6':'failed'};return m[v]||'sent'}
function media(m){return m.conversation_id&&m.id?`/api/conversation/${encodeURIComponent(m.conversation_id)}/message/${m.id}/media`:''}
async function load(){loading.value=true;try{items.value=await api('/api/escalation?status='+filter.value)}catch{items.value=[]}loading.value=false}
async function open(id){detailId.value=id;try{detail.value=await api('/api/escalation/'+id);msgs.value=(detail.value.messages||[]).filter(m=>m.direction!=='note'||m.content_type==='SYSTEM');connectWs(id)}catch{detailId.value=null}}
function back(){detailId.value=null;detail.value={};msgs.value=[];wsClose()}

function connectWs(id){
  const botId=(detail.value.conversation_id||'').split(':')[0]
  if(!botId)return
  wsConnect(`/api/bot/${encodeURIComponent(botId)}/events?tail=0`,{
    onmessage(e){try{const evt=JSON.parse(e.data);if(evt.type==='message_status'){const st=evt.data||{};if(!st.msgId)return;const bub=msgs.value.find(m=>m.msg_id===st.msgId);if(bub)bub.status=st.status}}catch{}}
  })
}
async function claim(){try{const o=await ElMessageBox.prompt('Operator name?','Claim',{inputValue:'kenny'});await api('/api/escalation/'+detailId.value+'/claim',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operator:o.value})});ElMessage.success('Claimed')}catch{}open(detailId.value)}
async function unclaim(){await api('/api/escalation/'+detailId.value+'/unclaim',{method:'POST'});ElMessage.success('Unclaimed');open(detailId.value)}
async function resolve(){await api('/api/escalation/'+detailId.value+'/resolve',{method:'POST'});ElMessage.success('Resolved');back();load()}
async function reply(){const t=replyText.value.trim();if(!t)return;await api('/api/escalation/'+detailId.value+'/reply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});ElMessage.success('Sent');replyText.value='';open(detailId.value)}
watch(filter,()=>{back();load()})
onMounted(()=>{load();timer=setInterval(load,15000)})
onUnmounted(()=>clearInterval(timer))
</script>

<style scoped>
.esc-view{height:100%;overflow-y:auto;padding-bottom:20px}
.card-row{display:flex;align-items:center;gap:12px}.sub{font-size:12px;color:var(--el-text-color-secondary)}.meta{font-size:13px;margin:8px 0;padding:8px 12px;background:var(--el-fill-color-light);border-radius:6px}
.msg-list{max-height:50vh;overflow-y:auto;display:flex;flex-direction:column-reverse;gap:4px;margin:10px 0}
.mb{max-width:70%;padding:8px 12px;border-radius:12px;font-size:13px;line-height:1.4;white-space:pre-wrap;word-break:break-word}
.mi{background:#e8f0fe;align-self:flex-start}.mo{background:#e8f5e9;align-self:flex-end;margin-left:auto}
.mm{font-size:11px;color:var(--el-text-color-secondary);margin-top:2px}.mcap{margin-top:4px;font-size:13px}.mnote{margin-top:4px;padding-top:4px;border-top:1px solid rgba(0,0,0,.1);font-style:italic;font-size:12px;color:var(--el-text-color-secondary)}
.mc{font-size:13px;margin-left:4px;display:inline-block;width:22px;letter-spacing:-4px}.mc.sent{color:#999}.mc.exec{color:#bbb}.mc.delivered{color:#999}.mc.read{color:#34b7f1}.mc.failed{color:#ef4444}
.act{display:flex;gap:8px;margin-top:12px;align-items:center}
</style>
