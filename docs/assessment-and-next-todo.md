# 项目评估与下阶段工作计划

**评估日期**: 2026-06-16  
**当前版本**: v0.9.5  
**分支**: dev  
**复核人**: GitHub Copilot (DeepSeek V4 Pro) — 独立复核 Claude 评估

---

## 〇、复核意见

Claude 的原始评估 **整体方向正确，细节有 4 处修正**：

| # | 修正点 | Claude 原文 | 实际情况 | 状态 |
|---|--------|------------|---------|------|
| 1 | 测试失败根因 | "均為環境配置問題" | `conftest.py` 硬编码了不存在的 `TEST_BOT_ID` 默认值 `263783604300`，**是 fixture 设计缺陷**，不是纯环境问题 | ✅ 已修复 |
| 2 | `router.py` 架构 | 未提及 | 已膨胀到 400+ 行，路由/业务/迁移混在一起，**需要拆分** | ✅ 已拆分 |
| 3 | Cluster 安全 | 仅提 CLUSTER_SECRET | Agent 已有完善的 access_key 机制，但 **Cluster 管理面完全绕过** — 两层的安全模型都缺失 | ✅ 已修复 |
| 4 | Agent 残留 | 未提及 | Agent 被 kill -9 后注册信息残留 45s，`pick_agent()` 会误选已死 Agent | ✅ TTL+过期机制 |

以下计划已整合以上修正。

---

## 一、测试状态

当前测试结果: **110 通过 / 0 失败 / 0 跳过**

> Phase B 完成：新增 `test_phase9_cluster.py`（42 测试）+ `test_phase10_plugin.py`（18 测试），CI 安全模式 `-m "not requires_connection"` 99 pass / 11 deselected。

---

## 二、代码质量

| 方面 | 状态 | 说明 |
|------|------|------|
| 语法检查 | ✅ 通过 | 全部 `.py` 文件解析正常 |
| 导入链 | ✅ 通过 | `agent` + `agent.cluster` + `agent.cluster.migrate` + `agent.cluster.helpers` 均可干净导入 |
| 遗留标记 | ✅ 无 | 无 TODO / FIXME / HACK |
| 异步规范 | ✅ 通过 | 注册/心跳在 lifespan 内运行，无 DeprecationWarning |
| 文件大小 | ✅ 已拆分 | `router.py` 511 行，迁移编排 → `migrate.py`(80行)，共享工具 → `helpers.py`(47行) |

---

## 三、功能缺口

### ✅ 已关闭（Phase A + A.5 + B）

| 缺口 | 解决方案 |
|------|----------|
| Cluster 无身份验证 | `--cluster-secret` + `X-Cluster-Secret` header，所有 `/api/cluster/*` 管理端点受保护 |
| Agent 注册无 TTL | `AGENT_TTL_SECONDS=120s`，查询时自动 `_expire_stale_agents()` |
| Router 单点故障 | 记录为已知限制（暂无 HA），TTL 机制已缓解 Agent 残留问题 |
| Web Console 无认证 UI | `--console-token` + `?token=` query 参数保护 |
| `router.py` 单体膨胀 | 已拆分为 `migrate.py` + `helpers.py` |
| Plugin/Cluster 无测试覆盖 | `test_phase9_cluster.py` 42 测试 + `test_phase10_plugin.py` 18 测试 |

### 🟡 中优先级（已解决）

| 缺口 | 说明 | 状态 |
|------|------|------|
| **`POST /api/cluster/deploybot` 已实现** | 接受 Bot 文件包（六段号 CSV），自动选负载最轻的 Agent 导入并启动 | ✅ |
| **`startbot` 负载均衡粗糙** | ~~`pick_agent()` 只选当前 bots 最少的 Agent，未考虑 CPU/内存~~ → 已修复：startbot 不再用 pick_agent()，按已有路由精确分发 | ✅ |
| **Conversation API 路由已优化** | 无 `bot_id` 时 scatter-gather + merge + 去重已实现 | ✅ |

### 🟠 低优先级

| 缺口 | 说明 |
|------|------|
| **消息发送无重试机制** | `sendmsg` proxy 失败直接返回错误，无 retry/queue |
| **Bot 迁移前无容量检查** | 迁移时不检查目标 Agent 是否有余量 |
| **迁移失败清理不完整** | import 失败有回滚，但 export/start/cleanup 失败时残留状态未处理 |

---

## 四、下阶段工作计划

### ✅ 方向 A — 安全加固 + Agent 残留修复（已完成）

