"""
Audio pipeline — connects media codecs with network transport.

TxPipeline:  PCM float samples → Opus encode → RTP packetize → SRTP encrypt → relay send
RxPipeline:  relay receive → STUN filter → SRTP decrypt → Opus decode → PCM callback

Reference: WaCalls internal/voip/call/callmanager_media.go (FeedCapturedPCM, sendOpusFrameLocked, onRelayData)
"""

import struct
import logging
from collections import deque
from array import array
from typing import Optional, Callable

from .codec import Codec, NullCodec, MLowCodec
from .rtp import RtpPacket, RtpSession, RtpHeader
from .srtp import SrtpContext, SrtpError
from ..transport.stun import is_stun_packet

log = logging.getLogger(__name__)

# WhatsApp RTP extension
RTP_EXTENSION_PROFILE = 0xDEBE  # WhatsApp WARP ext profile (real device uses 0xDEBE)

# WhatsApp primary device audio frame types (relay transport)
# WhatsApp primary device audio frame types (relay transport)
# byte0 = 0x90 (V=2, X=1, CC=0); byte1 = marker<<7 | PT
# PT=120 (0x78) = MLow/Opus audio; PT=121 (0x79) = accepted on receive
# marker=0 → 0x9078/0x9079; marker=1 → 0x90F8/0x90F9 (speech onset)
FRAME_TYPE_AUDIO   = 0x9078  # PT=120, marker=0 — SEND this
FRAME_TYPE_AUDIO_2 = 0x9079  # PT=121, marker=0 — receive only
FRAME_TYPE_AUDIO_3 = 0x8FCE  # PT=121, marker=0 — relay-forwarded (secondary device)
FRAME_TYPE_AUDIO_M = 0x90F8  # PT=120, marker=1 — speech onset (receive)
FRAME_TYPE_AUDIO_M2 = 0x90F9 # PT=121, marker=1 — speech onset (receive)
# 0x81CA / 0x81C8 are RTCP (V=2, P=0, RC=1, PT=202/200) — NOT audio frames

# RTP extension lengths (bytes 14-15 of WARP frame = ext length in 32-bit words)
EXT_LEN_SPEECH  = 0   # 0 words → 16B header (no extension data)
EXT_LEN_DTX     = 1   # 1 word  → 20B header (DTX: 0x30010000)
EXT_LEN_PRIMING = 2   # 2 words → 24B header (priming: 8B setup on first frame)

FRAME_HEADER_SPEECH  = 16    # 12B RTP + 4B ext header (ext_len=0)
FRAME_HEADER_DTX     = 20    # 12B RTP + 4B ext header + 4B ext data
FRAME_HEADER_PRIMING = 24    # 12B RTP + 4B ext header + 8B ext data
FRAME_HEADER_SHORT   = 8     # 8FCE: type + seq + ssrc

# Recognized audio frame types (all have V=2, X=1, CC=0)
_FRAME_HEADERS = {
    FRAME_TYPE_AUDIO:    True,   # 9078 — PT=120, marker=0
    FRAME_TYPE_AUDIO_2:  True,   # 9079 — PT=121, marker=0
    FRAME_TYPE_AUDIO_3:  True,   # 8FCE — PT=121, marker=0
    FRAME_TYPE_AUDIO_M:  True,   # 90F8 — PT=120, marker=1 (speech onset)
    FRAME_TYPE_AUDIO_M2: True,   # 90F9 — PT=121, marker=1 (speech onset)
}


def _is_dtx_payload(opus_data: bytes) -> bool:
    """WACRG DTX classifier (rtp-framing REL-05) + MLow DTX detection.

    Opus DTX patterns: 1B (0x10/0x88/0x90), 2-15B (0x08.. || 0x0A), ≤6B (0x30..)
    MLow DTX:    bit7=0, short frames (≤6B) — WhatsApp sends 1-2B comfort noise
    """
    if not opus_data:
        return False
    b0 = opus_data[0]
    n = len(opus_data)
    # MLow DTX: short frames with no CELT bit
    if (b0 & 0x80) == 0x00 and n <= 6:
        return True
    # Opus single-byte DTX values
    if n == 1 and b0 in (0x10, 0x88, 0x90):
        return True
    # Opus 2–15 bytes with (first_byte & 0xf8) == 0x08 or first_byte == 0x0a
    if 2 <= n <= 15:
        if (b0 & 0xF8) == 0x08 or b0 == 0x0A:
            return True
    # Opus ≤6 bytes with (first_byte & 0xf0) == 0x30
    if n <= 6 and (b0 & 0xF0) == 0x30:
        return True
    return False


