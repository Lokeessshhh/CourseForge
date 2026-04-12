"""
Smoke test for OpenRouter Qwen 3.5 9B with reasoning disabled.
Tests that the model returns content properly without using tokens for reasoning.
"""
import os
import sys
import django
import httpx
import json
import time

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.conf import settings


def test_openrouter_reasoning_disabled():
    """Test Qwen 3.5 9B with reasoning disabled."""
    
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    if not api_key:
        print(" OPENROUTER_API_KEY not set in settings")
        return False
    
    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    model = getattr(settings, 'OPENROUTER_LLM_MODEL', 'qwen/qwen-2.5-7b-instruct')
    
    print(f"\n{'='*60}")
    print(f" OpenRouter Qwen 3.5 9B Smoke Test")
    print(f"{'='*60}")
    print(f"Model: {model}")
    print(f"Base URL: {base_url}")
    print(f"Reasoning: DISABLED")
    print(f"{'='*60}\n")
    
    # Test payload with reasoning disabled
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Be concise."
            },
            {
                "role": "user",
                "content": "What is Python? Answer in exactly one sentence."
            }
        ],
        "max_tokens": 100,
        "temperature": 0.3,
        "reasoning": {"enabled": False}  # Disable reasoning
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/your-org/ai-course-generator",
        "X-Title": "AI Course Generator",
        "Content-Type": "application/json",
    }
    
    print(f" Sending request to OpenRouter...")
    start_time = time.time()
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            
            elapsed = time.time() - start_time
            
            if response.status_code != 200:
                print(f" HTTP {response.status_code}: {response.text}")
                return False
            
            data = response.json()
            
            # Check response structure
            if 'choices' not in data or not data['choices']:
                print(f" Missing 'choices' in response")
                print(f"Response: {json.dumps(data, indent=2)[:500]}")
                return False
            
            choice = data['choices'][0]
            message = choice.get('message', {})
            content = message.get('content')
            reasoning = message.get('reasoning')
            finish_reason = choice.get('finish_reason')
            
            print(f"\n Results:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Time: {elapsed:.2f}s")
            print(f"   Finish Reason: {finish_reason}")
            print(f"   Has Content: {bool(content)}")
            print(f"   Has Reasoning: {bool(reasoning)}")
            
            if content:
                print(f"\n Content received ({len(content)} chars):")
                print(f"   {content[:200]}...")
            else:
                print(f"\n No content received!")
                if reasoning:
                    print(f"   Reasoning field: {str(reasoning)[:200]}...")
                print(f"   Full response: {json.dumps(data, indent=2)[:500]}")
                return False
            
            # Check usage
            usage = data.get('usage', {})
            print(f"\n Token Usage:")
            print(f"   Prompt: {usage.get('prompt_tokens', 'N/A')}")
            print(f"   Completion: {usage.get('completion_tokens', 'N/A')}")
            print(f"   Total: {usage.get('total_tokens', 'N/A')}")
            
            if finish_reason == 'length':
                print(f"\n  Warning: Hit token limit (finish_reason: length)")
                return False
            
            print(f"\n{'='*60}")
            print(f" TEST PASSED: Model working correctly without reasoning")
            print(f"{'='*60}\n")
            return True
            
    except httpx.TimeoutException:
        print(f" Request timed out after {time.time() - start_time:.2f}s")
        return False
    except Exception as e:
        print(f" Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_qwen_client_class():
    """Test the actual QwenClient class used in the app."""
    print(f"\n{'='*60}")
    print(f" Testing QwenClient Class")
    print(f"{'='*60}\n")
    
    try:
        from services.llm.qwen_client import QwenClient
        
        client = QwenClient(max_tokens=100, temperature=0.3)
        
        print(f" Testing QwenClient.generate()...")
        start_time = time.time()
        
        result = client.generate(
            prompt="What is Django? Answer in one sentence.",
            max_tokens=100,
        )
        
        elapsed = time.time() - start_time
        
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Result type: {type(result)}")
        
        if result.startswith("[Error:"):
            print(f" Error: {result}")
            return False
        
        if not result or len(result.strip()) == 0:
            print(f" Empty result")
            return False
        
        print(f"\n QwenClient returned content ({len(result)} chars):")
        print(f"   {result[:200]}...")
        print(f"\n{'='*60}")
        print(f" QwenClient TEST PASSED")
        print(f"{'='*60}\n")
        return True
        
    except Exception as e:
        print(f" QwenClient test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Test 1: Direct API call
    test1_passed = test_openrouter_reasoning_disabled()
    
    # Test 2: QwenClient class
    test2_passed = test_qwen_client_class()
    
    # Summary
    print(f"\n{'='*60}")
    print(f" TEST SUMMARY")
    print(f"{'='*60}")
    print(f"   Direct API Test: {' PASSED' if test1_passed else ' FAILED'}")
    print(f"   QwenClient Test: {' PASSED' if test2_passed else ' FAILED'}")
    print(f"{'='*60}\n")
    
    sys.exit(0 if (test1_passed and test2_passed) else 1)
