# 项目评估与下阶段工作计划

**评估日期**: 2026-06-16  
**当前版本**: v0.9.5  
**分支**: dev  
**复核人**: GitHub Copilot (DeepSeek V4 Pro) — 独立复核 Claude 评估

---

## 〇、复核意见

Claude 的原始评估 **整体方向正确，细节有 4 处修正**：

| # | 修正点 | Claude 原文 | 实际情况 |
|---|--------|------------|---------|
| 1 | 测试失败根因 | "均為環境配置問題" | `conftest.py` 硬编码了不存在的 `TEST_BOT_ID` 默认值 `263783604300`，**是 fixture 设计缺陷**，不是纯环境问题 |
| 2 | `router.py` 架构 | 未提及 | 已膨胀到 400+ 行，路由/业务/迁移混在一起，**需要拆分** |
| 3 | Cluster 安全 | 仅提 CLUSTER_SECRET | Agent 已有完善的 access_key 机制，但 **Cluster 管理面完全绕过** — 两层的安全模型都缺失 |
| 4 | Agent 残留 | 未提及 | Agent 被 kill -9 后注册信息残留 45s，`pick_agent()` 会误选已死 Agent |

以下计划已整合以上修正。

---

## 一、测试状态

当前测试结果: **40 通过 / 9 失败 / 1 跳过**

### 失败原因分类

| 测试文件 | 失败数 | 根因 |
|----------|--------|------|
| `test_phase2_bots.py` | 5 | `conftest.py` 中 `AGENT_TEST_BOT_ID` 默认值 `263783604300` 在 AccountStore 中不存在，需自动发现可用账号 |
| `test_phase3_cmd.py` | 2 | 依赖运行中的 bot（需真实 WhatsApp 连接，CI 无法自动化） |
| `test_phase5_logs.py` | 1 | 同上，需 bot 运行状态 |
| `test_phase7_e2e.py` | 1 | 同上，全生命周期需要真实连接 |

> **结论**: 5 个失败是 fixture 缺陷（可立即修复），4 个是真实的 WA 连接依赖（需标记 skip）。**Cluster 代码（router、registry、proxy、migrate）目前完全没有测试覆盖。**

---

## 二、代码质量

| 方面 | 状态 | 说明 |
|------|------|------|
| 语法检查 | ✅ 通过 | 全部 32 个 `.py` 文件解析正常 |
| 导入链 | ✅ 通过 | `agent` + `agent.cluster` 均可干净导入 |
| 遗留标记 | ✅ 无 | 无 TODO / FIXME / HACK |
| 异步规范 | ✅ 通过 | 注册/心跳在 lifespan 内运行，无 DeprecationWarning |
| 文件大小 | ⚠️ 警告 | `router.py` 400+ 行，路由定义与业务逻辑混在一起 |

---

## 三、功能缺口

### 🔴 高优先级

| 缺口 | 说明 |
|------|------|
| **Cluster 无身份验证** | `/api/cluster/agents`、`/api/cluster/migrate` 完全开放。Agent 端已有 `access_key` 机制，但 Cluster 管理面零防护。需引入 `CLUSTER_SECRET` 共享密钥，所有管理端点验证 `X-Cluster-Secret` header |
| **Agent 注册无 TTL** | 注册是幂等 `INSERT OR UPDATE`，Agent 被 kill -9 后残留 45s 才被 health check 标记 offline，期间 `pick_agent()` 可能选中已死的 Agent |

### 🟡 中优先级

| 缺口 | 说明 |
|------|------|
| **Router 单点故障** | Router 宕机则整个集群不可用，无 HA/Failover 机制 |
| **`POST /api/cluster/importbot` 未实现** | 从外部直接向集群导入 Bot 时，应自动选择负载最轻的 Agent |
| **`startbot` 负载均衡粗糙** | `pick_agent()` 只选当前 bots 最少的 Agent，未考虑 CPU/内存等因素 |
| **Conversation API 无 `bot_id` 时路由不稳** | scatter-gather 可能重复或丢失 |
| **Web Console 无认证 UI** | 控制台依赖外部反向代理或端口隔离 |
| **`router.py` 单体膨胀** | 路由、proxy、migrate 逻辑全在一个文件，应拆分为独立模块 |

### 🟠 低优先级

