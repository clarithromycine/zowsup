<template>
  <div class="conv-view">
    <!-- List view -->
    <el-card v-if="!chatId">
      <template #header>
        <div class="card-row">
          <span>💬 Conversations</span>
          <el-select v-model="selBot" size="small" style="width:160px" @change="loadList" placeholder="Bot">
            <el-option v-for="b in botIds" :key="b" :value="b" :label="b"/>
          </el-select>
          <el-input v-model="search" placeholder="Search JID/PN/name..." size="small" style="width:200px" clearable/>
          <el-button size="small" @click="loadList">Refresh</el-button>
        </div>
      </template>
      <el-table :data="filteredConvs" stripe size="small" v-loading="loading" @row-click="openChat">
        <el-table-column label="JID" width="220"><template #default="{row}"><span style="font-size:12px">{{row.jid}}</span></template></el-table-column>
        <el-table-column label="Name" min-width="140"><template #default="{row}"><b>{{row.notify_name||'—'}}</b></template></el-table-column>
        <el-table-column label="PN" width="150"><template #default="{row}"><span style="font-size:11px;color:var(--el-text-color-secondary)">{{row.pn_jid?row.pn_jid.replace('@s.whatsapp.net',''):'—'}}</span></template></el-table-column>
        <el-table-column label="Type" width="100"><template #default="{row}"><el-tag size="small" :type="row.type==='group'?'warning':''">{{row.type}}</el-tag></template></el-table-column>
        <el-table-column prop="message_count" label="Msgs" width="100" align="center"/>
        <el-table-column label="Last" width="180"><template #default="{row}"><span style="white-space:nowrap;font-size:12px">{{row.last_message_at?new Date(row.last_message_at*1000).toLocaleString():''}}</span></template></el-table-column>
        <el-table-column width="100"><template #default="{row}"><el-button type="primary" size="small" @click.stop="openChat(row)">Chat</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <!-- Chat view -->
    <el-card v-else class="chat-card">
      <div class="card-row chat-top">
        <span><b v-if="chatName">{{chatName}} </b><span class="sub">(jid={{chatJid}}<span v-if="chatPn">, PN: {{chatPn}}</span>)</span></span>
        <span class="sub" style="flex:1">{{msgCount}} msgs</span>
        <span v-if="wsLive" style="color:#10b981;font-size:18px">●</span>
        <el-button size="small" @click="closeChat">← Back</el-button>
      </div>
      <div class="chat-body" ref="chatBody" @scroll="onChatScroll">
        <div v-for="m in chatMsgs" :key="m.id||m._key" class="mb" :class="m.direction==='incoming'?'mi':'mo'">
          <img v-if="m.content_type==='IMAGE'&&m.media_url" :src="media(m)" @load="onImgLoad" style="max-width:240px;max-height:240px;border-radius:8px;cursor:pointer" @click="window.open(media(m))"/>
          <video v-else-if="m.content_type==='VIDEO'&&m.media_url" :src="media(m)" controls style="max-width:300px;max-height:240px;border-radius:8px" preload="metadata"/>
          <audio v-else-if="m.content_type==='AUDIO'&&m.media_url" :src="media(m)" controls style="max-width:300px" preload="metadata"/>
          <div v-else-if="m.content_type==='DOCUMENT'&&m.media_url">📄 <a :href="media(m)" :download="m.media_file_name||m.content" style="color:var(--el-color-primary)">{{m.media_file_name||m.content}}</a><span class="sub"> · {{fsize(m.media_file_length)}}</span></div>
          <div v-else>{{m.content}}</div>
          <div v-if="m.media_caption" class="mcap">{{m.media_caption}}</div>
          <div v-if="m.note" class="mnote">{{m.note}}</div>
          <div class="mm">{{m.direction}} · {{m.content_type||'TEXT'}} · {{fmt(m.created_at)}}<span v-if="m.direction==='outgoing'" class="mc" :class="ccls(m.status)">{{cico(m.status)}}</span></div>
        </div>
      </div>
      <div class="chat-foot">
        <el-input v-model="sendText" placeholder="Send... (Enter=send)" size="small" @keyup.enter="sendMsg" :disabled="sending"/>
        <el-button type="primary" size="small" @click="sendMsg" :loading="sending">Send</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useApi } from '../composables/useApi'
