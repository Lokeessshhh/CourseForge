'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import styles from './CTA.module.css';

export default function CTA() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section className={styles.section} ref={ref}>
      <div className={styles.container}>
        <svg className={styles.star1} viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">
          <path d="M15 5 L17 12 L24 12 L18 17 L20 24 L15 20 L10 24 L12 17 L6 12 L13 12 Z" stroke="#000" strokeWidth="2" fill="none"/>
        </svg>
        <svg className={styles.star2} viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">
          <path d="M15 5 L17 12 L24 12 L18 17 L20 24 L15 20 L10 24 L12 17 L6 12 L13 12 Z" stroke="#000" strokeWidth="2" fill="none"/>
        </svg>

        <motion.h2
          className={styles.title}
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
        >
          Ready to learn?
        </motion.h2>

        <motion.p
          className={styles.subtitle}
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          Your AI course is one prompt away.
        </motion.p>

        <motion.a
          href="/login"
          className={styles.button}
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.2 }}
          whileHover={{ x: -4, y: -4 }}
        >
          START FOR FREE →
        </motion.a>

        <motion.p
          className={styles.note}
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          No credit card required · Powered by CourseForge AI
        </motion.p>
      </div>
    </section>
  );
}