def _detect_frame(data: bytes):
    """Return (srtp_payload, ssrc, seq, ts) if *data* is a known audio frame, else None.

    WARP frame layout (0x9078/0x9079/0x90F8/0x90F9):
        bytes 0-1:   V=2,X=1,CC=0 | marker<<7 | PT (120 or 121)
        bytes 2-3:   sequence number (BE)
        bytes 4-7:   timestamp (BE)
        bytes 8-11:  SSRC (BE)
        bytes 12-13: extension profile (0xDEBE)
        bytes 14-15: extension length in 32-bit words (0=speech, 1=DTX, 2=priming)
        bytes 16+:   extension data (ext_len * 4 bytes), then encrypted payload + MI(4B)

    8FCE frame layout (relay-forwarded, secondary/companion device):
        bytes 0-1:   frame type (0x8FCE)
        bytes 2-3:   sequence number (BE)
        bytes 4-7:   SSRC (BE)
        bytes 8+:    HBH-encrypted(E2E_header + E2E_payload) + WARP_MI(4B)
    """
    if len(data) < 8:
        return None
    frame_type = (data[0] << 8) | data[1]
    if frame_type not in _FRAME_HEADERS:
        return None

    # 8FCE uses short 8-byte header (no RTP extension fields)
    if frame_type == FRAME_TYPE_AUDIO_3:
        if len(data) < 8:
            return None
        seq = (data[2] << 8) | data[3]
        ssrc = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7]
        ts = 0  # 8FCE doesn't carry RTP timestamp
        hdr_size = 8
        if len(data) <= hdr_size:
            return None
        return (data[hdr_size:], ssrc, seq, ts)

    # Standard WARP frames: RTP header + extension
    if len(data) < 16:
        return None
    ext_words = (data[14] << 8) | data[15]
    hdr_size = 16 + ext_words * 4  # 12B RTP + 4B ext header + ext data
    ssrc = (data[8] << 24) | (data[9] << 16) | (data[10] << 8) | data[11]
    seq = (data[2] << 8) | data[3]
    ts = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7]

    if len(data) <= hdr_size:
        return None
    return (data[hdr_size:], ssrc, seq, ts)


def _depack_split_red(p: bytes) -> list[bytes]:
    """Depacketize a SplitRED (0x86) MLow payload into sub-frames.

    Structure: [RED header bytes]* + [main marker byte] + [RED data]* + [main data]
    Each RED header: 1B (high bit set, lower 7 bits = timecode) + 1B (size)
    Main marker: 1B (high bit clear, lower 7 bits = timecode)

    Returns list of frame bytes (RED frames first, main frame last).
    Returns None if parsing fails OR if payload is a bare frame (no RED headers).
    """
    n = len(p)
    if n == 0:
        return None
    red_blocks = []  # (timecode, size)
    cur = 0
    rem = n
    while True:
        if rem == 0:
            return None
        b0 = p[cur]
        if b0 < 0x80:  # high bit clear — main marker or bare frame TOC
            if rem <= 1:
                return None
            break
        if rem <= 2:
            return None
        size = p[cur + 1]
        if size + 2 >= rem:
            return None
        red_blocks.append((b0 & 0x7f, size))
        cur += 2
        rem -= size + 2

    # Bare frame: no RED headers before the high-bit-clear byte.
    # This is NOT a RED-encapsulated frame — the byte is the frame TOC.
    if not red_blocks:
        return None

    cur += 1  # consume main marker byte
    frames = []
    for _code, size in red_blocks:
        frames.append(bytes(p[cur:cur + size]))
        cur += size
    main_size = rem - 1
    frames.append(bytes(p[cur:cur + main_size]))
    return frames


