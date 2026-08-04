class RelayAttributes:

    '''
    <relay attribute_padding="1" peer_pid="1" self_pid="0" uuid="xFGXvPWtAHmVOUPO">
            <participant pid="1" jid="248846345101511@lid" />
            <token id="0">
                0x090f01f5413f044f16427eeeb5220f6a8a10cb971a90845afe68ae136b147388ac423ddbf039bb19650a11e88b903280512d72f96163952a499553fb245f419f7294c46df6139efd84e1ae1dbb7eeddda19565f599b7b86b9ecdb099023ecb879cf91b3678cffd3b3a57e8e9af0617ec9cc4bbf35dab40d4d54e375e0bb4d574f40f4833d51dfacb52784446b9fb0e85206eb1da491f22a31e3860b334f8c9504c1f75525023bb884c24e59fadb455673aa2d88b6a20e16492edebaa9a9528
            </token>
            <token id="1">
                0x090f01f59fc43c9275ee4542f112875c018921c2c2ae122fc36b6996ba26d2eeb0bf97d29dac8fef1e668fd27b77bc2a4f77dae04bc133bdcc5ef45d0d47d02486bd092642ee74442b0d4d3e32a05ec718a8326ebc85763c2bee2bc63f9221e27a5620da5fd4ccb5e3ac5786cf7973511009ee0384ffa6fa1c6cba3a42e3053fac3c5f3a5ae19c7650c875ae4a0080ecae88a5fd354c4520c96267bcebd48ac97047f53320018db047f1ae457ddf05479fd8a5627648dc495ca31ac5a3ad10
            </token>
            <token id="2">
                0x090f01f5c375aa61d2f54c285decb517357e62ae584ef3555e444571bfcdc833af5a3ba5c91f6d64e6734bbf787b091142bb61a29169b1417a3eb9c679410d3ee128459e75c5155ff0de095a47987e7f4706cdcc3f941b29c030c745f928a106faabb74d8caa856a89385a40487bce04d40d8ad904baa49844791ab34f80cf14c40e5a17af32cd30161aea20dea438a4971db026c267b4e0316a198408537c4ea81355c2bed0eb7449003ea06969e6a014213456105af1c06477c685af008c
            </token>
            <key>
                0x65685830677774726e636265386a514e714175614b513d3d
            </key>
            <te2 protocol="1" relay_name="nrt6c01" c2r_rtt="55" relay_id="0" token_id="1">
                0x39902d360d96
            </te2>
            <te2 protocol="1" relay_name="nrt6c01" c2r_rtt="55" relay_id="0" token_id="1">
                0x2a032880f3130136faceb00c000000b10d96
            </te2>
            <te2 relay_name="nrt6c01" c2r_rtt="55" relay_id="0" token_id="1">
                0x39902d360d96
            </te2>
            <te2 relay_name="nrt6c01" c2r_rtt="55" relay_id="0" token_id="1">
                0x2a032880f3130136faceb00c000000b10d96
            </te2>
            <te2 protocol="1" relay_name="itm1c01" c2r_rtt="53" relay_id="1" token_id="0">
                0x9df0d13e0d96
            </te2>
            <te2 protocol="1" relay_name="itm1c01" c2r_rtt="53" relay_id="1" token_id="0">
                0x2a032880f24e00c0faceb00c000001770d96
            </te2>
            <te2 relay_name="itm1c01" c2r_rtt="53" relay_id="1" token_id="0">
                0x9df0d13e0d96
            </te2>
            <te2 relay_name="itm1c01" c2r_rtt="53" relay_id="1" token_id="0">
                0x2a032880f24e00c0faceb00c000001770d96
            </te2>
            <te2 protocol="1" relay_name="sin2c01" c2r_rtt="36" relay_id="2" token_id="2">
                0x399099360d96
            </te2>
            <te2 protocol="1" relay_name="sin2c01" c2r_rtt="36" relay_id="2" token_id="2">
                0x2a032880f34c0136faceb00c000000b10d96
            </te2>
            <te2 relay_name="sin2c01" c2r_rtt="36" relay_id="2" token_id="2">
                0x399099360d96
            </te2>
            <te2 relay_name="sin2c01" c2r_rtt="36" relay_id="2" token_id="2">
                0x2a032880f34c0136faceb00c000000b10d96
            </te2>
            <hbh_key>
                0x434f396139715162534b7a554c685673724b723837444a6762514a32384671472b4c5757382b5a63
            </hbh_key>
        </relay>    
    '''    

    def __init__(self, participants=None, tokenList=None, key=None, te2List=None, hbhKey=None,
                 uuid=None, self_pid=None, peer_pid=None, callCreator=None, callId=None, attributePadding=None) -> None:
        self.participants = participants or []  # list[dict] with pid+JID
        self.tokenList = tokenList
        self.key = key
        self.te2List = te2List
        self.hbhKey = hbhKey
        self.uuid = uuid
        self.self_pid = self_pid
        self.peer_pid = peer_pid
        self.callCreator = callCreator
        self.callId = callId
        self.attributePadding = attributePadding

    def __repr__(self):
        return (
            f"RelayAttributes(participants={self.participants}, tokenList={self.tokenList}, key={self.key}, te2List={self.te2List}, hbhKey={self.hbhKey})"
        )

    @staticmethod
    def parse_from_node(node):       #node的根节点就是relay

        # Relay node attributes (uuid, self_pid, peer_pid)
        uuid = node.getAttributeValue("uuid")
        self_pid = node.getAttributeValue("self_pid")
        peer_pid = node.getAttributeValue("peer_pid")
        self_pid = int(self_pid) if self_pid is not None else None
        peer_pid = int(peer_pid) if peer_pid is not None else None
        callCreator = node.getAttributeValue("call-creator")
        callId = node.getAttributeValue("call-id")
        attributePadding = node.getAttributeValue("attribute_padding")


        participantNode = node.getChild("participant")
        participant = None  # legacy single participant
        participants = []
        for pn in node.getAllChildren("participant"):
            p_info = {
                "pid": pn.getAttributeValue("pid"),
                "jid": pn.getAttributeValue("jid")
            }
            participants.append(p_info)
            if participant is None:
                participant = p_info  # legacy compat

        tokenList = []
        for tokenNode in node.getAllChildren("token"):
            tokenList.append({
                "id": tokenNode.getAttributeValue("id"),
                "value": tokenNode.getData()
            })
        
        keyNode = node.getChild("key")
        key = keyNode.getData() if keyNode is not None else None

        te2List = []
        for te2Node in node.getAllChildren("te2"):
            te2List.append({
                "protocol": te2Node.getAttributeValue("protocol"),
                "relay_name": te2Node.getAttributeValue("relay_name"),
                "c2r_rtt": te2Node.getAttributeValue("c2r_rtt"),
                "relay_id": te2Node.getAttributeValue("relay_id"),
                "token_id": te2Node.getAttributeValue("token_id"),
                "value": te2Node.getData()
            })

        hbhKeyNode = node.getChild("hbh_key")
        hbhKey = hbhKeyNode.getData() if hbhKeyNode is not None else None

        return RelayAttributes(
            participants=participants,
            tokenList=tokenList,
            key=key,
            te2List=te2List,
            hbhKey=hbhKey,
            uuid=uuid,
            self_pid=self_pid,
            peer_pid=peer_pid,
            callCreator=callCreator,
            callId=callId,
            attributePadding=attributePadding
        )

    def to_relay_data(self) -> dict:
        """Convert to the relay_data dict expected by CallSession.

        Mirrors the structure produced by voip.signaling.parser.parse_relay_node(),
        but works directly from the already-parsed RelayAttributes — no need
        to re-serialize to ProtocolTreeNode.
        """
        import base64
        from voip.signaling import RelayEndpoint

        # Build token lookup: id → (base64_str, raw_bytes)
        tokens: dict[str, str] = {}
        raw_tokens: dict[str, bytes] = {}
        for tok in self.tokenList or []:
            tid = tok.get("id", "0")
            raw = tok.get("value", b"")
            raw_tokens[tid] = raw
            tokens[tid] = base64.b64encode(raw).decode()

        relay_key = self.key.decode("latin-1") if self.key else ""

        # Build participant_jids list and ParticipantInfo list
        participant_jids = []
        participant_infos = []
        for p in self.participants or []:
            jid = p.get("jid", "")
            pid_str = p.get("pid", "0")
            pid = int(pid_str) if pid_str is not None else 0
            if jid and jid not in participant_jids:
                participant_jids.append(jid)
                participant_infos.append({"pid": pid, "jid": jid})

        # Build RelayEndpoint list from te2 entries
        relays: list[RelayEndpoint] = []
        for te2 in self.te2List or []:
            data = te2.get("value", b"")
            if not data or len(data) != 6:
                # Only 6-byte entries are IPv4:port pairs.
                # 18-byte entries (e.g. 0x2a032880f3500136...) are NOT
                # relay addresses — they contain a different binary format
                # and should be skipped.
                continue
            ip = ".".join(str(b) for b in data[0:4])
            port = (data[4] << 8) | data[5]
            if not ip or port <= 0:
                continue

            token_id = te2.get("token_id", "0")
            protocol = te2.get("protocol")
            protocol = int(protocol) if protocol is not None else 0
            c2r_rtt = te2.get("c2r_rtt")
            c2r_rtt = int(c2r_rtt) if c2r_rtt is not None else None

            relays.append(RelayEndpoint(
                ip=ip,
                port=port,
                token=tokens.get(token_id, ""),
                raw_token=raw_tokens.get(token_id, b""),
                key=relay_key,
                relay_id=int(te2.get("relay_id", 0) or 0),
                relay_name=te2.get("relay_name", ""),
                protocol=protocol,
                c2r_rtt=c2r_rtt,
                address_bytes=bytes(data),
            ))

        # Sort by client-to-relay RTT (lowest first), nil RTT at end
        relays.sort(key=lambda ep: (ep.c2r_rtt is None, ep.c2r_rtt or 0))

        return {
            "relays": relays,
            "participant_jids": participant_jids,
            "participants": participant_infos,
            "uuid": self.uuid or "",
            "self_pid": self.self_pid,
            "peer_pid": self.peer_pid,
            "hbh_key": self.hbhKey,
            "rte": "",  # rte comes from offer ack, not from relay node
        }