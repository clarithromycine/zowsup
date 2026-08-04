"""
VoIP signaling builder — constructs WhatsApp <call> stanza ProtocolTreeNodes.

Provides high-level builders for accept, preaccept, transport, and other
VoIP signaling stanzas. Uses the protocol entities under the hood.

Reference: WaCalls internal/voip/signaling/signaling_build.go
"""

from typing import Optional, Any, Callable
import base64

try:
    from core.structs import ProtocolTreeNode
except ImportError:
    ProtocolTreeNode = None  # type: ignore


async def build_offer_stanza(
    call_id: str,
    call_key: bytes,
    peer_jid: str,
    own_jid: str,
    send_iq: Callable,
    db: Any = None,
    autotrust: bool = False,
    id_type: Any = None,
) -> Any:
    """Build an OfferCallProtocolEntity for an outgoing call.

    Handles:
    1. Device JID discovery (DevicesGetSyncIq)
    2. E2E session assurance (GetKeysIq)
    3. OfferCallProtocolEntity construction

    Args:
        call_id: Unique call identifier.
        call_key: 32-byte encryption key for the call.
        peer_jid: Target peer JID.
        own_jid: Our own JID (call creator).
        send_iq: Async callback(entity) → dict with {"result": response_entity, ...}.
        db: Axolotl session store.
        autotrust: Whether to auto-trust new identity keys.
        id_type: WhatsApp device identity type.
    """
    import logging
    _log = logging.getLogger(__name__)

    from core.layers.protocol_calls.protocolentities.call_offer import OfferCallProtocolEntity
    from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes

    # ── 1. Discover all device JIDs ──
    all_jids = await _discover_device_jids(peer_jid, send_iq, _log)

    # ── 2. Ensure E2E sessions for all devices ──
    await _ensure_sessions(all_jids, send_iq, db, autotrust, id_type, _log)

    # ── 3. Build offer entity ──
    offer = OfferCallProtocolEntity(
        callId=call_id,
        callCreator=own_jid,
        privacy="auto",
        destinationJids=all_jids,
        callKey=call_key,
        callMetaAttributes=CallMetaAttributes(
            id=id_type,
            recipient=all_jids[0],
        ),
        db=db,
    )
    return offer


async def _discover_device_jids(jid: str, send_iq: Callable, _log) -> list:
    """Discover all device JIDs for a given peer JID."""
    from core.layers.protocol_contacts.protocolentities import (
        DevicesGetSyncIqProtocolEntity,
        DevicesResultSyncIqProtocolEntity,
    )
    entity = DevicesGetSyncIqProtocolEntity(jids=[jid])
    resp = await send_iq(entity)
    result = resp.get("result") if isinstance(resp, dict) else resp
    if not isinstance(result, DevicesResultSyncIqProtocolEntity):
        _log.warning("VoIP offer: unexpected DevicesSync response type: %s", type(result))
        return [jid]
    jids = []
    for key, val in result.devicesDict.items():
        for dev_id in val:
            if dev_id == "0":
                jids.append(f"{key}@lid")
            else:
                jids.append(f"{key}:{dev_id}@lid")
    _log.info("VoIP offer: discovered %d device JIDs for %s", len(jids), jid)
    return jids


async def _ensure_sessions(jids: list, send_iq: Callable, db, autotrust: bool, id_type, _log):
    """Ensure E2E Axolotl sessions exist for all given JIDs."""
    if db is None:
        return
    missing = [jid for jid in jids if not db.session_exists(jid)]
    if not missing:
        return
    from core.axolotl.exceptions import UntrustedIdentityException
    from core.layers.axolotl.protocolentities.iq_key_get import GetKeysIqProtocolEntity
    from core.layers.axolotl.protocolentities.iq_keys_get_result import ResultGetKeysIqProtocolEntity

    _log.info("VoIP offer: fetching pre-keys for %d missing sessions", len(missing))
    getKeysEntity = GetKeysIqProtocolEntity(missing, _id=id_type)
    resp = await send_iq(getKeysEntity)
    resultEntity = resp.get("result") if isinstance(resp, dict) else resp
    if not isinstance(resultEntity, ResultGetKeysIqProtocolEntity):
        _log.warning("VoIP offer: unexpected GetKeys response type: %s", type(resultEntity))
        return
    resultJids = resultEntity.getJids()
    for jid in missing:
        if jid not in resultJids:
            _log.warning("VoIP offer: no pre-key for %s", jid)
            continue
        username = jid.split('@')[0]
        preKeyBundle = resultEntity.getPreKeyBundleFor(jid)
        try:
            db.create_session(username, preKeyBundle, autotrust=autotrust)
        except UntrustedIdentityException as e:
            _log.error("VoIP offer: untrusted identity for %s: %s", jid, e)