def _pack_split_red(main_frame: bytes, redundant_frames: list[bytes],
                    red_timecode: int = 6, main_timecode: int = 0) -> bytes:
    """Pack a SplitRED (0x86) MLow payload from sub-frames.

    Inverse of _depack_split_red. Encodes redundant frames (older frames
    for FEC) followed by the main frame.

    Structure (matching real device):
      [RED_header × N] + [main_marker] + [RED_data × N] + [main_data]
      RED_header: 1B (0x80 | red_timecode) + 1B (size)
      main_marker: 1B (main_timecode, high bit clear) — NOT the main frame TOC
      main_data: complete main frame (TOC + body)

    Args:
        main_frame: current frame bytes (TOC + body)
        redundant_frames: previous frames to include as redundancy (oldest first)
        red_timecode: 7-bit timecode for redundant frames (default 6, matching real device)
        main_timecode: 7-bit timecode for main marker (default 0, matching real device)

    Returns:
        Packed RED payload starting with 0x80+ (high bit set)
    """
    rtc = red_timecode & 0x7F
    mtc = main_timecode & 0x7F
    out = bytearray()

    # RED headers (one per redundant frame)
    for red_frame in redundant_frames:
        if not red_frame:
            continue
        out.append(0x80 | rtc)  # high bit set = RED header
        out.append(len(red_frame))

    # Main marker (high bit clear — separate from main frame TOC)
    out.append(mtc)

    # RED data blocks (redundant frame payloads)
    for red_frame in redundant_frames:
        if not red_frame:
            continue
        out.extend(red_frame)

    # Main frame data (complete frame: TOC + body)
    out.extend(main_frame)

    return bytes(out)


