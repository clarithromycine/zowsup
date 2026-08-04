"""
Decode and compare device-identity from two pair-success IQs.

Usage: python script/decode_pair_success_identity.py
"""
import base64
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from proto import wa_struct_pb2


def decode_device_identity(label, device_identity_b64_or_raw):
    """Decode ADVSignedDeviceIdentityHMAC -> ADVSignedDeviceIdentity -> ADVDeviceIdentity"""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    # The device-identity in pair-success is raw bytes (not base64 in the XML)
    # But from logs it appears as base64 text in the XML
    if isinstance(device_identity_b64_or_raw, str):
        raw = base64.b64decode(device_identity_b64_or_raw)
    else:
        raw = device_identity_b64_or_raw

    print(f"  Raw length: {len(raw)} bytes")
    print(f"  Raw hex: {raw.hex()}")

    # Level 1: ADVSignedDeviceIdentityHMAC
    hmac_container = wa_struct_pb2.ADVSignedDeviceIdentityHMAC()
    try:
        hmac_container.ParseFromString(raw)
    except Exception as e:
        print(f"  ERROR parsing ADVSignedDeviceIdentityHMAC: {e}")
        # Try as GT4 (v11 format with account_type)
        gt4 = wa_struct_pb2.GT4()
        try:
            gt4.ParseFromString(raw)
            print(f"  Parsed as GT4 (v11 format)!")
            print(f"    GT4.details length: {len(gt4.details)} bytes")
            print(f"    GT4.hmac length: {len(gt4.hmac)} bytes")
            print(f"    GT4.hmac hex: {gt4.hmac.hex()}")
            print(f"    GT4.account_type: {gt4.account_type} (0=E2EE, 128=HOSTED)")

            # Level 2: GTB (v11 SignedDeviceIdentity)
            gtb = wa_struct_pb2.GTB()
            gtb.ParseFromString(gt4.details)
            print(f"\n  GTB (v11 SignedDeviceIdentity):")
            print(f"    details length: {len(gtb.details)} bytes")
            print(f"    account_signature_key length: {len(gtb.account_signature_key)} bytes")
            print(f"    account_signature_key hex: {gtb.account_signature_key.hex()}")
            print(f"    account_signature length: {len(gtb.account_signature)} bytes")
            print(f"    account_signature hex: {gtb.account_signature.hex()}")
            # Note: GTB has field 4 for account_signature, not field 3

            # Level 3: GTF (v11 DeviceIdentity)
            gtf = wa_struct_pb2.GTF()
            gtf.ParseFromString(gtb.details)
            print(f"\n  GTF (v11 DeviceIdentity):")
            print(f"    raw_id: {gtf.raw_id}")
            print(f"    timestamp: {gtf.timestamp}")
            print(f"    key_index: {gtf.key_index}")
            print(f"    device_type: {gtf.device_type} (0=E2EE, 128=HOSTED)")
            print(f"    account_type: {gtf.account_type} (0=E2EE, 128=HOSTED)")
            return
        except Exception as e2:
            print(f"  ERROR parsing as GT4: {e2}")
            return

    print(f"\n  ADVSignedDeviceIdentityHMAC:")
    print(f"    details length: {len(hmac_container.details)} bytes")
    print(f"    hmac length: {len(hmac_container.hmac)} bytes")
    print(f"    hmac hex: {hmac_container.hmac.hex()}")

    # Check if there's an account_type field (field 4 in GT4 vs field 2 in old)
    # The old ADVSignedDeviceIdentityHMAC only has details(1) and hmac(2)
    # GT4 has details(1), hmac(2), and account_type(4)

    # Level 2: ADVSignedDeviceIdentity
    signed = wa_struct_pb2.ADVSignedDeviceIdentity()
    try:
        signed.ParseFromString(hmac_container.details)
    except Exception as e:
        print(f"  ERROR parsing ADVSignedDeviceIdentity: {e}")
        return

    print(f"\n  ADVSignedDeviceIdentity:")
    print(f"    details length: {len(signed.details)} bytes")
    print(f"    account_signature_key length: {len(signed.account_signature_key)} bytes")
    print(f"    account_signature_key hex: {signed.account_signature_key.hex()}")
    print(f"    account_signature length: {len(signed.account_signature)} bytes")
    print(f"    account_signature hex: {signed.account_signature.hex()}")
    print(f"    device_signature length: {len(signed.device_signature)} bytes")

    # Level 3: ADVDeviceIdentity
    identity = wa_struct_pb2.ADVDeviceIdentity()
    try:
        identity.ParseFromString(signed.details)
    except Exception as e:
        print(f"  ERROR parsing ADVDeviceIdentity: {e}")
        return

    print(f"\n  ADVDeviceIdentity:")
    print(f"    raw_id: {identity.raw_id}")
    print(f"    timestamp: {identity.timestamp}")
    print(f"    key_index: {identity.key_index}")


