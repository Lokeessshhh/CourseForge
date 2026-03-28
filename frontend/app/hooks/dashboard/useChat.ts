import { useState, useEffect, useRef, useCallback } from 'react';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: { title: string; page?: number }[];
  timestamp: Date;
}

interface UseChatOptions {
  courseId?: string;
  weekId?: number;
  dayId?: number;
}

export function useChat({ courseId, weekId, dayId }: UseChatOptions = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/chat/';
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        
        // Send context if available
        if (courseId) {
          ws.send(JSON.stringify({
            type: 'set_context',
            courseId,
            weekId,
            dayId,
          }));
        }
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'stream_start') {
          setIsStreaming(true);
          setMessages((prev) => [
            ...prev,
            {
              id: data.messageId,
              role: 'assistant',
              content: '',
              sources: [],
              timestamp: new Date(),
            },
          ]);
        } else if (data.type === 'stream_token') {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === data.messageId
                ? { ...msg, content: msg.content + data.token }
                : msg
            )
          );
        } else if (data.type === 'stream_end') {
          setIsStreaming(false);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === data.messageId
                ? { ...msg, sources: data.sources || [] }
                : msg
            )
          );
        } else if (data.type === 'error') {
          setError(data.message);
          setIsStreaming(false);
        }
      };

      ws.onerror = () => {
        setError('WebSocket connection error');
        setIsConnected(false);
      };

      ws.onclose = () => {
        setIsConnected(false);
      };
    } catch {
      setError('Failed to connect to chat');
    }
  }, [courseId, weekId, dayId]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);

  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('Not connected to chat');
      return;
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);

    wsRef.current.send(JSON.stringify({
      type: 'message',
      content,
    }));
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    isStreaming,
    isConnected,
    error,
    sendMessage,
    clearMessages,
    reconnect: connect,
  };
}
