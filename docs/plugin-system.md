# Plugin System — 架构与使用文档

> 日期: 2026-06-15  
> 版本: v0.1  
> 测试: 20/20 通过

---

## 0. 概述

插件系统为 agent 提供可插拔的消息处理能力。每个插件在 bot 收到消息或发送消息时被调用，返回 `Action` 来控制 bot 行为。

### 设计原则

| 原则 | 说明 |
|------|------|
| 零侵入 | 默认全部禁用，不在 agent 核心代码中耦合 |
| bot 级控制 | 全局有默认开关，每个 bot 可单独覆盖 |
| 异步非阻塞 | 插件在事件循环中运行，不阻塞 bot 线程 |
| 可配置 | 每个插件有独立的配置键值对 |

---

## 1. 架构

```
┌──────────────────────────────────────────────┐
│                 bot_manager                   │
│                                              │
│  _on_bot_event  ──→ _dispatch_to_plugins     │
│  _execute()     ──→ dispatch_on_before_send  │
└──────────────────┬───────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │   PluginManager    │
         │                    │
         │  register()        │
         │  dispatch_*()      │
         │  execute_actions() │
         └────────┬───────────┘
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
  ┌────────┐ ┌────────┐ ┌─────────┐
  │  AI    │ │ Trans  │ │  Future │
  │ Plugin │ │ Plugin │ │  Plugin │
  └────────┘ └────────┘ └─────────┘
```

### 文件布局

```
agent/
  plugin/
    __init__.py           Plugin ABC + Action 基类
    manager.py            PluginManager 单例
    store.py              PluginStore 配置持久化
    ai/                   AI 插件 (stub)
      __init__.py
    translation/          翻译插件
      __init__.py          TranslationPlugin
      translators.py      Google / LLM 翻译提供者
  api/
    plugin_api.py         插件配置 REST API
```

---

## 2. Plugin 基类

```python
from agent.plugin import Plugin, MessageContext, Action, NoAction

class MyPlugin(Plugin):
    name = "my_plugin"
    version = "0.1.0"
    description = "描述"

    async def on_message(self, ctx: MessageContext) -> list[Action]: ...
    async def on_before_send(self, ctx: MessageContext) -> list[Action]: ...
    async def on_start(self, bot_id: str) -> list[Action]: ...
    async def on_stop(self, bot_id: str) -> list[Action]: ...
```

### MessageContext

| 字段 | 类型 | 说明 |
|------|------|------|
| `bot_id` | `str` | bot 标识 |
| `jid` | `str` | 对端 canonical JID（LID / group JID） |
| `pn_jid` | `str\|None` | 对端 phone JID |
| `direction` | `str` | `"incoming"` \| `"outgoing"` |
| `content_type` | `str` | `"TEXT"`, `"IMAGE"`, ... |
| `content` | `str\|None` | 消息内容 |
| `message_id` | `str\|None` | WhatsApp message ID |
| `conversation_id` | `str` | `bot_id:jid` |
| `participant_jid` | `str\|None` | 群聊发言人 |
| `raw` | `dict\|None` | 原始 WhatsApp 消息字典 |

### Action 类型

| Action | 说明 |
|--------|------|
| `NoAction` | 无操作 |
| `ReplyAction(conversation_id, text)` | 发送回复 |
| `EscalateAction(conversation_id, reason, priority)` | 升级到人工 |
| `ConfigAction(bot_id, key, value)` | 修改配置 |

---

## 3. PluginManager

单例 `plugin_manager`，全局唯一。

```python
from agent.plugin.manager import plugin_manager

# 注册
plugin_manager.register(MyPlugin())

# 注销
plugin_manager.unregister("my_plugin")

# 查询
plugin_manager.names                 # → ["translation", "ai"]
plugin_manager.get("translation")    # → Plugin instance
```

### 生命周期

1. 注册：`server.py` lifespan 启动时
2. 收到消息：`bot_manager._on_bot_event` → `_dispatch_to_plugins` → `dispatch_on_message(ctx)`
3. 发送消息：`msg_api._execute` / `conversation_api.send_message` → `dispatch_on_before_send(ctx)`
4. bot 启动/停止：通过 `bot_manager` 调用 `dispatch_on_start` / `dispatch_on_stop`

---

## 4. PluginStore — 配置持久化

存储在 `ACCOUNT_PATH/plugin_config.db`。

### Schema

```sql
plugin_config (bot_id, plugin_name, enabled, config_json, updated_at)
```

- `bot_id = ""` → 全局默认
- `bot_id = "233541115312"` → 单 bot 覆盖

### 启用/禁用优先级

