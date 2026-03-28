'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import SignInForm from '../SignInForm/SignInForm';
import SignUpForm from '../SignUpForm/SignUpForm';
import styles from './AuthPage.module.css';

const stats = [
  { value: '87.0', label: 'HUMANEVAL' },
  { value: '325', label: 'BOOKS' },
  { value: '7B', label: 'MODEL' },
];

export default function AuthPage() {
  const [activeTab, setActiveTab] = useState<'signin' | 'signup'>('signin');

  return (
    <div className={styles.page}>
      {/* LEFT PANEL */}
      <div className={styles.left}>
        <div className={styles.leftContent}>
          <span className={styles.brand}>► COURSEFORGE</span>

          <motion.h1
            className={styles.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            Your AI tutor is waiting.
          </motion.h1>

          <motion.p
            className={styles.subtitle}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            Generate a personalized coding course in under 30 seconds.
          </motion.p>

          <div className={styles.stats}>
            {stats.map((stat, index) => (
              <motion.div
                key={stat.label}
                className={styles.statBox}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.2 + index * 0.1 }}
              >
                <span className={styles.statValue}>{stat.value}</span>
                <span className={styles.statDivider}>/</span>
                <span className={styles.statLabel}>{stat.label}</span>
              </motion.div>
            ))}
          </div>

          <svg className={styles.illustration} viewBox="0 0 200 150" xmlns="http://www.w3.org/2000/svg">
            {/* Person */}
            <circle cx="60" cy="50" r="15" stroke="#fff" strokeWidth="2" fill="none"/>
            <line x1="60" y1="65" x2="60" y2="100" stroke="#fff" strokeWidth="2"/>
            <line x1="60" y1="100" x2="45" y2="130" stroke="#fff" strokeWidth="2"/>
            <line x1="60" y1="100" x2="75" y2="130" stroke="#fff" strokeWidth="2"/>
            <line x1="60" y1="75" x2="40" y2="85" stroke="#fff" strokeWidth="2"/>
            <line x1="60" y1="75" x2="80" y2="90" stroke="#fff" strokeWidth="2"/>
            
            {/* Laptop */}
            <rect x="85" y="85" width="60" height="40" stroke="#fff" strokeWidth="2" fill="none"/>
            <line x1="80" y1="125" x2="150" y2="125" stroke="#fff" strokeWidth="2"/>
            
            {/* Code on screen */}
            <line x1="95" y1="95" x2="130" y2="95" stroke="#fff" strokeWidth="1.5"/>
            <line x1="95" y1="105" x2="120" y2="105" stroke="#fff" strokeWidth="1.5"/>
            <line x1="95" y1="115" x2="135" y2="115" stroke="#fff" strokeWidth="1.5"/>
            
            {/* Speech bubble */}
            <path d="M150 30 L180 30 Q190 30 190 40 L190 60 Q190 70 180 70 L160 70 L150 85 L155 70 L150 70 Q140 70 140 60 L140 40 Q140 30 150 30" stroke="#fff" strokeWidth="2" fill="none"/>
            <text x="152" y="55" fill="#fff" fontSize="14" fontFamily="monospace">&lt;/&gt;</text>
          </svg>

          <span className={styles.techCredit}>Fine-tuned Qwen 7B · AMD MI300x ROCm</span>
        </div>
      </div>

      {/* RIGHT PANEL */}
      <div className={styles.right}>
        <div className={styles.rightContent}>
          {/* TABS */}
          <div className={styles.tabs}>
            <button
              className={`${styles.tab} ${activeTab === 'signin' ? styles.active : ''}`}
              onClick={() => setActiveTab('signin')}
            >
              SIGN IN
            </button>
            <button
              className={`${styles.tab} ${activeTab === 'signup' ? styles.active : ''}`}
              onClick={() => setActiveTab('signup')}
            >
              SIGN UP
            </button>
          </div>

          <div className={styles.tabLabel}>
            {activeTab === 'signin' ? '── WELCOME BACK ──' : '── JOIN COURSEFORGE ──'}
          </div>

          {/* FORMS */}
          <AnimatePresence mode="wait">
            {activeTab === 'signin' ? (
              <motion.div
                key="signin"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
              >
                <SignInForm onSwitchToSignUp={() => setActiveTab('signup')} />
              </motion.div>
            ) : (
              <motion.div
                key="signup"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                <SignUpForm onSwitchToSignIn={() => setActiveTab('signin')} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
