# 会话满意度调查插件 — 实施计划

> 版本: v0.1 | 日期: 2026-06-18 | 状态: 设计阶段

---

## 概述

在会话服务结束时，插件向客户发起满意度评分提问（1-5 分），收集评分后发送感谢语并结束会话。评分记录支持 agent 本地存储和 cluster 集中存储两种模式。

---

## Phase 0: Conversation Stage 框架改动

> **依赖**: 无
> **影响范围**: `agent/plugin/__init__.py`, `agent/plugin/manager.py`

### 任务

- [ ] **0.1** `MessageContext` 新增 `stage: str = "normal"` 字段
- [ ] **0.2** `PluginManager` 新增 `_conv_stages: dict[str, str]` 内存字典
- [ ] **0.3** `PluginManager` 新增 `get_stage(conv_id)` / `set_stage(conv_id, stage)` 方法
- [ ] **0.4** `dispatch_on_message` 中注入 `ctx.stage`，并检查 `skip_stages` 配置跳过对应插件
- [ ] **0.5** AI 插件默认配置增加 `"skip_stages": ["surveying"]`

### 验收

```bash
# 1. 单元测试：stage 读写正确
pytest tests/test_phase10_plugin.py -k "test_stage"

# 2. 集成测试：surveying stage 下 AI 退避
#    发送消息 → 设 stage="surveying" → AI 返回 NoAction
pytest tests/test_phase10_plugin.py -k "test_skip_stages"
```

### 改动文件

| 文件 | 行数 |
|---|---|
| `agent/plugin/__init__.py` | +1 |
| `agent/plugin/manager.py` | +30 |
| `agent/plugin/ai/__init__.py` | +1 |

---

## Phase 1: Survey Session 存储层

> **依赖**: 无
> **状态**: 待实现

### 任务

- [ ] **1.1** 新建 `agent/plugin/satisfaction/store.py`
  - SQLite 表 `survey_sessions`，包含: `id, bot_id, conversation_id, session_status, started_at, last_msg_at, survey_sent_at, rating, rating_at, ended_at, created_at`
  - session_status: `active` | `surveying` | `completed` | `expired`
- [ ] **1.2** 实现 `SurveyStore` 类，API:
  - `get_active_session(conv_id)` → 返回 status 为 active/surveying 的最新记录
  - `create_session(bot_id, conv_id)` → INSERT 新 session
  - `touch_session(session_id)` → 更新 last_msg_at
  - `set_surveying(session_id)` → status → surveying, 记录 survey_sent_at
  - `complete_survey(session_id, rating)` → status → completed, 记录 rating + rating_at
  - `expire_session(session_id)` → status → expired
- [ ] **1.3** 支持 Cluster 模式：`CLUSTER_URL` 环境下 POST 到 Router 的 `/api/survey`
- [ ] **1.4** 单例导出 `survey_store`

### 验收

```bash
# 单元测试：SQLite CRUD
pytest tests/test_phase11_satisfaction.py -k "test_store"

# 验证点：
# - create → get_active_session 返回正确
# - touch_session → last_msg_at 更新
# - complete_survey → status=completed, rating 已存
# - expire_session → status=expired
# - 同一 conv_id 已有 active session 时再次 create → 不会创建重复
```

### 改动文件

| 文件 | 行数 |
|---|---|
| `agent/plugin/satisfaction/__init__.py` | (占位) |
| `agent/plugin/satisfaction/store.py` | ~100 |

---

## Phase 2: Satisfaction 插件主逻辑

> **依赖**: Phase 0, Phase 1
> **状态**: 待实现

### 任务

- [ ] **2.1** 新建 `SatisfactionPlugin(Plugin)` 类
  - `name = "satisfaction"`, `version = "0.1.0"`, `priority = 200`
- [ ] **2.2** 实现 `on_start(bot_id)` → 启动后台扫描协程（见 Phase 3）
- [ ] **2.3** 实现 `on_stop(bot_id)` → 取消该 bot 的后台协程
- [ ] **2.4** 实现 `on_message(ctx)` 核心逻辑：

```
ctx.direction != "incoming"  → NoAction
ctx.conversation_id 含 @g.us → NoAction（跳过群聊）

active_session = survey_store.get_active_session(conv_id)

if active_session is None:
    # 新服务会话起点
    survey_store.create_session(bot_id, conv_id)
    mark_session_start(conv_id)         # 记录开始时间，启动计时器
    → NoAction（不打断正常服务）

elif active_session.status == "active":
    # 服务中，更新最后活跃时间
    survey_store.touch_session(active_session.id)
    reset_inactivity_timer(conv_id)
    → NoAction

elif active_session.status == "surveying":
    rating = parse_rating(ctx.content)  # 尝试解析 1-5
    if rating is not None:
        survey_store.complete_survey(active_session.id, rating)
        plugin_manager.set_stage(conv_id, "normal")   # ← 恢复 stage
        return [ReplyAction(conv_id, thank_you_msg)]
    else:
        # 评分等待中，但客户发了其他消息 → 可能是新问题
        # 可选策略 A: 结束旧 session（不评分），开新 session
        # 可选策略 B: 忽略，继续等评分
        → 策略 A（默认）: survey_store.expire_session(...) + create_session(...)
```

- [ ] **2.5** 实现 `parse_rating(text)` → 从文本中提取 1-5 的数字评分（支持 "5分"、"评分5"、"5" 等）

### 验收

