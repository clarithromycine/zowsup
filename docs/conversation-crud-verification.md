# Conversation CRUD — 人工验证手册

> 日期: 2026-06-14  
> 前提: agent 已启动，至少有一个 bot 处于 running 状态  
> 工具: curl / Postman / 手机 WhatsApp

---

## 0. 准备工作

### 0.1 启动 agent

```bash
cd /Volumes/Project_Wisight/zowsup
python -m agent
```

### 0.2 确认 bot 在线

```bash
curl -s http://localhost:8000/api/listbot | python -m json.tool
```

记下你要测试的 `bot_id`（例如 `263783604300`）。

以下所有命令用到的变量（替换为实际值）：

```bash
AGENT=http://localhost:8000
BOT_ID=263783604300          # 替换为实际 bot_id
YOUR_PHONE=8613800138000     # 替换为你的 WhatsApp 号码（不带 +）
```

---

## 1. 入站消息 (Incoming) — 手机发消息给 Bot

### 1.1 发送文本消息

**操作**: 用你的手机 WhatsApp，给 bot 发一条文本，内容：`"人工测试: hello from phone #1"`

### 1.2 验证 — 会话自动创建

```bash
curl -s "$AGENT/api/conversation?bot_id=$BOT_ID" | python -m json.tool
```

**期望**:
- 列表中有一条记录，`jid` 是你的号码 `"8613800138000@s.whatsapp.net"`
- `type` = `"1v1"`
- `status` = `"active"`
- `message_count` >= 1
- `last_message_at` 不为 null

### 1.3 验证 — 消息详情

```bash
# conv_id 格式: bot_id:jid
curl -s "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net?limit=10" | python -m json.tool
```

**期望**:
- `messages` 数组至少包含 1 条记录
- 最新一条的 `direction` = `"incoming"`
- `content_type` = `"TEXT"`
- `content` = `"人工测试: hello from phone #1"`
- `status` = `"EXECUTED"`

---

## 2. 出站消息 (Outgoing) — API 发消息给手机

### 2.1 发送文本

```bash
curl -s -X POST \
  "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net/message" \
  -H "Content-Type: application/json" \
  -d '{"content": "人工测试: hello from API", "content_type": "TEXT"}' | python -m json.tool
```

**Android 期望**: `retcode` = `0`  
**SMBA 期望**: 可能返回 `retcode` != 0（SMBA 不直接支持发送），记录实际返回值即可。

### 2.2 手机确认

检查手机 WhatsApp 是否收到了 `"人工测试: hello from API"`。

- [ ] 手机已收到 ✓

### 2.3 验证 — 出站消息已入库

```bash
curl -s "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net?limit=10" | python -m json.tool
```

**期望**:
- `messages` 中有一条 `direction` = `"outgoing"`
- `content` = `"人工测试: hello from API"`
- `message_count` 已更新（incoming + outgoing 总数）

---

## 3. 消息状态追踪 (Phase 3)

### 3.1 检查出站消息的状态

从步骤 2.3 的输出中找到 outgoing 消息的 `msg_id`（如 `WA-MSG-xxx`），或者直接用：

```bash
curl -s "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net" | python -c "
import sys,json
d=json.load(sys.stdin)
for m in d['messages']:
    if m['direction']=='outgoing':
        print(f'id={m[\"id\"]} msg_id={m[\"msg_id\"]} status={m[\"status\"]}')
"
```

**期望**:
- 初始状态为 `"EXECUTED"`
- 如果 bot 在线且消息已送达，状态应该演进为 `"SENT"` 或 `"DELIVERED"` 或 `"READ"`
- 等几秒后再次查询，检查 `status_updated` 是否有变化

### 3.2 验证状态演进

等 10-30 秒后重新查询同一条消息：

```bash
# 等 15 秒
sleep 15
curl -s "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net?limit=10" | python -c "
import sys,json
d=json.load(sys.stdin)
for m in d['messages'][-3:]:
    print(f'[{m[\"direction\"]}] status={m[\"status\"]} updated={m[\"status_updated\"]}')
"
```

**期望记录**:
| 状态 | 含义 | 是否出现 |
|------|------|----------|
| EXECUTED | 初始 | [ ] |
| SENT | 已发送 | [ ] |
| DELIVERED | 已送达 | [ ] |
| READ | 已读 | [ ] |

> 至少确认 EXECUTED → SENT 或 DELIVERED 的演进是正常的。

---

## 4. Revoke — 撤回消息 (Phase 4)

### 4.1 发送一条可撤回的消息

```bash
RESP=$(curl -s -X POST \
  "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net/message" \
  -H "Content-Type: application/json" \
  -d '{"content": "这条消息将被撤回", "content_type": "TEXT"}')
echo "$RESP" | python -m json.tool
```

从返回中记下 `msg_id`（WhatsApp 消息 ID，如 `WA-xxxxx`）。

