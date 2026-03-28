'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import styles from './ProblemSolution.module.css';

const oldWay = [
  'Generic tutorials not suited to your level',
  'No structure, no progression',
  'No feedback on what you\'re missing',
  'You forget 90% within a week',
];

const newWay = [
  'AI course built around YOUR goals',
  'Week-by-week structured progression',
  'Daily quizzes that adapt to weak spots',
  'Certificate when you actually finish',
];

export default function ProblemSolution() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section className={styles.section} ref={ref}>
      <div className={styles.container}>
        <div className={styles.label}>── 01 / THE PROBLEM ──</div>

        <div className={styles.grid}>
          <motion.div
            className={styles.left}
            initial={{ opacity: 0, x: -40 }}
            animate={isInView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.5 }}
          >
            <h2 className={styles.title}>Learning to code is broken.</h2>
            <ul className={styles.list}>
              {oldWay.map((item, index) => (
                <li key={index} className={styles.item}>
                  <span className={styles.x}>✗</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            className={styles.right}
            initial={{ opacity: 0, x: 40 }}
            animate={isInView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <h2 className={styles.titleWhite}>CourseForge fixes this.</h2>
            <ul className={styles.listWhite}>
              {newWay.map((item, index) => (
                <li key={index} className={styles.itemWhite}>
                  <span className={styles.check}>✓</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