import { useWebSocket } from '../composables/useWebSocket'
const { api } = useApi()
const { connect: wsConnect, close: wsClose, connected: wsLive } = useWebSocket()

const selBot=ref(''),search=ref(''),bots=ref([]),convs=ref([]),loading=ref(false),chatId=ref(null),chatMsgs=ref([]),sendText=ref(''),sending=ref(false)
const chatBody=ref(null),msgCount=ref(0)
let timer=null,_k=0,_autoScroll=true

function scrollBottom(){if(!chatBody.value)return;chatBody.value.scrollTop=0}
function onChatScroll(){if(!chatBody.value)return;_autoScroll=chatBody.value.scrollTop===0}
function onImgLoad(){if(_autoScroll)scrollBottom()}

const botIds=computed(()=>bots.value.map(b=>b.bot_id).filter(Boolean))
const filteredConvs=computed(()=>{let c=convs.value;if(search.value){const q=search.value.toLowerCase();c=c.filter(x=>(x.jid||'').toLowerCase().includes(q)||(x.pn_jid||'').toLowerCase().includes(q)||(x.notify_name||'').toLowerCase().includes(q))}return c})
const chatName=computed(()=>{const c=convs.value.find(x=>x.id===chatId.value);return c?.notify_name||''})
const chatJid=computed(()=>{const c=convs.value.find(x=>x.id===chatId.value);return c?.jid||''})
const chatBotId=computed(()=>(chatId.value||'').split(':')[0])
const chatPn=computed(()=>{const c=convs.value.find(x=>x.id===chatId.value);return c?.pn_jid?c.pn_jid.replace('@s.whatsapp.net',''):''})

function fmt(t){return t?new Date(t*1000).toLocaleString():''}
function fsize(b){if(!b)return'';return b>1048576?(b/1048576).toFixed(1)+'MB':(b>1024?(b/1024).toFixed(1)+'KB':b+'B')}
function cico(s){const v=String(s||'').toUpperCase();const m={READ:'✓✓',DELIVERED:'✓✓',RECEIVED:'✓✓',SENT:'✓',SERVER_ACK:'✓',EXECUTED:'⏳',FAILED:'✗',ERROR:'✗','3':'✓','4':'✓✓','5':'✓✓','6':'✗'};return m[v]||'✓'}
function ccls(s){const v=String(s||'').toUpperCase();const m={READ:'read',DELIVERED:'delivered',RECEIVED:'delivered',SENT:'sent',SERVER_ACK:'sent',EXECUTED:'exec',FAILED:'failed',ERROR:'failed','3':'sent','4':'delivered','5':'read','6':'failed'};return m[v]||'sent'}
function media(m){return m.conversation_id&&m.id?`/api/conversation/${encodeURIComponent(m.conversation_id)}/message/${m.id}/media`:''}

async function loadBots(){try{bots.value=await api('/api/listbot')}catch{bots.value=[]};if(!selBot.value&&botIds.value.length)selBot.value=botIds.value[0]}
async function loadList(){if(!selBot.value)return;loading.value=true;try{convs.value=await api('/api/conversation?bot_id='+selBot.value)}catch{convs.value=[]}loading.value=false}

async function openChat(row){chatId.value=row.id;try{const d=await api('/api/conversation/'+chatId.value+'?limit=50');chatMsgs.value=(d.messages||[]).filter(m=>m.direction!=='note');msgCount.value=d.message_count||0;_autoScroll=true;connectWs();nextTick(scrollBottom)}catch{closeChat()}}
function closeChat(){chatId.value=null;chatMsgs.value=[];wsClose()}

