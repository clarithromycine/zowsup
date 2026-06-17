<template>
  <div class="conv-view">
    <!-- Left Panel: Conversation List -->
    <div class="conv-left">
      <div class="left-header">
        <el-select v-model="selBot" size="small" @change="loadList" placeholder="Bot">
          <el-option v-for="b in botIds" :key="b" :value="b" :label="b"/>
        </el-select>
        <el-input v-model="search" placeholder="Search..." size="small" clearable class="left-search"/>
      </div>
      <div class="left-list" v-loading="loading">
        <div
          v-for="c in filteredConvs" :key="c.id"
          class="conv-item"
          :class="{ active: chatId === c.id }"
          @click="openChat(c)"
        >
          <div class="avatar-circle" :style="{background:avatarProps(c).bg}">
            <img :src="avatarUrl(c)" class="avatar-img" @error="onAvatarErr($event)" @load="onAvatarLoad($event)" />
            <span class="avatar-initials" :class="{'avatar-group':c.type==='group'}">{{ c.type==='group'?'👥':avatarProps(c).initials }}</span>
          </div>
          <div class="conv-item-body">
            <div class="conv-item-top">
              <span class="conv-name">{{ c.notify_name || c.jid }}</span>
              <span class="conv-time">{{ c.last_message_at ? fmtShort(c.last_message_at) : '' }}</span>
            </div>
            <div class="conv-item-sub">
              <span class="conv-last">{{ c.last_message || '' }}</span>
              <span v-if="unread.has(c.id)" class="conv-dot"></span>
            </div>
          </div>
        </div>
        <div v-if="!filteredConvs.length && !loading" class="conv-empty">No conversations</div>
      </div>
    </div>

    <!-- Right Panel: Chat -->
    <div class="conv-right">
      <div v-if="!chatId" class="conv-empty-state">
        <span>Select a conversation</span>
      </div>
      <template v-else>
        <div class="chat-top">
          <span class="chat-title"><b v-if="chatName">{{ chatName }}</b><span class="sub"> ({{ chatJid }}<span v-if="chatPn">, {{ chatPn }}</span>)</span></span>
          <span class="sub" style="flex:1">{{ msgCount }} msgs</span>
          <span v-if="wsLive" class="ws-dot">●</span>
          <el-button size="small" type="warning" plain @click="escalateChat" :disabled="escalating||escalated">{{ escalating ? 'Escalating...' : escalated ? '🡅 Escalated' : '🡅 Escalate' }}</el-button>
          <el-button size="small" text @click="closeChat">✕</el-button>
        </div>
        <div class="chat-body" ref="chatBody" @scroll="onChatScroll">
          <div v-for="m in chatMsgs" :key="m.id||m._key" class="mb" :class="m.direction==='incoming'?'mi':(m.direction==='system'||m.content_type==='SYSTEM')?'ms':'mo'">
            <template v-if="m.direction==='system'||m.content_type==='SYSTEM'">
              <span class="sys-msg">{{ m.content }}</span>
              <span class="sys-time">{{ fmt(m.created_at) }}</span>
            </template>
            <template v-else>
            <img v-if="m.content_type==='IMAGE'&&m.media_url" :src="media(m)" @load="onImgLoad" class="msg-img" @click="window.open(media(m))"/>
            <video v-else-if="m.content_type==='VIDEO'&&m.media_url" :src="media(m)" controls class="msg-video" preload="metadata"/>
            <audio v-else-if="m.content_type==='AUDIO'&&m.media_url" :src="media(m)" controls class="msg-audio" preload="metadata"/>
            <div v-else-if="m.content_type==='DOCUMENT'&&m.media_url">📄 <a :href="media(m)" :download="m.media_file_name||m.content" class="msg-link">{{ m.media_file_name||m.content }}</a><span class="sub"> · {{ fsize(m.media_file_length) }}</span></div>
            <div v-else>{{ m.content }}</div>
            <div v-if="m.media_caption" class="mcap">{{ m.media_caption }}</div>
            <div v-if="m.note" class="mnote">{{ m.note }}</div>
            <div class="mm">{{ m.direction }} · {{ m.content_type||'TEXT' }} · {{ fmt(m.created_at) }}<span v-if="m.direction==='outgoing'" class="mc" :class="ccls(m.status)">{{ cico(m.status) }}</span></div>
          </template>
          </div>
        </div>
        <div class="chat-foot">
          <el-input v-model="sendText" placeholder="Type a message..." size="small" @keyup.enter="sendMsg" :disabled="sending"/>
          <el-button type="primary" size="small" @click="sendMsg" :loading="sending">Send</el-button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useApi } from '../composables/useApi'