# ── From logs ────────────────────────────────────────────────────────

# Case 1: 真机主端扫描真机副端android (SUCCESS)
# pair-success device-identity (base64 from XML):
success_device_identity_b64 = "CngKEgiV14ynBhCljNzSBhgMIAIoABIgxsFmzY/grmF7u2Y3U+cMNrP633PzCQ4du8AUMoeh6jUiQNxPjKqEunt56adBcspP+1xsLu2zcov9NnO4GPcNP0OdmbDxQ3zlH5MRireqzMi+739kAB6Jjb1MmKxDaihnYAgSIKN5hlpuXy3J8B9UUIOLJk3cvYc/03BDB2P0rTgGm11UIAA="

# Case 2: zowsup主端扫描真机副端android (401 ERROR)
# pair-success device-identity (base64 from XML):
error_device_identity_b64 = "CngKEgiV14ynBhCljNzSBhgMIAIoABIgxsFmzY/grmF7u2Y3U+cMNrP633PzCQ4du8AUMoeh6jUiQNxPjKqEunt56adBcspP+1xsLu2zcov9NnO4GPcNP0OdmbDxQ3zlH5MRireqzMi+739kAB6Jjb1MmKxDaihnYAgSIKN5hlpuXy3J8B9UUIOLJk3cvYc/03BDB2P0rTgGm11UIAA="

# Wait - let me re-read the logs more carefully
# The SUCCESS case (真机主端→真机副端) pair-success:
#   <device-identity>CngKEgjlrcvsBxChvtvSBhgBIAAoABIgLwGGVbv/MdieQRMvhWZ3VpGEwxN0kAXfBmrTZ67n0X0aQB5M0Q0Fim6MCGYv1CCZWYyVFfplWkW7UAphFq6YJBy6UIv54jvM7kCJJ9gX0Df3oRBrDGtu/1MT1FUsOK4NPQESIDmyE66jJVG/xjTiOuN7gxw/6UkvSYKxrUMfWgNU0Ir/GAA=</device-identity>

# The ERROR case (zowsup主端→真机副端) pair-success:
#   <device-identity>CngKEgiV14ynBhCljNzSBhgMIAIoABIgxsFmzY/grmF7u2Y3U+cMNrP633PzCQ4du8AUMoeh6jUiQNxPjKqEunt56adBcspP+1xsLu2zcov9NnO4GPcNP0OdmbDxQ3zlH5MRireqzMi+739kAB6Jjb1MmKxDaihnYAgSIKN5hlpuXy3J8B9UUIOLJk3cvYc/03BDB2P0rTgGm11UIAA=</device-identity>

print("=" * 70)
print("  COMPARISON: SUCCESS vs ERROR device-identity")
print("=" * 70)

