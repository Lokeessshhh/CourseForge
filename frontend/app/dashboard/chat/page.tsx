'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useParams } from 'next/navigation';
import MarkdownRenderer from '@/app/components/dashboard/MarkdownRenderer/MarkdownRenderer';
import { useChatSessions, useChat, useChatHistory, useSessionTitlePoll } from '@/app/hooks/api';
import styles from './page.module.css';

function LoadingSkeleton() {
  return (
    <div className={styles.page}>
      <div className={styles.skeletonBox} style={{ width: '280px', height: '100%' }} />
      <div className={styles.skeletonBox} style={{ flex: 1, height: '400px' }} />
    </div>
  );
}

function ErrorBox({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className={styles.page}>
      <div className={styles.errorBox}>
        <span className={styles.errorText}>✗ FAILED TO LOAD · {message}</span>
        <motion.button
          className={styles.retryBtn}
          onClick={onRetry}
          whileHover={{ x: -2, y: -2 }}
        >
          RETRY →
        </motion.button>
      </div>
    </div>
  );
}

export default function ChatPage() {
  const params = useParams();
  const courseId = params.course_id as string | undefined;

  const { sessions, isLoading: sessionsLoading, error: sessionsError, refetch: refetchSessions, createSession, deleteSession, renameSession, archiveSession } = useChatSessions();

  // Session state - null means no session selected (new chat mode)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; sessionId: string } | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  // Track if user has sent at least one message in current session
  const [hasSentFirstMessage, setHasSentFirstMessage] = useState(false);

  // Track the session we're currently viewing history for
  const [viewingSessionId, setViewingSessionId] = useState<string | null>(null);

  // Track if the current session was just created (to avoid loading empty history)
  const isNewSessionRef = useRef(false);

  // WebSocket hook - only pass sessionId when we have an active session
  const { messages: wsMessages, isConnected, isThinking: isWsThinking, send, clearMessages, setMessages, error: wsError, onTitleUpdate } = useChat(courseId, currentSessionId || undefined);

  // History hook - only fetch when we're explicitly viewing an existing session
  const { messages: historyMessages, isLoading: historyLoading, refetch: refetchHistory } = useChatHistory(
    viewingSessionId || ''
  );

  // Poll for title updates after first message
  const { startPolling: startTitlePolling, stopPolling: stopTitlePolling } = useSessionTitlePoll(
    currentSessionId || '',
    (newTitle) => {
      refetchSessions();
      stopTitlePolling();
    }
  );

  // Handle title updates from WebSocket
  useEffect(() => {
    if (onTitleUpdate) {
      onTitleUpdate((sessionId: string, title: string) => {
        refetchSessions();
        stopTitlePolling();
      });
    }
  }, [onTitleUpdate, refetchSessions, stopTitlePolling]);

  // Use WebSocket messages (which get updated with streaming)
  const messages = wsMessages;

  // Combined thinking state
  const isThinking = isWsThinking || (currentSessionId && historyLoading && messages.length === 0);

  const [inputValue, setInputValue] = useState('');
  const [showSources, setShowSources] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const currentCourseContext = courseId || 'general';
  const currentSession = sessions.find((s: { id: string }) => s.id === currentSessionId);

  // Starter suggestions for empty chat
  const starterSuggestions = [
    'Explain the key concepts from Week 1',
    'What are the best practices for this topic?',
    'Give me a practical example I can try',
    'Quiz me on what I have learned so far',
  ];

  // Inspirational quote for empty chat
  const chatQuote = {
    text: "The expert in anything was once a beginner. Start your journey today.",
    author: "CourseForge AI"
  };

  // Follow-up suggestions based on last AI message
  const getFollowUpSuggestions = () => {
    const lastAssistantMessage = messages.filter(msg => msg.role === 'assistant').pop();
    if (!lastAssistantMessage) return [];
    
    const defaultSuggestions = [
      'Can you elaborate on this?',
      'Show me a code example',
      'What are common mistakes to avoid?',
      'How does this apply in real projects?',
    ];
    return defaultSuggestions;
  };

  // Load session history when user clicks on an existing session (not for new sessions)
  useEffect(() => {
    console.log('[CHAT] Session effect triggered:', { currentSessionId, isNewSession: isNewSessionRef.current });

    if (!currentSessionId) {
      // No session selected (new chat mode)
      console.log('[CHAT] No session selected');
      setViewingSessionId(null);
      return;
    }

    if (isNewSessionRef.current) {
      // New session just created - don't load history, use WebSocket messages
      console.log('[CHAT] New session created, using WebSocket messages:', currentSessionId);
      setViewingSessionId(null);
      isNewSessionRef.current = false; // Reset for next time
      return;
    }

    // User clicked existing session - load history
    console.log('[CHAT] Loading existing session history:', currentSessionId);
    clearMessages();
    setMessages([]);
    setHasSentFirstMessage(false);
    stopTitlePolling();
    setViewingSessionId(currentSessionId);
  }, [currentSessionId, clearMessages, setMessages, stopTitlePolling]);

  // Load messages from history when fetched
  useEffect(() => {
    if (viewingSessionId && !historyLoading && historyMessages.length > 0) {
      setMessages(historyMessages);
      setHasSentFirstMessage(true);
    }
  }, [historyMessages, historyLoading, viewingSessionId, setMessages]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!inputValue.trim() || isThinking) return;
    if (!isConnected) return;

    const isFirstMessage = !hasSentFirstMessage;

    // Create new session if no current session (first message without clicking NEW CHAT)
    let sessionIdToUse = currentSessionId;
    if (!currentSessionId) {
      const newSessionId = await createSession({ course_id: courseId });
      if (newSessionId) {
        sessionIdToUse = newSessionId;
        // IMPORTANT: Clear messages BEFORE setting new session to prevent old messages from showing
        console.log('[CHAT] Creating new session, clearing messages:', newSessionId);
        clearMessages();
        setMessages([]);
        setHasSentFirstMessage(false);
        setCurrentSessionId(newSessionId);
        isNewSessionRef.current = true; // Mark as new session - don't load history
        // Wait for WebSocket to connect with new session
        await new Promise(resolve => setTimeout(resolve, 300));
      }
    }

    // Send message with session ID
    if (sessionIdToUse && isConnected) {
      console.log('[CHAT] Sending message to session:', sessionIdToUse);
      const success = send(inputValue, sessionIdToUse);
      if (success) {
        setInputValue('');
        setHasSentFirstMessage(true);

        // Start title polling for first message
        if (isFirstMessage) {
          startTitlePolling();
        }
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputValue(suggestion);
    inputRef.current?.focus();
  };

  // Start a new chat - create new session immediately
  const handleNewChat = async () => {
    console.log('[CHAT] handleNewChat called - creating new session');

    // Create a new session immediately
    const newSessionId = await createSession({ course_id: courseId });
    if (newSessionId) {
      console.log('[CHAT] New session created:', newSessionId);
      setCurrentSessionId(newSessionId);
      setViewingSessionId(null);
      // Clear messages for new chat
      clearMessages();
      setMessages([]);
      setHasSentFirstMessage(false);
      stopTitlePolling();
      isNewSessionRef.current = true;
    }
  };

  // Click on existing session - load it
  const handleSessionClick = (sessionId: string) => {
    if (sessionId === currentSessionId) return;
    setCurrentSessionId(sessionId);
    // History will be loaded by useEffect
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingSessionId(sessionId);
    const deleted = await deleteSession(sessionId);
    if (deleted && currentSessionId === sessionId) {
      handleNewChat();
    }
    setDeletingSessionId(null);
  };

  const handleContextMenu = (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      sessionId
    });
  };

  const handleRename = async () => {
    if (!contextMenu) return;
    setIsRenaming(true);
    const session = sessions.find(s => s.id === contextMenu.sessionId);
    if (session) {
      setNewTitle(session.title);
    }
  };

  const handleArchive = async () => {
    if (!contextMenu) return;
    setContextMenu(null);
    const archived = await archiveSession(contextMenu.sessionId);
    if (archived && currentSessionId === contextMenu.sessionId) {
      handleNewChat();
    }
  };

  const handleDelete = async () => {
    if (!contextMenu) return;
    setContextMenu(null);
    const deleted = await deleteSession(contextMenu.sessionId);
    if (deleted && currentSessionId === contextMenu.sessionId) {
      handleNewChat();
    }
  };

  const handleSaveRename = async () => {
    if (!contextMenu || !newTitle.trim()) return;
    const success = await renameSession(contextMenu.sessionId, newTitle);
    if (success) {
      setIsRenaming(false);
      setNewTitle('');
      setContextMenu(null);
    }
  };

  // Close context menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setContextMenu(null);
      setIsRenaming(false);
      setNewTitle('');
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  if (sessionsLoading && sessions.length === 0) return <LoadingSkeleton />;
  if (sessionsError) {
    return <ErrorBox message={sessionsError} onRetry={refetchSessions} />;
  }

  return (
    <div className={styles.page}>
      {/* Custom Context Menu */}
      {contextMenu && (
        <div
          className={styles.contextMenu}
          style={{
            position: 'fixed',
            left: `${contextMenu.x}px`,
            top: `${contextMenu.y}px`,
            zIndex: 1000,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {isRenaming ? (
            <div className={styles.renameForm}>
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveRename();
                  if (e.key === 'Escape') {
                    setIsRenaming(false);
                    setNewTitle('');
                  }
                }}
                autoFocus
                placeholder="Enter new title..."
              />
              <div className={styles.renameActions}>
                <button onClick={handleSaveRename}>Save</button>
                <button onClick={() => { setIsRenaming(false); setNewTitle(''); }}>Cancel</button>
              </div>
            </div>
          ) : (
            <>
              <button onClick={handleRename} className={styles.contextMenuItem}>
                ✏️ Rename
              </button>
              <button onClick={handleArchive} className={styles.contextMenuItem}>
                📦 Archive
              </button>
              <button onClick={handleDelete} className={styles.contextMenuItem}>
                🗑️ Delete
              </button>
            </>
          )}
        </div>
      )}

      {/* Left: Sessions */}
      <aside className={styles.sessionsPanel}>
        <div className={styles.sessionsHeader}>
          <span className={styles.sessionsLabel}>► SESSIONS</span>
          <span className={styles.connectionStatus}>
            {isConnected ? '●' : '○'} {isConnected ? 'CONNECTED' : 'RECONNECTING...'}
          </span>
        </div>
        <div className={styles.sessionsList}>
          {sessions.map((session: { id: string; title: string; message_count: number }) => (
            <button
              key={session.id}
              className={`${styles.sessionItem} ${currentSessionId === session.id ? styles.active : ''}`}
              onClick={() => handleSessionClick(session.id)}
              onContextMenu={(e) => handleContextMenu(e, session.id)}
              disabled={deletingSessionId === session.id}
            >
              <span className={styles.sessionTitle}>{session.title}</span>
              <span className={styles.sessionMeta}>
                {deletingSessionId === session.id ? 'Deleting...' : `${session.message_count} msgs`}
              </span>
            </button>
          ))}
        </div>
        <button className={styles.newSessionBtn} onClick={handleNewChat}>
          + NEW CHAT
        </button>
        <div className={styles.contextBadge}>
          <span className={styles.contextLabel}>CONTEXT:</span>
          <span className={styles.contextValue}>{currentCourseContext.toUpperCase()}</span>
        </div>
      </aside>

      {/* Main: Chat */}
      <main className={styles.chatMain}>
        <div className={styles.chatHeader}>
          <span className={styles.chatTitle}>
            {currentSessionId && currentSession
              ? `CHATTING ABOUT: ${currentSession.title}`
              : 'NEW CHAT - Send a message to start'}
          </span>
          <div className={styles.scopeToggles}>
            <button className={`${styles.scopeBtn} ${styles.active}`}>COURSE CONTEXT</button>
            <button className={styles.scopeBtn}>ALL COURSES</button>
            <button className={styles.scopeBtn}>GLOBAL</button>
          </div>
        </div>

        <div className={styles.messagesContainer}>
          <div className={styles.messages}>
            {messages
              .filter(msg =>
                msg.content !== '[Session created]' &&
                msg.content !== 'New Chat' &&
                msg.role !== 'system'
              )
              .map((msg) => (
              <motion.div
                key={msg.id}
                className={`${styles.message} ${styles[msg.role]}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
              >
                <div className={styles.messageContent}>
                  {msg.role === 'assistant' ? (
                    <MarkdownRenderer content={msg.content} />
                  ) : (
                    <p>{msg.content}</p>
                  )}
                </div>
                {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                  <div className={styles.sourcesSection}>
                    <button
                      className={styles.sourcesToggle}
                      onClick={() => setShowSources(showSources === msg.id ? null : msg.id)}
                    >
                      ► SOURCES ({msg.sources.length})
                    </button>
                    <AnimatePresence>
                      {showSources === msg.id && (
                        <motion.div
                          className={styles.sourcesList}
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                        >
                          {msg.sources.map((source, i) => (
                            <span key={i} className={styles.sourceItem}>
                              {source.title}
                              {source.page && ` (p.${source.page})`}
                            </span>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </motion.div>
            ))}

            {/* Typing indicator */}
            {isThinking && (
              <div className={styles.typingIndicator}>
                COURSEFORGE IS THINKING
                <span className={styles.typingBar}>
                  <motion.span
                    className={styles.typingProgress}
                    initial={{ width: '0%' }}
                    animate={{ width: '100%' }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                </span>
              </div>
            )}

            {/* Starter Suggestions - Show when no messages */}
            {messages.length === 0 && !isThinking && (
              <div className={styles.suggestionsContainer}>
                <div className={styles.quoteCard}>
                  <p className={styles.quoteText}>"{chatQuote.text}"</p>
                  <span className={styles.quoteAuthor}>— {chatQuote.author}</span>
                </div>
                <div className={styles.suggestionsWrapper}>
                  <div className={styles.suggestionsGrid}>
                    {starterSuggestions.map((suggestion, index) => (
                      <motion.button
                        key={index}
                        className={styles.suggestionCard}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: index * 0.05 }}
                        onClick={() => handleSuggestionClick(suggestion)}
                      >
                        <span className={styles.suggestionText}>{suggestion}</span>
                      </motion.button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Follow-up Suggestions - Show after AI response */}
            {!isThinking && messages.length > 0 && messages[messages.length - 1]?.role === 'assistant' && (
              <div className={styles.suggestionsContainer}>
                <div className={styles.suggestionsWrapper}>
                  <div className={styles.suggestionsGrid}>
                    {getFollowUpSuggestions().map((suggestion, index) => (
                      <motion.button
                        key={index}
                        className={styles.suggestionCard}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.2, delay: index * 0.05 }}
                        onClick={() => handleSuggestionClick(suggestion)}
                      >
                        <span className={styles.suggestionText}>{suggestion}</span>
                      </motion.button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className={styles.inputArea}>
          <textarea
            ref={inputRef}
            className={styles.input}
            placeholder="Ask your AI tutor anything..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <motion.button
            className={styles.sendBtn}
            onClick={handleSend}
            disabled={!inputValue.trim() || isThinking || !isConnected}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            SEND →
          </motion.button>
        </div>
      </main>
    </div>
  );
}
