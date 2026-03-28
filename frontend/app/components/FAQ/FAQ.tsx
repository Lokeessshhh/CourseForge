'use client';

import { useState, useRef } from 'react';
import { motion, AnimatePresence, useInView } from 'framer-motion';
import styles from './FAQ.module.css';

const faqs = [
  {
    question: 'How is this different from ChatGPT?',
    answer: 'CourseForge generates structured, week-by-week courses with daily lessons, quizzes, and certificates — not just chat answers. Our model is fine-tuned specifically for coding education.',
  },
  {
    question: 'What topics can I learn?',
    answer: 'Any programming topic — Python, JavaScript, React, DSA, Machine Learning, Django, and more. The AI adapts to any technical subject.',
  },
  {
    question: 'How long does course generation take?',
    answer: 'Under 30 seconds for the course structure. Full content (lessons + quizzes) is ready within 2-3 minutes, generated in parallel.',
  },
  {
    question: 'Is my progress saved?',
    answer: 'Yes. Everything is stored — your progress, quiz scores, knowledge state, and streak. Resume exactly where you left off.',
  },
  {
    question: 'How do certificates work?',
    answer: 'Complete all lessons + pass all weekly tests. A PDF certificate is auto-generated with your name, course, score, and completion date.',
  },
  {
    question: 'Is it free?',
    answer: 'Currently in beta — free to use.',
  },
];

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  const toggleFaq = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <section id="faq" className={styles.section} ref={ref}>
      <div className={styles.container}>
        <div className={styles.label}>── 07 / FAQ ──</div>
        
        <motion.h2
          className={styles.title}
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
        >
          Answers.
        </motion.h2>

        <div className={styles.faqList}>
          {faqs.map((faq, index) => (
            <motion.div
              key={index}
              className={styles.faqItem}
              initial={{ opacity: 0, y: 20 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.4, delay: index * 0.05 }}
            >
              <button
                className={styles.question}
                onClick={() => toggleFaq(index)}
              >
                <span>{faq.question}</span>
                <span className={styles.icon}>
                  {openIndex === index ? '×' : '+'}
                </span>
              </button>
              
              <AnimatePresence>
                {openIndex === index && (
                  <motion.div
                    className={styles.answer}
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <p>{faq.answer}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
