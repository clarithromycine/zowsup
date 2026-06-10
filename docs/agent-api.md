# ZowSup Agent API

HTTP REST + WebSocket 服务，提供多账号 WhatsApp 机器人的远程管理能力。

## 启动

```bash
python -m agent [--accesskey KEY] [--host 127.0.0.1] [--port 8000]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--accesskey` | 无（免认证） | 设置后所有接口需携带密钥 |
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8000` | 监听端口 |

## 认证

- **REST**：Header `X-Access-Key: <key>`
- **WebSocket**：Query 参数 `?access_key=<key>`
- 未配置 `--accesskey` 时认证自动跳过

---

## REST API

### 健康检查

```
GET /api/health
```

**Response** `200`
```json
{"status": "ok"}
```

---

### 账号列表

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

| 字段 | 类型 | 说明 |
|------|------|------|
| `bot_id` | string | 电话号码 |
| `status` | enum | `INITIAL` / `RUNNING` / `STOPPING` / `STOPPED` / `ERROR` |
| `env` | string | `android` / `smb_android` / `ios` / `smb_ios` |
| `started_at` | int | Unix 时间戳 |
| `uptime_seconds` | int | 运行时长（秒） |
| `error` | string | 错误信息（仅 ERROR 状态） |

---

### 单个账号

```
GET /api/bot/{bot_id}
```

**Response** `200` — 同上的单个 `BotInfo` 对象  
**Response** `404` — 账号不存在

---

### 启动机器人

```
POST /api/startbot
```

**Request**
```json
{
  "bots": [
    {"bot_id": "8613800138000", "env": "android", "auto_login": true, "proxy": "socks5://host:port"}
  ],
  "bot_ids": ["8613800138001", "8613800138002"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `bots` | array | 否 | 完整配置（可按 bot 指定 env / proxy） |
| `bots[].bot_id` | string | 是 | 电话号码 |
| `bots[].env` | string | 否 | 设备环境，不填则自动从 config 检测 |
| `bots[].auto_login` | bool | 否 | 是否自动登录，默认 `true` |
| `bots[].proxy` | string | 否 | 代理地址 |
| `bot_ids` | string[] | 否 | 简单 ID 列表（自动检测 env，默认配置） |

> `bots` 和 `bot_ids` 可以同时使用，会自动合并。

**Response** `200`
```json
{
  "results": [
    {"bot_id": "8613800138000", "status": "RUNNING", "env": "android", "started_at": 1718000000}
  ],
  "success_count": 1,
  "error_count": 0
}
```

---

### 停止机器人

```
POST /api/stopbot
```

**Request**
```json
{"bot_ids": ["8613800138000", "8613800138001"]}
```

**Response** `200` — 同上的 `BatchResult`

---

### 执行命令

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

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `bot_id` | string | 是 | 目标机器人 |
| `command` | string | 是 | 命令名，如 `msg.send`、`misc.prekeycount` |
| `args` | string[] | 否 | 位置参数 |
| `options` | object | 否 | 命名参数 |
| `timeout` | int | 否 | 超时秒数（1-300），默认 30 |

**Response** `200` — 命令成功
```json
{"retcode": 0, "result": {...}, "error": null}
```

**Response** `200` — 命令失败（retcode ≠ 0）
```json
{"retcode": -2, "result": null, "error": "Command Not Found"}
```

**Response** `404` — 机器人不存在

---

### 导入账号

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

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `accounts[].data` | string | 是 | 6 段 CSV（phone,pk1,sk1,pk2,sk2,6th） |
| `accounts[].env` | string | 否 | 设备环境，默认 `android` |

**Response** `200` — `BatchResult`

---

### 导出账号

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

> `data` 为 `null` 表示该账号导出失败；`env` 为账号当前设备环境。

---

### 日志

#### 拉取最近日志

```
GET /api/bot/{bot_id}/logs/recent?lines=50
```

| Query | 默认 | 说明 |
|-------|------|------|
| `lines` | 50 | 返回行数（1-1000） |

**Response** `200`
```json
{"bot_id": "8613800138000", "lines": ["[2026-06-10 12:00:00] INFO Login..."]}
```

#### 清除日志

```
DELETE /api/bot/{bot_id}/logs
```

**Response** `200`
```json
{"bot_id": "8613800138000", "cleared": true}
```

---

## WebSocket API

### 实时日志流

```
ws://host:port/api/bot/{bot_id}/logs?tail=10&access_key=<key>
```

| Query | 默认 | 说明 |
|-------|------|------|
| `tail` | 0 | 连接时先推送历史 N 行 |
| `access_key` | — | 认证密钥 |

连接成功后先发送 `tail` 行历史，之后实时推送新日志。  
认证失败返回 close code `4003`。

### 实时事件流

```
ws://host:port/api/bot/{bot_id}/events?tail=5&access_key=<key>
```

| Query | 默认 | 说明 |
|-------|------|------|
| `tail` | 0 | 连接时先推送历史 N 条事件 |
| `access_key` | — | 认证密钥 |

推送 JSON 格式的结构化事件：

```json
{"type": "message", "bot_id": "8613800138000", "data": {...}}
```

---

## 错误响应

所有 REST 接口在出错时返回：

```json
{"detail": "错误描述"}
```

| HTTP Status | 含义 |
|-------------|------|
| 403 | 认证失败 |
| 404 | 资源不存在 |
| 422 | 请求参数校验失败 |
| 500 | 服务端内部错误 |
| 504 | 命令执行超时 |
