'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useParams, useRouter } from 'next/navigation';
import { usePathname } from 'next/navigation';
import { useAuth } from '@clerk/nextjs';
import MarkdownRenderer from '@/app/components/dashboard/MarkdownRenderer/MarkdownRenderer';
import { useChatSessions, useChat, useChatHistory, useSessionTitlePoll, ChatMessage, useCourses } from '@/app/hooks/api';
import { useChatCourse } from '@/app/hooks/api/useChatCourse';
import { useUpdateCourse } from '@/app/hooks/api/useCourses';
import { useGenerationProgress } from '@/app/context/GenerationProgressContext';
import { useChatStorage } from '@/app/hooks/useChatStorage';
import CourseCreationForm, { FormSchema } from '@/app/components/chat/CourseCreationForm';
import DayContentCard from '@/app/components/chat/DayContentCard';
import ChatGenerationProgress from '@/app/components/chat/ChatGenerationProgress';
import WebSearchToggle from '@/app/components/chat/WebSearchToggle';
import CrudToggle from '@/app/components/chat/CrudToggle';
import WebSearchStatus from '@/app/components/chat/WebSearchStatus';
import SessionStatus from '@/app/components/chat/SessionStatus';
import CourseUpdateModal, { UpdateType } from '@/app/components/CourseUpdateModal/CourseUpdateModal';
import styles from './page.module.css';

// Types
interface SearchMatch {
  sessionId: string;
  sessionTitle: string;
  messageId: string;
  content: string;
  matchedText: string;
  timestamp: string;
  role: 'user' | 'assistant';
  date?: string;
}

interface ContextMenuState {
  isOpen: boolean;
  x: number;
  y: number;
  sessionId: string | null;
  sessionTitle: string;
}

