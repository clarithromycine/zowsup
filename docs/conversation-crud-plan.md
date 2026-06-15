# Conversation CRUD — 实施计划

> 日期: 2026-06-14  
> 状态: 方案已确认，待实施

---

## 0. 设计原则

| 原则 | 说明 |
|------|------|
| 自动建会话 | 第一条 incoming 或 outgoing 消息触发，不手动创建 |
| 群消息区分发言人 | `from`=群JID，`participant`=实际发言人 |
| 消息状态追踪 | EXECUTED→SENT→DELIVERED→READ→RESPONSE→ERROR |
| 删除=DB清理 | 不触发 WhatsApp revoke；revoke 单独端点 |

---

## 1. 数据模型

### 1.1 SQLite Schema

```sql
CREATE TABLE conversations (
    id              TEXT PRIMARY KEY,
    bot_id          TEXT NOT NULL,
    jid             TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT '1v1',
    status          TEXT NOT NULL DEFAULT 'active',
    last_message_at REAL,
    message_count   INTEGER NOT NULL DEFAULT 0,
    created_at      REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at      REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);
CREATE INDEX idx_conv_bot ON conversations(bot_id);
CREATE INDEX idx_conv_updated ON conversations(bot_id, updated_at DESC);

CREATE TABLE messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    msg_id          TEXT,
    direction       TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    content         TEXT,
    participant_jid TEXT,
    status          TEXT NOT NULL DEFAULT 'EXECUTED',
    status_updated  REAL,
    raw             TEXT,
    sent_at         REAL NOT NULL,
    created_at      REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);
CREATE INDEX idx_msg_conv ON messages(conversation_id, sent_at);
CREATE INDEX idx_msg_msgid ON messages(msg_id);
```

### 1.2 Pydantic 模型

```python
class MessageType(str, Enum):
    TEXT="TEXT"; AD="AD"; INTERACTIVE="INTERACTIVE"; URL="URL"
    IMAGE="IMAGE"; VIDEO="VIDEO"; AUDIO="AUDIO"; DOCUMENT="DOCUMENT"
    STICKER="STICKER"; REACTION="REACTION"; POLL="POLL"
    REVOKE="REVOKE"; UNKNOWN_MEDIA="UNKNOWN_MEDIA"; OTHER="OTHER"

class MessageStatusEnum(str, Enum):
    EXECUTED="EXECUTED"; SENT="SENT"; DELIVERED="DELIVERED"
    READ="READ"; RESPONSE="RESPONSE"; ERROR="ERROR"

class ConversationType(str, Enum):
    ONE_TO_ONE="1v1"; GROUP="group"

class ConversationInfo(BaseModel):
    id: str; bot_id: str; jid: str
    type: ConversationType; status: str
    message_count: int; last_message_at: float | None
    created_at: float; updated_at: float

class MessageInfo(BaseModel):
    id: int; conversation_id: str; msg_id: str | None
    direction: str; content_type: str; content: str | None
    participant_jid: str | None
    status: str; status_updated: float | None
    sent_at: float

class ConversationDetail(ConversationInfo):
    messages: list[MessageInfo]

class SendMessageRequest(BaseModel):
    content: str; content_type: str = "TEXT"
```

---

## 2. 实施 Phase

### Phase 0: ConversationStore（1.5h）

**目标**: SQLite CRUD 层，线程安全

| # | 任务 | 检查点 |
|---|------|--------|
| 0.1 | `conversation_store.py` — 建表 + WAL | `start()` 首次自动建表 |
| 0.2 | `upsert_conversation(bot_id, jid, type)` | 幂等：存在→更新，不存在→INSERT |
| 0.3 | `record_message(cid, ...)` | INSERT msg + UPDATE conv count/updated_at |
| 0.4 | `update_message_status(msg_id, status)` | 按 msg_id 更新状态 |
| 0.5 | `get_conversation(cid)` → 详情+消息 | `limit/before` 分页 |
| 0.6 | `list_conversations(bot_id)` | 按 bot_id 过滤，updated_at 倒序 |
| 0.7 | `delete_conversation(cid)` / `close_conversation(cid)` | 级联删消息 / 仅标记 closed |

