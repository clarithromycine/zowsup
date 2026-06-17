# 头像系统实现方案

## 数据来源

### 主动获取
`contact.getavatar [jid]` 返回：
```json
{ "retcode": 0, "id": "1477322060", "type": "image", "url": "https://pps.whatsapp.net/..." }
```
- `id` (pictureId): 头像版本号，用于判断新旧
- `url`: 直接下载链接

### 被动通知
`SetPictureNotificationProtocolEntity` — 联系人换头像时推送：
```
notification type="picture" from="SENDER_JID"
  └─ <set jid="WHO_CHANGED" id="NEW_PICTURE_ID" />
```
转为事件: `{ event: 8 (CONTACT_UPDATE), detail: { target, key: "AVATAR", value: pictureId } }`

## WebSocket 事件格式

前端收到的 event 类型消息：
```json
{ "type": "event", "bot_id": "...", "timestamp": ..., "data": { "event": "8", "detail": { "target": "...", "key": "AVATAR", "value": "..." } } }
```

## 缓存策略

- 缓存目录: `{ACCOUNT_PATH}/avatars/{bot_id}_{conv_id_hash}.jpg`
- 版本判断: DB `avatar_id` 列存储 pictureId，与 getavatar 返回的 id 比较
- bot 离线时: 有缓存用缓存，无缓存 fallback 到彩色圆
- 加载策略: 惰性加载，列表页不主动触发下载

## 修改清单

| # | 文件 | 改动 |
|---|------|------|
| 1 | `conversation_store.py` | migration: `avatar_id TEXT` |
| 2 | `agent/api/avatar_api.py` | **新建** - `GET /api/avatar/{conv_id}` |
| 3 | `schemas.py` | `ConversationInfo` + `avatar_id: Optional[str]` |
| 4 | `bot_manager.py` | `_on_bot_event` 处理 CONTACT_UPDATE/AVATAR |
| 5 | `server.py` | 注册 avatar_router |
| 6 | `ConversationsTab.vue` | <img> + fallback + WebSocket 头像更新 |