```
查询 is_enabled("translation", "bot123"):

  1. bot123 有记录 → 返回该记录 enabled
  2. 全局 (bot_id="") 有记录 → 返回该记录 enabled
  3. 都没有 → 默认 True
```

### 配置优先级

```
get_config("translation", "bot123"):

  1. 全局配置作为 base
  2. bot123 的配置覆盖 base
  → 返回合并后的 dict
```

---

## 5. 插件 API

### 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/plugin` | 列出所有已注册插件及全局启用状态 |
| `GET` | `/api/plugin/{name}/config?bot_id=` | 获取配置（可选 bot_id 查单 bot） |
| `PUT` | `/api/plugin/{name}/config?bot_id=` | 更新配置（空 bot_id = 全局） |
| `PUT` | `/api/plugin/{name}/enabled` | 启用/禁用 |

### 示例

```bash
# 查看所有插件
curl -s localhost:8000/api/plugin | python -m json.tool

# 查看 translation 全局配置
curl -s localhost:8000/api/plugin/translation/config | python -m json.tool

# 设置 AI 插件全局禁用
curl -s -X PUT localhost:8000/api/plugin/ai/enabled \
  -H 'Content-Type: application/json' \
  -d '{"enabled": false}'

# 单独为 bot123 启用 AI
curl -s -X PUT localhost:8000/api/plugin/ai/enabled \
  -H 'Content-Type: application/json' \
  -d '{"enabled": true, "bot_id": "bot123"}'

# 设置全局 translation 配置
curl -s -X PUT localhost:8000/api/plugin/translation/config \
  -H 'Content-Type: application/json' \
  -d '{"work_lang":"zh","target_lang":"es"}'

# 单独为 bot456 设置不同的目标语言
curl -s -X PUT 'localhost:8000/api/plugin/translation/config?bot_id=bot456' \
  -H 'Content-Type: application/json' \
  -d '{"target_lang":"pt"}'
```

### 响应格式

```json
// GET /api/plugin
[
  {"name":"ai","version":"0.1.0","description":"LLM-powered...","enabled":true},
  {"name":"translation","version":"0.1.0","description":"Auto-translate...","enabled":true}
]

// GET/PUT /api/plugin/translation/config?bot_id=bot123
{
  "plugin": "translation",
  "bot_id": "bot123",
  "enabled": true,
  "config": {"work_lang":"zh","target_lang":"es","provider":"google"}
}

// PUT /api/plugin/translation/enabled
{
  "plugin": "translation",
  "bot_id": "",
  "enabled": false
}
```

---

## 6. Translation Plugin

### 核心逻辑

```
incoming:
  customer sends [target_lang] text → auto-detect → translate to [work_lang]
  → store as TRANSLATION note in conversation

outgoing:
  operator sends [work_lang] text via API → on_before_send hook
  → translate to [target_lang] → send bilingual: "原文\n\n[翻译]"
```

### 配置项

| 键 | 默认 | 说明 |
|----|------|------|
| `work_lang` | `""` | 操作员工作语言 (e.g. `"zh"`) |
| `target_lang` | `""` | 客户目标语言 (e.g. `"es"`) |
| `provider` | `"google"` | `"google"` (免费) 或 `"llm"` 或 `"anthropic"` |
| `llm_api_key` | `""` | LLM API Key (仅 provider=llm) |
| `llm_api_url` | `"https://api.openai.com/v1"` | LLM 端点 |
| `llm_model` | `"gpt-4o-mini"` | LLM 模型名 |

### 自动启用

`on_start` 检测到 `work_lang != target_lang` 且都有值时，自动设置 `enabled = true`。

### 使用步骤

```bash
# 1. 设置工作语言和目标语言
curl -s -X PUT localhost:8000/api/plugin/translation/config \
  -H 'Content-Type: application/json' \
  -d '{"work_lang":"zh","target_lang":"es"}'

# 2. 确认已启用
curl -s localhost:8000/api/plugin/translation/config | python -m json.tool

# 3. 发一条西班牙语消息到 bot
# → 会话中会出现 TRANSLATION note 显示中文翻译

# 4. 通过 API 发中文消息
# → 对方收到 "中文\n\n[Spanish translation]"

# 5. 切换到 LLM 翻译
curl -s -X PUT localhost:8000/api/plugin/translation/config \
  -H 'Content-Type: application/json' \
  -d '{"provider":"llm","llm_api_key":"sk-xxx","llm_model":"gpt-4o-mini"}'

# 6. 切换到 Anthropic 原生翻译
curl -s -X PUT localhost:8000/api/plugin/translation/config \
  -H 'Content-Type: application/json' \
  -d '{"provider":"anthropic","llm_api_key":"sk-ant-xxx","llm_model":"claude-3-haiku-20240307"}'

# 7. 禁用（恢复原始行为）
curl -s -X PUT localhost:8000/api/plugin/translation/enabled \
  -H 'Content-Type: application/json' \
  -d '{"enabled":false}'
```

