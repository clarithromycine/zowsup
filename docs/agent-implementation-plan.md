# Agent 模块实施计划

> **创建时间**: 2026-06-10  
> **最后更新**: 2026-06-10  
> **状态**: ✅ 全部完成  
> **目标**: 将 zowsup 从纯命令行工具升级为可对外暴露 API 的多 bot 管理 agent 服务

---

## 0. 架构概览

```
agent 进程 (FastAPI asyncio event loop)
├── BotManager                 # 线程管理多 bot 生命周期
│   ├── ZowBot "263783604300"  → Thread-1 → asyncio loop → WhatsApp 长连接
│   ├── ZowBot "8613900000000" → Thread-2 → asyncio loop → WhatsApp 长连接
│   └── ZowBot "8614000000000" → Thread-3 → asyncio loop → WhatsApp 长连接
├── LogBroadcaster             # BotLogHandler → 环形缓冲 → WebSocket 广播
├── API Router (REST)          # /api/bots, /api/scripts, /api/cmd, /api/logs
├── API Router (WebSocket)     # /api/bots/{id}/logs
└── Access Key Middleware      # REST: Header, WS: Query param
```

**关键决策**:
- Bot 运行模型: 线程 (`ZowBot.runAsThread`)，每 bot 增量 ≈2MB
- 对外协议: FastAPI (HTTP REST + WebSocket)
- Bot 命令通信: `callDirectCompat()` → `run_coroutine_threadsafe()`（跨线程安全）
- 认证: REST 用 `X-Access-Key` Header，WebSocket 用 `?access_key=` Query

---

## 1. 实际文件结构

```
zowsup/
├── agent/                              # 🆕 新模块 (Phase 1-5 已实现)
│   ├── __init__.py
│   ├── __main__.py                     # 入口: python -m agent [--accesskey KEY] [--host H] [--port P]
│   ├── server.py                       # FastAPI app + ACCESSKEY 认证 + lifespan
│   ├── schemas.py                      # 15 个 Pydantic 模型
│   ├── api/
│   │   ├── __init__.py
│   │   ├── bot_api.py                  # Bot CRUD (5 endpoints)
│   │   ├── cmd_api.py                  # POST /api/bots/{id}/cmd
│   │   ├── script_api.py               # GET + POST /api/scripts
│   │   └── log_api.py                  # REST /logs/recent + WebSocket /logs
│   └── manager/
│       ├── __init__.py
│       ├── bot_manager.py              # start/stop/list/get + execute_cmd
│       └── log_broadcaster.py          # BotLogHandler + ring buffer + WS fan-out
├── tests/                              # 🆕 测试套件 (Phase 1-5)
│   ├── __init__.py
│   ├── conftest.py                     # Agent 启动/关闭 fixtures
│   ├── test_phase1_auth.py             # 5 tests
│   ├── test_phase2_bots.py             # 8 tests
│   ├── test_phase3_cmd.py              # 4 tests
│   ├── test_phase4_scripts.py          # 4 tests
│   ├── test_phase5_logs.py             # 4 tests
│   ├── test_phase6_import_export.py    # 3 tests
│   └── test_phase7_e2e.py              # 3 tests
├── app/
│   ├── zowbot.py                       # 🔧 + wait_logged_in() / logger 初始化顺序修复
│   ├── zowbot_values.py                # (未改动)
│   └── layer/
│       └── connection.py               # 🔧 修复 ZowBotType 导入
├── requirements.txt                    # 🔧 + fastapi, uvicorn, websockets
└── conf/
    └── config.conf.example             # (未改动)
```

---

## 2. 分阶段任务状态

### ✅ Phase 1: 基础设施搭建 — 完成

| ID | 任务 | 产出文件 | 状态 |
|----|------|---------|------|
| 1.1 | 添加依赖 | `requirements.txt` | ✅ |
| 1.2 | Pydantic 数据模型 | `agent/schemas.py` | ✅ |
| 1.3 | FastAPI 骨架 + ACCESSKEY | `agent/server.py` | ✅ |
| 1.4 | 入口 `__main__.py` | `agent/__main__.py` | ✅ |

### ✅ Phase 2: Bot 管理器 — 完成

| ID | 任务 | 产出文件 | 状态 |
|----|------|---------|------|
| 2.1 | BotManager: start/stop/list/get | `agent/manager/bot_manager.py` | ✅ |
| 2.2 | ZowBot: `wait_logged_in()` | `app/zowbot.py` | ✅ |
| 2.3 | Bot API endpoints | `agent/api/bot_api.py` | ✅ |

### ✅ Phase 3: 命令执行 API — 完成

| ID | 任务 | 产出文件 | 状态 |
|----|------|---------|------|
| 3.1 | `POST /api/bot/cmd` (bot_id 在 body) | `agent/api/cmd_api.py` | ✅ |
| 3.2 | BotManager.execute_cmd() | `agent/manager/bot_manager.py` | ✅ |

### ❌ Phase 4: 脚本执行 API — 已废弃

> **已删除** — import/export 功能已合并到 bot_api 的 `/api/importbot` 和 `/api/exportbot`。
> `agent/api/script_api.py` 保留空 router，测试文件 `test_phase4_scripts.py` 已删除。

| ID | 任务 | 原产出文件 | 状态 |
|----|------|---------|------|
| 4.1 | `GET /api/scripts` | `agent/api/script_api.py` | ❌ 已删除 |
| 4.2 | `POST /api/scripts/{name}` | 同上 | ❌ 已删除 |

### ✅ Phase 5: 日志系统 — 完成

