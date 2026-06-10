# Agent 多进程架构改造方案

> **创建时间**: 2026-06-10  
> **状态**: 草案，待确认  
> **目标**: 将单进程 agent 升级为多进程架构，突破 GIL 限制，充分利用多核

---

## 1. 现状分析

### 当前架构

```
agent 进程 (FastAPI asyncio loop)
├── BotManager
│   ├── ZowBot "A" → Thread-1 → asyncio loop → WhatsApp
│   ├── ZowBot "B" → Thread-2 → asyncio loop → WhatsApp
│   └── ZowBot "C" → Thread-3 → asyncio loop → WhatsApp
└── LogBroadcaster (单进程内 Handler + 环形缓冲)
```

### 问题

| 场景 | 当前影响 |
|------|---------|
| GIL 锁 | I/O 密集型影响小，但 protobuf 序列化/crypto 计算等 CPU 操作会互相阻塞 |
| 多核利用 | 所有线程共享 1 个核心 |
| 故障隔离 | 一个 bot 的 C 扩展 crash → 整个 agent 崩 |
| 扩展性 | 单进程内存上限 ~2GB (Python 对象) |

### 实际影响评估

对于 WhatsApp bot 这个场景：
- 主要操作：网络 I/O（长连接读写）、JSON/Protobuf 序列化、少量加密计算
- **单个 bot ≈ 2MB 内存**，100 个 bot ≈ 200MB，内存不是瓶颈
- CPU 瓶颈：大量 bot 同时收发消息时，protobuf 解码/signal 加密会争抢 GIL
- **结论**：单进程在 50-100 bot 内问题不大，超过 100 或对延迟敏感时，多进程有显著收益

---

## 2. 目标架构

```
                          ┌─────────────────────────────┐
                          │       Main Agent Process     │
                          │  (FastAPI + 调度 + 聚合)     │
                          │  Port: 8000                  │
                          └──────┬──────────┬───────────┘
                                 │          │
                    ┌────────────┘          └────────────┐
                    ▼                                    ▼
          ┌──────────────────┐              ┌──────────────────┐
          │  Worker-1 (pid)  │              │  Worker-2 (pid)  │
          │  Port: 19001     │              │  Port: 19002     │
          │  ┌─────────────┐ │              │  ┌─────────────┐ │
          │  │ BotManager  │ │              │  │ BotManager  │ │
          │  │ ├ Bot "A"   │ │              │  │ ├ Bot "C"   │ │
          │  │ └ Bot "B"   │ │              │  │ └ Bot "D"   │ │
          │  └─────────────┘ │              │  └─────────────┘ │
          │  LogBroadcaster  │              │  LogBroadcaster  │
          └──────────────────┘              └──────────────────┘
```

### 关键原则

1. **Main 进程不变**：对外 API 完全不变，客户端无感知
2. **Worker 是透明代理**：Main 把 bot 操作转发给 Worker，Worker 执行后返回结果
3. **日志聚合**：Worker 把日志推送到 Main，Main 负责 WebSocket 广播
4. **动态扩缩**：Worker 数量可配置，bot 自动分配到负载最低的 Worker

---

## 3. 进程间通信设计

### 方案选择：HTTP (内部 localhost)

```
Main ──HTTP──→ Worker (start/stop/cmd)
Main ←──HTTP── Worker (result)
Main ←──WS──── Worker (log push)
```

| 维度 | HTTP 内部 | Unix Socket | Redis/Queue |
|------|----------|-------------|-------------|
| 复杂度 | ✅ 最低，复用 FastAPI | 中等 | ❌ 需要额外服务 |
| 调试 | ✅ curl 直接调 Worker | 需要专用工具 | — |
| 性能 | 足够（localhost 延迟 <1ms） | 略优 | — |
| 代码复用 | ✅ Worker 直接继承现有 agent 代码 | 需改传输层 | 需全新设计 |

**结论**：用 HTTP，每个 Worker 就是一个轻量 FastAPI 服务，Main 作为反向代理。

