"""
Smoke test for vLLM embedding server
Tests embedding endpoint at http://<IP>:8001
"""

import httpx

BASE_URL = "http://165.245.139.32:8000"   # change if needed

print("=== Embedding Smoke Test ===")
print(f"Target: {BASE_URL}")

# 1. Health check
print("\n1. Health check...")
try:
    resp = httpx.get(f"{BASE_URL}/health", timeout=5.0)
    print(f"   Health status: {resp.status_code} - OK")
except Exception as e:
    print(f"   Health check FAILED: {e}")

# 2. Model info
print("\n2. Model info...")
try:
    resp = httpx.get(f"{BASE_URL}/v1/models", timeout=5.0)
    if resp.status_code == 200:
        models = resp.json()
        print(f"   Available models: {[m['id'] for m in models.get('data', [])]}")
    else:
        print(f"   Models endpoint returned: {resp.status_code}")
except Exception as e:
    print(f"   Model info FAILED: {e}")

# 3. Embedding test
print("\n3. Embedding test...")
try:
    payload = {
        "model": "qwen3-embedding",
        "input": "hello world"
    }

    resp = httpx.post(f"{BASE_URL}/v1/embeddings", json=payload, timeout=30.0)

    if resp.status_code == 200:
        data = resp.json()
        embedding = data.get("data", [{}])[0].get("embedding", [])
        print(f"   Embedding SUCCESS: vector length = {len(embedding)}")
    else:
        print(f"   Embedding FAILED: {resp.status_code} - {resp.text[:200]}")

except Exception as e:
    print(f"   Embedding FAILED: {e}")

print("\n=== Smoke test complete ===")