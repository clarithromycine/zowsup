"""Analyze real device CANONICAL exchange request structure."""
import json

# Real device CANONICAL exchange request (id='063') - decoded from hex in the dump
real_query = {
    "queryId": "25727187160203620",
    "variables": {
        "input": {
            "encrypted_password": {
                "algorithm": "rsa2048",
                "data": "be2rcEBOnfGEpirvrc6offgYjRfhWVJcsL/Lq7Wn9RXPGgLEHmWiPGZS4zLIAP0/wzWgjL2sxWWI\ndSggabsTEuCJjRGt9NIiWk7SI0uEVfFomyyvLSf7WckaMZEmVWKJuMj//IHDallz5vakWrmMGNKC\nCgv9RxmqGVkG8R5ionxI17dWVZUHQR7KPdSfX9JGXkYIzrOcyGPuIo4NJZs+wTA1jFkDQxYwnV5i\nq0V1r2T6AMs13zT9KXAl2nDEhF8paZh99LldnsBEudZFyzoRwDZ8RqR+Xq3fvdAPhIPQlG4JvZr+\nhfx6uAkqJzzqCn3ZitqElTr6xoH87XlJUFvclrGMOleFbA0bc3BVmRr/mVyF9udmYlVXUvmMjEGT\nZXqNI1T1AQjYnDFwQ2FwjeYSKSJ+fviiO0bRoYpKiqHQiEQMgldKB9lEfcCp9P4k6OoxBRFwZKPv\nWVz5C2vv9BQBMGGPW5vKFpE+cWAU0jyqjgFXpQGkukvuXbLt5ETMN0oB5/XwcAb+YFq5KDOXicMT\noT/YF6kDJNA3OwUEhSTXP5PDKUl7U1V6HlFsERwMVNqZQgiXIUeZ+5FawiAqlT8Mhu2vSzHtHSeN\nO0+cBnpnE5qURpak8pvB4XK/ns86ixLyQ5ZiFmzf/N9szCIMLvCySpi32idJlqXgSSTH3hzTwWsI\nH6wj+tuf6pTK2mKrBXyV+u59SiT9ReqI56NOvRohL3HZAY0h4hTzaPxKYdatIk1EfCuHrYj8PCGD\ndDlDCmR/b0ivu5So5jRRy7Sb8Q+e7Nhfc77EMPsng4M+FnUjeMJD/vqrQh/gqkMOsif3fQ8riO25\n1vwz9SBhYkCeyS3pb1GJ1s88hYrki28Y5ZjGbA2VPmRhlrFPt2097rRmg4BaHrMP28EHrGttBpZV\nt6vHPVRRZRNOzwzr4urLb3wPiARn9y6a/meLVRKnpWlcartIqOmljPb10XT+xfs/gPWDPOLOwJlx\nmZB9GGyaGQq0Ki/g/IqjccA5DFBPGPCnjS7kQrLKJwHB1WApO96uGmGNcYVXhfW++TN1fFy45+az\nV5jQqvzPFpxpxzC5TgV/9BuDJVbvM80nvvwV00swQJcvHpSUchcw1a5DGmH+q3m3P7xs0abCnkTy\nkCSbfypOwmq7LRuWcIeZbmTG3k8t/7PlaPSNrD3/C4tYS69Qeddtc2SBulxHKkc66QH/CG/1J8uf\nCEX/8vydK9BPSFx1aCnpfztKvxUKmq4DF/jd/2Gx46RwNrO01sBbNdYmASSp7RAMIQp6wK4X8GDg\nrxoE3cYWCelWelinL/UBFZSQ61NfCO9heRwegGNwuknukzsp4TcJpi222TOMl0CIv7LxL29lH6CU\na0g=\n",
                "key": "XFbZhk1siTGM9/FluWIhIWt6dkuPQwHZKIu3C5VaNbZk1dfBm6BL1XohVxsBs7ITWyuQWSl09BfZ\n+cee1IZefx6mazSP6g1dMxhZ1PtUqxQaOCMzlGxKUjlhBRdYhJfdgGkBoenVoKIWGAmXhG5ASHdW\nL+UXWz68naLRsypQi1UrkeM4+sCP0g3XgbFTXKZUuIS73ePPh4B6GlESj03mz75nu026PC7qowzq\nLnb6w1Sgy8YokO9xvZNsITAwT5baucWrgP2Ymsfl5UiupdAC9hLfzU54PduSqZfEOyQYmbFjPWVt\nL7Bl3U7cOnm5WCrZ6OLvRU3cAUOuwuQHqHfHZw==\n",
                "nonce": "CIakjFN1hjoYI9rf\n",
                "tag": "6hwj0gidSFuPWugUntsDyg==\n"
            },
            "nonce": "IDIGlnzEB3wQtmXk8STFVPPpKeUKDnPBK3QPAssEMkm9TTb1TupW4Yna1YFHhZJK",
            "registration_trace_id": "af2af285-7633-4966-be49-30a46226fa48",
            "request_id": "4c45b313-b325-4002-b379-53799fa6a287",
            "use_case": "CANONICAL"
        }
    }
}

print("=" * 60)
print("Real Device CANONICAL Exchange Request (id=063)")
print("=" * 60)
print()

ep = real_query["variables"]["input"]["encrypted_password"]
print("encrypted_password keys order:", list(ep.keys()))
print()
for k, v in ep.items():
    if k != "algorithm":
        last_chars = repr(v[-3:])
        print(f"  {k}: len={len(v)}, ends with: {last_chars}, has n: {v.endswith(chr(10))}")

print()
print(f"nonce value length: {len(real_query['variables']['input']['nonce'])}")
print(f"nonce value: {real_query['variables']['input']['nonce'][:40]}...")
print()

# Show the outer input keys order
inp = real_query["variables"]["input"]
print("input keys order:", list(inp.keys()))
print()

# Serialize to JSON and show
json_str = json.dumps(real_query, indent=2, ensure_ascii=False)
print("Full JSON (first 500 chars):")
print(json_str[:500])
print("...")
print("Full JSON (last 300 chars):")
print(json_str[-300:])