```bash
pytest tests/test_phase11_satisfaction.py -k "test_plugin"

# 验证点：
# 1. 群聊消息返回 NoAction
# 2. 无 active session 时创建 session
# 3. active session 下更新 last_msg_at
# 4. surveying stage 收到 "5" → 返回 ReplyAction(感谢语) + stage 恢复 normal
# 5. "5分" / "评分4" / "3" 都能正确解析
# 6. surveying stage 收到非评分消息 → session expired + 新 session 创建
```

---

## Phase 3: 不活跃检测 & 自动触发调查

> **依赖**: Phase 2
> **状态**: 待实现

### 任务

- [ ] **3.1** 在 `on_start` 中为每个 bot 启动后台 `asyncio.create_task` 扫描协程
- [ ] **3.2** 实现扫描逻辑：每 15 秒扫描一次该 bot 下所有 active session
- [ ] **3.3** 对 `last_msg_at < now - config.inactivity_minutes` 的 session：
  1. 设置 `plugin_manager.set_stage(conv_id, "surveying")`
  2. 发送 `ReplyAction(conv_id, survey_message)`
  3. 更新 `survey_store.set_surveying(session.id)`
- [ ] **3.4** 在 `on_message` 的 active 分支中，重置该 session 的不活跃计时器
- [ ] **3.5** 在 `on_stop` 中取消对应后台协程

### 验收

```bash
pytest tests/test_phase11_satisfaction.py -k "test_inactivity"

# 验证点：
# 1. 配置 inactivity_minutes=1，1分钟后自动触发 → stage 变为 surveying
# 2. 用户在此期间发消息 → 计时器重置，不触发
# 3. 后台协程在 on_stop 时正确取消
```

---

## Phase 4: 插件配置 & 前端

> **依赖**: Phase 2
> **状态**: 待实现

### 任务

- [ ] **4.1** 在 `agent/api/plugin_api.py` 中为 satisfaction 插件注册默认配置:
  ```json
  {
    "inactivity_minutes": 5,
    "survey_message": "请对本次服务评分（1-5分，5分为非常满意）",
    "thank_you_message": "感谢您的评价！如有其他问题，欢迎随时联系我们。"
  }
  ```
- [ ] **4.2** 在 `agent/static/console/src/views/PluginsTab.vue` 中为 satisfaction 插件增加配置编辑 UI（可选：如果现有通用配置 UI 已足够则跳过）

### 验收

```bash
# API 测试
curl -X PUT /api/plugin/satisfaction/config -H "Content-Type: application/json" \
  -d '{"bot_id":"265996090985","config":{"inactivity_minutes":3}}'
# → 验证返回 ok

curl /api/plugin/satisfaction/config?bot_id=265996090985
# → 验证 inactivity_minutes=3
```

---

## Phase 5: 评分记录 API

> **依赖**: Phase 1, Phase 2
> **状态**: 待实现

### 任务

- [ ] **5.1** 新建 `agent/api/survey_api.py`，提供：
  - `GET /api/survey?bot_id=&status=&from=&to=` → 评分列表
  - `GET /api/survey/{id}` → 单条评分详情
- [ ] **5.2** 在 `agent/server.py` 中注册路由
- [ ] **5.3** Cluster 模式下代理到 Router

### 验收

```bash
# 查询某 bot 的评分记录
curl "/api/survey?bot_id=265996090985&status=completed"
# → 返回评分列表，含 rating 值、会话时间等
```

---

## Phase 6: 集成测试 & 回归

> **依赖**: Phase 0-5 全部完成
> **状态**: 待实现

### 任务

- [ ] **6.1** 端到端测试：模拟完整满意度调查流程
  ```
  用户发消息 → 服务交互 → 5分钟无回复 → 插件发评分提问
  → 用户回复 "5" → 插件发感谢语 → stage 恢复 normal
  ```
- [ ] **6.2** AI 插件回归测试：surveying stage 下 AI 退避
- [ ] **6.3** 群聊消息跳过测试
- [ ] **6.4** 已 escalate 会话跳过测试

### 验收

```bash
pytest tests/test_phase11_satisfaction.py -v
# 全部通过
```

---

## 依赖关系图

```
Phase 0 (stage framework) ────┐
                               ├──→ Phase 2 (主逻辑) ──→ Phase 3 (不活跃检测)
Phase 1 (存储层) ──────────────┘         │
                                         ├──→ Phase 4 (配置 & 前端)
                                         │
                                         └──→ Phase 5 (API)
                                                  │
                                                  └──→ Phase 6 (集成测试)
```

---

## 进度跟踪

| Phase | 描述 | 状态 | 完成日期 |
|---|---|---|---|
| 0 | Conversation Stage 框架 | ✅ 已完成 | 2026-06-18 |
| 1 | Survey Session 存储层 | ✅ 已完成 | 2026-06-18 |
| 2 | Satisfaction 插件主逻辑 | ✅ 已完成 | 2026-06-18 |
| 3 | 不活跃检测 & 自动触发 | ✅ 已完成 | 2026-06-18 |
| 4 | 插件配置 & 前端 | ✅ 已完成 | 2026-06-18 |
| 5 | 评分记录 API | ✅ 已完成 | 2026-06-18 |
| 6 | 集成测试 & 回归 | ✅ 已完成 | 2026-06-18 |

---

## 风险清单

| 风险 | 等级 | 缓解 |
|---|---|---|
| 后台扫描协程内存泄漏 | 中 | on_stop 取消 + try/finally 保护 |
| AI 插件升级后覆盖 skip_stages 配置 | 低 | 代码中设默认值 + 配置合并 |
| 老客户多条并发消息触发多个 session | 低 | get_active_session 保证幂等 |
| Cluster 模式下存储可用性 | 低 | 已有 escalation_queue 验证该模式稳定 |