- [x] Router `__main__.py` 新增 `--cluster-secret` CLI 参数
- [x] Router 新增 `_check_cluster_secret` 依赖，对 `/api/cluster/*` 端点统一验证 `X-Cluster-Secret` header
- [x] Agent `server.py` lifespan 注册/心跳请求携带该 header
- [x] Web Console 可选 `CONSOLE_TOKEN` → `--console-token`，开启后控制台需 `?token=` query 参数
- [x] Registry 新增注册 TTL（120s），查询时自动 `_expire_stale_agents()`
- [x] 文档更新：`CLUSTER_SECRET` + `CONSOLE_TOKEN` 配置说明

### ✅ 方向 A.5 — router.py 拆分（已完成）

- [x] 迁移编排逻辑 → `agent/cluster/migrate.py`（80 行）
- [x] 共享工具 → `agent/cluster/helpers.py`（47 行）
- [x] `router.py` 从 ~600 行精简至 511 行

### ✅ 方向 B — 测试补全（已完成）

- [x] `conftest.py`: 从 `AccountStore` 自动发现可用账号，`pytest_configure` 注册 `requires_connection` marker
- [x] 对需要真实 WA 连接的测试加 `@pytest.mark.requires_connection`（5 个测试类）
- [x] 新增 `tests/test_phase9_cluster.py` — Registry / Router HTTP / Escalation / Plugin Sync（42 测试）
- [x] 新增 `tests/test_phase10_plugin.py` — PluginStore CRUD / Manager dispatch（18 测试）

### ✅ 方向 C — 功能扩展（已完成）

**目标**: 补完规划但未实现的功能

- [x] `POST /api/cluster/deploybot` — 接受 Bot 文件包（六段号 CSV），自动选 Agent 导入并启动。
  - **命名说明**: 不叫 `importbot`。Agent 已有 `POST /api/importbot`（解析六段号 CSV 并写入本地 AccountStore）。Cluster 的职责是"部署分发到集群节点"，语义不同，用 `deploybot` 区分。
  - 实现：接收上传的 CSV → `pick_agent()` 选节点 → `POST {agent}/api/importbot` 代理导入 → `startbot` 启动（`router.py:179`）
- [x] `GET /api/conversation` cluster 路由优化 — 按 `bot_id` 精确路由，无 bot_id 时 scatter+merge+去重（`router.py:367`）
- [x] Web Console Plugins 标签增强 — 点击插件行展开内联 JSON 编辑器，支持 Save / Toggle Enable（`static/index.html`）
- [x] Bot 迁移容量检查 — 迁移前拒绝目标 Agent 超载（`MAX_BOTS_PER_AGENT=50`，`deploybot` + `migrate.py` 均有检查）
- [x] `GET /api/cluster/health` 聚合接口 — 返回所有 Agent 健康状态汇总（`router.py:298`）

### ✅ 方向 D — 稳定性 & 路由修复（本次会话追加，已完成）

本轮修复了一系列在集群模式下暴露的问题：

- [x] **Agent 地址修复** — 写死 `127.0.0.1` → 支持 `--host` + `CLUSTER_ADVERTISE_HOST` 环境变量；cluster 端从 HTTP 请求自动提取真实 IP
- [x] **startbot / stopbot 路由修复** — 不再用 `pick_agent()` 覆盖已有路由，按 bot 实际所属 agent 精确分发
- [x] **`DELETE /api/bot/{bot_id}` 新增** — 完整清理：stop bot + 删 DB 记录 + 删磁盘目录
- [x] **日志格式升级** — 毫秒精度时间戳 `2026-06-16 10:30:45.123 | INFO  | module | msg`，uvicorn 日志统一格式
- [x] **心跳间隔调整** — Agent 主动心跳 30s→60s，Cluster 被动探测 15s→30s
- [x] **测试清理修复** — `test_import_and_export_roundtrip` 的 fake 账号目录现在正确清理

---

## 五、执行状态

```
✅ A（安全 + 残留修复） → ✅ A.5（router 拆分） → ✅ B（测试补全） → ✅ C（功能扩展） → ✅ D（稳定性修复）
```

- **全部完成**：Cluster 管理端点有认证、Agent 注册有 TTL、router.py 已拆分、测试从 50 → 110。
- **Phase C 全部 5 项已实现**：deploybot、conversation 路由、Plugins 内联编辑、容量检查、health 聚合。
- **Phase D**：本轮修复了 startbot 路由错乱、Agent 地址写死、日志缺时间等集群模式关键问题。

### 下一步方向

- **方向 D2 — Media 消息支持**：Conversation API 扩展 media 字段 + 下载端点 + Web Console 渲染 IMAGE/VIDEO/AUDIO/STICKER
- **方向 E — 迁移完整性**：迁移失败回滚、断点续传、迁移进度追踪

---

*初评: GitHub Copilot (Claude Sonnet 4.6)*  
*复核 & 补充: GitHub Copilot (DeepSeek V4 Pro)*  
*最后更新: 2026-06-16（Phase A + A.5 + B + C + D 完成）*