### 翻译提供者

| 提供者 | API Key | 说明 |
|--------|---------|------|
| Google | 无需 | translate-pa.googleapis.com JSON API，fallback HTML scrape |
| LLM | 需要 | OpenAI 兼容端点，支持任何 `/chat/completions` API |
| Anthropic | 需要 | 原生 Anthropic Messages API (`/v1/messages`) |

### 国内 LLM 兼容表

以下厂商的 API 均为 OpenAI `/chat/completions` 兼容格式，`provider` 设为 `"llm"`，配置对应的 `llm_api_url` 和 `llm_model` 即可：

| 厂商 | `llm_api_url` | `llm_model` (推荐) |
|------|---------------|---------------------|
| GLM (智谱) | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Qwen (阿里) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-turbo` |
| Moonshot (月之暗面) | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| ZhipuGLM (旧版) | `https://open.bigmodel.cn/api/paas/v4` | `glm-4` |
| Minimax | `https://api.minimax.chat/v1` | `abab6.5s-chat` |
| 零一万物 | `https://api.lingyiwanwu.com/v1` | `yi-34b-chat` |
| SiliconFlow | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` |

---

## 7. AI Plugin

### 核心逻辑

```
incoming message
     │
     ├─ 关键词匹配 escalate_keywords? → ESCALATE (省 LLM 调用)
     │
     └─ LLM 分类 →
           REPLY: <回复文字> → ReplyAction
           ESCALATE: <原因>  → EscalateAction
           IGNORE            → NoAction
```

### 配置项

| 键 | 默认 | 说明 |
|----|------|------|
| `provider` | `"openai"` | `"openai"` \| `"anthropic"` |
| `api_key` | `""` | **必填**，LLM API Key |
| `api_url` | `"https://api.openai.com/v1"` | OpenAI 兼容端点 |
| `model` | `"gpt-4o-mini"` | 模型名 |
| `system_prompt` | 内置默认 | 自定义系统提示词 |
| `escalate_keywords` | `[]` | 触发关键词列表，命中直接升级 |

### 使用步骤

```bash
# 1. 配置 API key（必填）
curl -s -X PUT localhost:8000/api/plugin/ai/config \
  -H 'Content-Type: application/json' \
  -d '{"api_key":"sk-xxx","model":"gpt-4o-mini"}'

# 2. 启用
curl -s -X PUT localhost:8000/api/plugin/ai/enabled \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true}'

# 3. 设关键词升级（可选）
curl -s -X PUT localhost:8000/api/plugin/ai/config \
  -H 'Content-Type: application/json' \
  -d '{"escalate_keywords":["退款","投诉","经理"]}'

# 4. 发送消息测试 → LLM 自动分类并回复/升级
```

### LLM 响应格式

LLM 必须返回以下三种之一：

```
REPLY: 您好，我们的产品保修期为两年...
ESCALATE: 退款需人工审核
IGNORE
```

LLM 响应不匹配以上格式时，默认升级到人工处理（安全兜底）。

---

## 8. 如何创建新插件

### 最小示例

```python
# agent/plugin/myplugin/__init__.py
from agent.plugin import Plugin, MessageContext, Action, NoAction

class MyPlugin(Plugin):
    name = "myplugin"
    version = "0.1.0"
    description = "My custom plugin"

    async def on_message(self, ctx: MessageContext) -> list[Action]:
        if "urgent" in (ctx.content or "").lower():
            from agent.plugin import EscalateAction
            return [EscalateAction(
                conversation_id=ctx.conversation_id,
                reason="Keyword 'urgent' detected",
                priority="high",
            )]
        return [NoAction()]
```

### 注册

在 `agent/server.py` lifespan 中注册：

```python
from agent.plugin.myplugin import MyPlugin
plugin_manager.register(MyPlugin())
```

### 内置钩子

| 钩子 | 触发时机 | 用途 |
|------|----------|------|
| `on_message(ctx)` | 收到入站消息 | 自动回复、升级、翻译 |
| `on_before_send(ctx)` | 消息发送到 WhatsApp 之前 | 翻译、内容过滤 |
| `on_start(bot_id)` | bot 启动 | 初始化配置、自动启用 |
| `on_stop(bot_id)` | bot 停止 | 清理 |

---

## 8. 当前状态

| 插件 | 状态 | 说明 |
|------|------|------|
| `ai` | 完整 | LLM 消息分类 → REPLY / ESCALATE / IGNORE |
| `translation` | 完整 | Google + LLM 翻译，incoming/outgoing 双向 |

**20/20 测试通过。**