---

## 4. 模块设计

### 文件结构（新增）

```
agent/
├── worker/
│   ├── __init__.py
│   ├── worker_server.py         # Worker FastAPI 服务（轻量版 agent）
│   └── worker_manager.py        # Main 进程的 Worker 进程管理器
├── manager/
│   ├── bot_manager.py           # 🔧 重构：增加请求转发逻辑
│   └── scheduler.py             # 🆕 bot 分配调度器
├── schemas.py                   # 🔧 增加 WorkerInfo 等模型
└── server.py                    # 🔧 lifespan 启动 Worker 池
```

### 核心类

```python
# ---- scheduler.py ----
class BotScheduler:
    """决定 bot 分配到哪个 Worker"""
    
    def assign(bot_id) -> WorkerInfo
        # 策略：轮询 / 最少 bot 数 / 哈希固定
    
    def reassign(bot_id) -> WorkerInfo
        # Worker 挂掉时迁移 bot


# ---- worker_manager.py ----
class WorkerManager:
    """管理 Worker 进程池"""
    
    def __init__(worker_count=4):
        self.workers: list[WorkerProcess] = []
    
    def start():
        """启动所有 Worker 子进程"""
        for i in range(count):
            proc = subprocess.Popen([
                sys.executable, "-m", "agent.worker",
                "--port", str(base_port + i),
                "--main-url", f"http://127.0.0.1:{MAIN_PORT}",
            ])
    
    def get_healthy_workers() -> list[WorkerInfo]:
        """返回存活的 Worker 列表"""
    
    def restart_worker(worker_id):
        """重启挂掉的 Worker"""


# ---- worker_server.py ----
class WorkerServer:
    """Worker 进程：轻量版 agent，只管理 bot 线程"""
    
    # 继承现有 BotManager + LogBroadcaster 逻辑
    # 额外提供：
    #   POST /internal/bots/start
    #   POST /internal/bots/{id}/stop  
    #   POST /internal/bots/{id}/cmd
    #   GET  /internal/health
    #   WS   /internal/logs/push  (推送日志到 Main)
```

---

## 5. Bot 生命周期（改造后）

```
客户端 POST /api/startbots → Main Agent
  ↓
  Main: scheduler.assign(bot_id) → Worker-2
  ↓
  Main: HTTP POST Worker-2:19002/internal/bots/start
  ↓
  Worker-2: ZowBot(bot_id).runAsThread()
  ↓
  Worker-2: wait_logged_in() → success
  ↓
  Worker-2: HTTP 201 → Main
  ↓
  Main: 返回给客户端
```

```
客户端 POST /api/bots/{id}/cmd → Main Agent
  ↓
  Main: 查表得知 bot_id 在 Worker-2
  ↓
  Main: HTTP POST Worker-2:19002/internal/bots/{id}/cmd
  ↓
  Worker-2: bot.callDirectCompat(cmd, args) → result
  ↓
  Main: 返回给客户端
```

```
Bot 线程日志 → Worker LogBroadcaster
  ↓
  Worker: WS push → Main /internal/logs/receive
  ↓
  Main LogBroadcaster: 合并 + WS 广播给客户端
```

---

## 6. Bot 分配策略

### 策略一：轮询 (Round Robin) — 默认

```python
class RoundRobinScheduler:
    _next = 0
    
    def assign(self, bot_id):
        worker = self.workers[self._next % len(self.workers)]
        self._next += 1
        return worker
```

### 策略二：最少负载 (Least Loaded)

```python
class LeastLoadedScheduler:
    def assign(self, bot_id):
        return min(self.workers, key=lambda w: w.bot_count)
```

### 策略三：哈希固定 (Consistent Hash) — 适合 stop/start 频繁场景

```python
class HashScheduler:
    def assign(self, bot_id):
        idx = hash(bot_id) % len(self.workers)
        return self.workers[idx]
```

**建议**：默认轮询，配置项可切换。

---

## 7. 故障处理

