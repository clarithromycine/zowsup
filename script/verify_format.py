"""Verify our fixed JSON format matches real device format."""
import json

# Simulate our fixed serialization
query_obj = {
    "variables": {
        "input": {
            "encrypted_password": {
                "algorithm": "rsa2048",
                "data": "dGVzdA==\n",
                "key": "a2V5\n",
                "nonce": "bm9uY2U=\n",
                "tag": "dGFn\n",
            },
            "nonce": "TEST_NONCE",
            "registration_trace_id": "trace-123",
            "request_id": "req-456",
            "use_case": "CANONICAL",
        }
    }
}

qid = "25727187160203620"
ordered = {"queryId": qid}
ordered.update(query_obj)

our_json = json.dumps(ordered, separators=(",", ":"))
print("=== Our fixed JSON ===")
print(our_json)
print()

# Real device format (from packet capture, with placeholder values)
print("=== Structure analysis ===")
print(f"Starts with queryId: {our_json.startswith('{\"queryId\":')}")
print(f"No spaces after colon: {\": \" not in our_json}")
print(f"No spaces after comma: {\", \" not in our_json}")
print()

# Check key order
print("encrypted_password keys:", list(query_obj["variables"]["input"]["encrypted_password"].keys()))
# Expected: ['algorithm', 'data', 'key', 'nonce', 'tag']
print("input keys:", list(query_obj["variables"]["input"].keys()))
# Expected: ['encrypted_password', 'nonce', 'registration_trace_id', 'request_id', 'use_case']
print("top-level keys:", list(ordered.keys()))
# Expected: ['queryId', 'variables']
print()

# Also verify trigger format
trigger_query = {
    "variables": {
        "input": {
            "nonce_encryption_key": "TEST_KEY\n",
            "registration_trace_id": "trace-123",
            "request_id": "req-456",
            "use_case": "CANONICAL",
        }
    }
}
ordered2 = {"queryId": "24896267680055094"}
ordered2.update(trigger_query)
trigger_json = json.dumps(ordered2, separators=(",", ":"))
print("=== Trigger JSON ===")
print(trigger_json)
print()
print("Trigger input keys:", list(trigger_query["variables"]["input"].keys()))
# Expected: ['nonce_encryption_key', 'registration_trace_id', 'request_id', 'use_case']
