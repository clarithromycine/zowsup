# ZowSup Agent API

HTTP REST + WebSocket service for remote multi-bot WhatsApp management.

## Startup

```bash
python -m agent [--accesskey KEY] [--host 127.0.0.1] [--port 8000]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--accesskey` | none (no auth) | When set, all endpoints require the key |
| `--host` | `0.0.0.0` | Listen address |
| `--port` | `8000` | Listen port |

## Authentication

- **REST**: Header `X-Access-Key: <key>`
- **WebSocket**: Query param `?access_key=<key>`
- Auth is automatically skipped when `--accesskey` is not set.

---

## REST API

### Health Check

```
GET /api/health
```

**Response** `200`
```json
{"status": "ok", "thread_count": 6}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always `"ok"` when the service is reachable |
| `thread_count` | int | Active threads in the agent process (main, uvicorn, bots) |

---

### List Accounts

```
GET /api/listbot
```

**Response** `200`
```json
[
  {
    "bot_id": "8613800138000",
    "status": "RUNNING",
    "env": "android",
    "started_at": 1718000000,
    "uptime_seconds": 3600,
    "error": null
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `bot_id` | string | Phone number |
| `status` | enum | `INITIAL` / `RUNNING` / `STOPPING` / `STOPPED` / `ERROR` |
| `env` | string | `android` / `smb_android` / `ios` / `smb_ios` |
| `started_at` | int | Unix timestamp |
| `uptime_seconds` | int | Uptime in seconds |
| `error` | string | Error message (only when status is `ERROR`) |

---

### Get Single Account

```
GET /api/bot/{bot_id}
```

**Response** `200` — same `BotInfo` object as above  
**Response** `404` — account not found

---

### Start Bots

```
POST /api/startbot
```

Launches bot threads **concurrently**. Two modes:

- `"sync"` (default) — wait for all logins to complete, then return results
- `"fire"` — return immediately with `INITIAL` status; login results arrive via WebSocket events

**Request**
```json
{
  "mode": "sync",
  "bots": [
    {"bot_id": "8613800138000", "env": "android", "auto_login": true, "proxy": "socks5://host:port"}
  ],
  "bot_ids": ["8613800138001", "8613800138002"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | no | `"sync"` (default) or `"fire"` |
| `bots` | array | no | Full config (per-bot env / proxy) |
| `bots[].bot_id` | string | yes | Phone number |
| `bots[].env` | string | no | Device env; auto-detected from config if omitted |
| `bots[].auto_login` | bool | no | Auto-login on start, defaults to `true` |
| `bots[].proxy` | string | no | Proxy address |
| `bot_ids` | string[] | no | Plain ID list (auto-detect env, default settings) |

> `bots` and `bot_ids` can be used together — they are merged automatically.
> In `"fire"` mode, bot statuses are `INITIAL`; monitor via `WS /api/bot/{id}/events`.

**Response** `200` (sync mode)
```json
{
  "results": [
    {"bot_id": "8613800138000", "status": "RUNNING", "env": "android", "started_at": 1718000000}
  ],
  "success_count": 1,
  "error_count": 0
}
```

**Response** `200` (fire mode)
```json
{
  "results": [
    {"bot_id": "8613800138000", "status": "INITIAL", "env": "android"}
  ],
  "success_count": 1,
  "error_count": 0
}
```

---

### Stop Bots

```
POST /api/stopbot
```

**Request**
```json
{"bot_ids": ["8613800138000", "8613800138001"]}
```

**Response** `200` — same `BatchResult` as above

---

### Execute Command

```
POST /api/bot/cmd
```

**Request**
```json
{
  "bot_id": "8613800138000",
  "command": "msg.send",
  "args": ["8613800138001", "Hello World"],
  "options": {},
  "timeout": 30
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bot_id` | string | yes | Target bot |
| `command` | string | yes | Command name, e.g. `msg.send`, `misc.prekeycount` |
| `args` | string[] | no | Positional arguments |
| `options` | object | no | Keyword options |
| `timeout` | int | no | Timeout in seconds (1-300), defaults to 30 |

**Response** `200` — success
```json
{"retcode": 0, "result": {...}, "error": null}
```

**Response** `200` — command failed (retcode ≠ 0)
```json
{"retcode": -2, "result": null, "error": "Command Not Found"}
```

**Response** `404` — bot not found

---

### Send Message

```
POST /api/sendmsg
```

High-level wrapper over `msg.send` and `msg.sendad`. Accepts text or ad content.

**Text message**

```json
{
  "bot_id": "8613800138000",
  "to": "8613800138001@s.whatsapp.net",
  "content": {"text": "Hello World"}
}
```

**Ad message**

```json
{
  "bot_id": "8613800138000",
  "to": "8613800138001@s.whatsapp.net",
  "content": {
    "ad": {
      "title": "Product Name",
      "titlebody": "Short description",
      "titleurl": "https://example.com",
      "text": "Check out this product!"
    }
  }
}
```

**Media message**

```json
{
  "bot_id": "8613800138000",
  "to": "8613800138001@s.whatsapp.net",
  "content": {
    "media": {
      "type": "image",
      "url": "https://example.com/photo.jpg",
      "caption": "Check this out!"
    }
  }
}
```

**Base64 file upload**

```json
{
  "bot_id": "8613800138000",
  "to": "8613800138001@s.whatsapp.net",
  "content": {
    "media": {
      "type": "document",
      "base64": "dGhpcyBpcyBmaWxlIGNvbnRlbnQ=",
      "fileName": "report.pdf"
    }
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bot_id` | string | yes | Target bot |
| `to` | string | yes | Recipient JID (`number@s.whatsapp.net`) |
| `waitid` | int | no | If set, wait for message ID and return it (timeout seconds) |
| `content.text` | string | *one of* | Plain text → calls `msg.send` |
| `content.ad.title` | string | *one of* | Ad title → calls `msg.sendad` |
| `content.ad.titlebody` | string | no | Ad subtitle |
| `content.ad.titleurl` | string | yes | Ad source URL |
| `content.ad.text` | string | yes | Ad body text |
| `content.ad.thumbnailb64` | string | no | Ad thumbnail as base64 |
| `content.ad.body` | string | no | Ad title body text |
| `content.media.type` | string | *one of* | `image` / `video` / `audio` / `document` |
| `content.media.url` | string | no | HTTP(S) URL of media file |
| `content.media.base64` | string | no | Base64-encoded file content |
| `content.media.path` | string | no | Server-side file path |
| `content.media.caption` | string | no | Caption (image/video/audio) |
| `content.media.fileName` | string | no | Filename (document type) |

> For media, exactly one of `url`, `base64`, or `path` must be provided.  
> Base64 files are decoded to temp files and cleaned up after sending.

**Response** `200` — same `CmdResult`

---

### Import Accounts

```
POST /api/importbot
```

**Request**
```json
{
  "accounts": [
    {"data": "8613800138000,<pk1>,<sk1>,<pk2>,<sk2>,<6th>", "env": "android"},
    {"data": "8613800138001,<pk1>,<sk1>,<pk2>,<sk2>,<6th>", "env": "smb_android"}
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `accounts[].data` | string | yes | 6-segment CSV (phone,pk1,sk1,pk2,sk2,6th) |
| `accounts[].env` | string | no | Device env, defaults to `android` |

**Response** `200` — `BatchResult`

---

### Export Accounts

```
POST /api/exportbot
```

**Request**
```json
{"bot_ids": ["8613800138000", "8613800138001"]}
```

**Response** `200`
```json
{
  "exports": {
    "8613800138000": {
      "data": "8613800138000,<pk1>,<sk1>,<pk2>,<sk2>,<6th>",
      "env": "android"
    },
    "8613800138001": {
      "data": "8613800138001,<pk1>,<sk1>,<pk2>,<sk2>,<6th>",
      "env": "smb_android"
    }
  }
}
```

> `data` is `null` if export failed for that account; `env` is the account's current device environment.

---

### Logs

#### Fetch Recent Logs

```
GET /api/bot/{bot_id}/logs/recent?lines=50
```

| Query | Default | Description |
|-------|---------|-------------|
| `lines` | 50 | Number of lines to return (1-1000) |

**Response** `200`
```json
{"bot_id": "8613800138000", "lines": ["[2026-06-10 12:00:00] INFO Login..."]}
```

#### Clear Logs

```
DELETE /api/bot/{bot_id}/logs
```

**Response** `200`
```json
{"bot_id": "8613800138000", "cleared": true}
```

---

## WebSocket API

### Real-time Log Stream

```
ws://host:port/api/bot/{bot_id}/logs?tail=10&access_key=<key>
```

| Query | Default | Description |
|-------|---------|-------------|
| `tail` | 0 | Send the last N lines on connect |
| `access_key` | — | Auth key |

Sends `tail` historical lines first, then streams new log lines in real time.  
Auth failure results in close code `4003`.

### Real-time Event Stream

```
ws://host:port/api/bot/{bot_id}/events?tail=5&access_key=<key>
```

| Query | Default | Description |
|-------|---------|-------------|
| `tail` | 0 | Send the last N events on connect |
| `access_key` | — | Auth key |

Pushes structured JSON events:

```json
{"type": "message", "bot_id": "8613800138000", "data": {...}}
```

---

## Error Responses

All REST endpoints return errors as:

```json
{"detail": "Error description"}
```

| HTTP Status | Meaning |
|-------------|---------|
| 403 | Authentication failed |
| 404 | Resource not found |
| 422 | Request validation failed |
| 500 | Internal server error |
| 504 | Command execution timed out |