def build_accept_stanza(
    peer_jid: str,
    call_id: str,
    call_creator: str,
    call_key: bytes = None,
    db: Any = None,
    is_video: bool = False,
    te_candidates: list = None,
) -> Any:
    """
    Build a <call><accept> stanza entity.

    Real-device Frida capture (callee → caller):
    <call to="{peer_jid}" id="{stanza_id}">
      <accept call-id="{call_id}" call-creator="{call_creator}" device_class="2015">
        <audio rate="16000" enc="opus"/>
        <te priority="96">base64_ice_candidate</te>
        <te priority="32">base64_ice_candidate</te>
        <net medium="1"/>
        <encopt keygen="2"/>
        <metadata peer_abtest_bucket_id_list="..."/>
      </accept>
    </call>

    Key finding: accept does NOT carry <enc> callKey. The callKey was
    already exchanged in the offer (initiator generates it, callee
    decrypts it). Accept only carries ICE candidates and capabilities.

    Args:
        te_candidates: Optional list of {"priority": int, "data": bytes} for
                       P2P ICE candidates. priority=96 is local (host),
                       priority=32 is server-reflexive (STUN).
    """
    from core.layers.protocol_calls.protocolentities.call_accept import AcceptCallProtocolEntity
    from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes

    meta = CallMetaAttributes(
        recipient=peer_jid,
    )
    entity = AcceptCallProtocolEntity(
        callId=call_id,
        callCreator=call_creator,
        callKey=None,  # No callKey in accept — already exchanged in offer
        netMedium="2",  # Relay-only (we don't support P2P)
        callMetaAttributes=meta,
        db=None,  # No E2E encryption needed — no <enc> node
    )
    if te_candidates:
        entity.te_candidates = te_candidates
    return entity


def build_preaccept_stanza(
    peer_jid: str,
    call_id: str,
    call_creator: str,
) -> Any:
    """
    Build a <call><preaccept> stanza.

    <call to="{peer_jid}" id="{stanza_id}">
      <preaccept call-id="{call_id}" call-creator="{call_creator}">
        <audio enc="opus" rate="16000"/>
        <net medium="3"/>
        <capability ver="1">0105ff09e4bb07</capability>
        <encopt keygen="2"/>
      </preaccept>
    </call>
    """
    from core.layers.protocol_calls.protocolentities.call_preaccept import PreacceptCallProtocolEntity
    from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes

    meta = CallMetaAttributes(
        recipient=peer_jid,
    )
    entity = PreacceptCallProtocolEntity(
        callId=call_id,
        callCreator=call_creator,
        encoptKeygen="2",
        callMetaAttributes=meta,
    )
    return entity


def build_transport_stanza(
    peer_jid: str,
    call_id: str,
    call_creator: str,
    transport_message_type: str = "1",
    p2p_cand_round: str = "1",
    relay_endpoints: list = None,  # list[RelayEndpoint]
    rte: bytes = b"",               # <rte> raw binary from offer ack
    te_candidates: list = None,     # list[dict]: {"priority":int, "data":bytes}
) -> Any:
    """
    Build a <call><transport> stanza with <te> and <rte> relay tokens.

    Real primary-device format (Frida-verified):
    <call to="{peer_jid}" id="{stanza_id}">
      <transport p2p-cand-round="1" call-creator="{creator}" call-id="{id}"
                 transport-message-type="1">
        <te priority="96">base64_relay_addr</te>
        <te priority="32">base64_relay_addr</te>
        <net protocol="0" medium="2"/>
        <rte>{rte_from_offer_ack}</rte>
      </transport>
    </call>

    <te> data: 6-byte binary relay address (IP:port), base64-encoded.
    <rte> data: copied verbatim from offer ack's <rte> element.
    """
    from core.layers.protocol_calls.protocolentities.call_transport import TransportCallProtocolEntity
    from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes

    meta = CallMetaAttributes(
        recipient=peer_jid,
    )
    entity = TransportCallProtocolEntity(
        callId=call_id,
        callCreator=call_creator,
        netMedium="2",
        netProtocol="0",
        transportMessageType=transport_message_type,
        p2pCandRound=p2p_cand_round,
        rte=None,
        te_candidates=te_candidates or [],
        callMetaAttributes=meta,
    )

    import logging
    _log = logging.getLogger(__name__)
    _log.info("build_transport: rte=%s relay_eps=%d te_cands=%d",
              rte[:20].hex() if rte else "EMPTY",
              len(relay_endpoints) if relay_endpoints else 0,
              len(te_candidates) if te_candidates else 0)

    return entity