**可测试**（纯单元，不依赖 agent）:
```python
store = ConversationStore(":memory:"); store.start()
c = store.upsert_conversation("bot1", "j@s.wp.net", "1v1")
assert c["id"] == "bot1:j@s.wp.net"
# 幂等
c2 = store.upsert_conversation("bot1", "j@s.wp.net", "1v1")
assert c2["id"] == c["id"]
```

**验收**: `python -m pytest tests/test_phase8_conversation.py::TestStore -v` ✅

---

### Phase 1: REST API（1.5h）

**目标**: 5 个 CRUD 端点 + revoke

| # | 任务 | 检查点 |
|---|------|--------|
| 1.1 | `schemas.py` 新增模型 | ConversationInfo, MessageInfo, ConversationDetail, SendMessageRequest |
| 1.2 | `conversation_api.py` | 见下方 API 表 |
| 1.3 | `server.py` 注册路由 | lifespan include_router |

**API**:

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/conversation?bot_id=` | 列出会话 |
| `GET` | `/api/conversation/{cid:path}` | 详情+消息（`?limit=50&before=ts`） |
| `DELETE` | `/api/conversation/{cid:path}` | 删除（`?mode=close` 仅关闭） |
| `POST` | `/api/conversation/{cid:path}/message` | 发送消息 |
| `POST` | `/api/conversation/{cid:path}/message/{msg_id}/revoke` | Revoke |

**可测试**:
```python
# 发消息 → 自动建会话
r = requests.post(f"{b}/api/conversation/{bot_id}:{jid}/message", json={"content":"hi"})
assert r.status_code == 200
# 获取详情
r = requests.get(f"{b}/api/conversation/{bot_id}:{jid}")
assert len(r.json()["messages"]) == 1
# 删除
r = requests.delete(f"{b}/api/conversation/{bot_id}:{jid}")
assert r.json()["deleted"] is True
```

**验收**: `python -m pytest tests/test_phase8_conversation.py::TestAPI -v` ✅

---

### Phase 2: 消息捕获（1h）

**目标**: incoming/outgoing 消息自动入库

| # | 任务 | 检查点 |
|---|------|--------|
| 2.1 | incoming 捕获 | `_on_bot_event` message → `conv_store.record_message()` |
| 2.2 | outgoing 捕获 | `msg_api` + `conversation_api` send 成功后记录 |
| 2.3 | 群 participant | `message["participant"]` → `participant_jid` |

**可测试**（需 real bot）:
```python
# 真实 bot 收一条 WhatsApp 消息 → GET conversation 验证存在
# POST sendmsg → 验证 conversation 中新增 outgoing
```

**验收**: `python -m pytest tests/test_phase8_conversation.py::TestCapture -v` ✅

---

### Phase 3: 状态追踪（0.5h）

**目标**: EXECUTED→SENT→DELIVERED→READ 流转

| # | 任务 | 检查点 |
|---|------|--------|
| 3.1 | messageStatus 回调 | `_on_bot_event` → `update_message_status(msg_id, status)` |
| 3.2 | API 返回含 status | `GET conversation` 消息带 status 字段 |

**可测试**:
```python
# outgoing 初始 status=EXECUTED
# GET conversation 返回中 status 字段存在
```

**验收**: `python -m pytest tests/test_phase8_conversation.py::TestStatus -v` ✅

---

### Phase 4: Revoke（0.5h）

**目标**: WhatsApp 消息撤回

| # | 任务 | 检查点 |
|---|------|--------|
| 4.1 | revoke 端点 | `POST .../{msg_id}/revoke` → 调 `msg.revoke` |
| 4.2 | DB 标记 | status → REVOKE |

**验收**: `python -m pytest tests/test_phase8_conversation.py::TestRevoke -v` ✅

---

## 3. 依赖与汇总

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3
                              └─→ Phase 4
```

| Phase | 内容 | 测试类 | 预计 |
|-------|------|--------|------|
| 0 | ConversationStore | `TestStore` | 1.5h |
| 1 | REST API | `TestAPI` | 1.5h |
| 2 | 消息捕获 | `TestCapture` | 1h |
| 3 | 状态追踪 | `TestStatus` | 0.5h |
| 4 | Revoke | `TestRevoke` | 0.5h |
| **Total** | | | **~5h** |