import { useWebSocket } from '../composables/useWebSocket'
const { api } = useApi()
const { connect: wsConnect, close: wsClose, connected: wsLive } = useWebSocket()

const selBot=ref(''),search=ref(''),bots=ref([]),convs=ref([]),loading=ref(false),chatId=ref(null),chatMsgs=ref([]),sendText=ref(''),sending=ref(false),escalating=ref(false),escalated=ref(false)
const chatBody=ref(null),msgCount=ref(0),unread=ref(new Set())
let timer=null,_k=0,_autoScroll=true,_escTimer=null,_autoOpenDone=false

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
function fmtShort(t){if(!t)return'';const d=new Date(t*1000),now=new Date();const isToday=d.toDateString()===now.toDateString();return isToday?d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):d.toLocaleDateString()}
function fsize(b){if(!b)return'';return b>1048576?(b/1048576).toFixed(1)+'MB':(b>1024?(b/1024).toFixed(1)+'KB':b+'B')}
function cico(s){const v=String(s||'').toUpperCase();const m={READ:'✓✓',DELIVERED:'✓✓',RECEIVED:'✓✓',SENT:'✓',SERVER_ACK:'✓',EXECUTED:'⏳',FAILED:'✗',ERROR:'✗','3':'✓','4':'✓✓','5':'✓✓','6':'✗'};return m[v]||'✓'}
function ccls(s){const v=String(s||'').toUpperCase();const m={READ:'read',DELIVERED:'delivered',RECEIVED:'delivered',SENT:'sent',SERVER_ACK:'sent',EXECUTED:'exec',FAILED:'failed',ERROR:'failed','3':'sent','4':'delivered','5':'read','6':'failed'};return m[v]||'sent'}
function media(m){return m.conversation_id&&m.id?`/api/conversation/${encodeURIComponent(m.conversation_id)}/message/${m.id}/media`:''}
function avatarUrl(c){return `/api/avatar/${encodeURIComponent(c.id)}?v=${c.avatar_id||0}`}
function onAvatarErr(e){e.target.style.display='none'}
function onAvatarLoad(e){e.target.style.display=''}

const AVATAR_COLORS=['#ef4444','#f97316','#f59e0b','#eab308','#84cc16','#22c55e','#14b8a6','#06b6d4','#0ea5e9','#3b82f6','#6366f1','#8b5cf6','#a855f7','#d946ef','#ec4899','#f43f5e']
function avatarProps(row){
  const seed=(row.jid||row.id||'')+'_'+((row.notify_name||'').charCodeAt(0)||0)
  let h=0;for(let i=0;i<seed.length;i++)h=((h<<5)-h)+seed.charCodeAt(i)|0
  const bg=AVATAR_COLORS[Math.abs(h)%AVATAR_COLORS.length]
  let initials='?'
  if(row.notify_name){
    const parts=row.notify_name.trim().split(/\s+/)
    initials=parts.length>=2?parts[0][0]+parts[1][0]:row.notify_name.trim().slice(0,2)
  }else if(row.pn_jid){
    initials=row.pn_jid.replace('@s.whatsapp.net','').replace(/[^0-9]/g,'').slice(-2)||'#'
  }else if(row.jid){
    initials=row.jid.split('@')[0].slice(-2)||'#'
  }
  return{initials:initials.toUpperCase(),bg}
}

function updateConvPreview(convId, text, ts){
  const idx=convs.value.findIndex(c=>c.id===convId)
  if(idx<0)return
  const now=ts||Date.now()/1000
  const item={...convs.value[idx],last_message:text||convs.value[idx].last_message,last_message_at:now,updated_at:now,message_count:convs.value[idx].message_count+1}
  const arr=convs.value.filter(c=>c.id!==convId)
  arr.unshift(item)
  convs.value=arr
}

async function loadBots(){try{bots.value=await api('/api/listbot')}catch{bots.value=[]};if(!selBot.value&&botIds.value.length)selBot.value=botIds.value[0]}
async function loadList(){if(!selBot.value)return;loading.value=true;try{convs.value=await api('/api/conversation?bot_id='+selBot.value)}catch{convs.value=[]}loading.value=false;if(!_autoOpenDone&&convs.value.length>0&&!chatId.value){_autoOpenDone=true;openChat(convs.value[0])}}