# Correct values from logs
success_b64 = "CngKEgjlrcvsBxChvtvSBhgBIAAoABIgLwGGVbv/MdieQRMvhWZ3VpGEwxN0kAXfBmrTZ67n0X0aQB5M0Q0Fim6MCGYv1CCZWYyVFfplWkW7UAphFq6YJBy6UIv54jvM7kCJJ9gX0Df3oRBrDGtu/1MT1FUsOK4NPQESIDmyE66jJVG/xjTiOuN7gxw/6UkvSYKxrUMfWgNU0Ir/GAA="
error_b64 = "CngKEgiV14ynBhCljNzSBhgMIAIoABIgxsFmzY/grmF7u2Y3U+cMNrP633PzCQ4du8AUMoeh6jUiQNxPjKqEunt56adBcspP+1xsLu2zcov9NnO4GPcNP0OdmbDxQ3zlH5MRireqzMi+739kAB6Jjb1MmKxDaihnYAgSIKN5hlpuXy3J8B9UUIOLJk3cvYc/03BDB2P0rTgGm11UIAA="

decode_device_identity("SUCCESS CASE (真机主端→真机副端)", success_b64)
decode_device_identity("ERROR CASE (zowsup主端→真机副端, 401)", error_b64)

# Also try parsing with GT4 format (v11 with account_type)
print("\n\n" + "=" * 70)
print("  TRYING GT4 (v11) FORMAT PARSING")
print("=" * 70)

for label, b64 in [("SUCCESS", success_b64), ("ERROR (401)", error_b64)]:
    raw = base64.b64decode(b64)
    print(f"\n--- {label} ---")
    print(f"  Raw bytes ({len(raw)}): {raw.hex()}")

    # Try GT4
    gt4 = wa_struct_pb2.GT4()
    try:
        gt4.ParseFromString(raw)
        print(f"  GT4 parsed OK:")
        print(f"    details: {len(gt4.details)} bytes")
        print(f"    hmac: {len(gt4.hmac)} bytes = {gt4.hmac.hex()}")
        print(f"    account_type: {gt4.account_type}")

        gtb = wa_struct_pb2.GTB()
        gtb.ParseFromString(gt4.details)
        print(f"  GTB parsed OK:")
        print(f"    details: {len(gtb.details)} bytes")
        print(f"    account_signature_key: {len(gtb.account_signature_key)} bytes = {gtb.account_signature_key.hex()}")
        print(f"    account_signature: {len(gtb.account_signature)} bytes = {gtb.account_signature.hex()}")

        gtf = wa_struct_pb2.GTF()
        gtf.ParseFromString(gtb.details)
        print(f"  GTF parsed OK:")
        print(f"    raw_id: {gtf.raw_id}")
        print(f"    timestamp: {gtf.timestamp}")
        print(f"    key_index: {gtf.key_index}")
        print(f"    device_type: {gtf.device_type}")
        print(f"    account_type: {gtf.account_type}")
    except Exception as e:
        print(f"  GT4 parse failed: {e}")

    # Also try old format
    hmac_container = wa_struct_pb2.ADVSignedDeviceIdentityHMAC()
    try:
        hmac_container.ParseFromString(raw)
        print(f"\n  Old ADVSignedDeviceIdentityHMAC parsed OK:")
        print(f"    details: {len(hmac_container.details)} bytes")
        print(f"    hmac: {len(hmac_container.hmac)} bytes = {hmac_container.hmac.hex()}")

        signed = wa_struct_pb2.ADVSignedDeviceIdentity()
        signed.ParseFromString(hmac_container.details)
        print(f"  ADVSignedDeviceIdentity parsed OK:")
        print(f"    details: {len(signed.details)} bytes")
        print(f"    account_signature_key: {len(signed.account_signature_key)} bytes = {signed.account_signature_key.hex()}")
        print(f"    account_signature: {len(signed.account_signature)} bytes = {signed.account_signature.hex()}")
        print(f"    device_signature: {len(signed.device_signature)} bytes")

        identity = wa_struct_pb2.ADVDeviceIdentity()
        identity.ParseFromString(signed.details)
        print(f"  ADVDeviceIdentity parsed OK:")
        print(f"    raw_id: {identity.raw_id}")
        print(f"    timestamp: {identity.timestamp}")
        print(f"    key_index: {identity.key_index}")
    except Exception as e:
        print(f"  Old format parse failed: {e}")