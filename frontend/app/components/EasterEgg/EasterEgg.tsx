'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useKeySequence } from '@/app/hooks';
import styles from './EasterEgg.module.css';

const KONAMI_CODE = ['UP', 'UP', 'DOWN', 'DOWN', 'LEFT', 'RIGHT', 'LEFT', 'RIGHT', 'B', 'A'];

export default function EasterEgg() {
  const [showEasterEgg, setShowEasterEgg] = useState(false);

  useKeySequence(KONAMI_CODE, () => {
    setShowEasterEgg(true);
  });

  const dismiss = () => setShowEasterEgg(false);

  return (
    <AnimatePresence>
      {showEasterEgg && (
        <motion.div
          className={styles.overlay}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={dismiss}
        >
          <motion.div
            className={styles.content}
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.5, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 200 }}
          >
            <h2 className={styles.title}>YOU FOUND THE RAG PIPELINE</h2>
            <pre className={styles.ascii}>
{`
    ╭─────────────────╮
    │  🤖 STUDYING... │
    ╰────┬────────────╯
         │
    ┌────▼────┐
    │  BOOKS  │
    │ 325+ 📚 │
    └────┬────┘
         │
    ┌────▼────────────────┐
    │  RAG PIPELINE       │
    │  ┌──────────────┐   │
    │  │ HYDE + RETRIEVE│  │
    │  └──────────────┘   │
    │  ┌──────────────┐   │
    │  │ RERANKER V2   │   │
    │  └──────────────┘   │
    └─────────────────────┘
         │
    ┌────▼────┐
    │ OUTPUT  │
    │ = GRAD  │
    └─────────┘
`}
            </pre>
            <p className={styles.hint}>Click anywhere to dismiss</p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