async function openChat(row){chatId.value=row.id;escalated.value=false;if(unread.value.has(row.id)){unread.value.delete(row.id);unread.value=new Set(unread.value)}try{const d=await api('/api/conversation/'+chatId.value+'?limit=50');chatMsgs.value=(d.messages||[]).filter(m=>m.direction!=='note'||m.content_type==='SYSTEM');msgCount.value=d.message_count||0;_autoScroll=true;connectWs();checkEscalated();_escTimer=setInterval(checkEscalated,10000);nextTick(scrollBottom)}catch{closeChat()}}
function closeChat(){chatId.value=null;chatMsgs.value=[];escalated.value=false;wsClose();clearInterval(_escTimer)}

async function checkEscalated(){
  if(!chatId.value)return
  try{
    const items=await fetch('/api/escalation?bot_id='+chatBotId.value).then(r=>r.ok?r.json():[])
    const wasEscalated=escalated.value
    escalated.value=Array.isArray(items)&&items.some(e=>(e.status==='pending'||e.status==='claimed')&&e.conversation_id===chatId.value)
    if(wasEscalated&&!escalated.value)ElMessage.info('Escalation resolved')
  }catch{escalated.value=false}
}

async function escalateChat(){
  if(!chatId.value||escalating.value||escalated.value)return
  escalating.value=true
  await nextTick()
  try{
    await api('/api/escalation',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({bot_id:chatBotId.value,conversation_id:chatId.value,reason:'manual',priority:'normal'})})
    await api('/api/conversation/'+chatId.value+'/note',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({content:'⬆ Escalation created'})})
    insertSysMsg('⬆ Escalation created')
    escalated.value=true
    ElMessage.success('Escalated')
  }catch{}finally{escalating.value=false}
}

function insertSysMsg(text){
  chatMsgs.value.unshift({_key:'sys'+(_k++),direction:'system',content:text,created_at:Date.now()/1000})
}

function connectWs(){const url=`/api/bot/${encodeURIComponent(chatBotId.value)}/events?tail=0`;wsConnect(url,{onmessage(e){try{const evt=JSON.parse(e.data);if(evt.type==='message'){const msg=evt.data||{};const mc=chatBotId.value+':'+(msg.lid||msg.from_full||'');const wsText=msg.text||'['+({1:'TEXT',5:'IMAGE',6:'VIDEO',7:'AUDIO',8:'DOCUMENT'}[msg.type]||'?')+']';updateConvPreview(mc,wsText);if(mc!==chatId.value){if(!unread.value.has(mc)){unread.value.add(mc);unread.value=new Set(unread.value)}loadList();return}const m={_key:'ws'+(_k++),direction:msg.from_full?'incoming':'outgoing',content:wsText,content_type:{1:'TEXT',5:'IMAGE',6:'VIDEO',7:'AUDIO',8:'DOCUMENT'}[msg.type]||'TEXT',created_at:Date.now()/1000,msg_id:msg.msgId||null,id:msg.db_id||null,conversation_id:chatId.value,media_url:msg.media_url||null,media_key:msg.media_key||null,media_file_name:msg.media_file_name||null,media_file_length:msg.media_file_length||null,media_caption:msg.media_caption||null,status:'EXECUTED'};chatMsgs.value.unshift(m);msgCount.value++;if(_autoScroll)nextTick(scrollBottom);loadList()}else if(evt.type==='message_status'){const st=evt.data||{};if(!st.msgId)return;const bub=chatMsgs.value.find(m=>m.msg_id===st.msgId);if(bub)bub.status=st.status}else if(evt.type==='event'){const ed=evt.data||{};const ev=String(ed.event||'');if(ev==='8'||ev==='CONTACT_UPDATE'){const d=ed.detail||{};if(d.key==='AVATAR'){loadList()}}}}catch{}}})}

