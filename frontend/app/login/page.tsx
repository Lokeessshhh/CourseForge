'use client';

import { useState, useEffect } from 'react';
import { useUser } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import SignInForm from '@/app/components/auth/SignInForm/SignInForm';
import SignUpForm from '@/app/components/auth/SignUpForm/SignUpForm';
import styles from './page.module.css';

const terminalMessages = [
  '> Python course: READY',
  '> 20 lessons: GENERATED',
  '> Quiz score: 87%',
  '> Certificate: UNLOCKED',
];

export default function LoginPage() {
  const [activeTab, setActiveTab] = useState<'signin' | 'signup'>('signin');
  const [messageIndex, setMessageIndex] = useState(0);
  const [displayedText, setDisplayedText] = useState('');
  const [charIndex, setCharIndex] = useState(0);
  
  const { isLoaded, isSignedIn } = useUser();
  const router = useRouter();

  // Redirect if already logged in
  useEffect(() => {
    if (isLoaded && isSignedIn) {
      router.push('/dashboard');
    }
  }, [isLoaded, isSignedIn, router]);

  // Typewriter effect
  useEffect(() => {
    const currentMessage = terminalMessages[messageIndex];
    
    if (charIndex < currentMessage.length) {
      const timer = setTimeout(() => {
        setDisplayedText(currentMessage.slice(0, charIndex + 1));
        setCharIndex(charIndex + 1);
      }, 50);
      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => {
        setCharIndex(0);
        setDisplayedText('');
        setMessageIndex((messageIndex + 1) % terminalMessages.length);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [charIndex, messageIndex]);

  // Show nothing while checking auth or redirecting
  if (!isLoaded || isSignedIn) {
    return null;
  }

  return (
    <div className={styles.page}>
      {/* Left Panel - Black */}
      <motion.div
        className={styles.leftPanel}
        initial={{ x: -100, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <div className={styles.leftContent}>
          <motion.div
            className={styles.logo}
            initial={{ y: -20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            ► COURSEFORGE
          </motion.div>

          <motion.h1
            className={styles.heading}
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            Your AI tutor is waiting.
          </motion.h1>

          <motion.p
            className={styles.subheading}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
          >
            Generate personalized coding courses in under 30 seconds.
          </motion.p>

          <motion.div
            className={styles.stats}
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.5 }}
          >
            <div className={styles.stat}>87.0 / HUMANEVAL</div>
            <div className={styles.stat}>325 / BOOKS</div>
            <div className={styles.stat}>7B / MODEL</div>
          </motion.div>

          <motion.div
            className={styles.terminal}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
          >
            <span className={styles.terminalText}>{displayedText}</span>
            <span className={styles.cursor}>▌</span>
          </motion.div>

          <motion.div
            className={styles.footer}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.7 }}
          >
            Fine-tuned Qwen 7B · AMD MI300x ROCm
          </motion.div>
        </div>
      </motion.div>

      {/* Right Panel - White */}
      <motion.div
        className={styles.rightPanel}
        initial={{ x: 100, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <div className={styles.rightContent}>
          {/* Tab Switcher */}
          <div className={styles.tabs}>
            <motion.button
              className={`${styles.tab} ${activeTab === 'signin' ? styles.active : ''}`}
              onClick={() => setActiveTab('signin')}
              layout
            >
              SIGN IN
            </motion.button>
            <motion.button
              className={`${styles.tab} ${activeTab === 'signup' ? styles.active : ''}`}
              onClick={() => setActiveTab('signup')}
              layout
            >
              SIGN UP
            </motion.button>
          </div>

          {/* Form Content */}
          <div className={styles.formContainer}>
            <AnimatePresence mode="wait">
              {activeTab === 'signin' ? (
                <SignInForm
                  key="signin"
                  onSwitchToSignUp={() => setActiveTab('signup')}
                />
              ) : (
                <SignUpForm
                  key="signup"
                  onSwitchToSignIn={() => setActiveTab('signin')}
                />
              )}
            </AnimatePresence>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