### 4.2 撤回

```bash
MSG_ID="从上一步获取的 msg_id"
curl -s -X POST \
  "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net/message/$MSG_ID/revoke" | python -m json.tool
```

**期望**:
- HTTP 200
- 返回体包含 revoke 确认信息

### 4.3 手机确认

检查手机 WhatsApp 中该消息是否已消失/显示 "此消息已被撤回"。

- [ ] 消息已撤回 ✓

---

## 5. 会话管理 — 关闭 & 删除

### 5.1 关闭会话

```bash
curl -s -X DELETE \
  "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net?mode=close" | python -m json.tool
```

**期望**: `"status"` 变为 `"closed"`

### 5.2 验证关闭状态

```bash
curl -s "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net" | python -m json.tool
```

**期望**: `status` = `"closed"`，消息仍在。

### 5.3 删除会话

```bash
curl -s -X DELETE \
  "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net" | python -m json.tool
```

**期望**: 返回 `"deleted": true`

### 5.4 验证已删除

```bash
curl -s "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net"
```

**期望**: HTTP 404

---

## 6. 边界情况

### 6.1 连续多条消息

**操作**: 手机连续发 3 条消息：`"msg-a"`, `"msg-b"`, `"msg-c"`（间隔 1-2 秒）

```bash
curl -s "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net?limit=5" | python -c "
import sys,json
d=json.load(sys.stdin)
print(f'message_count={d[\"message_count\"]}')
for m in d['messages']:
    print(f'  [{m[\"direction\"]}] {m[\"content\"][:50]}')
"
```

**期望**:
- `message_count` 正确
- 3 条消息按时间 ASC 排列
- 每条 `direction` = `"incoming"`

### 6.2 分页

```bash
curl -s "$AGENT/api/conversation/$BOT_ID:${YOUR_PHONE}@s.whatsapp.net?limit=2" | python -c "
import sys,json
d=json.load(sys.stdin)
print(f'返回消息数: {len(d[\"messages\"])} (期望 ≤2)')
if d['messages']:
    print(f'最新一条 sent_at: {d[\"messages\"][-1][\"sent_at\"]}')
"
```

**期望**: 返回 ≤2 条消息。

### 6.3 不存在的会话

```bash
curl -s "$AGENT/api/conversation/nonexistent:fake@s.whatsapp.net"
```

**期望**: HTTP 404。

### 6.4 空列表

```bash
curl -s "$AGENT/api/conversation?bot_id=nonexistent"
```

**期望**: HTTP 200，返回 `[]`。

---

## 7. 群聊测试（如有 WhatsApp 群）

### 7.1 群消息捕获

**操作**: 让群成员在群中发消息 @bot

```bash
curl -s "$AGENT/api/conversation?bot_id=$BOT_ID" | python -m json.tool
```

**期望**:
- 列表中有一条 type = `"1v1"` 的记录，实际群消息 type 也是 `"1v1"`（当前设计如此）
- `jid` = `"群ID@g.us"`

### 7.2 群消息 participant

```bash
# 替换为实际群 JID
GROUP_JID="123456789@g.us"
curl -s "$AGENT/api/conversation/$BOT_ID:$GROUP_JID?limit=10" | python -c "
import sys,json
d=json.load(sys.stdin)
for m in d['messages']:
    print(f'[{m[\"direction\"]}] participant={m[\"participant_jid\"]} content={m[\"content\"][:40]}')
"
```

**期望**: `participant_jid` 不为 null，指向实际发言的群成员。

---

## 8. 汇总检查清单

| # | 测试项 | 通过 | 备注 |
|---|--------|------|------|
| 1.1 | 入站文本 → 自动建会话 | [ ] | |
| 1.3 | 会话详情含入站消息 | [ ] | |
| 2.1 | API 发送消息 | [ ] | |
| 2.2 | 手机收到消息 | [ ] | |
| 2.3 | 出站消息已入库 | [ ] | |
| 3.1 | 消息状态字段存在 | [ ] | |
| 3.2 | 状态有演进 | [ ] | |
| 4.1 | 发送可撤回消息 | [ ] | |
| 4.2 | Revoke 返回 200 | [ ] | |
| 4.3 | 手机消息已撤回 | [ ] | |
| 5.1 | 关闭会话 | [ ] | |
| 5.3 | 删除会话 | [ ] | |
| 5.4 | 删除后 404 | [ ] | |
| 6.1 | 连续多条消息 | [ ] | |
| 6.2 | 分页正确 | [ ] | |
| 6.3 | 不存在会话 404 | [ ] | |
| 6.4 | 空列表 | [ ] | |
| 7.1 | 群消息捕获 | [ ] | |
| 7.2 | 群 participant | [ ] | |

---

## 9. 异常情况记录

如有任何一项不通过，记录：

| 步骤 | 实际现象 | 期望 | 备注 |
|------|----------|------|------|
| | | | |
