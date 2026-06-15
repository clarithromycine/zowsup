# Agent 项目状态评估 — 2026-06-12

> 基于当前 dev 分支 (`2603aed`) 进行

---

## 1. 总体状态

| 维度 | 评分 | 说明 |
|------|------|------|
| 功能完整度 | ⭐⭐⭐⭐☆ | 核心功能完善，缺少少数运维接口 |
| 代码质量 | ⭐⭐⭐⭐☆ | 整体清晰，少量不一致 |
| 测试覆盖 | ⭐⭐⭐☆☆ | 26/30 通过，4 个已知 flaky |
| 文档 | ⭐⭐⭐⭐☆ | agent-api.md 完善，README 有入口 |
| API 设计 | ⭐⭐⭐⭐☆ | 整体合理，有个别不一致 |

**当前: 2101 行 agent 代码，24 个 Pydantic 模型，14 个端点，15 个 Py 文件**

---

## 2. API 清单

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/listbot` | ⚠️ 最近改成 POST（支持 bot_ids 过滤） |
| `GET` | `/api/bot/{id}` | 单个 bot 详情 |
| `DELETE` | `/api/bot/{id}` | 删除账号（停 bot + 清 DB + 删目录） |
| `POST` | `/api/startbot` | 并发启动（sync/fire 两模式） |
| `POST` | `/api/stopbot` | 批量停止 |
| `POST` | `/api/importbot` | 批量导入 |
| `POST` | `/api/exportbot` | 批量导出（含 env） |
| `POST` | `/api/botcmd` | 命令执行 |
| `POST` | `/api/sendmsg` | 高层消息封装（text/ad/media） |
| `POST` | `/api/purgebot` | 清理 auth_failed/orphaned 账号 |
| `GET` | `/api/health` | 健康检查（线程、内存、CPU、bot 数） |
| `GET` | `/api/bot/{id}/logs/recent` | 拉取历史日志 |
| `DELETE` | `/api/bot/{id}/logs` | 清空日志 |
| `WS` | `/api/bot/{id}/logs` | 实时日志流 |
| `WS` | `/api/bot/{id}/events` | 实时事件流 |

---

## 3. 已知问题

### 🟡 测试不稳定（已修复）
~~原因：测试硬编码 `"env": "android"`，真实账号是 SMBA，导致登录 401 → `success_count=0`。~~  
**已修复**：测试不再硬编码 env，由 agent 自动检测 config.json。stopbot 统一使用 force mode。

### 🟡 `/api/listbot` GET → POST 破坏性变更（已修复）

~~`listbot` 改成了 POST。~~  
**已修复**：同时保留 GET（全量）+ POST（bot_ids 过滤）。

---

## 4. 建议优化（按优先级）

### P0 — 稳定性
- [x] 修复 4 个 flaky 测试（去掉硬编码 env + force mode stopbot）

### P1 — 完善
- [x] `/api/listbot` 同时保留 GET（全量）+ POST（过滤）

### P2 — 运维增强
- [x] 请求 ID 追踪（`X-Request-ID` header → 日志关联）
- [x] 慢请求告警（执行超过 5 秒的请求记录 warn）
- [x] `/api/health` 增加 `uptime_seconds`
- [x] `/api/health` 增加 `version`

### P3 — 架构改进
- [x] 删除 `script_api.py` 空文件
- [x] `stop_bot` 可指定 `mode: "graceful" | "force"`（graceful 等线程退出，force 直接 kill）
- [x] `/api/startbot` 增加 `login_timeout` 参数
- [x] WebSocket 连接数监控（健康检查暴露 WS 连接数）

---

## 5. 已完成的重大改进（本次会话）

- concurrent startbot（sync/fire 两种模式）
- sendmsg 多态（text/ad/media + base64 文件上传）
- Swagger X-Access-Key security scheme
- env 映射修复（SMBA→smb_android 等）
- AccountStore 迁移修复（从 config.json 读 env）
- auth_detail 登录成功自动清空
- `CmdResult.extra="allow"` 允许 bot 响应额外字段透传
- `DELETE /api/bot/{id}` 账号删除
- `/api/health` 加入线程数、内存、CPU、bot 计数
- `onCallback` 去掉不必要的 `run_in_executor`

---

## 6. 结论

Agent 模块已进入**生产可用**状态。剩下的主要是打磨——修 flaky 测试、统一 API 风格、加运维接口。核心功能（启动/停止/命令/消息/导入导出/日志/事件）已完备且稳定。
