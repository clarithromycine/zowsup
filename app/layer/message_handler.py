"""MessageHandler — incoming message parsing, callback, and ack delivery."""

import base64
import logging
import random
import time

from proto import zowsup_pb2
from core.layers.protocol_messages.protocolentities import *
from core.layers.protocol_media.protocolentities import *
from core.layers.protocol_messages.protocolentities.attributes import ProtocolAttributes
from common.utils import Utils

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handles all incoming message processing: parsing, callback dispatch, and acks."""

    def __init__(self, layer):
        """
        Args:
            layer: ZowBotLayer instance
        """
        self.layer = layer

    # ── Public protocol callback handlers ──────────────────────────────────

    async def on_message(self, messageProtocolEntity):
        """Handle incoming message: parse, callback, ack."""

        # Parse JID and LID from message entity
        jid, lid = self._parse_jid_and_lid(messageProtocolEntity)

        if self.layer.db:
            notify = messageProtocolEntity.getNotify()
            # Don't store a JID-formatted string as a display name
            contact_name = None if (notify and "@" in notify) else notify
            self.layer.db._store.updateContact(jid=jid, lid=lid, name=contact_name)

        # Parse message type and extract text
        msg_type, text = self._parse_message_type(messageProtocolEntity)

        if isinstance(messageProtocolEntity, ProtocolMessageProtocolEntity):
            protocol_attrs = None
            if messageProtocolEntity.message_attributes is not None:
                protocol_attrs = messageProtocolEntity.message_attributes.protocol

            if protocol_attrs is not None and protocol_attrs.type in (
                ProtocolAttributes.TYPE_HISTORY_SYNC_NOTIFICATION,
                ProtocolAttributes.TYPE_APP_STATE_SYNC_KEY_SHARE,
            ):
                # History sync — send hist_sync ack and return (no callback, no READ)
                await self.layer.toLower(messageProtocolEntity.ack(histSync=True))
                return

            elif messageProtocolEntity.category == "peer":
                # App state sync key share — ack and return
                await self.layer.toLower(messageProtocolEntity.ack(peerMsg=True))
                return

        # Normalize canonical JID: LID for 1v1 chats, group JID for groups
        from_full = messageProtocolEntity.getFrom(True, noDevice=True)
        _pn_jid = messageProtocolEntity.getSenderPn()
        _sender_lid = messageProtocolEntity.getSenderLid()

        if from_full.endswith("@lid"):
            canonical_jid = from_full                              # xxx@lid
            pn_jid = _pn_jid                                       # phone@s.whatsapp.net or None
        elif from_full.endswith("@g.us"):
            canonical_jid = from_full                              # xxx@g.us
            pn_jid = None
        elif _sender_lid:
            canonical_jid = _sender_lid                            # xxx@lid
            pn_jid = from_full                                     # phone@s.whatsapp.net
        else:
            canonical_jid = from_full                              # fallback
            pn_jid = None

        participant_full = messageProtocolEntity.getParticipant(True)


        message={
            "type": msg_type,
            "text": text,
            "notify": messageProtocolEntity.getNotify() or None,
            "msgId": messageProtocolEntity.getId(),
            "from": messageProtocolEntity.getFrom(False),
            "from_full": from_full,
            "to": messageProtocolEntity.getTo(False) if messageProtocolEntity.fromme else self.layer.bot.botId,
            "participant": participant_full,
            "lid": canonical_jid,
            "pn_jid": pn_jid,
            "timestamp": messageProtocolEntity.getTimestamp() or int(time.time()),
            "raw": base64.b64encode(messageProtocolEntity.raw),
            **self._extract_media_attrs(messageProtocolEntity, msg_type),
        }
        # Feed media caption into translation pipeline by setting it as text
        if message.get("media_caption"):
            message["text"] = message["media_caption"]

        self.layer.callback(
            message=message,
        )

        # Send message acks with probabilistic behavior
        await self._async_send_message_acks(messageProtocolEntity)

    async def on_receipt(self, entity):
        """Handle message receipt (read/delivered notifications)."""

        target_full = entity.getFrom(True)

        if entity.getParticipant() is not None:
            num = entity.getFrom(False) + "::" + entity.getParticipant(False)
        else:
            num = entity.getFrom(False)

        if entity.getType() == "read":
            self.layer.callback(
                messageStatus={
                    "msgId": entity.getId(),
                    "target": num,
                    "target_full": target_full,
                    "status": zowsup_pb2.MessageStatus.READ,
                }
            )
        else:
            self.layer.callback(
                messageStatus={
                    "msgId": entity.getId(),
                    "target": num,
                    "target_full": target_full,
                    "status": zowsup_pb2.MessageStatus.DELIVERED,
                }
            )

        await self.layer.toLower(entity.ack())

    def on_ack(self, entity):
        """Handle message ack (sent confirmation / error)."""

        if entity.getId() in self.layer.ackQueue:

            target_full = entity._from if entity._from else None
            ack_ts = entity.timestamp

            if entity._from is not None:
                num = entity._from[0 : entity._from.rfind("@", 0)]
            else:
                num = "UNKNOWN"

            if entity.getError() is None:
                self.layer.callback(
                    messageStatus={
                        "msgId": entity.getId(),
                        "target": num,
                        "target_full": target_full,
                        "status": zowsup_pb2.MessageStatus.SENT,
                        "timestamp": ack_ts,
                    }
                )
            else:
                self.layer.callback(
                    messageStatus={
                        "msgId": entity.getId(),
                        "target": num,
                        "target_full": target_full,
                        "status": zowsup_pb2.MessageStatus.ERROR,
                        "errorCode": entity.getError(),
                        "timestamp": ack_ts,
                    }
                )

            self.layer.ackQueue.pop(self.layer.ackQueue.index(entity.getId()))

    # ── Internal helpers ────────────────────────────────────────────────────

    async def _async_send_message_acks(self, messageProtocolEntity):
        """Send message acknowledgments (received + read) with probabilistic behavior."""

        if random.random() < 0.8:
            await self.layer.toLower(messageProtocolEntity.ack())
        else:
            logger.debug(
                "Not sending received ack for message {}".format(messageProtocolEntity.getId())
            )

        # Always send read ack
        await self.layer.toLower(messageProtocolEntity.ack(read=True))

    def _parse_jid_and_lid(self, messageProtocolEntity):
        """Parse and extract JID and LID from messageProtocolEntity.

        Returns:
            tuple: (jid, lid)
        """
        _from = messageProtocolEntity.getFrom()

        if _from.endswith("lid"):
            lid = Utils.normalize_jid(_from)
            jid = messageProtocolEntity.getSenderPn()
            # sender_pn is sometimes absent; fall back to notify if it looks like a JID
            if not jid:
                notify = messageProtocolEntity.getNotify()
                if notify and notify.endswith("s.whatsapp.net"):
                    jid = notify
        else:
            jid = Utils.normalize_jid(_from)
            lid = messageProtocolEntity.getSenderLid()

        return jid, lid

    def _parse_message_type(self, messageProtocolEntity):
        """Parse message type and extract text from messageProtocolEntity.

        Returns:
            tuple: (message_type, text)
        """
        msg_type = messageProtocolEntity.getType()
        edit = messageProtocolEntity.getEdit()

        if edit=="7":
            if isinstance(messageProtocolEntity, ProtocolMessageProtocolEntity) and messageProtocolEntity.type==ProtocolAttributes.TYPE_REVOKE:
                return zowsup_pb2.MessageType.REVOKE, str(messageProtocolEntity.key.id)

        message_type = zowsup_pb2.MessageType.UNKNOWN_MEDIA
        text = ""

        if msg_type == "text":
            message_type = zowsup_pb2.MessageType.TEXT
            if isinstance(messageProtocolEntity, TextMessageProtocolEntity):
                text = messageProtocolEntity.getBody()
            elif isinstance(messageProtocolEntity, ExtendedTextMessageProtocolEntity):
                text = messageProtocolEntity.text
                if (
                    messageProtocolEntity.context_info is not None
                    and messageProtocolEntity.context_info.external_ad_reply is not None
                ):
                    message_type = zowsup_pb2.MessageType.AD

        elif msg_type == "reaction":
            self.layer.logger.debug("reaction entity: {}".format(messageProtocolEntity))
            if isinstance(messageProtocolEntity, ReactionMessageProtocolEntity):
                message_type = zowsup_pb2.MessageType.REACTION
                text = (
                    messageProtocolEntity.message_attributes.reaction.text
                    if messageProtocolEntity.message_attributes.reaction
                    else "[reaction]"
                )

        elif msg_type == "poll":
            message_type = zowsup_pb2.MessageType.POLL
            if isinstance(messageProtocolEntity, PollCreationMessageProtocolEntity):
                text = "[poll create]"
            elif isinstance(messageProtocolEntity, PollUpdateMessageProtocolEntity):
                text = "[poll update]"

        elif msg_type == "media":
            if isinstance(messageProtocolEntity, ExtendedTextMediaMessageProtocolEntity):
                message_type = zowsup_pb2.MessageType.URL
                text = messageProtocolEntity.text
                if (
                    messageProtocolEntity.media_specific_attributes.context_info is not None
                    and messageProtocolEntity.media_specific_attributes.context_info.external_ad_reply
                    is not None
                ):
                    message_type = zowsup_pb2.MessageType.AD
                    text = (
                        messageProtocolEntity.media_specific_attributes.context_info.external_ad_reply.source_url
                    )

            elif isinstance(
                messageProtocolEntity, ImageDownloadableMediaMessageProtocolEntity
            ):
                message_type = zowsup_pb2.MessageType.IMAGE
                text = "[image]"

            elif isinstance(
                messageProtocolEntity, VideoDownloadableMediaMessageProtocolEntity
            ):
                message_type = zowsup_pb2.MessageType.VIDEO
                text = "[video]"

            elif isinstance(
                messageProtocolEntity, AudioDownloadableMediaMessageProtocolEntity
            ):
                message_type = zowsup_pb2.MessageType.AUDIO
                text = "[audio]"

            elif isinstance(
                messageProtocolEntity, DocumentDownloadableMediaMessageProtocolEntity
            ):
                message_type = zowsup_pb2.MessageType.DOCUMENT
                text = "[document]"

            elif isinstance(
                messageProtocolEntity, StickerDownloadableMediaMessageProtocolEntity
            ):
                message_type = zowsup_pb2.MessageType.STICKER
                text = "[sticker]"

            else:
                message_type = zowsup_pb2.MessageType.UNKNOWN_MEDIA
                text = "[media]"

        return message_type, text

    @staticmethod
    def _extract_media_attrs(entity, msg_type: int) -> dict:
        """Extract media metadata (url, mimetype, media_key, file_name, file_length)
        for media messages.
        
        DOCUMENT/IMAGE/VIDEO/AUDIO:   entity.downloadablemedia_specific_attributes
        STICKER is excluded.
        """
        if msg_type not in (zowsup_pb2.MessageType.IMAGE, zowsup_pb2.MessageType.VIDEO,
                             zowsup_pb2.MessageType.AUDIO, zowsup_pb2.MessageType.DOCUMENT):
            return {}
        try:
            import base64 as _b64
            # DOCUMENT uses a different attribute path

            attrs = getattr(entity, 'downloadablemedia_specific_attributes', None)


            if attrs is None:
                return {}
                        

            url = attrs.url 
            mime = attrs.mimetype 
            key = attrs.media_key

            print(url)
            print(mime)
            print(key)
            fname = getattr(entity, 'file_name', '') or ''
            flen = getattr(entity, 'file_length', None) or 0
            caption = getattr(entity, 'caption', '') or ''
            return {
                "media_url": url,
                "media_mimetype": mime,
                "media_key": _b64.b64encode(key).decode() if key else "",
                "media_file_name": fname,
                "media_file_length": flen,
                "media_caption": caption,
            }
        except Exception:
            return {}