function connectWs(){const url=`/api/bot/${encodeURIComponent(chatBotId.value)}/events?tail=0`;wsConnect(url,{onmessage(e){try{const evt=JSON.parse(e.data);if(evt.type==='message'){const msg=evt.data||{};const mc=chatBotId.value+':'+(msg.lid||msg.from_full||'');if(mc!==chatId.value)return;const m={_key:'ws'+(_k++),direction:msg.from_full?'incoming':'outgoing',content:msg.text||'['+({1:'TEXT',5:'IMAGE',6:'VIDEO',7:'AUDIO',8:'DOCUMENT'}[msg.type]||'?')+']',content_type:{1:'TEXT',5:'IMAGE',6:'VIDEO',7:'AUDIO',8:'DOCUMENT'}[msg.type]||'TEXT',created_at:Date.now()/1000,msg_id:msg.msgId||null,id:msg.db_id||null,conversation_id:chatId.value,media_url:msg.media_url||null,media_key:msg.media_key||null,media_file_name:msg.media_file_name||null,media_file_length:msg.media_file_length||null,media_caption:msg.media_caption||null,status:'EXECUTED'};chatMsgs.value.unshift(m);msgCount.value++;if(_autoScroll)nextTick(scrollBottom)}else if(evt.type==='message_status'){const st=evt.data||{};if(!st.msgId)return;const bub=chatMsgs.value.find(m=>m.msg_id===st.msgId);if(bub)bub.status=st.status}}catch{}}})}

async function sendMsg(){const t=sendText.value.trim();if(!t)return;sending.value=true;const tmp={_key:'opt'+(_k++),direction:'outgoing',content:t,content_type:'TEXT',created_at:Date.now()/1000,conversation_id:chatId.value,status:'EXECUTED'};chatMsgs.value.unshift(tmp);sendText.value='';msgCount.value++;if(_autoScroll)nextTick(scrollBottom);try{const msg=await api('/api/conversation/'+chatId.value+'/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:t})});const idx=chatMsgs.value.indexOf(tmp);if(idx>=0)chatMsgs.value.splice(idx,1,msg)}catch{ElMessage.error('Send failed');tmp.status='FAILED'}sending.value=false}

onMounted(()=>{loadBots();loadList();timer=setInterval(loadList,15000)})
onUnmounted(()=>{clearInterval(timer);wsClose()})
watch(selBot,loadList)
</script>

<style scoped>
.conv-view{display:flex;flex-direction:column;overflow:hidden}
.card-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.sub{font-size:11px;color:var(--el-text-color-secondary)}
.chat-card{display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden}
.chat-card :deep(.el-card__header){flex-shrink:0;padding:12px 12px 0}
.chat-card :deep(.el-card__body){flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;padding:8px 12px 12px}
.chat-top{flex-shrink:0;margin-bottom:4px}
.chat-body{flex:1;overflow-y:auto;display:flex;flex-direction:column-reverse;gap:4px;min-height:0;padding:4px 0}
.chat-foot{display:flex;gap:8px;align-items:center;padding-top:10px;border-top:1px solid var(--el-border-color-light);flex-shrink:0}
.mb{max-width:75%;padding:8px 12px;border-radius:12px;font-size:13px;line-height:1.4;white-space:pre-wrap;word-break:break-word}
.mi{background:#e8f0fe;align-self:flex-start}.mo{background:#e8f5e9;align-self:flex-end;margin-left:auto}
.mm{font-size:11px;color:var(--el-text-color-secondary);margin-top:2px}.mcap{margin-top:4px;font-size:13px}.mnote{margin-top:4px;padding-top:4px;border-top:1px solid rgba(0,0,0,.1);font-style:italic;font-size:12px;color:var(--el-text-color-secondary)}
.mc{font-size:13px;margin-left:4px;display:inline-block;width:22px;letter-spacing:-4px}.mc.sent{color:#999}.mc.exec{color:#bbb}.mc.delivered{color:#999}.mc.read{color:#34b7f1}.mc.failed{color:#ef4444}
</style>