class TxPipeline:
    """
    Audio send pipeline: PCM → Opus → RTP → SRTP → Relay.

    Accumulates incoming PCM samples, encodes full frames, and sends them
    encrypted to the relay manager.

    Usage:
        tx = TxPipeline(codec, rtp_session, srtp_ctx, relay)
        tx.feed_pcm([0.1, -0.2, ...])  # feed arbitrarily-sized chunks

        # Silence keepalive (call periodically when no audio input)
        tx.send_silence_frame()
    """

    def __init__(
        self,
        codec: Codec,
        rtp_session: RtpSession,
        srtp_ctx: SrtpContext,
        relay,  # RelayManager (lazy import to avoid circular deps)
        hbh_ctx = None,   # optional HBH SrtpContext
        sframe_ctx = None,  # optional SFrameContext (AES-128-GCM)
        p2p_callback = None,  # optional callable(bytes) for P2P TX
    ):
        self._codec = codec
        self._rtp = rtp_session
        self._srtp = srtp_ctx
        self._relay = relay
        self._hbh = hbh_ctx
        self._sframe = sframe_ctx
        self._p2p_callback = p2p_callback

        self._frame_size = codec.frame_size()
        # Use deque for O(1) popleft and array('f') for bulk-append
        self._pcm_buf: deque[float] = deque()
        self._first_packet_log = True
        # SplitRED TX: keep last N encoded frames for redundancy
        self._red_redundancy = 1  # number of redundant frames to include
        self._red_history: list[bytes] = []  # recent encoded frames (oldest first)

    @property
    def pending_samples(self) -> int:
        """Number of PCM samples waiting in the accumulation buffer."""
        return len(self._pcm_buf)

    def feed_pcm(self, pcm: list[float]) -> None:
        """
        Feed PCM float samples into the pipeline.

        When enough samples accumulate to fill a codec frame,
        they are automatically encoded and sent.

        Uses deque + pre-allocated array for zero-copy frame extraction.

        Args:
            pcm: Float samples in [-1.0, 1.0], any length
        """
        self._pcm_buf.extend(pcm)

        while len(self._pcm_buf) >= self._frame_size:
            # O(1) popleft from deque — no list slice copy
            frame = [self._pcm_buf.popleft() for _ in range(self._frame_size)]
            self._encode_and_send(frame)

    def send_silence_frame(self) -> None:
        """Send a SID (Silence Insertion Descriptor) frame.

        SID frames have TOC bit7=1. The peer's MLow decoder sees SID=1 and
        returns silence directly — it does NOT call decodeActiveFrame, so
        there is no CELP synthesis state change and no audible click.

        Real device uses TOC=0x90: SID=1, VAD=0, Active=0, SR=16k, FrameMs=60
        """
        sid_payload = b"\x90"  # 1-byte SID frame (TOC only, no body)
        self._encode_and_send_raw(sid_payload)

    def _encode_and_send_raw(self, raw_mlow: bytes) -> None:
        """Send a pre-encoded MLow frame (bypass encoder)."""
        is_dtx = _is_dtx_payload(raw_mlow)
        if not getattr(self, '_first_packet_sent', False):
            frame_type = 0x90F8  # marker=1
        else:
            frame_type = FRAME_TYPE_AUDIO  # 0x9078
        encrypted_payload = self._srtp.protect_payload_only(
            raw_mlow, self._rtp.ssrc, self._rtp.sequence_number)
        frame = self._build_warp_frame(encrypted_payload, is_dtx, frame_type)
        self._relay.broadcast(frame)
        # Also send to P2P if callback is set
        if self._p2p_callback:
            try:
                self._p2p_callback(frame)
            except Exception:
                pass
        self._first_packet_sent = True
        self._rtp.sequence_number += 1
        self._rtp.timestamp += 960

    def _encode_and_send(self, pcm: list[float]) -> None:
        """Encode one frame → E2E encrypt payload-only → WARP frame → relay.

        WARP frame: WARP_hdr(16/20B) + [priming(8B) on first frame] + E2E_ciphertext + MI(4B).
        No inner RTP header — WARP frame header carries the RTP fields.
        
        Echo-test: if _echo_passthrough is set, uses the provided raw MLow bytes
        instead of encoding PCM.
        """
        # 1. MLow/Opus encode
        opus_data = self._codec.encode(pcm)

        # 1b. SplitRED packing — DISABLED: real device expects low-rate redundant
        # frames (config=1, TOC=0x54/0x14), not copies of the high-rate main frame.
        # Sending high-rate copies causes the peer decoder to fail silently.
        # TODO: implement low-rate re-encoding for redundant frames.
        red_payload = opus_data
        opus_data = red_payload

        # 2. DTX classification (BEFORE SFrame wrapping)
        is_dtx = _is_dtx_payload(opus_data)

        # 3. Pick frame type — PT=120 (0x9078), or 0x90F8 for first packet (marker=1)
        # WACRG REL-05: "marker bit MUST be set on the first speech packet"
        # Go reference: marker := !m.firstPacketSent
        if not getattr(self, '_first_packet_sent', False):
            frame_type = 0x90F8  # PT=120, marker=1 (speech onset)
        else:
            frame_type = FRAME_TYPE_AUDIO  # 0x9078, PT=120, marker=0

        # 4. SFrame inner encrypt — ONLY for companion device path (WebRTC SCTP)
        # Primary device raw UDP relay does NOT use SFrame on TX.

        # 5. E2E encrypt (codec) payload only
        encrypted_payload = self._srtp.protect_payload_only(
            opus_data, self._rtp.ssrc, self._rtp.sequence_number)

        # 6. Build WARP frame + MI tag
        frame = self._build_warp_frame(encrypted_payload, is_dtx, frame_type)
        self._relay.broadcast(frame)
        # Also send to P2P if callback is set
        if self._p2p_callback:
            try:
                self._p2p_callback(frame)
            except Exception:
                pass
        if self._first_packet_log:
            log.warning("FIRST TX: frame=%s", frame.hex())
            log.warning("  frame_type=0x%04x seq=%d ts=%d ssrc=0x%08x ext_words=%d",
                        frame_type, self._rtp.sequence_number, self._rtp.timestamp, self._rtp.ssrc,
                        2 if getattr(self, '_tx_priming_sent', False) and not getattr(self, '_priming_done', True) else (1 if is_dtx else 0))
            log.warning("  session_key=%s session_salt=%s", self._srtp.session_key.hex(), self._srtp.session_salt.hex())
            log.warning("  opus(%dB)=%s is_dtx=%s", len(opus_data), opus_data.hex(), is_dtx)
            log.warning("  enc_payload(%dB)=%s", len(encrypted_payload), encrypted_payload.hex())
            mi_key = getattr(self._srtp, '_warp_auth_key', None)
            log.warning("  warp_auth_key=%s roc=%d", mi_key.hex() if mi_key else "NONE", self._srtp.roc)
            log.warning("  frame_len=%d hdr=16 ext=%d payload=%d mi=4",
                        len(frame), 0 if not is_dtx else 4, len(encrypted_payload))
            self._first_packet_log = False
        self._first_packet_sent = True

        # Advance RTP session state
        self._rtp.sequence_number += 1
        self._rtp.timestamp += 960

    def _build_warp_frame(self, encrypted_payload: bytes, is_dtx: bool = False,
                           frame_type: int = FRAME_TYPE_AUDIO) -> bytes:
        """Build WARP frame: RTP_hdr(12B) + ext_hdr(4B) + [ext_data] + E2E_ciphertext + MI(4B).

        bytes 14-15 = extension length in 32-bit words:
          0 = speech (16B header)
          1 = DTX (20B header, ext=0x30010000)
          2 = priming (24B header, ext=d300004380000000) — first frame only
        MI = HMAC-SHA1(auth_key, hdr||ext||encrypted||ROC_be32)[:4]
        """
        seq = self._rtp.sequence_number
        ts = self._rtp.timestamp
        ssrc = self._rtp.ssrc

        # Determine extension: Go reference ALWAYS uses ExtensionData=nil
        # (ext_words=0) for ALL frames including DTX/silence.
        # Sending ext_words=1 for DTX shifts payload by 4B → peer decrypt fails.
        ext_words = EXT_LEN_SPEECH  # 0 — always, matching Go wacalls
        ext_data = b""

        warp_header = struct.pack(
            ">HH II HH",
            frame_type, seq & 0xFFFF,
            ts, ssrc,
            RTP_EXTENSION_PROFILE, ext_words,
        )
        mi_data = warp_header + ext_data + encrypted_payload
        mi_tag = self._srtp.compute_warp_mi(mi_data)
        return mi_data + mi_tag

    def _build_8fce(self, payload: bytes) -> bytes:
        """Build WARP relay 8FCE frame (8-byte header).

        WACRG WARP spec: type(2B BE) + seq(2B BE) + ssrc(4B BE) + payload
        """
        return struct.pack(
            ">HHI",
            FRAME_TYPE_AUDIO_3,
            self._rtp.sequence_number & 0xFFFF,
            self._rtp.ssrc & 0xFFFFFFFF,
        ) + payload


