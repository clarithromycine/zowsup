# Agent 集群 — 架构设计

> 日期: 2026-06-15  
> 状态: 方案设计，待实施

---

## 0. 背景

当前单 agent 管理所有 bot，无法横向扩展。集群化后：

- 多个 agent 分布在不同机器/进程
- 每个 agent 管理一部分 bot
- 客户端通过统一入口（Router）访问，不感知底层分布

zowsup-cli 已有 Agent Gateway 参考实现：WebSocket 注册、HMAC 鉴权、命令路由、状态聚合。

---

## 1. 整体架构

```
                         ┌──────────────┐
                         │   Client     │
                         │ (API/UI/WS)  │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │    Router    │  ← 透明代理，暴露与 agent 相同 API
                         │  (独立进程)   │
                         └──┬───┬───┬───┘
                            │   │   │
                   ┌────────┘   │   └────────┐
                   ▼            ▼            ▼
              ┌────────┐  ┌────────┐  ┌────────┐
              │Agent A │  │Agent B │  │Agent C │
              │ bot1   │  │ bot3   │  │ bot5   │
              │ bot2   │  │ bot4   │  │ bot6   │
              └────────┘  └────────┘  └────────┘
```

**Router 是透明代理**——它暴露和 agent 完全相同的 REST/WS API，客户端不需要知道底层有几个 agent。

---

## 2. 路由表

```
agent_registry (SQLite, 路由器本地):

  bot_id         agent_id       agent_url
  ──────────     ──────────     ─────────────────────
  233541115312   macbook-pro    http://192.168.1.10:8000
  263783604300   macbook-pro    http://192.168.1.10:8000
  8619874406144  linux-node-1   http://192.168.1.20:8000
```

### 路由规则

| 请求类型 | 路由方式 |
|----------|----------|
| `/api/listbot` | 查询所有 agent，聚合结果 |
| `/api/bot/{id}` | 查路由表 → 代理到对应 agent |
| `/api/startbot` | 选择负载最低的 agent → 注册 → 代理 |
| `/api/stopbot` | 查路由表 → 代理 |
| `/api/sendmsg` | `bot_id` → 代理 |
| `/api/conversation/*` | `bot_id` → 代理 |
| `/api/health` | 聚合所有 agent + router 自身 |
| `/api/plugin/*` | 代理到 router 自身（全局配置） |
| WebSocket | `bot_id` → 代理 WebSocket |

---

## 3. Router API

Router 暴露和 agent **完全相同** 的 API，外加集群管理端点：

### 集群管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/cluster/agents` | 列出所有 agent 及状态 |
| `POST` | `/api/cluster/agents` | 注册新 agent |
| `DELETE` | `/api/cluster/agents/{id}` | 注销 agent |
| `POST` | `/api/cluster/migrate` | 迁移 bot 到另一个 agent |

### 迁移

```bash
# 把 bot123 从 agent-A 迁移到 agent-B
curl -X POST /api/cluster/migrate \
  -d '{"bot_id":"bot123","target_agent":"linux-node-1"}'
```

流程：`stop_bot → export → import → start_bot`，原子操作，失败自动回滚。

---

## 4. Agent 注册

### 手动注册

```bash
curl -X POST http://router:8000/api/cluster/agents \
  -d '{"agent_id":"linux-node-1","url":"http://192.168.1.20:8000","access_key":"xxx"}'
```

### 自动注册（推荐）

Agent 启动时通过环境变量或 CLI 参数指定 Router 地址，自动注册：

```bash
AGENT_ID=linux-node-1 ROUTER_URL=http://router:8000 python -m agent
```

Agent 启动后：
1. 向 Router 注册自身（`POST /api/cluster/agents`）
2. 上报已有 bot 列表
3. 定期心跳（每 30s）
4. 优雅退出时注销

### 健康检查

Router 定期（15s）对所有 agent 执行 `GET /api/health`。连续 3 次失败 → 标记 `offline` → 其 bot 标记为 `unreachable`。

---

## 5. 请求路由实现

Router 内部分两层：

```
FastAPI app (agent API 兼容)
     │
     ▼
RoutingMiddleware
     │
     ├─ bot 相关请求 → 查路由表 → httpx 代理到目标 agent
     ├─ 全局请求    → 本地处理
     └─ 聚合请求    → scatter-gather 到所有 agent
```

### 示例：代理 sendmsg

```python
async def proxy_to_agent(agent_url: str, request: Request):
    """Forward request to target agent, return its response."""
    async with httpx.AsyncClient() as client:
        body = await request.body()
        resp = await client.request(
            method=request.method,
            url=f"{agent_url}{request.url.path}",
            headers={k: v for k, v in request.headers.items() if k != "host"},
            content=body,
            timeout=30,
        )
        return Response(content=resp.content, status_code=resp.status_code)
```

---

## 6. 目录结构

```
agent/
  cluster/
    __init__.py         # 导出
    router.py           # Router 主进程 (FastAPI app)
    registry.py         # 路由表 SQLite store
    proxy.py            # HTTP/WS 代理中间件
    health.py           # Agent 健康检查
  api/
    cluster_api.py      # 集群管理端点
```

Router 是**独立进程**，不依赖 agent 内部逻辑：

```bash
python -m agent.cluster.router --port 8000
```

---

## 7. 部署拓扑

```
┌─────────────────────────────────────────────────┐
│              Router (独立服务器)                  │
│  host: router.zowsup.local  port: 8000           │
│  DB: /data/router_registry.db                   │
└─────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│  Agent A        │  │  Agent B        │
│  host: 10.0.1.1 │  │  host: 10.0.1.2 │
│  bots: 100 个    │  │  bots: 100 个    │
└─────────────────┘  └─────────────────┘
```

### 启动命令

```bash
# Router
python -m agent.cluster.router --host 0.0.0.0 --port 8000

# Agent A
AGENT_ID=agent-a ROUTER_URL=http://router:8000 python -m agent --host 0.0.0.0 --port 8001

# Agent B
AGENT_ID=agent-b ROUTER_URL=http://router:8000 python -m agent --host 0.0.0.0 --port 8002
```

---

## 8. 与现有代码的关系

| 现有代码 | 集群化后 |
|----------|----------|
| `agent/server.py` | 不变，agent 仍独立运行 |
| `agent/__main__.py` | 加 `--router` 参数 |
| `agent/manager/account_store.py` | 不变 |
| 客户端 | 连 Router 而非直连 Agent |

**Router 是新增模块，对现有 agent 代码零侵入。**

---

## 9. 实施计划

| Phase | 内容 | 预计 |
|-------|------|------|
| 0 | `router.py` + `registry.py` + 透明代理中间件 | 2h |
| 1 | Agent 自动注册 + 心跳 | 1h |
| 2 | 聚合端点 (listbot, health) | 1h |
| 3 | Bot 迁移 | 1h |
| 4 | WebSocket 代理 | 1h |
| 5 | 健康检查 + offline 检测 | 1h |
| **Total** | | **~7h** |

---

## 10. 不做的

- ❌ 自动故障转移（Phase 0 不做，手动迁移）
- ❌ 分布式会话存储（每个 agent 有自己的 `agent_conversations.db`，后续统一）
- ❌ Redis 缓存（先用 SQLite）
- ❌ 负载均衡算法（先随机分配）
