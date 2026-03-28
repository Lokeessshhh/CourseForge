'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import styles from './HowItWorks.module.css';

const steps = [
  {
    num: '01',
    title: 'DESCRIBE YOUR GOAL',
    desc: 'Tell us what you want to learn and your current skill level.',
  },
  {
    num: '02',
    title: 'AI BUILDS YOUR COURSE',
    desc: 'Fine-tuned Qwen 7B generates a full week-by-week curriculum.',
  },
  {
    num: '03',
    title: 'LEARN EVERY DAY',
    desc: 'Theory + code examples + quizzes. Unlock each day by passing the quiz.',
  },
  {
    num: '04',
    title: 'EARN YOUR CERTIFICATE',
    desc: 'Complete the course and get a verified PDF certificate.',
  },
];

export default function HowItWorks() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section id="how-it-works" className={styles.section} ref={ref}>
      <div className={styles.container}>
        <div className={styles.label}>── 02 / PROCESS ──</div>
        
        <motion.h2
          className={styles.title}
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
        >
          Four steps to mastery.
        </motion.h2>

        <div className={styles.grid}>
          {steps.map((step, index) => (
            <motion.div
              key={step.num}
              className={styles.card}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              whileHover={{ x: -4, y: -4 }}
            >
              <span className={styles.number}>{step.num}</span>
              <h3 className={styles.cardTitle}>{step.title}</h3>
              <p className={styles.cardDesc}>{step.desc}</p>
              
              {index < steps.length - 1 && (
                <svg className={styles.arrow} viewBox="0 0 40 20" xmlns="http://www.w3.org/2000/svg">
                  <path d="M5 10 L30 10 M25 5 L30 10 L25 15" stroke="#000" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