class RxPipeline:
    """
    Audio receive pipeline: Relay bytes → SRTP → RTP → Opus → PCM.

    Filters STUN packets, decrypts SRTP, validates RTP payload type,
    decodes Opus, and delivers PCM via callback.

    Usage:
        rx = RxPipeline(codec, srtp_ctx)
        rx.on_audio = lambda pcm: play(pcm)
        rx.handle_packet(data)  # returns True if audio was decoded
    """

    def __init__(
        self,
        codec: Codec,
        srtp_ctx: SrtpContext,
        sframe_ctx = None,   # optional SFrameContext
        hbh_ctx = None,      # optional HBH SrtpContext
        peer_ssrc: int = 0,  # fallback SSRC for E2E decrypt_raw
    ):
        self._codec = codec
        self._srtp = srtp_ctx
        self._sframe = sframe_ctx
        self._hbh = hbh_ctx
        self._peer_ssrc_for_decrypt = peer_ssrc

        # Callback: called with (pcm: list[float], seq: int) when audio is decoded
        self.on_audio: Optional[Callable[[list[float], int], None]] = None
        # Callback: called with raw decrypted MLow bytes (for echo test)
        self.on_raw_mlow: Optional[Callable[[bytes], None]] = None

    def handle_packet(self, data: bytes) -> bool:
        """
        Handle a received packet from the relay.

        Frame type routing:
          9079/81CA (primary):
            header(16/20B) + E2E_encrypted_opus + WARP_MI(4B)
            → strip MI → AES-CTR decrypt with frame SSRC/seq → Opus decode
          8FCE (relay-forwarded, secondary device):
            header(8B) + HBH_encrypted(E2E_header+E2E_encrypted_opus) + WARP_MI(4B)
            → HBH decrypt → E2E decrypt → Opus decode

        Returns:
            True if audio decoded, False if STUN / non-audio.
        """
        if not data:
            return False

        # ── RAW PACKET DIAGNOSTIC (entry point, every path) ──
        if not hasattr(self, '_raw_cnt'):
            self._raw_cnt = 0
        self._raw_cnt += 1
        if self._raw_cnt <= 10 or self._raw_cnt % 100 == 0:
            log.info("RX PKT #%d: len=%d first48=%s",
                     self._raw_cnt, len(data), data[:48].hex())

        if is_stun_packet(data):
            return False

        preview = data[:32].hex() if len(data) >= 4 else data.hex()
        frame_info = _detect_frame(data)
        if not frame_info:
            # Silently drop RTCP (0x81xx) — these are control packets, not audio.
            # 8FCE that fails _detect_frame at this point is genuinely unrecognized
            # (too short or malformed), not companion-device audio.
            b0 = data[0] if data else 0
            hdr = (data[0] << 8 | data[1]) if len(data) >= 2 else 0
            if b0 == 0x81:
                log.debug("RxPipeline: dropping RTCP packet 0x%04x len=%d", hdr, len(data))
            elif hdr == 0x8FCE:
                log.warning("RxPipeline: 8FCE frame too short len=%d first16=%s",
                           len(data), data[:16].hex() if len(data) >= 16 else data.hex())
            else:
                log.info("RxPipeline: UNRECOGNIZED len=%d first32=%s full=%s",
                         len(data), preview, data[:64].hex())
            return False

        srtp_data, frame_ssrc, frame_seq, frame_ts = frame_info
        frame_type = (data[0] << 8) | data[1]

        # Real device sends PT=121 (not PT=120). Accept both.
        # Go reference only accepts PT=120, but real WhatsApp uses PT=121.
        pt = data[1] & 0x7F
        if pt not in (120, 121):
            log.debug("RxPipeline: dropping PT=%d (not 120/121)", pt)
            return False

        try:
            if frame_type in (FRAME_TYPE_AUDIO, FRAME_TYPE_AUDIO_2,
                              FRAME_TYPE_AUDIO_M, FRAME_TYPE_AUDIO_M2):
                # ── WARP frame: RTP hdr + ext + E2E_encrypted_codec + MI(4B) ──
                if len(srtp_data) < 5:  # at least 1B encrypted + 4B MI
                    log.debug("RxPipeline: payload too short: %dB", len(srtp_data))
                    return False

                # Strip MI tag (last 4 bytes)
                encrypted = srtp_data[:-4]
                if not encrypted:
                    return False

                # E2E AES-CTR decrypt using WARP frame SSRC + seq
                self._srtp._update_roc(frame_seq)
                idx = self._srtp._packet_index(frame_seq)
                iv = self._srtp._generate_iv(frame_ssrc, idx)
                e2e_output = self._srtp._fast_ctr.crypt(iv, encrypted)

                # ── FULL DUMP of first 3 frames for crypto debugging ──
                if frame_seq <= 3:
                    log.warning(
                        "CRYPTO_DUMP seq=%d: enc=%s session_key=%s salt=%s "
                        "iv=%s dec=%s mi=%s",
                        frame_seq, encrypted.hex(),
                        self._srtp.session_key.hex(),
                        self._srtp.session_salt.hex(),
                        iv.hex(), e2e_output.hex(),
                        srtp_data[-4:].hex(),
                    )

                # ── SFrame inner decryption (AES-128-GCM) ──
                # Go wacalls reference does NOT use SFrame for primary device
                # relay calls. E2E SRTP output is the raw MLow payload.
                # SFrame decrypt is disabled to match Go behavior and avoid
                # any chance of GCM false-positive corrupting audio.
                codec_payload = e2e_output
                # if self._sframe:
                #     sf_result, sf_data = self._sframe.decrypt(e2e_output)
                #     if sf_result == "decrypted":
                #         codec_payload = sf_data

                # ── SplitRED depacketization ──
                # Always try RED depack (matching Go MlowDecoder.Decode).
                # If the payload is a valid RED container (>= 2 sub-frames),
                # extract the main frame (last one) for decoding.
                # If depack fails or yields < 2 frames, treat as bare frame.
                red_frames = _depack_split_red(codec_payload)
                is_red = red_frames is not None and len(red_frames) >= 2
                if is_red:
                    main_payload = red_frames[-1]
                    if frame_seq <= 5 or frame_seq % 100 == 0:
                        log.info("SplitRED depack: seq=%d red_blocks=%d "
                                 "red0_len=%d main_len=%d main_toc=0x%02x",
                                 frame_seq, len(red_frames) - 1,
                                 len(red_frames[0]), len(main_payload),
                                 main_payload[0] if main_payload else 0)
                else:
                    main_payload = codec_payload

                # ── MLow frame dump: DISABLED (disk I/O in hot path) ──
                # Re-enable for debugging: uncomment the block below.
                # if not hasattr(self, '_mlow_dump') or self._mlow_dump is None:
                #     self._mlow_dump = open("logs/rx_mlow_frames.bin", "wb")
                #     self._mlow_dump_count = 0
                # self._mlow_dump_count += 1
                # self._mlow_dump.write(struct.pack("<H", len(main_payload)))
                # self._mlow_dump.write(main_payload)

                # ── Diagnostic (every 50th frame) ──
                if frame_seq <= 3 or frame_seq % 50 == 0:
                    log.info(
                        "RxPipeline: E2E decrypt frame=%04x ssrc=%08x seq=%d "
                        "roc=%d enc_len=%d e2e_len=%d final_len=%d red=%s "
                        "iv=%s.. dec=%s",
                        frame_type, frame_ssrc, frame_seq, self._srtp.roc,
                        len(encrypted), len(e2e_output), len(main_payload),
                        is_red, iv[:8].hex(),
                        main_payload[:16].hex() if main_payload else "",
                    )

                # ── Echo test: save raw MLow before decode ──
                if self.on_raw_mlow and main_payload:
                    if len(main_payload) > 0:
                        log.warning("RX RAW_MLOW: toc=0x%02x len=%d first16=%s",
                                    main_payload[0], len(main_payload),
                                    main_payload[:16].hex())
                    self.on_raw_mlow(main_payload)
                # Decode codec payload
                # For empty payloads (packet loss), use empty decode for PLC.
                # For SID/inactive frames WITH payload, decode directly —
                # the frame contains valid comfort noise data.
                if main_payload and len(main_payload) > 0:
                    pcm = self._codec.decode(main_payload)
                else:
                    # Empty payload: PLC (packet loss concealment)
                    pcm = self._codec.decode(b'')
                
                if not pcm and len(codec_payload) > 0:
                    log.info("RxPipeline: decode FAILED for %dB raw=%s",
                             len(codec_payload), codec_payload.hex())
                if self.on_audio:
                    self.on_audio(pcm, frame_ts)
                return True

            elif frame_type == FRAME_TYPE_AUDIO_3:
                # ── 8FCE: HBH + E2E layered SRTP (companion/secondary device) ──
                pkt = None
                if self._hbh:
                    try:
                        hbh_seq = getattr(self, '_hbh_tracked_seq', frame_seq)
                        hbh_pkt = self._hbh.decrypt_raw(srtp_data, frame_ssrc, hbh_seq)
                        e2e_srtp = hbh_pkt.header.encode() + hbh_pkt.payload
                        pkt = self._srtp.unprotect(e2e_srtp)
                        log.info("RxPipeline: HBH→E2E decrypt OK! PT=%d len=%d",
                                 pkt.header.payload_type, len(pkt.payload))
                        self._hbh_tracked_seq = (hbh_pkt.header.sequence_number + 1) & 0xFFFF
                    except (SrtpError, ValueError) as e:
                        log.debug("RxPipeline: HBH decrypt failed (%s)", e)

                if pkt is None:
                    # 8FCE requires HBH decrypt first — can't do plain E2E on HBH-encrypted data
                    log.debug("RxPipeline: 8FCE no HBH or HBH decrypt failed — skip")
                    return False

                # HBH→E2E succeeded → SFrame decrypt (if present) → decode inner payload
                opus_data = pkt.payload
                if self._sframe:
                    try:
                        sf_result, sf_data = self._sframe.decrypt(opus_data)
                        if sf_result == "decrypted":
                            opus_data = sf_data
                    except Exception:
                        pass
                pcm = self._codec.decode(opus_data)
                if self.on_audio:
                    self.on_audio(pcm, frame_ts)
                return True

            else:
                log.debug("RxPipeline: unknown frame type %04x", frame_type)
                return False

        except Exception as e:
            log.error("RxPipeline decode error [%s]: %s", preview, e, exc_info=True)
            return False