| 缺口 | 说明 |
|------|------|
| **消息发送无重试机制** | `sendmsg` proxy 失败直接返回错误，无 retry/queue |
| **Plugin AI/Translation 插件无测试** | 插件逻辑未被任何测试覆盖 |
| **Bot 迁移前无容量检查** | 迁移时不检查目标 Agent 是否有余量 |
| **迁移失败清理不完整** | import 失败有回滚，但 export/start/cleanup 失败时残留状态未处理 |

---

## 四、下阶段工作计划

### 方向 A — 安全加固 + Agent 残留在修复（优先推荐，预估 2~3 天）

**目标**: 关闭 Cluster 管理面安全缺口，修复 Agent 残留问题

- [ ] Router `__main__.py` 新增 `--cluster-secret` CLI 参数
- [ ] Router 新增 `depend_cluster_secret` 依赖，对 `/api/cluster/*` 端点统一验证 `X-Cluster-Secret` header
- [ ] Agent `server.py` lifespan 注册/心跳请求携带该 header
- [ ] Web Console 可选 `CONSOLE_TOKEN` 环境变量，开启后控制台需 Bearer token
- [ ] Registry 新增注册 TTL（如 120s），心跳刷新；超时自动标记 offline（替代仅靠 health check 的 45s 延迟）
- [ ] 文档更新：`CLUSTER_SECRET` + `CONSOLE_TOKEN` 配置说明

### 方向 A.5 — router.py 拆分（新增，预估 0.5 天）

**目标**: 解耦路由定义与业务逻辑

- [ ] 迁移编排逻辑抽到 `agent/cluster/migrate.py`
- [ ] 聚合端点（`listbot` 等）抽到 `agent/cluster/aggregate.py`
- [ ] `router.py` 只留路由定义 + lifespan

### 方向 B — 测试补全（预估 2~3 天）

**目标**: 消除 5 个 fixture 缺陷导致的失败，标记 4 个需要真实 WA 连接的测试，新增 Cluster 覆盖

- [ ] `conftest.py`: 从 `AccountStore` 自动发现可用账号，替代硬编码默认值 `263783604300`
- [ ] 对需要真实 WA 连接的测试加 `@pytest.mark.requires_connection`，CI 中 `-m "not requires_connection"` 跳过
- [ ] 新增 `tests/test_phase9_cluster.py`
  - [ ] Registry: register / heartbeat / unregister / resolve_bot / pick_agent / TTL 过期
  - [ ] Router 路由逻辑: 单 bot 路由、scatter-gather 逻辑、cluster_secret 拒绝
  - [ ] 集中化 Escalation: 创建 / 认领 / 关闭
  - [ ] Plugin sync: export_all / import_from
- [ ] 新增 `tests/test_phase10_plugin.py`
  - [ ] Plugin manager dispatch: EscalateAction / ReplyAction / TranslateAction
  - [ ] Plugin store: enable/disable / config update

### 方向 C — 功能扩展（预估 3~4 天）

**目标**: 补完规划但未实现的功能

- [ ] `POST /api/cluster/importbot` — 接受 Bot 文件包，自动选 Agent 导入并启动
- [ ] `GET /api/conversation` cluster 路由优化 — 按 `bot_id` 精确路由，无 bot_id 时 scatter+merge+去重
- [ ] Web Console Plugins 标签增强 — 点击插件可内联编辑 config JSON
- [ ] Bot 迁移容量检查 — 迁移前拒绝目标 Agent 超载（可配置 `max_bots_per_agent`）
- [ ] `GET /api/cluster/health` 聚合接口 — 返回所有 Agent 健康状态汇总

---

## 五、建议执行顺序

```
A（安全 + 残留修复） → A.5（router 拆分） → B（测试补全） → C（功能扩展）
```

- **A 必须先做**：无认证的 Cluster 在任何部署场景下都是安全漏洞。
- **A.5 紧接着**：在 A 改动 router.py 后进行拆分，避免在臃肿文件上叠加更多改动。
- **B 紧随其后**：修复 fixture 缺陷、补 Cluster 测试，防止后续功能开发引入退化。
- **C 最后推进**：基于稳固的安全和测试基础展开。

---

*初评: GitHub Copilot (Claude Sonnet 4.6)*  
*复核 & 补充: GitHub Copilot (DeepSeek V4 Pro)*
