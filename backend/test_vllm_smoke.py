"""
Smoke test for vLLM configuration and connectivity.
Tests the new vLLM server at http://129.212.187.15:8000
"""
import httpx
import json

BASE_URL = "http://134.199.201.125:8000"

print('=== vLLM Smoke Test ===')
print(f'Target: {BASE_URL}')

# 1. Health check
print('\n1. Health check...')
try:
    resp = httpx.get(f'{BASE_URL}/health', timeout=5.0)
    print(f'   Health status: {resp.status_code} - OK')
except Exception as e:
    print(f'   Health check FAILED: {e}')

# 2. Model info
print('\n2. Model info...')
try:
    resp = httpx.get(f'{BASE_URL}/v1/models', timeout=5.0)
    if resp.status_code == 200:
        models = resp.json()
        print(f'   Available models: {[m["id"] for m in models.get("data", [])]}')
    else:
        print(f'   Models endpoint returned: {resp.status_code}')
except Exception as e:
    print(f'   Model info FAILED: {e}')

# 3. Quick generation test
print('\n3. Quick generation test...')
try:
    payload = {
        "model": "qwen-coder",
        "messages": [{"role": "user", "content": "Say 'ok' and nothing else"}],
        "max_tokens": 5,
        "temperature": 0.1
    }
    resp = httpx.post(f'{BASE_URL}/v1/chat/completions', json=payload, timeout=30.0)
    if resp.status_code == 200:
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f'   Generation SUCCESS: {repr(content)}')
    else:
        print(f'   Generation FAILED: {resp.status_code} - {resp.text[:200]}')
except Exception as e:
    print(f'   Generation FAILED: {e}')

print('\n=== Smoke test complete ===')
