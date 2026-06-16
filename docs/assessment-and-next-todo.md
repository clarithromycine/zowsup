# Zowsup 项目架构评估与后续行动计划 (Assessment & Next Todo)

> **评估日期**: 2026-06-16  
> **当前版本**: 0.9.5 (本地开发版) / 0.9.0 (GitHub 公开版)  
> **评估范围**: 整体技术架构、BOT 基本功能、隐患梳理  
> **外部反馈来源**: GitHub Issues (clarithromycine/zowsup, 61★ / 19 forks) + Commit History

---

## 一、项目概览

**zowsup** 是一个基于 Python 的 WhatsApp 协议实现项目，fork 自已停止维护的 [yowsup](https://github.com/tgalal/yowsup/)，并将 axolotl（端到端加密）、consonance（Noise 协议握手）等关联项目整合为 All-In-One 工程，持续跟进 WhatsApp 最新协议版本。

| 指标 | 数值 |
|------|------|
| 当前版本 | 0.9.5 |
| 支持 WhatsApp 版本 | Android 2.26.21.75 / SMB Android 2.26.21.75 / iOS 2.26.13.74 / SMB iOS 2.26.13.74 |
| 支持设备环境 | android, smb_android, ios, smb_ios |
| 核心技术栈 | Python 3 (asyncio) + FastAPI + SQLite + Protobuf + WebSocket |
| 代码规模 | ~200+ Python 源文件 |

---

## 二、整体技术架构评估

### 2.1 分层架构设计 ★★★★☆

项目采用经典的分层 (Layer Stack) 架构，从底层网络到上层业务逻辑依次为：

```mermaid
graph TD
    subgraph "Agent / Cluster 层"
        WC[Web Console<br/>SPA]
        CL[Cluster Router<br/>路由代理]
        AG[Agent<br/>FastAPI + WebSocket]
    end
    
    subgraph "Bot 应用层 (app/layer/)"
        ZBL[ZowBotLayer<br/>协议层门面]
        CM[ConnectionManager<br/>连接生命周期]
        IM[IqManager<br/>IQ 请求/响应]
        MH[MessageHandler<br/>消息解析回调]
        NH[NotificationHandler<br/>推送通知]
        MM[MediaManager<br/>媒体下载解密]
        CTM[ContactManager<br/>联系人操作]
        SM[SyncManager<br/>状态同步/FCM]
        PM[PairingManager<br/>设备配对]
    end
    
    subgraph "Core 协议层 (core/layers/)"
        AX[Axolotl 加密层<br/>E2E 收发]
        PL[协议并行层<br/>18+ 协议子层]
    end
    
    subgraph "Core 基础层"
        NW[Network Layer<br/>TCP/SSL/SOCKS5]
        CD[Coder Layer<br/>二进制编解码]
        NS[Noise Layer<br/>WA Noise 握手]
        AU[Auth Layer<br/>登录认证]
    end
    
    WC --> CL --> AG
    AG --> ZBL
    ZBL --> CM & IM & MH & NH & MM & CTM & SM & PM
    CM --> PL
    PL --> AX
    AX --> NS --> CD --> NW
```

**优点：**
- 关注点分离清晰：`core/layers/` 负责协议栈（18+ 子协议层），`app/layer/` 负责业务逻辑（8 个 Manager），`agent/` 负责多 Bot 管理
- 通过 `YowStackBuilder` 的 Builder 模式灵活组装协议层，支持按需启用/禁用 groups、media、privacy、profiles 等模块
- `AxolotlSendLayer` / `AxolotlReceivelayer` 以 `YowParallelLayer` 方式并行运行，提升消息吞吐
- `DeviceEnv.__getattr__` 自动委托消除了 25+ 个手动透传方法，代码简洁

**不足：**
- `ZowBot` 类仍然承担过多职责：命令注册、事件循环管理、回调分发、连接控制、命令队列等，约 450+ 行
- `ZowBotLayer` 中的 `onCallback` 直接操作上层回调与 `run_in_executor`，线程模型不够清晰

### 2.2 异步架构 ★★★★☆

v0.9.0 完成了从「多线程 + 同步」到「asyncio + 协程」的全面改造：

- 所有命令 `execute()` 均为 `async def`，使用 `asyncio.Future` 替代 `threading.Event`
- `AsyncCommandExec` 以非阻塞方式等待登录后执行命令
- IQ 请求通过 `asyncio.wait_for(future, timeout=30)` 实现异步超时控制
- `_command_runner_loop` 和 `_agent_command_queue_loop` 作为后台 asyncio Task 运行

**优点：**
- 避免了传统多线程的 GIL 瓶颈与竞态条件
- 命令执行链路清晰：推送 → 队列 → 执行 → Future 返回
- 超时与取消机制完备（`asyncio.CancelledError` / `asyncio.TimeoutError`）

**不足：**
- Bot 实例运行在独立线程中（`runAsThread`），每个 Bot 各自拥有独立的 asyncio event loop（通过 `asyncio.run()`），线程间通信依赖 `run_in_executor` 投递到 Agent 的 event loop
- 这种「每 Bot 一个 event loop + 独立线程」模型在高 Bot 数（>50）时，线程资源开销较大
- Agent 自身的 asyncio loop 与 Bot 线程的 loop 之间存在 `run_in_executor` 桥接，增加了一层调度开销

### 2.3 水平扩展性 (Cluster) ★★★★☆

v0.9.5 引入的 Cluster 架构是项目最大的架构亮点：

```mermaid
graph TD
    B[Browser / Client] -->|HTTP/WS| CR[Cluster Router<br/>:8000]
    CR -->|bot_id 路由| A1[Agent A :8001]
    CR -->|bot_id 路由| A2[Agent B :8002]
    CR -->|bot_id 路由| A3[Agent C :8003]
    CR -->|聚合查询| A1 & A2 & A3
    
    R[(Registry DB<br/>SQLite)]
    CR --> R
    A1 -.->|注册/心跳| CR
    A2 -.->|注册/心跳| CR
    A3 -.->|注册/心跳| CR
```

**优点：**
- **透明代理**：Cluster 对外暴露与单 Agent 完全相同的 API，客户端无需感知集群拓扑
- **智能路由**：从 URL 路径 (`/api/bot/{bot_id}`)、Query 参数、JSON Body 中自动提取 `bot_id` 并路由到正确的 Agent
- **Scatter-Gather**：支持对所有在线 Agent 并行聚合查询（如 `listbot`、`escalation` 列表）
- **SQLite Registry**：线程安全的 WAL 模式 SQLite，记录 agent ↔ bot 映射关系
- **健康检查**：每 30s 主动 ping 所有 Agent，连续 3 次失败 → 标记 offline；心跳 TTL 120s 兜底（防止 kill -9 场景）
- **CLUSTER_SECRET**：集群内 Agent 注册/心跳需要共享密钥认证
- **Bot 迁移**：支持 stop → export(tar+base64) → import → start → route update → cleanup 全流程自动化，每步有 rollback

**不足：**
- Registry 是单点（SQLite 文件），虽然对于中小规模足够，但在极高并发场景下可能成为瓶颈
- 无内置的 Agent 负载均衡策略（仅 `pick_agent()` 随机选择），新增 Bot 时无智能调度
- 单 Agent 上限硬编码为 50 bots（`MAX_BOTS_PER_AGENT = 50`），虽然合理但缺乏动态调整

### 2.4 性能瓶颈分析

| 组件 | 当前状态 | 潜在瓶颈 |
|------|---------|---------|
| Bot 线程模型 | 每个 Bot 独立线程 + 独立 event loop | >50 Bots 时线程上下文切换开销显著 |
| Registry | SQLite + threading.Lock | 单点、锁竞争（虽然 WAL 模式缓解） |
| 消息回调 | `run_in_executor` 桥接 | 回调频繁时线程池可能成为瓶颈 |
| 媒体下载 | `requests.get()` 同步阻塞 | 大文件下载会阻塞 Bot 的 event loop |
| WebSocket | 单连接广播 | 大量 WebSocket 客户端时广播效率低下 |

---

## 三、BOT 基本功能评估

### 3.1 消息收发 ★★★★☆

**已实现：**
- 文本消息收发 (`msg.send`)：支持单发、广播模式、消息追踪 (waitid)
- 引用回复 (`msg.quotedreply`)
- 消息撤回 (`msg.revoke`)
- 消息编辑 (`msg.edit`)
- 互动消息 (`msg.sendinteractive`)：按钮、列表等交互式组件
- 广告消息 (`msg.sendad`)
- 富媒体消息 (`msg.sendmedia`)：图片、视频、音频、文档
- 短链接消息 (`msgshortlink.*`)
- 端到端加密：通过 Axolotl (Signal Protocol) 实现，收发自动加解密
- 消息已读/送达回执 (Receipt) 处理
- 消息 ACK 机制（概率性 ACK 模拟真实客户端行为）

**待完善：**
- 消息发送缺少重试机制（网络波动时直接失败）
- 无消息发送速率限制 (rate limiting)，批量发送时可能触发 WhatsApp 风控
- 广播模式仅支持 `bcid/phash` 方式，不支持逐步构建广播列表

### 3.2 群组管理 ★★★★☆

**已实现（13 个命令）：**
- 创建群组 (`group.create`)
- 添加/移除成员 (`group.add`, `group.remove`)
- 提升/降级管理员 (`group.promote`, `group.demote`)
- 获取邀请链接 (`group.getinvite`)
- 加入群组 (`group.join`)
- 退出群组 (`group.leave`)
- 审批加入请求 (`group.approve`)
- 群组信息查询 (`group.info`)
- 群组列表 (`group.list`)
- 设置群组属性 (`group.setprop`)：主题、描述等
- 设置群组图标 (`group.seticon`)

### 3.3 账号管理 ★★★★☆

- 账号初始化 (`account.init`)
- 获取/设置名称、头像、邮箱
- 两步验证设置 (`account.set2fa`)
- 邮箱验证流程
- 账号信息查询 (`account.info`)
- 设备配对 (Companion Device Registration)：支持扫码和 Link Code 两种方式

### 3.4 联系人管理 ★★★☆☆

- 联系人列表 (`contact.list`)
- 联系人同步 (`contact.sync`)
- 获取联系人资料 (`contact.getprofile`)
- 获取联系人设备列表 (`contact.getdevices`)
- 信任管理 (`contact.trust`)
- 消息阅后即焚设置 (`contact.setmsgdisappearing`)

### 3.5 通讯录 (Newsletter) ★★★☆☆

- 基本通讯录操作支持 (`newsletter.*` 命令族)

### 3.6 多设备管理 ★★★☆☆

- 设备列表查询 (`md.devices`)
- 设备关联码输入 (`md.inputcode`)
- 设备登出审批

### 3.7 Agent 管控能力 ★★★★★

- **Bot 生命周期管理**：批量启动/停止、状态监控、自动重连
- **命令远程执行**：通过 HTTP API 对运行中的 Bot 执行任意命令
- **WebSocket 实时推送**：日志流、消息事件、状态变更
- **E2E 会话持久化**：ConversationStore (SQLite) 完整记录会话与消息
- **消息状态追踪**：实时显示消息已发送/已送达/已读状态
- **媒体消息支持**：图片/视频/音频/文档的下载 + 解密 + 本地缓存
- **Escalation 队列**：AI 无法处理时升级到人工坐席 (claim/reply/resolve)
- **插件系统**：翻译插件 + AI 自动回复插件，关键词触发升级
- **Web Console**：单页管理界面，涵盖 Bot、会话、升级、插件、集群全维度

---

## 四、隐患梳理与风险评估

### 4.0 📌 已知设计边界（非缺陷）

#### 4.0.1 新号注册功能在公开版中主动阉割
**背景**: 注册相关代码（`script/requestcode.py` 等）在公开库中有意做了代码阉割，完整注册逻辑不开源。  
**技术根因（已明确）**: WhatsApp 注册服务器要求客户端提供大量只有真实设备/应用才能生成的环境证明信息，在纯协议层面无法模拟，包括：
  - **Google Play Integrity API (GPIA)** — 应用完整性证明，签名验证在 Google 服务器侧完成
  - **SafetyNet / Play Protect** — 设备环境安全证明，依赖 TEE/硬件安全模块
  - **大量 env metrics** — 运行时设备环境指标（传感器数据、系统属性等），在注册请求中作为参考信号上报

  这是整个行业的共同壁垒 —— **目前市面上基本没有做得较好的开源注册方案**，并非 zowsup 特有问题。  
**定性**: 这是**有意识的产品范围决策**，不是技术缺陷，不列入风险隐患。  
**实际影响**: 公开版本适用范围限定为「已有账号的运营管理」，新号注册需走私有渠道。

---

### 4.1 🔴 高风险

#### 4.1.1 媒体下载阻塞 Event Loop
**位置**: `app/layer/media.py:download()`  
**问题**: 使用 `requests.get()` 同步阻塞下载媒体文件，该方法在 Bot 的 asyncio event loop 线程中被调用。大文件下载会长时间阻塞整个 Bot 的消息处理。  
**影响**: 单个媒体下载会导致该 Bot 的消息收发、心跳全部暂停，可能触发服务器超时断连。  
**建议**: 改用 `aiohttp` 异步下载，或将下载操作投递到线程池。

#### 4.1.2 无消息发送速率限制
**位置**: 全局  
**问题**: 批量消息发送没有任何速率控制。WhatsApp 对消息频率有严格的隐形限制，超频会导致临时封禁或账号风控。  
**影响**: 批量营销场景极易触发封号。  
**建议**: 在 `BotSendCommand` 或 `MessageHandler` 中引入 Token Bucket 限流器，可配置默认速率（如每秒 5 条）。

#### 4.1.3 账号凭证明文存储
**位置**: `conf/config.conf` + `SysVar.ACCOUNT_PATH` 下的账号文件  
**问题**: 账号配置、密钥等敏感信息以明文 JSON/配置文件存储。  
**影响**: 服务器被入侵后所有账号凭据直接泄露。  
**建议**: 引入密钥加密存储（如 Fernet 对称加密），Agent 启动时输入主密钥解密。

### 4.2 🟡 中风险

#### 4.2.1 Cluster Registry 单点故障
**位置**: `agent/cluster/registry.py`  
**问题**: Registry 使用本地 SQLite 文件，Router 是唯一写入者。Router 宕机后整个集群不可用。  
**影响**: 集群不具备高可用 (HA) 能力。  
**建议**: 考虑引入 Redis 或 etcd 作为 Registry 后端；或实现 Router 主备切换。

#### 4.2.2 无全局消息去重
**位置**: `app/layer/message_handler.py`  
**问题**: 虽然维护了 `msgMap`，但在 Bot 重启或重连后可能收到重复消息。WhatsApp 服务器在某些异常情况下会重放消息。  
**影响**: 重复消息触发重复的业务逻辑（如 AI 多次回复）。  
**建议**: 消息 ID 在 ConversationStore 中做唯一约束，入库前检查去重。

#### 4.2.3 异常恢复不完整
**位置**: `app/zowbot.py:_async_run()`  
**问题**: 主循环捕获 `KeyboardInterrupt`、`SOCKS5Error`、`OSError`，但对其他异常（如 `asyncio.CancelledError` 传播、Protobuf 解析异常）可能直接导致循环退出且不重连。  
**影响**: 某些非预期异常可能导致 Bot 静默停止。  
**建议**: 在最外层增加泛化异常捕获与告警通知，区分「可恢复异常」（重连）与「致命异常」（停止）。

#### 4.2.4 线程间数据竞争风险 【已有真实案例】
**位置**: `app/zowbot.py:onCallback()`、`agent/manager/bot_manager.py`  
**问题**: `onCallback` 在 Bot 线程的 asyncio loop 中运行，但通过 `run_in_executor` 将回调投递到 Agent 线程池。`_exit_code`、`status` 等多线程共享变量缺乏同步保护。  
**外部验证**: GitHub 最新提交 (Jun 12) 为 `"dead lock about listbot"` — 证明 `BotManager._lock` 在 `listbot` 并发调用时确实发生过死锁，已修复并合入本地 0.9.5 代码。  
**影响**: 潜在数据竞争（listbot 死锁已修复，其他路径仍有风险）。  
**建议**: 使用 `threading.Lock` 保护共享状态，或将所有状态变更统一到 Agent 的 event loop 中。

#### 4.2.5 Google 翻译 API Key 硬编码
**位置**: `agent/plugin/translation/translators.py`  
**问题**: `_GT_PA_KEY = "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520"` 是硬编码的 Google API Key，可能来自逆向工程。  
**影响**: Key 可能随时失效，或被 Google 封禁。  
**建议**: 将 API Key 移至配置文件，并提供用户自带 Key 的选项。

### 4.3 🟢 低风险

#### 4.3.1 错误日志级别不一致
**位置**: 多处  
**问题**: 某些异常使用 `logger.info` 而非 `logger.error`/`logger.warning`（如 `app/zowbot.py:378` 的 `OSError: logger.info`）。  
**建议**: 统一错误日志规范。

#### 4.3.2 部分命令无参数校验
**问题**: 部分命令模块缺少参数数量和类型的严格校验，依赖 `ParamsNotEnoughException` 兜底。  
**建议**: 在 `BotCommand` 基类增加参数 Schema 定义支持。

#### 4.3.3 测试覆盖不均衡
**位置**: `tests/`  
**问题**: 有 10 个 Phase 测试文件，覆盖 auth、bots、cmd、logs、import/export、e2e、conversation、cluster、plugin。但缺少对核心协议层（如消息加解密正确性、Noise 握手）的单元测试。  
**建议**: 补充核心加密/协议层的单元测试。

#### 4.3.4 面向用户的文档严重不足 【外部反馈验证】
**问题**: GitHub Issues 中大量问题属于基础使用类（「what should config file look like」、「How to extract six parts」、「How to connect WhatsApp Business」），说明现有文档对初次使用者不够友好。  
**建议**: 补充 Quick Start、Account 生命周期说明、FAQ 到 `docs/` 目录。

---

## 五、外部反馈与当前状态对比

> **数据来源**: GitHub (clarithromycine/zowsup) Issues + Commit History，截至 2026-06-16

| 类型 | 外部反馈 | 与本地 0.9.5 的吻合度 |
|------|---------|---------------------|
| Open Issue #16 | 新号注册被 WhatsApp blocked (95%+) | ✅ 原因清楚（GPIA/SafetyNet/env metrics 无法模拟），属于公开版主动阉割的已知边界，已改入 4.0.1 说明 |
| Open Issue #15 | QR 注册后 Login 401，config.id 为 null | ℹ️ 疑似旧版本问题（日志前缀 `yowsup.` 而非 `zowsup.`），0.9.5 中日志系统已重构 |
| Closed Issues 模式 | 大量 Fail Login、Import Error、Decrypt Failed | ℹ️ 多数已在 0.9.x 修复；部分属于使用不当（缺乏文档） |
| Jun 12 Commit | `dead lock about listbot` — BotManager 并发死锁 | ✅ 确认匹配我们的 4.2.4 风险判断，已修复 |
| Jun 9-10 Commits | `bug fixed`×4, `cmd bugs`, `group bug fixed`, `pairing refactory` | ✅ 说明项目仍处于快速迭代修 bug 阶段，可靠性★★★☆☆评级准确 |
| GitHub 版本 | 公开版 README 仍显示 0.9.0（Jun 2），本地已是 0.9.5 | ℹ️ 本地有约 2 周的功能领先（Cluster、Web Console、Plugin、0.9.5 全部特性） |
| 项目影响力 | 61★ / 19 forks / 1 贡献者 | ℹ️ 仍是单人项目，依赖个人维护节奏，Bus Factor = 1 风险 |

**评估修正点：**
- `协议完整性（运营层面）` 维持 ★★★★★：对已登录账号的消息/群组/媒体协议全覆盖，评级准确
- `注册能力` 单独列为已知边界而非缺陷：原因明确（Google 应用证明体系无法在协议层模拟），为主动决策而非技术欠债
- 新增 Bus Factor 风险：单一贡献者维护节奏是客观风险

---

## 六、后续行动计划 (Next Todo)

### Phase 0: 用户引导 (立即)

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 0.1 | **文档明确适用范围** | 🟡 P1 | 在 README 首屏标注：公开版仅支持「已有账号运营」，新号注册需私有方案，减少用户在 Issue 中反复询问 |

### Phase 1: 紧急修复 (1-2 周)

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 1.1 | **媒体下载异步化** | 🔴 P0 | 将 `MediaManager.download()` 改为 `aiohttp` 异步实现，消除 event loop 阻塞 |
| 1.2 | **消息发送限流** | 🔴 P0 | 在 `BotSendCommand` 基类加入 Token Bucket 限流，默认 5 msg/s，可通过 Agent API 配置 |
| 1.3 | **异常泛化捕获** | 🔴 P0 | `_async_run()` 最外层增加 `except Exception` 兜底 + 日志告警，区分可恢复/致命 |

### Phase 2: 安全加固 (2-4 周)

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 2.1 | **账号凭据加密存储** | 🟡 P1 | 使用 `cryptography.fernet` 加密账号配置，Agent 启动时读取环境变量 `MASTER_KEY` 解密 |
| 2.2 | **Google API Key 外部化** | 🟡 P1 | 将翻译 API Key 移至 `config.conf`，支持用户自定义 |
| 2.3 | **API 访问审计日志** | 🟡 P1 | 记录所有 Agent API 调用（来源 IP、操作、Bot ID、时间戳） |

### Phase 3: 可靠性提升 (4-6 周)

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 3.1 | **消息去重机制** | 🟡 P1 | ConversationStore 中 `msg_id` 加唯一约束，入库前去重检查 |
| 3.2 | **消息发送重试** | 🟡 P1 | 发送失败时自动重试（指数退避，最多 3 次），结果通过 WebSocket 推送 |
| 3.3 | **Registry 高可用** | 🟡 P1 | 支持 Redis 作为 Registry 后端，Router 无状态化（可水平扩展） |
| 3.4 | **Bot 优雅降级** | 🟡 P1 | Bot 启动失败或异常退出时，自动通知 Agent，记录详细错误到 escalation |

### Phase 4: 性能优化 (6-8 周)

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 4.1 | **Agent 智能负载均衡** | 🟢 P2 | Cluster Router 根据 Agent 当前 Bot 数量、CPU/内存做加权调度 |
| 4.2 | **WebSocket 广播优化** | 🟢 P2 | 改为按频道订阅的 pub/sub 模式，减少无关注客户端的数据推送 |
| 4.3 | **Bot 线程池模型评估** | 🟢 P2 | 评估将「每 Bot 一线程」改为「共享线程池 + 多 event loop」或 `asyncio` 全协程方案的可行性 |

### Phase 5: 工程化完善 (长期)

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 5.1 | **核心协议层单元测试** | 🟢 P3 | 补充 Axolotl 加密、Noise 握手的独立单元测试 |
| 5.2 | **命令参数 Schema 校验** | 🟢 P3 | `BotCommand` 基类增加参数定义与自动校验 |
| 5.3 | **CI/CD Pipeline** | 🟢 P3 | 自动化测试、代码检查、版本发布流程 |
| 5.4 | **性能基准测试** | 🟢 P3 | 建立 Bot 并发数 vs 资源占用的基准数据，指导容量规划 |
| 5.5 | **面向用户文档** | 🟢 P3 | 补充 Quick Start、Account 生命周期、FAQ，减少「how to use」类 support 问题 |

---

## 七、总结评价

| 维度 | 评级 | 说明 |
|------|------|------|
| 协议完整性（已登录账号运营） | ★★★★★ | 18+ 协议子层，消息/群组/媒体/通知全覆盖，跟进最新 WA 版本 |
| 新号注册（公开版） | — | 主动阉割，不在公开版范围内；技术根因已明确（GPIA/SafetyNet），属行业共同壁垒 |
| 代码架构 | ★★★★☆ | 分层清晰、v0.9.0 asyncio 改造成功，但 ZowBot 类仍有优化空间 |
| 水平扩展性 | ★★★★☆ | Cluster 设计合理，透明代理 + 智能路由，但 Registry 是单点 |
| Bot 功能完整度 | ★★★★★ | 消息收发、群组管理、账号管理、媒体消息、多设备全部覆盖（前提：账号已登录） |
| Agent 管控能力 | ★★★★★ | Web Console + REST API + WebSocket + 插件系统，企业级管控 |
| 安全性 | ★★★☆☆ | 凭证明文存储、API Key 硬编码，需要安全加固 |
| 可靠性 | ★★★☆☆ | 异常恢复不完整、无消息去重、缺少重试机制；listbot 死锁 Jun 12 已修 |
| 测试覆盖 | ★★★☆☆ | 集成测试较完善，但协议核心层缺少单元测试 |
| 项目可持续性 | ★★★☆☆ | 单人维护、Bus Factor = 1；注册核心能力私有化，公开版依赖有限 |

**综合评级: B+ (良好，定位清晰后有进一步提升空间)**

zowsup 在「已有账号运营」这个场景下是当前开源社区最完整的 WhatsApp 协议 Python 实现。v0.9.x 架构演进方向正确（asyncio + Cluster + 插件化），工程基础扎实。新号注册不在公开版范围内，原因是 WhatsApp 注册依赖 Google 应用证明体系（GPIA、SafetyNet 等）和大量运行时环境指标，这些在纯协议层面无法模拟——这是整个行业的共同壁垒，而非项目缺陷，作者已有意识地将边界明确划定。后续重点应放在**可靠性提升**和**安全加固**上，补齐生产环境部署的关键短板。

---

> *本文档基于 2026-06-16 代码快照分析，随项目演进持续更新。*