async function sendMsg(){const t=sendText.value.trim();if(!t)return;sending.value=true;const tmp={_key:'opt'+(_k++),direction:'outgoing',content:t,content_type:'TEXT',created_at:Date.now()/1000,conversation_id:chatId.value,status:'EXECUTED'};chatMsgs.value.unshift(tmp);sendText.value='';msgCount.value++;if(_autoScroll)nextTick(scrollBottom);updateConvPreview(chatId.value,t,Date.now()/1000);try{const msg=await api('/api/conversation/'+chatId.value+'/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:t})});const idx=chatMsgs.value.indexOf(tmp);if(idx>=0)chatMsgs.value.splice(idx,1,msg);loadList()}catch{ElMessage.error('Send failed');tmp.status='FAILED'}sending.value=false}

onMounted(()=>{loadBots();loadList();timer=setInterval(loadList,15000)})
onUnmounted(()=>{clearInterval(timer);wsClose()})
watch(selBot,loadList)
</script>

<style scoped>
/* ── Layout ── */
.conv-view { display: flex; height: 100%; overflow: hidden; background: var(--zs-card); border-radius: 12px; box-shadow: var(--zs-shadow); }
.conv-left { width: 340px; flex-shrink: 0; border-right: 1px solid var(--zs-border); display: flex; flex-direction: column; }
.conv-right { flex: 1; display: flex; flex-direction: column; min-width: 0; }

/* ── Left Panel ── */
.left-header { display: flex; gap: 8px; padding: 12px; border-bottom: 1px solid var(--zs-border); background: #fafbfc; }
.left-header .el-select { flex: 1; }
.left-search { width: 140px; flex-shrink: 0; }
.left-list { flex: 1; overflow-y: auto; }
.conv-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-bottom: 1px solid #f1f5f9; cursor: pointer; transition: background .12s; }
.conv-item:hover { background: #f8fafc; }
.conv-item.active { background: #eff6ff; border-left: 3px solid var(--zs-accent); padding-left: 11px; }
.conv-item-body { flex: 1; min-width: 0; overflow: hidden; }
.conv-item-top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 3px; }
.conv-name { font-size: 14px; font-weight: 600; color: var(--zs-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px; }
.conv-time { font-size: 11px; color: var(--zs-muted); flex-shrink: 0; }
.conv-item-sub { display: flex; gap: 6px; align-items: center; }
.conv-jid { font-size: 12px; color: var(--zs-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conv-last { font-size: 12px; color: var(--zs-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.conv-dot { width: 8px; height: 8px; border-radius: 50%; background: #ef4444; flex-shrink: 0; margin-left: auto; }
.conv-badge { font-size: 10px; background: #e2e8f0; color: #64748b; padding: 0 6px; border-radius: 8px; }
.conv-empty { padding: 40px; text-align: center; color: var(--zs-muted); font-size: 13px; }

/* ── Right Panel Empty ── */
.conv-empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--zs-muted); font-size: 15px; }

/* ── Chat Header ── */
.chat-top { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--zs-border); background: #fafbfc; flex-shrink: 0; }
.chat-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ws-dot { color: #10b981; font-size: 16px; flex-shrink: 0; }

/* ── Chat Body + Foot ── */
.chat-body { flex: 1; overflow-y: auto; display: flex; flex-direction: column-reverse; gap: 4px; padding: 12px 16px; background: #f8fafc; }
.chat-foot { display: flex; gap: 8px; align-items: center; padding: 10px 16px; border-top: 1px solid var(--zs-border); flex-shrink: 0; background: #fff; }

/* ── Messages ── */
.mb { max-width: 72%; padding: 8px 12px; border-radius: 10px; font-size: 13px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
.mi { background: #fff; align-self: flex-start; box-shadow: 0 1px 2px rgba(0,0,0,.05); }
.mo { background: #d9fdd3; align-self: flex-end; margin-left: auto; }
.ms { background: transparent; align-self: center; max-width: 100%; box-shadow: none; padding: 2px 0; text-align: center; }
.sys-msg { font-size: 11px; color: #94a3b8; }
.sys-time { font-size: 10px; color: #c0c8d4; margin-left: 8px; }
.msg-img { max-width: 240px; max-height: 240px; border-radius: 8px; cursor: pointer; display: block; }
.msg-video { max-width: 300px; max-height: 240px; border-radius: 8px; }
.msg-audio { max-width: 280px; }
.msg-link { color: var(--zs-accent); }
.sub { font-size: 11px; color: var(--zs-muted); }
.mm { font-size: 11px; color: var(--zs-muted); margin-top: 3px; }
.mcap { margin-top: 4px; font-size: 13px; }
.mnote { margin-top: 4px; padding-top: 4px; border-top: 1px solid rgba(0,0,0,.08); font-style: italic; font-size: 12px; color: var(--zs-muted); }
.mc { font-size: 13px; margin-left: 4px; display: inline-block; width: 22px; letter-spacing: -4px; }
.mc.sent { color: #999; } .mc.exec { color: #bbb; } .mc.delivered { color: #999; } .mc.read { color: #34b7f1; } .mc.failed { color: #ef4444; }

/* ── Avatar ── */
.avatar-circle { width: 42px; height: 42px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden; position: relative; }
.avatar-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.avatar-group { font-size: 20px; filter: grayscale(0.3); }
.avatar-initials { color: #fff; font-size: 15px; font-weight: 600; line-height: 1; user-select: none; text-transform: uppercase; }
</style>
