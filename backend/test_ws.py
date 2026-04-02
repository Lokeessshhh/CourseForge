"""
Simple WebSocket test script.
Run this to test if WebSocket endpoint is accessible.
"""
import asyncio
import websockets

async def test_websocket():
    uri = "ws://localhost:8000/ws/chat/"
    print(f"Testing WebSocket connection to {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection successful!")
            
            # Send a test message
            await websocket.send('{"message": "test"}')
            print("📩 Sent test message")
            
            # Wait for response
            response = await websocket.recv()
            print(f"📨 Received: {response}")
            
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
