'use client';

import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import styles from './Testimonials.module.css';

const testimonials = [
  {
    id: 1,
    quote: 'Generated a full Python course in 30 seconds. The daily quizzes actually make you retain things.',
    author: 'ARJUN K.',
    role: 'Software Engineer',
    dark: false,
  },
  {
    id: 2,
    quote: 'Finally an AI learning tool that doesn\'t feel generic. It actually knows what I\'m struggling with.',
    author: 'PRIYA M.',
    role: 'CS Student',
    dark: false,
  },
  {
    id: 3,
    quote: 'The RAG pipeline means the answers are actually grounded in real textbook content. Impressive.',
    author: 'RAVI S.',
    role: 'Backend Developer',
    dark: false,
  },
  {
    id: 4,
    quote: 'This is what learning should feel like.',
    author: 'ANANYA T.',
    role: 'Bootcamp Graduate',
    dark: true,
  },
];

export default function Testimonials() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });
  const containerRef = useRef<HTMLDivElement>(null);

  return (
    <section id="testimonials" className={styles.section} ref={ref}>
      <div className={styles.container}>
        <div className={styles.label}>── 06 / WHAT PEOPLE SAY ──</div>
        
        <motion.h2
          className={styles.title}
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
        >
          Real feedback.
        </motion.h2>

        <motion.div
          ref={containerRef}
          className={styles.scrollContainer}
          drag="x"
          dragConstraints={{ left: -400, right: 0 }}
          dragElastic={0.1}
          whileDrag={{ cursor: 'grabbing' }}
        >
          {testimonials.map((testimonial, index) => (
            <motion.div
              key={testimonial.id}
              className={`${styles.card} ${testimonial.dark ? styles.darkCard : ''}`}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              whileHover={{ y: -4 }}
            >
              {testimonial.dark && (
                <span className={styles.bigQuote}>"</span>
              )}
              <p className={styles.quote}>{testimonial.quote}</p>
              <div className={styles.author}>
                <span className={styles.authorName}>── {testimonial.author}</span>
                <span className={styles.authorRole}>· {testimonial.role}</span>
              </div>
            </motion.div>
          ))}
        </motion.div>

        <div className={styles.dragHint}>
          ← DRAG →
        </div>
      </div>
    </section>
  );
}
