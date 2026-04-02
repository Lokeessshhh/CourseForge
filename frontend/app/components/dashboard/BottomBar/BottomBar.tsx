'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import CoursePopup from '../CoursePopup/CoursePopup';
import styles from './BottomBar.module.css';

type Mode = 'course' | 'chat';

export default function BottomBar() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('course');
  const [showPopup, setShowPopup] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const isConnected = true;

  const handleInputFocus = () => {
    if (mode === 'course') {
      setShowPopup(true);
    }
  };

  const handleClosePopup = () => {
    setShowPopup(false);
  };

  const handleToggleMode = () => {
    setMode(mode === 'course' ? 'chat' : 'course');
    setShowPopup(false);
    setInputValue('');
  };

  const handleChatSubmit = () => {
    if (inputValue.trim() && isConnected) {
      const q = inputValue.trim();
      setInputValue('');
      router.push(`/dashboard/chat?draft=${encodeURIComponent(q)}`);
    }
  };

  const handleGoToChat = () => {
    router.push('/dashboard/chat');
  };

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowPopup(false);
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, []);

  useEffect(() => {
    const openFromDashboard = () => {
      setMode('course');
      setShowPopup(true);
      try {
        localStorage.removeItem('dashboard:create_course');
      } catch {
        // no-op
      }
    };

    const handleFlag = () => {
      try {
        if (localStorage.getItem('dashboard:create_course') === '1') {
          openFromDashboard();
        }
      } catch {
        // no-op
      }
    };

    window.addEventListener('dashboard:create_course', openFromDashboard);
    window.addEventListener('focus', handleFlag);
    handleFlag();
    return () => {
      window.removeEventListener('dashboard:create_course', openFromDashboard);
      window.removeEventListener('focus', handleFlag);
    };
  }, []);

  return (
    <div className={styles.bottomBar}>
      <div className={styles.container}>
        {/* Input Bar */}
        <div className={styles.inputWrapper}>
          <motion.div
            className={styles.inputBar}
            layout
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          >
            <span className={styles.icon}>
              {mode === 'course' ? 'MODE: COURSE' : 'MODE: AI'}
            </span>
            
            {mode === 'chat' ? (
              <>
                <input
                  ref={inputRef}
                  type="text"
                  className={styles.input}
                  placeholder={'Ask your AI tutor anything...'}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleChatSubmit();
                    }
                  }}
                />
                <button 
                  className={styles.actionBtn} 
                  onClick={handleChatSubmit}
                  disabled={!isConnected || !inputValue.trim()}
                >
                  SEND →
                </button>
              </>
            ) : (
              <>
                <input
                  ref={inputRef}
                  type="text"
                  className={styles.input}
                  placeholder="What do you want to learn?"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onFocus={handleInputFocus}
                />
                <button className={styles.actionBtn} onClick={() => setShowPopup(true)}>
                  CREATE →
                </button>
              </>
            )}
          </motion.div>

          {/* Mode Toggle */}
          <motion.button
            className={styles.toggleBtn}
            onClick={handleToggleMode}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {mode === 'course' ? '◄' : '►'}
          </motion.button>
        </div>

        {/* Mini Chat Preview */}
        <AnimatePresence>
          {mode === 'chat' && (
            <motion.div
              className={styles.chatPreview}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
            >
              <button className={styles.expandBtn} onClick={handleGoToChat}>
                OPEN CHAT →
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Course Popup */}
        <AnimatePresence>
          {showPopup && mode === 'course' && (
            <CoursePopup onClose={handleClosePopup} />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