export default function ChatPage() {
  const params = useParams();
  const router = useRouter();
  const { getToken } = useAuth();
  const courseId = params.course_id as string | undefined;

  // Session state
  const { sessions, isLoading: sessionsLoading, error: sessionsError, refetch: refetchSessions, createSession, deleteSession, renameSession, archiveSession } = useChatSessions();
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [hasSentFirstMessage, setHasSentFirstMessage] = useState(false);
  const [viewingSessionId, setViewingSessionId] = useState<string | null>(null);
  const isNewSessionRef = useRef(false);

  // Get user's courses for CRUD operations
  const { data: userCoursesData } = useCourses();
  const user_courses = userCoursesData || [];

  // CRUD loading state (must be before isThinking)
  const [isCrudThinking, setIsCrudThinking] = useState(false);

  // Context menu state
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    isOpen: false,
    x: 0,
    y: 0,
    sessionId: null,
    sessionTitle: '',
  });
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [renameTitle, setRenameTitle] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  // WebSocket hook
  const { messages: wsMessages, isConnected, isThinking: isWsThinking, isSessionSwitching, send, clearMessages, setMessages, onTitleUpdate, webSearchState } = useChat(courseId, currentSessionId || undefined);

  // History hook
  const { messages: historyMessages, isLoading: historyLoading, refetch: refetchHistory } = useChatHistory(viewingSessionId || '');

  // Poll for title updates
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

  const messages = wsMessages;
  const isThinking = isWsThinking || isCrudThinking || (currentSessionId && historyLoading && messages.length === 0);

  // Course management state
  const {
    sendChatMessage,
    createCourse: createCourseFromChat,
    deleteCourse: deleteCourseFromChat,
    getDayContent: fetchDayContent,
    getMCQContent: fetchMCQContent,
    isLoading: isChatCourseLoading,
    error: chatCourseError,
  } = useChatCourse();

  const {
    updateCourse: executeCourseUpdate,
    isUpdating: isCourseUpdating,
    error: updateError,
  } = useUpdateCourse();

  const [courseFormSchema, setCourseFormSchema] = useState<FormSchema | null>(null);
  const [pendingCourseData, setPendingCourseData] = useState<any>(null);
  const [dayContent, setDayContent] = useState<any>(null);
  const [mcqContent, setMcqContent] = useState<any>(null);
  const [pendingAction, setPendingAction] = useState<{
    type: 'delete' | 'create';
    data: any;
  } | null>(null);

  // Update course state
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [pendingUpdateData, setPendingUpdateData] = useState<{
    course_id: string;
    course_name: string;
    user_query: string;
    current_duration_weeks: number;
  } | null>(null);

  // Use global generation progress context
  const {
    generatingCourses,
    addGeneratingCourse,
    updateGeneratingCourse,
    removeGeneratingCourse,
  } = useGenerationProgress();

  // Chat persistence
  const storage = useChatStorage();
  const hasRestoredRef = useRef(false);
  const autoCreatedSessionRef = useRef(false);

  // Auto-create session if none exists when chat loads
  useEffect(() => {
    if (sessions.length === 0 && !autoCreatedSessionRef.current && !sessionsLoading) {
      console.log('[CHAT] No sessions found, creating new session...');
      createSession({ course_id: courseId }).then((newSessionId) => {
        if (newSessionId) {
          console.log('[CHAT] Auto-created session:', newSessionId);
          setCurrentSessionId(newSessionId);
          autoCreatedSessionRef.current = true;
        }
      });
    }
  }, [sessions.length, sessionsLoading, courseId, createSession]);

  // Get the currently generating course for this chat session
  // Show progress bar for all stages: pending, generating, updating, and recently completed
  // This ensures progress bar shows from initialization through completion
  const generatingCourseInThisSession = Array.from(generatingCourses.values()).find(
    c => (c.generation_status === 'pending' || c.generation_status === 'generating' || c.generation_status === 'updating' || c.generation_status === 'ready') &&
    // Match if both are null/undefined OR both match exactly
    (c.createdBySessionId === currentSessionId ||
     (!c.createdBySessionId && !currentSessionId))  // Handle null/undefined case
  );
  const generatingCourseId = generatingCourseInThisSession?.courseId;
  const generatingCourse = generatingCourseId ? generatingCourses.get(generatingCourseId) : undefined;
  
  // Debug logging
  useEffect(() => {
    console.log('[DEBUG] generatingCourses:', Array.from(generatingCourses.entries()));
    console.log('[DEBUG] currentSessionId:', currentSessionId);
    console.log('[DEBUG] generatingCourseInThisSession:', generatingCourseInThisSession);
    console.log('[DEBUG] generatingCourseId:', generatingCourseId);
  }, [generatingCourses, currentSessionId, generatingCourseInThisSession, generatingCourseId]);
  
  // Restore session ID on mount (when sessions are loaded) - ONLY RUNS ONCE
  useEffect(() => {
    // Skip if already restored, already have a session, or sessions still loading
    if (hasRestoredRef.current || currentSessionId || sessions.length === 0) {
      return;
    }

    console.log('[CHAT] Running session restoration (first load only)...');

    // First, check localStorage for the last selected session
    const lastSelectedSessionId = storage.getCurrentSessionId();
    if (lastSelectedSessionId) {
      const sessionExists = sessions.some((s: { id: string }) => s.id === lastSelectedSessionId);
      if (sessionExists) {
        console.log('[CHAT] Restoring last selected session:', lastSelectedSessionId);
        setCurrentSessionId(lastSelectedSessionId);
        hasRestoredRef.current = true;
        return;
      }
    }

    // Second, check if any session has generating courses in Redis metadata
    const sessionWithGeneratingCourse = sessions.find((s: any) =>
      s.generating_course_ids && s.generating_course_ids.length > 0
    );

    if (sessionWithGeneratingCourse) {
      console.log('[CHAT] Restoring session with generating course:', sessionWithGeneratingCourse.id);
      setCurrentSessionId(sessionWithGeneratingCourse.id);
      hasRestoredRef.current = true;
      return;
    }

    // Third, check localStorage for sessions that had generating courses saved
    const allSessionIds = storage.getAllSessionIds();
    for (const sessionId of allSessionIds) {
      const session = storage.getSession(sessionId);
      if (session && session.generatingCourseIds && session.generatingCourseIds.length > 0) {
        // Check if this session exists in DB
        const sessionExists = sessions.some((s: { id: string }) => s.id === sessionId);
        if (sessionExists) {
          console.log('[CHAT] Restoring session from localStorage with generating courses:', sessionId);
          setCurrentSessionId(sessionId);
          hasRestoredRef.current = true;
          return;
        }
      }
    }

    console.log('[CHAT] No session to restore');
  }, [sessions.length]); // Only depend on sessions.length to run once when sessions load

  // UI State
  const [inputValue, setInputValue] = useState('');
  const [hoveredMessageId, setHoveredMessageId] = useState<string | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  
  // Web search state
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  // CRUD course management state
  const [crudEnabled, setCrudEnabled] = useState(false);
  
  // Web search keywords (matches backend) - for auto-detection when toggle is OFF
  const WEB_SEARCH_KEYWORDS = [
    // Search intent
    'search', 'web search', 'google', 'bing', 'look up',
    'find online', 'search the web', 'search online',
    
    // Time-sensitive
    'latest', 'current', 'recent', 'new', 'today',
    'yesterday', 'this week', 'this month', '2026', '2025',
    
    // News/Events
    'news', 'announcement', 'release', 'update', 'breaking',
    
    // Facts/Data
    'statistics', 'price', 'cost', 'population', 'market share',
    'ranking', 'report', 'study', 'survey',
    
    // People/Companies
    'who is', 'what company', 'founder', 'ceo', 'owner',
    
    // Technology
    'version', 'release date', 'documentation', 'changelog',
    
    // Weather/Current events
    'weather', 'temperature', 'forecast', 'score', 'result',
    
    // Conflict/Events
    'conflict', 'war', 'attack', 'election', 'protest',
  ];

  // Search state (for session search)
  const [sessionSearchQuery, setSearchQuery] = useState('');
  const [sessionSearchResults, setSearchResults] = useState<SearchMatch[]>([]);
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  // Session history map for search
  const sessionHistoryMap = useRef<Map<string, any[]>>(new Map());
  const sessionsFetchedRef = useRef<Set<string>>(new Set());

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const currentSession = sessions.find((s: { id: string }) => s.id === currentSessionId);

  // ========== PERSISTENCE: Save on navigation away ==========
  // Save to localStorage when currentSessionId changes (user navigates)
  useEffect(() => {
    if (!currentSessionId) {
      // Save before clearing
      const prevSessionId = storage.getCurrentSessionId();
      if (prevSessionId && messages.length > 0) {
        const storedMessages = messages.map(m => ({
          ...m,
          timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp,
        }));
        storage.saveSessionMessages(prevSessionId, storedMessages);
      }
    } else {
      // Save new session ID
      storage.saveCurrentSessionId(currentSessionId);
      
      // Also save session metadata with generating course IDs
      if (currentSession) {
        const generatingIds = Array.from(generatingCourses.values())
          .filter(c => c.createdBySessionId === currentSessionId)
          .map(c => c.courseId);
        
        storage.saveSession({
          id: currentSession.id,
          title: currentSession.title,
          course_id: currentSession.course_id,
          generatingCourseIds: generatingIds,
          created_at: currentSession.created_at,
          updated_at: new Date().toISOString(),
        });
      }
    }
  }, [currentSessionId, currentSession, generatingCourses, storage]);

  // Save messages periodically (debounced)
  useEffect(() => {
    if (currentSessionId && messages.length > 0) {
      const timeoutId = setTimeout(() => {
        const storedMessages = messages.map(m => ({
          ...m,
          timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp,
        }));
        storage.saveSessionMessages(currentSessionId, storedMessages);
      }, 1000); // Save 1 second after last message change
      return () => clearTimeout(timeoutId);
    }
  }, [messages, currentSessionId, storage]);
  // ========== END PERSISTENCE ==========

  // ========== ROUTE CHANGE: Save session to DB before navigation ==========
  const pathname = usePathname();
  const previousPathnameRef = useRef<string | null>(null);
  const isSavingSessionRef = useRef(false);
  const messagesRef = useRef(messages);
  const currentSessionRef = useRef(currentSession);
  const lastSavedTitleRef = useRef<string | null>(null);

  // Keep refs updated
  useEffect(() => {
    messagesRef.current = messages;
    currentSessionRef.current = currentSession;
  }, [messages, currentSession]);

  // Function to save current session to DB
  const saveCurrentSessionToDB = useCallback(async (force: boolean = false) => {
    if (!currentSessionId || isSavingSessionRef.current) {
      console.log('[SESSION SAVE] Skipping - no session or already saving');
      return;
    }

    // Only save if we have messages or generating courses
    const hasMessages = messagesRef.current.length > 0;
    const hasGeneratingCourses = Array.from(generatingCourses.values()).some(
      c => c.createdBySessionId === currentSessionId
    );

    if (!hasMessages && !hasGeneratingCourses && !force) {
      console.log('[SESSION SAVE] Skipping save - no messages or generating courses');
      return;
    }

    isSavingSessionRef.current = true;
    console.log('[SESSION SAVE] Starting save, messages:', messagesRef.current.length, 'force:', force);

    try {
      // Get the current title or generate one from first message
      let sessionTitle = currentSessionRef.current?.title || 'New Chat';

      // If title is placeholder or empty, generate from first user message
      if (sessionTitle === '[Session created]' || sessionTitle === 'New Chat' || !sessionTitle) {
        const firstUserMessage = messagesRef.current.find(m => m.role === 'user');
        if (firstUserMessage) {
          sessionTitle = firstUserMessage.content.slice(0, 50) + (firstUserMessage.content.length > 50 ? '...' : '');
          console.log('[SESSION SAVE] Generated title from first message:', sessionTitle);
        }
      }

      // Prevent duplicate saves with same title
      if (lastSavedTitleRef.current === sessionTitle && !force) {
        console.log('[SESSION SAVE] Skipping - title unchanged:', sessionTitle);
        isSavingSessionRef.current = false;
        return;
      }

      // ALWAYS update session title in DB to ensure session appears in sidebar
      console.log('[SESSION SAVE] Renaming session to:', sessionTitle);
      await renameSession(currentSessionId, sessionTitle);
      lastSavedTitleRef.current = sessionTitle;

      // Save generating course IDs to session metadata in Redis
      const generatingIds = Array.from(generatingCourses.values())
        .filter(c => c.createdBySessionId === currentSessionId)
        .map(c => c.courseId);

      if (generatingIds.length > 0) {
        console.log('[SESSION SAVE] Saving generating courses to session:', generatingIds);
        // Save to Redis via backend API
        await fetch(`/api/conversations/sessions/${currentSessionId}/generating-courses/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ course_ids: generatingIds }),
        }).catch(err => console.warn('[SESSION SAVE] Failed to save generating courses:', err));
      }

      // Also save to localStorage as backup
      storage.saveSession({
        id: currentSessionId,
        title: sessionTitle,
        course_id: currentSessionRef.current?.course_id || null,
        generatingCourseIds: generatingIds,
        created_at: currentSessionRef.current?.created_at || new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });

      console.log('[SESSION SAVE] ✅ Session saved successfully');
    } catch (err) {
      console.error('[SESSION SAVE] ❌ Failed to save session:', err);
    } finally {
      isSavingSessionRef.current = false;
    }
  }, [currentSessionId, generatingCourses, renameSession, storage]);

  // Save on unmount (when navigating away from chat page)
  useEffect(() => {
    return () => {
      console.log('[UNMOUNT] Chat page unmounting, saving session...');
      if (currentSessionId && !isSavingSessionRef.current) {
        saveCurrentSessionToDB(true); // Force save on unmount
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps - only run on mount/unmount

  // Save current session to DB when route changes (before navigation)
  useEffect(() => {
    // Skip on first mount
    if (previousPathnameRef.current === null) {
      previousPathnameRef.current = pathname;
      return;
    }

    // Check if route actually changed (not just query params)
    const oldRoute = previousPathnameRef.current.split('?')[0];
    const newRoute = pathname.split('?')[0];

    if (oldRoute !== newRoute && currentSessionId && !isSavingSessionRef.current) {
      console.log('[ROUTE CHANGE] Detected navigation from', oldRoute, 'to', newRoute);
      saveCurrentSessionToDB();
    }

    previousPathnameRef.current = pathname;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, currentSessionId]); // Removed saveCurrentSessionToDB from deps to prevent loop
  // ========== END ROUTE CHANGE ==========

  // Fetch session history for search (on-demand when search is opened)
  const fetchSessionForSearch = useCallback(async (sessionId: string) => {
    if (sessionHistoryMap.current.has(sessionId)) {
      return sessionHistoryMap.current.get(sessionId);
    }
    
    try {
      const res = await fetch(`/api/conversations/sessions/${sessionId}/`);
      if (!res.ok) return [];
      const data = await res.json();
      const messages = data.data?.messages || [];
      sessionHistoryMap.current.set(sessionId, messages);
      return messages;
    } catch {
      return [];
    }
  }, []);

  // Session management effect
  useEffect(() => {
    console.log('[CHAT] Session effect - currentSessionId:', currentSessionId);

    if (!currentSessionId) {
      setViewingSessionId(null);
      return;
    }

    if (isNewSessionRef.current) {
      console.log('[CHAT] New session - skipping history load');
      setViewingSessionId(null);
      isNewSessionRef.current = false;
      return;
    }

    // User clicked existing session - load history
    console.log('[CHAT] Loading existing session history:', currentSessionId);
    clearMessages();
    setMessages([]);
    setHasSentFirstMessage(false);  // Reset for new session
    stopTitlePolling();
    setViewingSessionId(currentSessionId);
  }, [currentSessionId, clearMessages, setMessages, stopTitlePolling]);

  // Load history when fetched
  useEffect(() => {
    if (viewingSessionId && !historyLoading && historyMessages.length > 0) {
      console.log('[CHAT] History loaded:', historyMessages.length, 'messages');

      // Set messages from history (always, since we cleared on session switch)
      setMessages(historyMessages);
      setHasSentFirstMessage(true);  // Mark as loaded
    }
  }, [historyMessages, historyLoading, viewingSessionId, setMessages]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Search across all sessions
  const performSearch = useCallback(async () => {
    if (!sessionSearchQuery.trim() || !isSearchOpen) {
      setSearchResults([]);
      return;
    }

    const query = sessionSearchQuery.toLowerCase();
    const results: SearchMatch[] = [];

    // Fetch all sessions for search
    await Promise.all(
      sessions.map(async (session: { id: string; title: string }) => {
        const messages = await fetchSessionForSearch(session.id);
        messages.forEach((msg: any) => {
          if (msg.content.toLowerCase().includes(query) && msg.role !== 'system') {
            const matchedIndex = msg.content.toLowerCase().indexOf(query);
            const start = Math.max(0, matchedIndex - 50);
            const end = Math.min(msg.content.length, matchedIndex + query.length + 50);

            results.push({
              sessionId: session.id,
              sessionTitle: session.title,
              messageId: msg.id,
              content: msg.content,
              matchedText: msg.content.slice(matchedIndex, matchedIndex + query.length),
              timestamp: msg.created_at,
              role: msg.role,
              date: msg.date,
            });
          }
        });
      })
    );

    setSearchResults(results);
  }, [sessionSearchQuery, sessions, isSearchOpen, fetchSessionForSearch]);

  useEffect(() => {
    if (isSearchOpen && sessionSearchQuery.trim()) {
      performSearch();
    }
  }, [isSearchOpen, sessionSearchQuery, performSearch]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K or Ctrl+K to open search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
        setTimeout(() => {
          document.getElementById('search-input')?.focus();
        }, 100);
      }
      // Escape to close search
      if (e.key === 'Escape') {
        setIsSearchOpen(false);
        setSearchQuery('');
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px';
    }
  }, [inputValue]);

  /**
   * Persist conversation to database (for CRUD-generated messages)
   * This ensures messages appear in chat history sidebar.
   */
  const persistConversation = useCallback(async (
    sessionId: string,
    userMessage: string,
    aiResponse: string
  ) => {
    try {
      const token = await getToken();
      const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      
      const response = await fetch(`${BASE_URL}/api/conversations/persist/`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          session_id: sessionId,
          user_message: userMessage,
          ai_response: aiResponse,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        console.log('[PERSIST] ✅ Conversation persisted:', data.data);
        
        // Refetch sessions to update sidebar
        refetchSessions();
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('[PERSIST] ❌ Failed to persist conversation:', response.status, errorData);
      }
    } catch (err) {
      console.error('[PERSIST] Error persisting conversation:', err);
    }
  }, [refetchSessions, getToken]);

  const handleSend = async () => {
    if (!inputValue.trim() || isThinking) return;
    if (!isConnected) return;

    const isFirstMessage = !hasSentFirstMessage;
    const messageToSend = inputValue.trim();

    // Flag to track if message was handled by course management
    let messageHandled = false;

    console.log('[SEND] CRUD Enabled:', crudEnabled, 'Message:', messageToSend);

    // Create user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageToSend,
      timestamp: new Date(),
    };

    // Add user message to chat immediately
    const messagesAfterUser = [...messages, userMessage];
    setMessages(messagesAfterUser);
    setInputValue('');

    // First, send to course management API if CRUD toggle is enabled
    if (crudEnabled) {
      console.log('[CRUD] Sending to CRUD API...');
      setIsCrudThinking(true);

      // Ensure we have a session ID
      let sessionIdToUse = currentSessionId;
      if (!sessionIdToUse) {
        sessionIdToUse = await createSession({ course_id: courseId });
        if (sessionIdToUse) {
          setCurrentSessionId(sessionIdToUse);
          isNewSessionRef.current = true;
        }
      }

      try {
        const courseResponse = await sendChatMessage({
          message: messageToSend,
          crud_enabled: true,
          session_id: sessionIdToUse || undefined,
        });
        setIsCrudThinking(false);

        if (courseResponse) {
          console.log('[CRUD] Course response:', courseResponse);
          const responseData = courseResponse.data || courseResponse;
          const {
            command,
            action,
            response,
            course_id,
            course_name,
            course_data,
            course,
            courses,
            missing_fields,
            prefilled,
            week_number,
            day_number,
            summary,
            summary_type,
            user_query,
            update_options,
            update_type,
          } = responseData;

          // Get current duration weeks for extend calculation
          const currentDurationWeeks = course_data?.duration_weeks || course?.duration_weeks || 4;

          console.log('[CRUD] Command:', command, 'Action:', action);

          // Handle different commands
          if (command === 'list_courses' && action === 'list') {
            // Display courses
            const courseList = (courses || []).map((c: any) =>
              `• **${c.course_name}** (${c.level}, ${c.duration_weeks} weeks) - Progress: ${c.progress}%`
            ).join('\n');

            const aiResponseContent = `**Your Courses:**\n\n${courseList}`;
            
            const coursesMessage: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: aiResponseContent,
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, coursesMessage]);
            messageHandled = true;
            console.log('[CRUD] Handled: list_courses');
            
            // Persist to database
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
          else if (command === 'delete_course' && action === 'confirm') {
            // Show confirmation dialog for deletion
            if (course_id) {
              setPendingAction({
                type: 'delete',
                data: {
                  course_id,
                  course_name: course_name || course_name,
                },
              });
              const aiResponseContent = response || "Are you sure you want to delete this course?";
              
              const confirmMessage: ChatMessage = {
                id: `ai-${Date.now()}`,
                role: 'assistant',
                content: aiResponseContent,
                timestamp: new Date(),
              };
              setMessages([...messagesAfterUser, confirmMessage]);
              messageHandled = true;
              console.log('[CRUD] Handled: delete_course confirm');
              
              // Persist to database
              if (sessionIdToUse) {
                persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
              }
            }
          }
          else if (command === 'delete_course' && action === 'deleted') {
            // Deletion completed
            const aiResponseContent = response || "Course has been deleted.";
            
            const confirmMessage: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: aiResponseContent,
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, confirmMessage]);
            setPendingAction(null);
            messageHandled = true;
            console.log('[CRUD] Handled: delete_course deleted');
            
            // Persist to database
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
          else if (command === 'create_course' && action === 'show_form') {
            // Show form for missing fields
            console.log('[CRUD] show_form - prefilled:', prefilled);
            console.log('[CRUD] show_form - missing_fields:', missing_fields);
            
            const formSchema: FormSchema = {
              fields: [],
              prefilled: prefilled || {},
            };
            if (!prefilled?.course_name) {
              formSchema.fields.push({
                name: 'course_name',
                type: 'text',
                label: 'Course Name',
                required: true,
              });
            }
            if (!prefilled?.duration_weeks) {
              formSchema.fields.push({
                name: 'duration_weeks',
                type: 'number',
                label: 'Duration (weeks)',
                min: 1,
                max: 52,
                required: true,
              });
            }
            if (!prefilled?.level) {
              formSchema.fields.push({
                name: 'level',
                type: 'select',
                label: 'Skill Level',
                options: [
                  { value: 'beginner', label: 'Beginner' },
                  { value: 'intermediate', label: 'Intermediate' },
                  { value: 'advanced', label: 'Advanced' },
                ],
                required: true,
              });
            }
            // Always add description as optional field
            formSchema.fields.push({
              name: 'description',
              type: 'textarea',
              label: 'Description (Optional)',
              placeholder: 'What will students learn in this course?',
              required: false,
              rows: 3,
            });
            console.log('[CRUD] show_form - formSchema.fields:', formSchema.fields);
            
            setCourseFormSchema(formSchema);
            setPendingCourseData(prefilled || {});
            const aiResponseContent = response || "Let's create a new course! Please fill in the details:";

            const formMessage: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: aiResponseContent,
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, formMessage]);
            messageHandled = true;
            console.log('[CRUD] Handled: create_course show_form');

            // Persist to database
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
          else if (command === 'create_course' && action === 'create' && course_data) {
            // Create the course
            // Ensure we have a session ID before creating the course
            let sessionIdToUse = currentSessionId;
            if (!sessionIdToUse) {
              // Create a new session first
              sessionIdToUse = await createSession({ course_id: courseId });
              if (sessionIdToUse) {
                setCurrentSessionId(sessionIdToUse);
                isNewSessionRef.current = true;
              }
            }

            // Build AI response message for course creation
            const aiResponseContent = `📚 **Generating Course**\n\n**${course_data.course_name}**\n• Duration: ${course_data.duration_weeks} weeks\n• Level: ${course_data.level}\n${course_data.description ? `• Description: ${course_data.description}` : ''}\n\n⏳ Starting content generation...`;

            const result = await createCourseFromChat({
              course_name: course_data.course_name,
              duration_weeks: course_data.duration_weeks,
              level: course_data.level as 'beginner' | 'intermediate' | 'advanced',
              description: course_data.description,
              session_id: sessionIdToUse || undefined,  // Pass session ID
            });

            if (result) {
              const courseData: any = result;
              const newCourseId = courseData?.data?.course_id || courseData?.course_id;

              // Display course specs in chat
              const courseSpecsMessage: ChatMessage = {
                id: `ai-${Date.now()}`,
                role: 'assistant',
                content: aiResponseContent,
                timestamp: new Date(),
              };
              setMessages([...messagesAfterUser, courseSpecsMessage]);

              // Add to global generation progress context
              // Always add, even without session_id (for fallback)
              if (newCourseId) {
                addGeneratingCourse({
                  courseId: newCourseId,
                  courseName: course_data.course_name,
                  progress: 0,
                  completed_days: 0,
                  total_days: course_data.duration_weeks * 5,
                  generation_status: 'generating',
                  current_stage: 'Initializing generation...',
                  topic: course_data.course_name,
                  createdBySessionId: sessionIdToUse || undefined,  // Now guaranteed to have session
                });

                console.log('[CRUD] Course generation started:', newCourseId, 'session:', sessionIdToUse);
              }
            }
            messageHandled = true;
            console.log('[CRUD] Handled: create_course create');
            
            // Persist to database
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
          else if (command === 'update_course' && action === 'show_options') {
            // Show update modal for user to select
            if (course_id && user_query && update_options) {
              // Find current duration from the first available option or default
              const currentDuration = update_options[0]?.duration_change 
                ? parseInt(update_options[0].duration_change.replace(/\D/g, '')) || 4
                : 4;

              setPendingUpdateData({
                course_id,
                course_name: course_name || 'Course',
                user_query,
                current_duration_weeks: currentDuration,
              });
              setIsUpdateModalOpen(true);

              const aiResponseContent = response || "Choose how you'd like to update this course:";

              const optionsMessage: ChatMessage = {
                id: `ai-${Date.now()}`,
                role: 'assistant',
                content: aiResponseContent,
                timestamp: new Date(),
              };
              setMessages([...messagesAfterUser, optionsMessage]);
              messageHandled = true;
              console.log('[CRUD] Handled: update_course show_options');

              // Persist to database
              if (sessionIdToUse) {
                persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
              }
            }
          }
          else if (command === 'update_course' && action === 'execute_update') {
            // Execute the course update
            const aiResponseContent = response || "Updating your course...";

            const updatingMessage: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: aiResponseContent,
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, updatingMessage]);

            if (course_id && update_type) {
              // Map old update types to new types
              let newUpdateType: 'percentage' | 'extend' | 'compact' = 'percentage';
              let percentage: 50 | 75 = 50;
              let extendWeeks: number | undefined;

              if (update_type === '50%') {
                newUpdateType = 'percentage';
                percentage = 50;
              } else if (update_type === '75%') {
                newUpdateType = 'percentage';
                percentage = 75;
              } else if (update_type === 'extend_50%') {
                newUpdateType = 'extend';
                extendWeeks = Math.ceil(currentDurationWeeks * 0.5);
              }

              // Build API data based on update type
              const apiData: any = {
                update_type: newUpdateType,
                user_query: user_query || '',
                web_search_enabled: webSearchEnabled,  // Use actual toggle state
              };

              if (newUpdateType === 'percentage') {
                apiData.percentage = percentage;
              } else if (newUpdateType === 'extend' && extendWeeks) {
                apiData.extend_weeks = extendWeeks;
              }

              // Call the update endpoint
              const result = await executeCourseUpdate(course_id, apiData);

              if (result) {
                const updateData: any = result;
                const weeksToUpdate = updateData?.data?.weeks_to_update || [];
                const newDuration = updateData?.data?.new_duration_weeks || 0;

                // Add updating course to generation progress
                addGeneratingCourse({
                  courseId: course_id,
                  courseName: course_name || 'Course',
                  progress: 0,
                  completed_days: 0,
                  total_days: newDuration * 5,
                  generation_status: 'updating',
                  current_stage: 'Starting update...',
                  topic: course_name || 'Course',
                  createdBySessionId: sessionIdToUse || undefined,
                });

                console.log('[CRUD] Course update started:', course_id, 'weeks to update:', weeksToUpdate);
              }
            }

            messageHandled = true;
            console.log('[CRUD] Handled: update_course execute_update');

            // Persist to database
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
          else if (command === 'chat' && action === 'respond') {
            // Backend couldn't match any CRUD command, treat as regular chat
            const aiResponseContent = response || "I understand. How can I help you with your learning today?";

            const chatMessage: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: aiResponseContent,
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, chatMessage]);
            messageHandled = true;
            console.log('[CRUD] Handled: chat (no CRUD match)');

            // Persist to database
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
          else if (command === 'show_course' && action === 'show' && course) {
            // Show course details
            const aiResponseContent = `**${course.course_name}**\n\n• Level: ${course.level}\n• Duration: ${course.duration_weeks} weeks\n• Progress: ${course.progress}%\n• Status: ${course.status}`;
            
            const courseDetail: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: aiResponseContent,
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, courseDetail]);
            messageHandled = true;
            console.log('[CRUD] Handled: show_course');
            
            // Persist to database
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
          else if (command === 'show_course' && action === 'list') {
            // No course matched, show all courses
            const courseList = (courses || []).map((c: any) =>
              `• **${c.course_name}** (${c.level}, ${c.duration_weeks} weeks) - Progress: ${c.progress}%`
            ).join('\n');

            const aiResponseContent = response + '\n\n' + (courseList || 'No courses found.');
            
            const coursesMessage: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: aiResponseContent,
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, coursesMessage]);
            messageHandled = true;
            console.log('[CRUD] Handled: show_course list');
            
            // Persist to database
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
          else if (command === 'week_day_summary' && action === 'show_llm_summary') {
            // Display LLM-generated summary
            const aiResponseContent = summary || response || "Here's a summary of your progress.";

            const summaryMessage: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: aiResponseContent,
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, summaryMessage]);
            messageHandled = true;
            console.log('[CRUD] Handled: week_day_summary (LLM)');

            // Persist ONLY the AI response (user message already added)
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
          else if (command === 'week_day_summary' && action === 'error') {
            // Display error message
            const errorMessage: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: response || "Sorry, I couldn't generate the summary.",
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, errorMessage]);
            messageHandled = true;
            console.log('[CRUD] Handled: week_day_summary error');

            // Persist ONLY the AI response (user message already added)
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, response || "Sorry, I couldn't generate the summary.");
            }
          }
          else if (command === 'week_day_summary' && action === 'show') {
            // Fetch and display week/day summary
            const courseId = course_id;
            const weekNum = week_number;
            const dayNum = day_number;

            console.log('[CRUD] Week/Day Summary:', { courseId, weekNum, dayNum });

            // Fetch the content from backend
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const token = await getToken();

            try {
              let url = `${baseUrl}/api/courses/${courseId}/`;
              if (weekNum && dayNum) {
                url += `weeks/${weekNum}/days/${dayNum}/`;
              } else if (weekNum) {
                url += `weeks/${weekNum}/`;
              }

              const res = await fetch(url, {
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json',
                },
              });

              if (res.ok) {
                const data = await res.json();
                const content = data.data || data;

                let summaryContent = `📚 **Summary for ${course_name}**\n\n`;

                if (weekNum && dayNum) {
                  // Day summary
                  summaryContent += `**Week ${weekNum}, Day ${dayNum}: ${content.day_title || content.title || 'Day Content'}**\n\n`;
                  summaryContent += `${content.theory_content || content.description || 'No content available'}\n\n`;

                  if (content.code_content) {
                    summaryContent += `**Code Example:**\n\`\`\`\n${content.code_content}\n\`\`\`\n\n`;
                  }

                  if (content.tasks && content.tasks.length > 0) {
                    summaryContent += `**Tasks:**\n`;
                    content.tasks.forEach((task: any, i: number) => {
                      summaryContent += `${i + 1}. ${task.title}\n`;
                    });
                  }
                } else if (weekNum) {
                  // Week summary
                  summaryContent += `**Week ${weekNum} Overview**\n\n`;
                  if (content.week_title || content.title) {
                    summaryContent += `${content.week_title || content.title}\n\n`;
                  }

                  if (content.days && content.days.length > 0) {
                    summaryContent += `**Days in this week:**\n`;
                    content.days.forEach((day: any, i: number) => {
                      summaryContent += `${i + 1}. **Day ${day.day_number}: ${day.title || day.day_title}**\n`;
                    });
                  }
                } else {
                  // Course overview
                  summaryContent += `${content.description || content.course_name || 'Course content'}\n\n`;
                  summaryContent += `**Progress:** ${content.progress || 0}%\n`;
                  summaryContent += `**Status:** ${content.status || 'Active'}\n`;
                }

                const summaryMessage: ChatMessage = {
                  id: `ai-${Date.now()}`,
                  role: 'assistant',
                  content: summaryContent,
                  timestamp: new Date(),
                };
                setMessages([...messagesAfterUser, summaryMessage]);
                messageHandled = true;
                console.log('[CRUD] Handled: week_day_summary');

                // Persist to database
                if (sessionIdToUse) {
                  persistConversation(sessionIdToUse, messageToSend, summaryContent);
                }
              } else {
                throw new Error('Failed to fetch content');
              }
            } catch (err) {
              console.error('[CRUD] Error fetching summary:', err);
              const errorMessage: ChatMessage = {
                id: `ai-${Date.now()}`,
                role: 'assistant',
                content: "⚠️ Sorry, I couldn't fetch the summary. Please make sure the course, week, and day exist.",
                timestamp: new Date(),
              };
              setMessages([...messagesAfterUser, errorMessage]);
              messageHandled = true;
            }
          }
          else {
            // Default: just show the response
            const aiResponseContent = response || "I understand. Let me help you with that.";

            const aiMessage: ChatMessage = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: aiResponseContent,
              timestamp: new Date(),
            };
            setMessages([...messagesAfterUser, aiMessage]);
            messageHandled = true;
            console.log('[CRUD] Handled: default');

            // Persist to database
            if (sessionIdToUse) {
              persistConversation(sessionIdToUse, messageToSend, aiResponseContent);
            }
          }
        } else {
          console.log('[CRUD] API returned null, passing to WebSocket');
        }
      } catch (error) {
        console.error('[CRUD] Error processing course management:', error);
        setIsCrudThinking(false);
        const errorMessage: ChatMessage = {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: '⚠️ Sorry, I encountered an error processing your request. Please try again.',
          timestamp: new Date(),
        };
        setMessages([...messagesAfterUser, errorMessage]);
        messageHandled = true;
      }
    } // End of if (crudEnabled)

    // Only send to WebSocket if not handled by course management
    console.log('[SEND] messageHandled:', messageHandled, 'Will send to WebSocket:', !messageHandled);
    if (!messageHandled) {
      // Determine if web search should be used:
      // 1. If toggle is ON → always use web search
      // 2. If toggle is OFF → use web search only if keywords detected
      const hasKeyword = WEB_SEARCH_KEYWORDS.some(keyword =>
        messageToSend.toLowerCase().includes(keyword)
      );
      const shouldUseWebSearch = webSearchEnabled || hasKeyword;

      let sessionIdToUse = currentSessionId;
      if (!currentSessionId) {
        const newSessionId = await createSession({ course_id: courseId });
        if (newSessionId) {
          sessionIdToUse = newSessionId;
          clearMessages();
          setMessages([]);
          setHasSentFirstMessage(false);
          setCurrentSessionId(newSessionId);
          isNewSessionRef.current = true;
          await new Promise(resolve => setTimeout(resolve, 300));
        }
      }

      if (sessionIdToUse && isConnected) {
        // Send message with web_search flag (silent - no UI)
        const success = send(messageToSend, sessionIdToUse, shouldUseWebSearch);
        if (success) {
          setHasSentFirstMessage(true);
          if (isFirstMessage) {
            startTitlePolling();
          }
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

  // Course management handlers
  const handleCourseFormSubmit = async (formData: Record<string, any>) => {
    // Merge with pending course data
    const mergedData = { ...pendingCourseData, ...formData };

    console.log('[CRUD] Form submit - mergedData:', mergedData);

    // Send to API with form_data and crud_enabled
    const response = await sendChatMessage({ 
      message: `create ${mergedData.course_name || 'course'} course`,
      crud_enabled: true,  // IMPORTANT: Must be true for form submission
      form_data: mergedData,
    });

    if (response) {
      const responseData = response.data || response;
      const { action, response: responseText, course_data } = responseData;

      if (action === 'create' && course_data) {
        // Create the course
        // Ensure we have a session ID before creating the course
        let sessionIdToUse = currentSessionId;
        if (!sessionIdToUse) {
          // Create a new session first
          sessionIdToUse = await createSession({ course_id: courseId });
          if (sessionIdToUse) {
            setCurrentSessionId(sessionIdToUse);
            isNewSessionRef.current = true;
          }
        }

        const result = await createCourseFromChat({
          course_name: course_data.course_name,
          duration_weeks: course_data.duration_weeks,
          level: course_data.level as 'beginner' | 'intermediate' | 'advanced',
          description: course_data.description,
          session_id: sessionIdToUse || undefined,  // Pass session ID
        });

        if (result) {
          const courseData: any = result;
          const newCourseId = courseData?.data?.course_id || courseData?.course_id;

          // Build AI response content
          const aiResponseContent = `📚 **Generating Course**\n\n**${course_data.course_name}**\n• Duration: ${course_data.duration_weeks} weeks\n• Level: ${course_data.level}\n${course_data.description ? `• Description: ${course_data.description}` : ''}\n\n⏳ Starting content generation...`;

          // Show course specs in a chat message container (not toast)
          const courseSpecsMessage: ChatMessage = {
            id: `ai-${Date.now()}`,
            role: 'assistant',
            content: aiResponseContent,
            timestamp: new Date(),
          };
          setMessages([...messages, courseSpecsMessage]);

          // Add to global generation progress context
          if (newCourseId) {
            addGeneratingCourse({
              courseId: newCourseId,
              courseName: course_data.course_name,
              progress: 0,
              completed_days: 0,
              total_days: course_data.duration_weeks * 5,
              generation_status: 'generating',
              current_stage: 'Initializing generation...',
              topic: course_data.course_name,
              createdBySessionId: sessionIdToUse || undefined,
            });
            console.log('[CRUD] Course generation started (form):', newCourseId, 'session:', sessionIdToUse);
          }

          // Persist to database
          if (sessionIdToUse) {
            persistConversation(sessionIdToUse, "Create course with details", aiResponseContent);
          }
        }
      } else {
        const aiMessage: ChatMessage = {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: responseText || "Processing...",
          timestamp: new Date(),
        };
        setMessages([...messages, aiMessage]);
      }
    }

    setCourseFormSchema(null);
    setPendingCourseData(null);
  };

  const handleCourseFormCancel = () => {
    setCourseFormSchema(null);
    setPendingCourseData(null);
  };

  const handlePendingActionConfirm = async () => {
    if (!pendingAction) return;

    if (pendingAction.type === 'delete') {
      // Send confirmation to backend to delete with course_id and crud_enabled
      const response = await sendChatMessage({
        message: `confirm delete ${pendingAction.data.course_name}`,
        crud_enabled: true,  // IMPORTANT: Must be true for delete to work
        form_data: {
          confirm_delete: true,
          course_id: pendingAction.data.course_id,
        },
      });

      if (response) {
        const responseData = response.data || response;
        const aiResponseContent = responseData.response || `✅ Course '${pendingAction.data.course_name}' has been deleted.`;
        
        const confirmMessage: ChatMessage = {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: aiResponseContent,
          timestamp: new Date(),
        };
        setMessages([...messages, confirmMessage]);
        
        // Persist to database
        let sessionIdToUse = currentSessionId;
        if (!sessionIdToUse) {
          sessionIdToUse = await createSession({ course_id: courseId });
        }
        if (sessionIdToUse) {
          persistConversation(sessionIdToUse, `Confirm delete ${pendingAction.data.course_name}`, aiResponseContent);
        }
      }
    }

    setPendingAction(null);
  };

  const handlePendingActionCancel = () => {
    setPendingAction(null);
    // Add cancellation message
    const cancelMessage: ChatMessage = {
      id: `ai-${Date.now()}`,
      role: 'assistant',
      content: 'Operation cancelled.',
      timestamp: new Date(),
    };
    setMessages([...messages, cancelMessage]);
  };

  // Context menu handlers
  const handleContextMenu = useCallback((e: React.MouseEvent, sessionId: string, sessionTitle: string) => {
    e.preventDefault();
    setContextMenu({
      isOpen: true,
      x: e.clientX,
      y: e.clientY,
      sessionId,
      sessionTitle,
    });
  }, []);

  const closeContextMenu = useCallback(() => {
    setContextMenu(prev => ({ ...prev, isOpen: false }));
  }, []);

  const handleRename = useCallback(() => {
    if (contextMenu.sessionId) {
      setRenameTitle(contextMenu.sessionTitle);
      setIsRenameModalOpen(true);
      closeContextMenu();
    }
  }, [contextMenu.sessionId, contextMenu.sessionTitle, closeContextMenu]);

  const handleDelete = useCallback(async () => {
    if (contextMenu.sessionId) {
      const success = await deleteSession(contextMenu.sessionId);
      if (success && contextMenu.sessionId === currentSessionId) {
        setCurrentSessionId(null);
        clearMessages();
        setMessages([]);
      }
      closeContextMenu();
    }
  }, [contextMenu.sessionId, contextMenu.sessionId, currentSessionId, deleteSession, closeContextMenu, clearMessages, setMessages]);

  const handleArchive = useCallback(async () => {
    if (contextMenu.sessionId) {
      await archiveSession(contextMenu.sessionId, true);
      if (contextMenu.sessionId === currentSessionId) {
        setCurrentSessionId(null);
        clearMessages();
        setMessages([]);
      }
      closeContextMenu();
    }
  }, [contextMenu.sessionId, currentSessionId, archiveSession, closeContextMenu, clearMessages, setMessages]);

  const handleRenameSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (contextMenu.sessionId && renameTitle.trim()) {
      await renameSession(contextMenu.sessionId, renameTitle.trim());
      setIsRenameModalOpen(false);
      setRenameTitle('');
    }
  }, [contextMenu.sessionId, renameTitle, renameSession]);

  // Close context menu on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        closeContextMenu();
      }
    };

    if (contextMenu.isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [contextMenu.isOpen, closeContextMenu]);

  // Close context menu on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && contextMenu.isOpen) {
        closeContextMenu();
      }
      if (e.key === 'Escape' && isRenameModalOpen) {
        setIsRenameModalOpen(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [contextMenu.isOpen, isRenameModalOpen, closeContextMenu]);

  const handleNewChat = async () => {
    const newSessionId = await createSession({ course_id: courseId });
    if (newSessionId) {
      setCurrentSessionId(newSessionId);
      setViewingSessionId(null);
      clearMessages();
      setMessages([]);
      setHasSentFirstMessage(false);
      stopTitlePolling();
      isNewSessionRef.current = true;
      console.log('[CHAT] New chat created:', newSessionId);
    }
  };

  const handleSessionClick = (sessionId: string) => {
    if (sessionId === currentSessionId) return;
    setCurrentSessionId(sessionId);
    setIsSearchOpen(false);
    setSearchQuery('');
    console.log('[CHAT] Session selected:', sessionId);
  };

  const handleSearchResultClick = (sessionId: string) => {
    handleSessionClick(sessionId);
    setIsSearchOpen(false);
    setSearchQuery('');
  };

  const handleCopyMessage = async (content: string, messageId: string) => {
    await navigator.clipboard.writeText(content);
    setCopiedMessageId(messageId);
    setTimeout(() => setCopiedMessageId(null), 2000);
  };

  const handleEditMessage = (content: string, messageId: string) => {
    setEditingMessageId(messageId);
    setEditValue(content);
  };

  const handleSaveEdit = (messageId: string) => {
    if (!editValue.trim()) return;

    // Update the message in the current messages array
    const updatedMessages = messages.map(msg =>
      msg.id === messageId ? { ...msg, content: editValue } : msg
    );
    setMessages(updatedMessages);
    setEditingMessageId(null);
    setEditValue('');

    // Resend the edited message to get a new response
    if (currentSessionId) {
      send(editValue, currentSessionId);
    }
  };

  const handleCancelEdit = () => {
    setEditingMessageId(null);
    setEditValue('');
  };

  const handleRegenerate = () => {
    const lastUserMessage = messages.filter(msg => msg.role === 'user').pop();
    if (lastUserMessage && currentSessionId) {
      send(lastUserMessage.content, currentSessionId);
    }
  };

  const handleClearConversation = () => {
    if (currentSessionId) {
      clearMessages();
      setMessages([]);
      setHasSentFirstMessage(false);
    }
  };

  const formatRelativeTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days}d ago`;
    if (days < 30) return `${Math.floor(days / 7)}w ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  if (sessionsLoading && sessions.length === 0) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.loadingSpinner}>
          <div className={styles.loadingDot} />
          <div className={styles.loadingDot} />
          <div className={styles.loadingDot} />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.chatPage}>
      {/* Left Sidebar - Always visible */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarInner}>
          {/* New Chat Button */}
          <button className={styles.newChatBtn} onClick={handleNewChat}>
            <span className={styles.newChatIcon}>+</span>
            New Chat
          </button>

          {/* Search Bar */}
          <div className={styles.searchContainer}>
            <input
              id="search-input"
              type="text"
              className={styles.searchInput}
              placeholder="Search all messages... (⌘K)"
              value={sessionSearchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => setIsSearchOpen(true)}
            />
            {sessionSearchQuery && (
              <button
                className={styles.searchClear}
                onClick={() => { setSearchQuery(''); setIsSearchOpen(false); }}
              >
                ×
              </button>
            )}
          </div>

          {/* Search Results or Session List */}
          <div className={styles.sidebarContent}>
            {isSearchOpen && sessionSearchQuery ? (
              <div className={styles.searchResults}>
                {sessionSearchResults.length === 0 ? (
                  <div className={styles.noResults}>
                    <span className={styles.noResultsIcon}>🔍</span>
                    <span>No matches found</span>
                  </div>
                ) : (
                  sessionSearchResults.map((result, index) => (
                    <button
                      key={`${result.sessionId}-${result.messageId}-${index}`}
                      className={styles.searchResultItem}
                      onClick={() => handleSearchResultClick(result.sessionId)}
                    >
                      <div className={styles.searchResultHeader}>
                        <span className={styles.searchSessionTitle}>{result.sessionTitle}</span>
                        <span className={styles.searchResultDate}>{result.date ? result.date : formatRelativeTime(result.timestamp)}</span>
                      </div>
                      <div className={styles.searchResultPreview}>
                        {result.role === 'user' && <span className={styles.userBadge}>You</span>}
                        <span className={styles.previewText}>
                          {result.content.toLowerCase().includes(sessionSearchQuery.toLowerCase()) ? (
                            <>
                              {result.content.split(new RegExp(`(${sessionSearchQuery})`, 'gi')).map((part, i) =>
                                part.toLowerCase() === sessionSearchQuery.toLowerCase() ? (
                                  <mark key={i} className={styles.searchHighlight}>{part}</mark>
                                ) : (
                                  part
                                )
                              )}
                            </>
                          ) : result.content}
                        </span>
                      </div>
                    </button>
                  ))
                )}
              </div>
            ) : (
              <div className={styles.sessionList}>
                {sessions.map((session: { id: string; title: string; message_count: number; created_at: string; date?: string }) => (
                  <button
                    key={session.id}
                    className={`${styles.sessionItem} ${currentSessionId === session.id ? styles.active : ''}`}
                    onClick={() => handleSessionClick(session.id)}
                    onContextMenu={(e) => handleContextMenu(e, session.id, session.title)}
                  >
                    <div className={styles.sessionItemContent}>
                      <span className={styles.sessionTitle}>{session.title}</span>
                      <span className={styles.sessionDate}>{session.date ? session.date : formatRelativeTime(session.created_at)}</span>
                    </div>
                    <div className={styles.sessionMeta}>
                      <span className={styles.messageCount}>{session.message_count} msgs</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className={styles.mainChat}>
        {/* Top Bar */}
        <header className={styles.topBar}>
          <button className={styles.backBtn} onClick={() => router.push('/dashboard')}>
            ← DASHBOARD
          </button>
          
          <div className={styles.sessionInfo}>
            {currentSessionId && currentSession ? (
              <>
                <span className={styles.sessionTitleDisplay}>{currentSession.title}</span>
                {courseId && (
                  <span className={styles.courseBadge}>
                    COURSE CONTEXT
                  </span>
                )}
              </>
            ) : (
              <span className={styles.newChatLabel}>NEW CHAT</span>
            )}
          </div>

          <div className={styles.topBarActions}>
            <SessionStatus isConnected={isConnected} isSessionSwitching={isSessionSwitching} />
            {messages.length > 0 && (
              <button className={styles.clearBtn} onClick={handleClearConversation} title="Clear conversation">
                CLEAR
              </button>
            )}
          </div>
        </header>

        {/* Messages Area */}
        <div className={styles.messagesWrapper}>
          <div className={styles.messagesContainer}>
            {messages.length === 0 && !isThinking ? (
              <div className={styles.emptyState}>
                <div className={styles.emptyStateContent}>
                  <h1 className={styles.emptyTitle}>CourseForge Chat</h1>
                  <p className={styles.emptySubtitle}>
                    Ask anything about your course. Get instant, contextual answers.
                  </p>
                  <div className={styles.starterSuggestions}>
                    <button className={styles.starterBtn} onClick={() => setInputValue('Explain the key concepts from Week 1')}>
                      Explain key concepts
                    </button>
                    <button className={styles.starterBtn} onClick={() => setInputValue('What are the best practices for this topic?')}>
                      Best practices
                    </button>
                    <button className={styles.starterBtn} onClick={() => setInputValue('Give me a practical example I can try')}>
                      Practical example
                    </button>
                    <button className={styles.starterBtn} onClick={() => setInputValue('Quiz me on what I have learned so far')}>
                      Quiz me
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <>
                {/* Course Management Components - Day Content Only */}
                <AnimatePresence>
                  {/* Day Content Card */}
                  {dayContent && dayContent.status === 'ready' && (
                    <motion.div
                      className={styles.dayContentWrapper}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -20 }}
                    >
                      <DayContentCard
                        courseName={dayContent.course_name}
                        weekNumber={dayContent.week_number}
                        dayNumber={dayContent.day_number}
                        dayTitle={dayContent.day_title}
                        theoryContent={dayContent.theory_content}
                        codeContent={dayContent.code_content}
                        quizzes={dayContent.quizzes}
                        tasks={dayContent.tasks}
                      />
                      <button
                        className={styles.closeDayContentBtn}
                        onClick={() => setDayContent(null)}
                      >
                        × Close
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>

                {(() => {
                  // Deduplicate messages by ID before rendering
                  const seenIds = new Set();
                  const uniqueMessages = messages.filter(msg => {
                    if (seenIds.has(msg.id)) {
                      console.warn('[CHAT] Duplicate message ID detected:', msg.id);
                      return false;
                    }
                    seenIds.add(msg.id);
                    return true;
                  });

                  return uniqueMessages
                    .filter(msg =>
                      msg.content !== '[Session created]' &&
                      msg.content !== 'New Chat' &&
                      msg.role !== 'system'
                    )
                    .map((msg) => {
                      // Check if this message has a pending action (confirmation dialog)
                      const hasPendingAction = pendingAction && pendingAction.type === 'delete' &&
                        msg.content.includes('Are you sure') && msg.role === 'assistant';

                      return (
                      <motion.div
                        key={msg.id}
                        className={`${styles.message} ${styles[msg.role]}`}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3 }}
                        onMouseEnter={() => setHoveredMessageId(msg.id)}
                        onMouseLeave={() => setHoveredMessageId(null)}
                      >
                        <div className={styles.messageInner}>
                        {msg.role === 'assistant' && (
                          <div className={styles.aiAvatar}>
                            <span className={styles.aiMonogram}>CF</span>
                          </div>
                        )}

                        <div className={styles.messageBody}>
                          <div className={styles.messageHeader}>
                            <span className={styles.messageRole}>
                              {msg.role === 'user' ? 'YOU' : 'COURSEFORGE AI'}
                            </span>
                            <span className={styles.messageDate}>
                              {msg.date || msg.timestamp.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                            </span>
                          </div>
                          <div className={styles.messageContent}>
                            {editingMessageId === msg.id && msg.role === 'user' ? (
                              <div className={styles.editContainer}>
                                <textarea
                                  className={styles.editTextarea}
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                      e.preventDefault();
                                      handleSaveEdit(msg.id);
                                    }
                                    if (e.key === 'Escape') {
                                      handleCancelEdit();
                                    }
                                  }}
                                  autoFocus
                                />
                                <div className={styles.editActions}>
                                  <button
                                    className={styles.editSaveBtn}
                                    onClick={() => handleSaveEdit(msg.id)}
                                  >
                                    SAVE
                                  </button>
                                  <button
                                    className={styles.editCancelBtn}
                                    onClick={handleCancelEdit}
                                  >
                                    CANCEL
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <MarkdownRenderer content={msg.content} />
                            )}
                          </div>

                          {/* Confirmation Buttons for Delete Action */}
                          {hasPendingAction && (
                            <div className={styles.confirmationButtons}>
                              <button
                                className={styles.confirmationCancelBtn}
                                onClick={handlePendingActionCancel}
                              >
                                Cancel
                              </button>
                              <button
                                className={styles.confirmationConfirmBtn}
                                onClick={handlePendingActionConfirm}
                              >
                                Confirm Delete
                              </button>
                            </div>
                          )}

                          {/* Message Actions */}
                          <AnimatePresence>
                            {hoveredMessageId === msg.id && (
                              <motion.div
                                className={styles.messageActions}
                                initial={{ opacity: 0, y: 5 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: 5 }}
                              >
                                <button
                                  className={styles.actionBtn}
                                  onClick={() => handleCopyMessage(msg.content, msg.id)}
                                  title="Copy"
                                >
                                  {copiedMessageId === msg.id ? '✓ COPIED' : 'COPY'}
                                </button>
                                {msg.role === 'user' && (
                                  <button
                                    className={styles.actionBtn}
                                    onClick={() => handleEditMessage(msg.content, msg.id)}
                                    title="Edit"
                                  >
                                    EDIT
                                  </button>
                                )}
                                {msg.role === 'assistant' && (
                                  <>
                                    <button
                                      className={styles.actionBtn}
                                      onClick={handleRegenerate}
                                      title="Regenerate"
                                    >
                                      REGENERATE
                                    </button>
                                  </>
                                )}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </div>
                    </motion.div>
                  );
                  });
                })()}

                {/* Thinking Indicator */}
                {isThinking && (
                  <motion.div
                    className={`${styles.message} ${styles.thinking}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <div className={styles.messageInner}>
                      <div className={styles.aiAvatar}>
                        <span className={styles.aiMonogram}>CF</span>
                      </div>
                      <div className={styles.thinkingContent}>
                        <span className={styles.thinkingText}>THINKING</span>
                        <span className={styles.thinkingDots}>
                          <motion.span
                            className={styles.dot}
                            animate={{ opacity: [0.3, 1, 0.3] }}
                            transition={{ duration: 1.5, repeat: Infinity, delay: 0 }}
                          />
                          <motion.span
                            className={styles.dot}
                            animate={{ opacity: [0.3, 1, 0.3] }}
                            transition={{ duration: 1.5, repeat: Infinity, delay: 0.2 }}
                          />
                          <motion.span
                            className={styles.dot}
                            animate={{ opacity: [0.3, 1, 0.3] }}
                            transition={{ duration: 1.5, repeat: Infinity, delay: 0.4 }}
                          />
                        </span>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Web Search Status */}
                <WebSearchStatus webSearchState={webSearchState} />

                {/* Course Generation Progress - Rendered as part of message flow */}
                {generatingCourseId && generatingCourse && (
                  <motion.div
                    key={`progress-${generatingCourseId}`}
                    className={styles.message}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <div className={styles.messageInner}>
                      <div className={styles.aiAvatar}>
                        <span className={styles.aiMonogram}>CF</span>
                      </div>
                      <div className={styles.messageBody}>
                        <div className={styles.messageHeader}>
                          <span className={styles.messageRole}>COURSEFORGE AI</span>
                          <span className={styles.messageDate}>
                            {new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                          </span>
                        </div>
                        <div className={styles.messageContent}>
                          <ChatGenerationProgress
                            courseId={generatingCourseId}
                            courseName={generatingCourse.courseName || generatingCourse.topic || 'Course'}
                            onComplete={() => {
                              console.log('[Chat] Generation complete, removing from chat view');
                            }}
                            onCancel={async () => {
                              console.log('[Chat] Generation cancelled by user');
                              // Add cancellation message to chat
                              const cancelMessage: ChatMessage = {
                                id: `ai-${Date.now()}`,
                                role: 'assistant',
                                content: `⚠️ **Course Generation Cancelled**\n\nThe generation for '${generatingCourse.courseName || 'this course'}' has been stopped. You can start a new course anytime!`,
                                timestamp: new Date(),
                              };
                              setMessages([...messages, cancelMessage]);

                              // Persist cancellation message to database
                              let sessionIdToUse = currentSessionId;
                              if (!sessionIdToUse) {
                                sessionIdToUse = await createSession({ course_id: courseId });
                              }
                              if (sessionIdToUse) {
                                persistConversation(sessionIdToUse, `Cancel generation of ${generatingCourse.courseName}`, cancelMessage.content);
                              }
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </>
            )}
          </div>
        </div>

        {/* Course Creation Form - Above Input Box */}
        <AnimatePresence>
          {courseFormSchema && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              <CourseCreationForm
                schema={courseFormSchema}
                onSubmit={handleCourseFormSubmit}
                onCancel={handleCourseFormCancel}
                isSubmitting={isChatCourseLoading}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Course Update Modal */}
        <CourseUpdateModal
          isOpen={isUpdateModalOpen}
          onClose={() => {
            setIsUpdateModalOpen(false);
            setPendingUpdateData(null);
          }}
          onSubmit={async (updateType, options) => {
            if (!pendingUpdateData) return;

            // Build API data based on update type
            const apiData: any = {
              update_type: updateType,
              user_query: pendingUpdateData.user_query,
              web_search_enabled: webSearchEnabled,  // Use actual toggle state
            };

            if (updateType === 'percentage' && options.percentage) {
              apiData.percentage = options.percentage;
            } else if (updateType === 'extend' && options.extendWeeks) {
              apiData.extend_weeks = options.extendWeeks;
            } else if (updateType === 'compact' && options.targetWeeks) {
              apiData.target_weeks = options.targetWeeks;
            }

            // Execute the update with selected type
            const result = await executeCourseUpdate(pendingUpdateData.course_id, apiData);

            if (result) {
              const updateData: any = result;
              const weeksToUpdate = updateData?.data?.weeks_to_update || [];
              const newDuration = updateData?.data?.new_duration_weeks || 0;

              // Add updating course to generation progress
              addGeneratingCourse({
                courseId: pendingUpdateData.course_id,
                courseName: pendingUpdateData.course_name,
                progress: 0,
                completed_days: 0,
                total_days: newDuration * 5,
                generation_status: 'updating',
                current_stage: 'Starting update...',
                topic: pendingUpdateData.course_name,
                createdBySessionId: currentSessionId || undefined,
              });

              console.log('[CRUD] Course update started:', pendingUpdateData.course_id, 'type:', updateType, 'options:', options);

              // Clear modal state
              setIsUpdateModalOpen(false);
              setPendingUpdateData(null);
            }
          }}
          courseName={pendingUpdateData?.course_name || ''}
          currentDurationWeeks={pendingUpdateData?.current_duration_weeks || 4}
          isSubmitting={isCourseUpdating}
        />

        {/* Input Area */}
        <div className={styles.inputWrapper}>
          <div className={styles.inputContainer}>
            {courseId && (
              <div className={styles.contextIndicator}>
                <span className={styles.contextDot}>●</span>
                <span className={styles.contextText}>Course context active</span>
              </div>
            )}

            <div className={styles.inputWithToggle}>
              <textarea
                ref={inputRef}
                className={styles.input}
                placeholder="Message CourseForge..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={Boolean(!isConnected || isThinking)}
              />
            </div>

            <div className={styles.inputFooter}>
              <div className={styles.footerToggles}>
                <WebSearchToggle
                  enabled={webSearchEnabled}
                  onToggle={() => setWebSearchEnabled(!webSearchEnabled)}
                  disabled={Boolean(isThinking)}
                />
                <CrudToggle
                  enabled={crudEnabled}
                  onToggle={() => setCrudEnabled(!crudEnabled)}
                  disabled={Boolean(isThinking)}
                />
              </div>
              <span className={styles.charCount}>
                {inputValue.length} / 4000
              </span>
              <button
                className={`${styles.sendBtn} ${(!inputValue.trim() || !isConnected || isThinking) ? styles.disabled : ''}`}
                onClick={handleSend}
                disabled={Boolean(!inputValue.trim() || !isConnected || isThinking)}
              >
                <span className={styles.sendIcon}>➤</span>
              </button>
            </div>
          </div>
          <div className={styles.inputHint}>
            <kbd>ENTER</kbd> to send · <kbd>SHIFT</kbd> + <kbd>ENTER</kbd> for new line
          </div>
        </div>
      </main>

      {/* Context Menu Popup */}
      <AnimatePresence>
        {contextMenu.isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              className={styles.contextMenuBackdrop}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={closeContextMenu}
            />
            
            {/* Menu */}
            <motion.div
              ref={menuRef}
              className={styles.contextMenu}
              style={{ left: contextMenu.x, top: contextMenu.y }}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
            >
              <div className={styles.contextMenuHeader}>
                <span className={styles.contextMenuTitle}>{contextMenu.sessionTitle}</span>
              </div>
              <div className={styles.contextMenuDivider} />
              <button className={styles.contextMenuItem} onClick={handleRename}>
                <span className={styles.contextMenuIcon}>R</span>
                Rename
              </button>
              <button className={styles.contextMenuItem} onClick={handleArchive}>
                <span className={styles.contextMenuIcon}>A</span>
                Archive
              </button>
              <button className={`${styles.contextMenuItem} ${styles.deleteItem}`} onClick={handleDelete}>
                <span className={styles.contextMenuIcon}>D</span>
                Delete
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Note: Generation progress is now shown in-chat via ChatGenerationProgress component */}
      {/* Toast is handled globally by GlobalGenerationToastWrapper for when user navigates away */}

      {/* Rename Modal */}
      <AnimatePresence>
        {isRenameModalOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              className={styles.modalBackdrop}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsRenameModalOpen(false)}
            />
            
            {/* Modal */}
            <motion.div
              className={styles.renameModal}
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
            >
              <h3 className={styles.modalTitle}>Rename Chat</h3>
              <form onSubmit={handleRenameSubmit}>
                <input
                  type="text"
                  className={styles.modalInput}
                  value={renameTitle}
                  onChange={(e) => setRenameTitle(e.target.value)}
                  placeholder="Enter new title"
                  autoFocus
                  maxLength={100}
                />
                <div className={styles.modalActions}>
                  <button
                    type="button"
                    className={`${styles.modalBtn} ${styles.modalBtnSecondary}`}
                    onClick={() => setIsRenameModalOpen(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className={`${styles.modalBtn} ${styles.modalBtnPrimary}`}
                    disabled={!renameTitle.trim()}
                  >
                    Rename
                  </button>
                </div>
              </form>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