def build_transport_keepalive(
    peer_jid: str,
    call_id: str,
    call_creator: str,
) -> Any:
    """
    Build transport keepalive/reply (type=9).

    WACRG: <transport call-id=... call-creator=... transport-message-type="9">
             <net medium="2"/>   ← no protocol attribute
           </transport>
    """
    from core.layers.protocol_calls.protocolentities.call_transport import TransportCallProtocolEntity
    from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes

    meta = CallMetaAttributes(recipient=peer_jid)
    entity = TransportCallProtocolEntity(
        callId=call_id,
        callCreator=call_creator,
        netMedium="2",
        netProtocol=None,  # type 9 omits protocol
        transportMessageType="9",
        p2pCandRound="0",
        callMetaAttributes=meta,
    )
    return entity


def build_mute_v2_stanza(
    peer_jid: str,
    call_id: str,
    call_creator: str,
    muted: int = 0,
) -> Any:
    """
    Build a <call><mute_v2> stanza (mute state notification).

    Real device format (Frida-verified):
      <mute_v2 mute-state="0" call-id="..." call-creator="..."/>

    Note: mute-state is an ATTRIBUTE, NOT a child <mute> element.
    """
    from core.layers.protocol_calls.protocolentities.call_mute_v2 import MuteV2CallProtocolEntity
    from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes

    meta = CallMetaAttributes(recipient=peer_jid)
    entity = MuteV2CallProtocolEntity(
        callId=call_id,
        callCreator=call_creator,
        muteState=str(muted),
        callMetaAttributes=meta,
    )
    return entity


def build_relaylatency_stanza(
    peer_jid: str,
    call_id: str,
    call_creator: str,
    relays: list[dict],
    destination_jids: list[str] = None,
) -> Any:
    """
    Build a <call><relaylatency> stanza (WACRG SIG-15).

    <call to="{peer-jid}">   ← NO id attribute!
      <relaylatency call-id="{call-id}" call-creator="{call-creator}">
        <te latency="{0x02000000+rtt_ms}" relay_name="{name}">{addr_bytes}</te>
        <destination><to jid="..."/></destination>  <!-- optional -->
      </relaylatency>
    </call>

    Args:
        peer_jid: Target JID.
        call_id, call_creator: Call identifiers.
        relays: List of {"relay_name": str, "rtt_ms": int, "addr_bytes": bytes}.
        destination_jids: Optional list of device JIDs to target.

    Reference: wacalls internal/voip/signaling/signaling_build.go BuildRelayLatencyStanza
    """
    from core.layers.protocol_calls.protocolentities.call_relaylatency import RelayLatencyCallProtocolEntity
    from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes

    meta = CallMetaAttributes(recipient=peer_jid)

    # Build <te> entries
    te_entries = []
    seen = set()
    for r in relays:
        name = r.get("relay_name", "")
        if not name or name in seen:
            continue
        seen.add(name)
        encoded = str(0x02000000 + int(r.get("rtt_ms", 0)))
        te_entries.append({
            "latency": encoded,
            "relay_name": name,
            "data": r.get("addr_bytes", b""),
        })

    entity = RelayLatencyCallProtocolEntity(
        callId=call_id,
        callCreator=call_creator,
        te_entries=te_entries,
        destination_jids=destination_jids or [],
        callMetaAttributes=meta,
    )
    return entity