| ID | 任务 | 产出文件 | 状态 |
|----|------|---------|------|
| 5.1 | LogBroadcaster + BotLogHandler | `agent/manager/log_broadcaster.py` | ✅ |
| 5.2 | WebSocket 实时日志 | `agent/api/log_api.py` | ✅ |
| 5.3 | REST 最近日志 | 同上 | ✅ |
| 5.4 | WebSocket 认证 | 同上 | ✅ |

### ✅ Phase 6: 导入导出 — 完成

| ID | 任务 | 产出文件 | 状态 |
|----|------|---------|------|
| 6.1 | `POST /api/importbot` 多账号导入 (env 参数) | `agent/api/bot_api.py` | ✅ 子进程调用 import6.py |
| 6.2 | `POST /api/exportbot` 多账号导出 (含 env) | 同上 | ✅ 子进程调用 export6.py |

> 数据格式：import6.py / export6.py 的 6 段 CSV（phone,pk1,sk1,pk2,sk2,sixth）
> 导出返回 `{"data": csv, "env": "android"}` 结构，re-import 时使用导出中的 env 避免覆盖配置

### ✅ Phase 7: 事件回调 + E2E — 完成

| ID | 任务 | 产出文件 | 状态 |
|----|------|---------|------|
| 7.1 | `WS /api/bot/{id}/events` 结构化事件 | `agent/api/log_api.py` | ✅ |
| 7.2 | E2E 完整生命周期测试 | `tests/test_phase7_e2e.py` | ✅ 2 tests |

### 🆕 Phase 8: 高层消息发送 + 账号管理 — 超出计划

| ID | 任务 | 产出文件 | 状态 |
|----|------|---------|------|
| 8.1 | `POST /api/sendmsg` 高层封装 (text/ad → msg.send/sendad) | `agent/api/msg_api.py` | ✅ |
| 8.2 | AccountStore (SQLite 账号元数据 + 自动迁移) | `agent/manager/account_store.py` | ✅ |
| 8.3 | `DELETE /api/bot/{id}/logs` 日志清理 | `agent/api/log_api.py` | ✅ |

---

## 3. API 完整清单

| 方法 | 路径 | 状态 | 说明 |
|------|------|------|------|
| `GET` | `/api/health` | ✅ | 健康检查 |
| `GET` | `/api/listbot` | ✅ | 列出所有账号 |
| `GET` | `/api/bot/{id}` | ✅ | 单个账号详情 |
| `POST` | `/api/startbot` | ✅ | 启动 bot（支持批量 + env/proxy 配置） |
| `POST` | `/api/stopbot` | ✅ | 停止 bot（批量） |
| `POST` | `/api/bot/cmd` | ✅ | 执行命令（bot_id 在 body） |
| `POST` | `/api/sendmsg` | 🆕 | 高层消息发送（text/ad 自动路由） |
| `POST` | `/api/importbot` | ✅ | 导入账号（多账号 + env 参数） |
| `POST` | `/api/exportbot` | ✅ | 导出账号（多 bot + 含 env 信息） |
| `GET` | `/api/bot/{id}/logs/recent` | ✅ | 拉取最近 N 行日志 |
| `DELETE` | `/api/bot/{id}/logs` | 🆕 | 清除日志 |
| `WS` | `/api/bot/{id}/logs` | ✅ | 实时日志推送 |
| `WS` | `/api/bot/{id}/events` | ✅ | 结构化事件推送 |

> 旧路径（`/api/bots`, `/api/startbots`, `/api/scripts` 等）已全部废弃。详细文档见 [`agent-api.md`](agent-api.md)。

---

## 4. 测试状态

| Phase | 测试文件 | Tests | 状态 |
|-------|---------|-------|------|
| Phase 1: Auth | `test_phase1_auth.py` | 5 | ✅ |
| Phase 2: Bots | `test_phase2_bots.py` | 8 | ✅ |
| Phase 3: Cmd + SendMsg | `test_phase3_cmd.py` | 5 | ✅ |
| ~~Phase 4: Scripts~~ | — | — | ❌ 已删除 |
| Phase 5: Logs | `test_phase5_logs.py` | 4 | ✅ |
| Phase 6: Import/Export | `test_phase6_import_export.py` | 3 | ✅ |
| Phase 7: E2E + Events | `test_phase7_e2e.py` | 2 | ✅ |
| **Total** | | **27** | **✅ 27 passed** |

运行方式:
```bash
python -m pytest tests/ -v              # 全部
python -m pytest tests/test_phase2_bots.py -v  # 单个
```

测试使用真实账号 `AGENT_TEST_BOT_ID`（默认 `263783604300`），通过环境变量可覆盖。

---

## 5. 发现并修复的预存 Bug

| 文件 | 行 | 问题 | 修复 |
|------|-----|------|------|
| `app/zowbot.py` | 47 | `from app.zowbot_layer import ...` → `ModuleNotFoundError` | 改为 `app.layer.zowbot_layer` |
| `app/zowbot.py` | 73/92 | `self.logger` 在 `ZowBotLayer` 构造后才赋值，后者访问 `bot.logger` 时尚未初始化 | 移到构造前赋值 |
| `app/layer/connection.py` | 12 | 缺少 `ZowBotType` 导入，运行时 `NameError` | 添加导入 |
| `app/layer/connection.py` | 142 | 登录失败时 `bot.botId = None`，导致 `BotInfo` 序列化失败 | `_build_bot_info` 改为用 dict key 追踪 ID |

---

## 6. 待确认事项

- [x] 导入/导出功能的接口数据格式：**复用 `import6.py` / `export6.py` 的 6 段 CSV 格式**（非目录打包）
- [x] agent 端口和 host：**CLI 参数 `--host` / `--port` 指定，默认 `0.0.0.0:8000`**
- [x] Swagger UI：**保留**（FastAPI 自带 `/docs`）
- [x] 日志环形缓冲区：**每 bot 保留最近 1000 行**（已调整）
