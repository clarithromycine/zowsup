"""MessageHandler — incoming message parsing, callback, and ack delivery."""

from asyncio import Protocol
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

            # ── PeerDataOperation REQUEST: companion asks primary for waFbid ──
            if protocol_attrs is not None and protocol_attrs.type == \
                    ProtocolAttributes.TYPE_PEER_DATA_OPERATION_REQUEST_MESSAGE:
                raw = messageProtocolEntity.raw
                sender = messageProtocolEntity.getFrom(True)
                self.layer.logger.info(
                    f"PeerDataOp REQUEST from {sender}, raw_len={len(raw) if raw else 0}"
                )
                if raw:
                    from proto.e2e_pb2 import Message
                    m = Message()
                    m.ParseFromString(raw)
                    req = m.protocol_message.peer_data_operation_request_message
                    # Log which fields ARE set (skip repeated fields)
                    fields = []
                    for field_desc in req.DESCRIPTOR.fields:
                        try:
                            if req.HasField(field_desc.name):
                                fields.append(field_desc.name)
                        except (AttributeError, ValueError):
                            # upb protobuf: repeated fields or missing label attr
                            pass
                    self.layer.logger.info(f"PeerDataOp REQUEST fields: {fields}")
                    if req.HasField("companionCanonicalUserNonceFetchRequest"):
                        # Companion device is requesting waFbid — respond with our fbid
                        fbid = getattr(self.layer, '_fbid', None) or ""
                        if hasattr(self.layer, 'pairing') and self.layer.pairing.wa_fbid:
                            fbid = self.layer.pairing.wa_fbid
                        self.layer.logger.info(
                            f"PeerDataOp REQUEST: companion requests waFbid, "
                            f"responding with fbid={fbid}"
                        )
                        await self._respond_peer_data_op(
                            messageProtocolEntity, fbid,
                        )
                        return
                    else:
                        # Empty/minimal request — companion is signaling readiness.
                        # The PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE with
                        # nonce + waFbid is sent proactively by md.link right after
                        # WWWGetNonceForCompanionDevice succeeds (NOT in response to
                        # this REQUEST). Here we only ACK the companion's request.
                        self.layer.logger.info(
                            f"PeerDataOp REQUEST: minimal/empty, ACKing only "
                            f"(nonce response sent proactively by md.link)"
                        )
                        await self.layer.toLower(messageProtocolEntity.ack(peerMsg=True))
                        return
                await self.layer.toLower(messageProtocolEntity.ack(peerMsg=True))
                return

            # ── PeerDataOperation response: extract waFbid (legacy, may still be useful) ──
            if protocol_attrs is not None and protocol_attrs.type == \
                    ProtocolAttributes.TYPE_PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE:
                raw = messageProtocolEntity.raw
                if raw:
                    from proto.e2e_pb2 import Message
                    m = Message()
                    m.ParseFromString(raw)
                    if m.protocol_message.peer_data_operation_request_response_message.peerDataOperationResult:
                        result = m.protocol_message.peer_data_operation_request_response_message.peerDataOperationResult[0]
                        if result.HasField("companionCanonicalUserNonceFetchRequestResponse"):
                            resp = result.companionCanonicalUserNonceFetchRequestResponse
                            if resp.waFbid:
                                self.layer.logger.info(f"Got waFbid from CompanionCanonicalUserNonceFetch: {resp.waFbid}")
                                self.layer.pairing.wa_fbid = str(resp.waFbid)
                                self.layer._fbid = self.layer.pairing.wa_fbid
                await self.layer.toLower(messageProtocolEntity.ack(peerMsg=True))

            if messageProtocolEntity.category == "peer":
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

    async def _respond_peer_data_op(self, request_entity, fbid: str, nonce: str = ""):
        """Respond to PeerDataOperationRequest (companion requests waFbid + nonce).

        Sends TYPE_PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE with
        CompanionCanonicalUserNonceFetchResponse containing waFbid and nonce.
        """
        from proto.e2e_pb2 import Message as ProtoMessage
        from core.layers.protocol_messages.protocolentities import (
            ProtocolMessageProtocolEntity,
        )
        from core.layers.protocol_messages.protocolentities.attributes import (
            ProtocolAttributes, MessageMetaAttributes,
        )

        companion_jid = request_entity.getFrom(True)
        # Also check layer for stored companion_nonce
        if not nonce:
            nonce = getattr(self.layer, '_companion_nonce', None) or ""
        self.layer.logger.info(
            f"_respond_peer_data_op: sending fbid={fbid}, nonce={nonce[:20] if nonce else ''}... to {companion_jid}"
        )

        # Build the response proto
        resp_msg = ProtoMessage()
        resp_msg.protocol_message.type = ProtoMessage.ProtocolMessage.PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE
        pr = resp_msg.protocol_message.peer_data_operation_request_response_message

        result = pr.peerDataOperationResult.add()
        resp = result.companionCanonicalUserNonceFetchRequestResponse
        if fbid:
            resp.waFbid = fbid
        if nonce:
            resp.nonce = nonce


        # Wrap in ProtocolMessageProtocolEntity and send
        resp_entity = ProtocolMessageProtocolEntity(
            protocol_attr=ProtocolAttributes(
                type=ProtocolAttributes.TYPE_PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE,
                peer_data_operation_request_response_message=pr,
            ),
            message_meta_attributes=MessageMetaAttributes(
                recipient=companion_jid, category="peer"
            ),
        )
        # Set raw protobuf bytes
        resp_entity.raw = resp_msg.SerializeToString()
        await self.layer.toLower(resp_entity)

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
