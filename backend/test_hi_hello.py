"""
Simple test for vLLM connectivity with "hi hello" message.
Tests basic chat functionality.
"""

import httpx
import json

BASE_URL = "http://165.245.139.32:8000"

print('=== Hi Hello Test ===')
print(f'Target: {BASE_URL}')

# Simple chat completion test
print('\nSending "hi" message...')
try:
    payload = {
        "model": "qwen-coder",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "hi"}
        ],
        "max_tokens": 50,
        "temperature": 0.7
    }
    
    print('Request payload:', json.dumps(payload, indent=2))
    
    resp = httpx.post(f'{BASE_URL}/v1/chat/completions', json=payload, timeout=30.0)
    
    if resp.status_code == 200:
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f'\n SUCCESS!')
        print(f'Response: {content}')
        print(f'Tokens used: {data.get("usage", {})}')
    else:
        print(f'\n FAILED: Status {resp.status_code}')
        print(f'Response: {resp.text[:500]}')
        
except httpx.ConnectError as e:
    print(f'\n CONNECTION ERROR: {e}')
    print('   The vLLM server is not reachable at the configured URL')
    print('   Make sure the vLLM server is running and accessible')
except Exception as e:
    print(f'\n ERROR: {e}')

print('\n=== Test complete ===')