| 场景 | 处理方式 |
|------|---------|
| Worker 进程 crash | Main 检测到 `/internal/health` 失败 → 重启 Worker → bot 在该 Worker 上丢失（需客户端重新 start） |
| Worker 进程假死 | Health check 超时 → 标记 unhealthy → kill + restart |
| Main 进程 crash | 所有 Worker 失去日志推送目标 → 自动退出（孤儿进程检测） |
| 启动时 Worker 不足 | 至少 1 个 Worker 健康才接受请求，否则返回 503 |

### Bot 迁移（可选，复杂度高）

Worker crash 后可自动迁移 bot 到其他 Worker，但这需要：
1. 每个 Worker 有统一的 bot 状态快照
2. Main 记录每个 bot 的分配关系
3. crash 后自动在其他 Worker 重新 login

**初版建议不做迁移**，Worker crash 后 bot 状态丢失，由客户端感知并重新 start。

---

## 8. 日志聚合

```
Worker BotLogHandler → 环形缓冲
    ↓ (WS 推送)
Main /internal/logs/receive
    ↓
Main LogBroadcaster → 环形缓冲
    ↓ (WS 广播)
客户端 WebSocket 连接
```

Main 进程的 `LogBroadcaster` 成为唯一对外出口，Worker 不直接暴露日志 WS。

---

## 9. 配置设计

```ini
# conf/config.conf
[Agent]
WORKER_COUNT = 4               # Worker 进程数（0 = 单进程模式）
WORKER_BASE_PORT = 19000       # Worker 起始端口
SCHEDULER = round_robin        # 调度策略

# 单进程模式（兼容）
[Agent]
WORKER_COUNT = 0               # 0 表示直接在 Main 进程中跑 bot 线程
```

当 `WORKER_COUNT = 0` 时，完全回退到当前的线程模式，保证向后兼容。

---

## 10. 分阶段实施

### Phase A: Worker 进程 + 内部通信（2 天）

| 任务 | 说明 |
|------|------|
| A1 | `agent/worker/worker_server.py` — Worker FastAPI 服务 |
| A2 | `agent/worker/worker_manager.py` — 子进程管理 |
| A3 | `agent/manager/scheduler.py` — bot 分配 |
| A4 | Main → Worker HTTP 转发（start/stop/cmd） |

### Phase B: 日志聚合（1 天）

| 任务 | 说明 |
|------|------|
| B1 | Worker 日志 → Main WebSocket 推送 |
| B2 | Main LogBroadcaster 合并多个 Worker 的日志 |
| B3 | 客户端无感知（同一 WS 端点） |

### Phase C: 故障处理 + 测试（1 天）

| 任务 | 说明 |
|------|------|
| C1 | Health check + 自动重启 crash Worker |
| C2 | Worker 不足 → 503 降级 |
| C3 | 多进程集成测试 |
| C4 | 单进程模式兼容测试（WORKER_COUNT=0） |

---

## 11. 风险与权衡

| 方面 | 收益 | 代价 |
|------|------|------|
| 并发能力 | 4 Worker ≈ 4 核利用，bot 容量 ×4 | 增加进程管理复杂度 |
| 故障隔离 | Worker crash 不影响其他 Worker | bot 迁移未实现，需客户端重试 |
| 内存 | 每个 Worker ~30MB（Python 运行时） | 4 Worker ≈ 120MB 基础开销 |
| 延迟 | 内部 HTTP 转发 <1ms | 比直接线程调用多 1 次网络往返 |
| 调试 | 每个 Worker 可独立调试 | 日志需要聚合查看 |

---

## 12. 待确认

- [ ] Worker 数量默认几个？（建议 CPU 核心数）
- [ ] 是否需要 bot 自动迁移？（建议初版不要，等稳定后再加）
- [ ] 单进程模式是否保留？（建议保留，WORKER_COUNT=0 回退）
- [ ] 是否所有 bot 操作都转发，还是只在 Worker 达到阈值时启用多进程？
