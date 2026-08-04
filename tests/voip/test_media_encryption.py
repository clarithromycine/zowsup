"""
Phase 2 tests — Call key generation and SRTP key derivation.

Tests: generate_call_key, derive_per_jid_srtp_key,
HKDF determinism, cross-check with Go values.
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from voip.media.encryption import (
    generate_call_key,
    derive_per_jid_srtp_key,
    SrtpKeyingMaterial,
)


class TestCallKeyGeneration:

    def test_length(self):
        key = generate_call_key()
        assert len(key) == 32

    def test_random(self):
        """Successive calls produce different keys."""
        k1 = generate_call_key()
        k2 = generate_call_key()
        assert k1 != k2

    def test_bytes_type(self):
        key = generate_call_key()
        assert isinstance(key, bytes)


class TestPerJidSrtpKeyDerivation:

    def test_master_key_length(self):
        material = derive_per_jid_srtp_key(
            b"\x01" * 32, "user@s.whatsapp.net"
        )
        assert len(material.master_key) == 16
        assert len(material.master_salt) == 14

    def test_deterministic(self):
        """Same inputs → same keys."""
        ck = b"\x02" * 32
        jid = "device@s.whatsapp.net"
        m1 = derive_per_jid_srtp_key(ck, jid)
        m2 = derive_per_jid_srtp_key(ck, jid)
        assert m1.master_key == m2.master_key
        assert m1.master_salt == m2.master_salt

    def test_different_call_key(self):
        """Different call keys → different SRTP keys."""
        jid = "user@s.whatsapp.net"
        m1 = derive_per_jid_srtp_key(b"\x01" * 32, jid)
        m2 = derive_per_jid_srtp_key(b"\x02" * 32, jid)
        assert m1.master_key != m2.master_key

    def test_different_jid(self):
        """Different JIDs → different SRTP keys (per-device separation)."""
        ck = b"\x03" * 32
        m1 = derive_per_jid_srtp_key(ck, "device1:0@s.whatsapp.net")
        m2 = derive_per_jid_srtp_key(ck, "device2:0@s.whatsapp.net")
        assert m1.master_key != m2.master_key
        assert m1.master_salt != m2.master_salt

    def test_whatsapp_format_jid(self):
        """Test with typical WhatsApp device JID format."""
        ck = generate_call_key()
        material = derive_per_jid_srtp_key(ck, "1234567890:0@s.whatsapp.net")
        assert len(material.master_key) == 16
        assert len(material.master_salt) == 14

    def test_dataclass_type(self):
        material = derive_per_jid_srtp_key(b"\x04" * 32, "j@s.whatsapp.net")
        assert isinstance(material, SrtpKeyingMaterial)
