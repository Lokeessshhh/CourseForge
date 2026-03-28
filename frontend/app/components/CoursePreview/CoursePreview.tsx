'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import styles from './CoursePreview.module.css';

const durations = ['1 WEEK', '2 WEEKS', '1 MONTH', '3 MONTHS'];
const skills = ['BEGINNER', 'INTERMEDIATE', 'ADVANCED'];

const courseData: Record<string, string[]> = {
  'Python Programming': [
    '✓ Week 1: Python Fundamentals',
    '  Day 1: Variables & Data Types',
    '  Day 2: Control Flow',
    '  Day 3: Functions',
    '  Day 4: Lists & Dictionaries',
    '  Day 5: Week Review',
    '✓ Week 2: Intermediate Python',
    '  Day 1: File Handling',
    '  Day 2: Error Handling',
    '  Day 3: OOP Basics',
    '  Day 4: Modules & Packages',
    '  Day 5: Mini Project',
    '✓ Week 3: Advanced Concepts',
    '  Day 1: Decorators',
    '  Day 2: Generators',
    '  Day 3: Context Managers',
    '  Day 4: Testing',
    '  Day 5: Final Project',
  ],
  'JavaScript Basics': [
    '✓ Week 1: JS Fundamentals',
    '  Day 1: Variables & Types',
    '  Day 2: Operators & Expressions',
    '  Day 3: Conditionals',
    '  Day 4: Loops',
    '  Day 5: Week Review',
    '✓ Week 2: Functions & Objects',
    '  Day 1: Function Basics',
    '  Day 2: Arrow Functions',
    '  Day 3: Objects',
    '  Day 4: Arrays',
    '  Day 5: DOM Basics',
  ],
  'default': [
    '✓ Week 1: Foundations',
    '  Day 1: Introduction',
    '  Day 2: Core Concepts',
    '  Day 3: Basic Syntax',
    '  Day 4: First Exercises',
    '  Day 5: Review & Practice',
    '✓ Week 2: Building Skills',
    '  Day 1: Intermediate Topics',
    '  Day 2: Hands-on Practice',
    '  Day 3: Common Patterns',
    '  Day 4: Mini Challenges',
    '  Day 5: Weekly Assessment',
  ],
};

export default function CoursePreview() {
  const [topic, setTopic] = useState('Python Programming');
  const [duration, setDuration] = useState('2 WEEKS');
  const [skill, setSkill] = useState('BEGINNER');
  const [isGenerating, setIsGenerating] = useState(false);
  const [outputLines, setOutputLines] = useState<string[]>([]);
  const [showStats, setShowStats] = useState(false);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  const handleGenerate = () => {
    setIsGenerating(true);
    setOutputLines([]);
    setShowStats(false);

    const lines = courseData[topic] || courseData['default'];
    
    lines.forEach((line, index) => {
      setTimeout(() => {
        setOutputLines(prev => [...prev, line]);
        
        if (index === lines.length - 1) {
          setTimeout(() => {
            setIsGenerating(false);
            setShowStats(true);
          }, 300);
        }
      }, index * 150);
    });
  };

  return (
    <section id="preview" className={styles.section} ref={ref}>
      <div className={styles.container}>
        <div className={styles.label}>── 05 / LIVE PREVIEW ──</div>
        
        <motion.h2
          className={styles.title}
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
        >
          Watch it build in real time.
        </motion.h2>

        <div className={styles.grid}>
          {/* INPUT PANEL */}
          <motion.div
            className={styles.inputPanel}
            initial={{ opacity: 0, x: -30 }}
            animate={isInView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <div className={styles.panelLabel}>CONFIGURE YOUR COURSE</div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>TOPIC</label>
              <input
                type="text"
                className={styles.input}
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Enter a topic..."
              />
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>DURATION</label>
              <div className={styles.options}>
                {durations.map((d) => (
                  <button
                    key={d}
                    className={`${styles.optionBtn} ${duration === d ? styles.selected : ''}`}
                    onClick={() => setDuration(d)}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>SKILL LEVEL</label>
              <div className={styles.options}>
                {skills.map((s) => (
                  <button
                    key={s}
                    className={`${styles.optionBtn} ${skill === s ? styles.selected : ''}`}
                    onClick={() => setSkill(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <motion.button
              className={styles.generateBtn}
              onClick={handleGenerate}
              disabled={isGenerating}
              whileHover={{ x: -3, y: -3 }}
              transition={{ type: 'spring', stiffness: 400 }}
            >
              {isGenerating ? 'GENERATING...' : 'GENERATE PREVIEW →'}
            </motion.button>
          </motion.div>

          {/* OUTPUT PANEL */}
          <motion.div
            className={styles.outputPanel}
            initial={{ opacity: 0, x: 30 }}
            animate={isInView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <div className={styles.panelLabel}>COURSE STRUCTURE</div>

            <div className={styles.output}>
              {outputLines.map((line, index) => (
                <motion.div
                  key={index}
                  className={`${styles.outputLine} ${line.startsWith('✓') ? styles.weekHeader : ''}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  {line}
                </motion.div>
              ))}
              
              {outputLines.length === 0 && !isGenerating && (
                <div className={styles.placeholder}>
                  Click "Generate Preview" to see your course structure
                </div>
              )}
            </div>

            {showStats && (
              <motion.div
                className={styles.statsStrip}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                20 LESSONS · 60 QUIZZES · 1 CERTIFICATE
              </motion.div>
            )}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
