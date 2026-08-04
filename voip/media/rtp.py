"""
RTP (Real-time Transport Protocol) — packet encapsulation for WhatsApp VoIP.

Implements RFC 3550 RTP header encoding/decoding with WhatsApp-specific
extensions (0xBEDE profile, PT=120 for Opus).

Reference: WaCalls internal/voip/media/rtp.go
"""

from dataclasses import dataclass, field
import random
import struct


# WhatsApp Opus payload type
RTP_PAYLOAD_TYPE_OPUS = 120

# WhatsApp custom RTP extension profile
RTP_EXTENSION_PROFILE = 0xDEBE  # WACRG spec: WARP profile

# RTP version is always 2
RTP_VERSION = 2


@dataclass
class RtpHeader:
    """RTP fixed header (12 bytes + optional CSRC + optional extension)."""
    version: int = RTP_VERSION
    padding: bool = False
    extension: bool = False
    csrc_count: int = 0
    marker: bool = False
    payload_type: int = RTP_PAYLOAD_TYPE_OPUS
    sequence_number: int = 0
    timestamp: int = 0
    ssrc: int = 0
    csrc: list[int] = field(default_factory=list)
    extension_profile: int = RTP_EXTENSION_PROFILE
    extension_data: bytes = b""

    def size(self) -> int:
        """Total header size in bytes."""
        s = 12 + len(self.csrc) * 4
        if self.extension:
            s += 4 + len(self.extension_data)
        return s

    def encode(self) -> bytes:
        """Encode RTP header to bytes."""
        buf = bytearray(self.size())

        # Byte 0: V(2) | P(1) | X(1) | CC(4)
        buf[0] = ((self.version & 0x03) << 6) \
               | (1 << 5 if self.padding else 0) \
               | (1 << 4 if self.extension else 0) \
               | (self.csrc_count & 0x0F)

        # Byte 1: M(1) | PT(7)
        buf[1] = (0x80 if self.marker else 0) | (self.payload_type & 0x7F)

        # Bytes 2-3: sequence number
        struct.pack_into("!H", buf, 2, self.sequence_number & 0xFFFF)

        # Bytes 4-7: timestamp
        struct.pack_into("!I", buf, 4, self.timestamp & 0xFFFFFFFF)

        # Bytes 8-11: SSRC
        struct.pack_into("!I", buf, 8, self.ssrc & 0xFFFFFFFF)

        # CSRC list
        offset = 12
        for c in self.csrc:
            struct.pack_into("!I", buf, offset, c & 0xFFFFFFFF)
            offset += 4

        # Extension header
        if self.extension:
            # Profile (2 bytes) + length in 32-bit words (2 bytes) + data
            ext_words = max(len(self.extension_data) // 4, 0)
            struct.pack_into("!HH", buf, offset, self.extension_profile & 0xFFFF, ext_words)
            offset += 4
            buf[offset:offset + len(self.extension_data)] = self.extension_data

        return bytes(buf)

    @classmethod
    def decode(cls, data: bytes) -> "RtpHeader":
        """Decode RTP header from bytes."""
        if len(data) < 12:
            raise ValueError(f"RTP packet too short: {len(data)} bytes (min 12)")

        version = (data[0] >> 6) & 0x03
        if version != RTP_VERSION:
            # Log but don't fail — let caller decide
            import logging
            logging.getLogger(__name__).debug(
                "RtpHeader.decode: nonstandard version=%d (expected 2), data[0:12]=%s",
                version, data[:12].hex())
            # raise ValueError(f"Invalid RTP version: {version}")

        padding = (data[0] >> 5) & 0x01 != 0
        extension = (data[0] >> 4) & 0x01 != 0
        csrc_count = data[0] & 0x0F
        marker = (data[1] >> 7) & 0x01 != 0
        payload_type = data[1] & 0x7F
        sequence_number = struct.unpack_from("!H", data, 2)[0]
        timestamp = struct.unpack_from("!I", data, 4)[0]
        ssrc = struct.unpack_from("!I", data, 8)[0]

        # CSRC
        header_size = 12 + csrc_count * 4
        if len(data) < header_size:
            raise ValueError(f"RTP data too short for CSRC list: {len(data)} < {header_size}")

        csrc = []
        offset = 12
        for _ in range(csrc_count):
            csrc.append(struct.unpack_from("!I", data, offset)[0])
            offset += 4

        # Extension
        extension_profile = RTP_EXTENSION_PROFILE
        extension_data = b""
        if extension and len(data) >= offset + 4:
            extension_profile = struct.unpack_from("!H", data, offset)[0]
            ext_words = struct.unpack_from("!H", data, offset + 2)[0]
            ext_bytes = ext_words * 4
            offset += 4
            if len(data) >= offset + ext_bytes:
                extension_data = bytes(data[offset:offset + ext_bytes])

        return cls(
            version=version,
            padding=padding,
            extension=extension,
            csrc_count=csrc_count,
            marker=marker,
            payload_type=payload_type,
            sequence_number=sequence_number,
            timestamp=timestamp,
            ssrc=ssrc,
            csrc=csrc,
            extension_profile=extension_profile,
            extension_data=extension_data,
        )


@dataclass
class RtpPacket:
    """RTP packet = header + payload."""
    header: RtpHeader
    payload: bytes

    def encode(self) -> bytes:
        """Encode full RTP packet (header + payload)."""
        return self.header.encode() + self.payload

    @classmethod
    def decode(cls, data: bytes) -> "RtpPacket":
        """Decode RTP packet from bytes."""
        header = RtpHeader.decode(data)
        payload = data[header.size():]
        return cls(header=header, payload=payload)

    @staticmethod
    def is_rtp(data: bytes) -> bool:
        """Check if data looks like an RTP packet (version=2, byte 0 MSB bits)."""
        if len(data) < 2:
            return False
        return (data[0] & 0xC0) == 0x80


class RtpSession:
    """
    Manages RTP sequence number and timestamp for a single SSRC stream.

    WhatsApp Opus defaults: 16000 Hz, 960 samples per packet (60ms).
    """

    def __init__(
        self,
        ssrc: int,
        payload_type: int = RTP_PAYLOAD_TYPE_OPUS,
        sample_rate: int = 16000,
        samples_per_packet: int = 960,
    ):
        self.ssrc = ssrc
        self.payload_type = payload_type
        self.sample_rate = sample_rate
        self.samples_per_packet = samples_per_packet

        # Go wacalls reference uses random initial seq/ts (randUint).
        # WACRG spec says "start at 1/0" but real devices accept random.
        import os as _os
        self.sequence_number = int.from_bytes(_os.urandom(2), "big") or 1
        self.timestamp = int.from_bytes(_os.urandom(4), "big")

    def create_packet(self, payload: bytes, marker: bool = False) -> RtpPacket:
        """Create an RTP packet, advancing sequence and timestamp."""
        return self.create_packet_with_duration(payload, self.samples_per_packet, marker)

    def create_packet_with_duration(
        self, payload: bytes, duration_samples: int, marker: bool = False
    ) -> RtpPacket:
        """Create an RTP packet with a specific sample duration."""
        header = RtpHeader(
            payload_type=self.payload_type,
            sequence_number=self.sequence_number,
            timestamp=self.timestamp,
            ssrc=self.ssrc,
            marker=marker,
        )
        # Advance state
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        self.timestamp = (self.timestamp + duration_samples) & 0xFFFFFFFF

        return RtpPacket(header=header, payload=payload)

    @classmethod
    def whatsapp_opus(cls, ssrc: int) -> "RtpSession":
        """Create a session with WhatsApp Opus defaults."""
        return cls(
            ssrc=ssrc,
            payload_type=RTP_PAYLOAD_TYPE_OPUS,
            sample_rate=16000,
            samples_per_packet=960,
        )
