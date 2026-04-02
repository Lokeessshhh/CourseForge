'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import styles from './FeaturesGrid.module.css';

const features = [
  {
    id: 'ai-tutor',
    title: 'AI Tutor Chat',
    desc: 'Ask anything about your course. Context-aware, remembers your progress.',
    size: 'large',
    svg: (
      <svg viewBox="0 0 60 50" xmlns="http://www.w3.org/2000/svg">
        <rect x="5" y="5" width="50" height="35" stroke="#000" strokeWidth="2" fill="none"/>
        <path d="M15 45 L30 40 L45 45" stroke="#000" strokeWidth="2" fill="none"/>
        <circle cx="20" cy="20" r="3" fill="#000"/>
        <circle cx="40" cy="20" r="3" fill="#000"/>
        <path d="M22 28 Q30 35 38 28" stroke="#000" strokeWidth="2" fill="none"/>
      </svg>
    ),
  },
  {
    id: 'daily-quizzes',
    title: 'Daily Quizzes',
    desc: '3 MCQs per day. Score >50% to unlock next lesson.',
    size: 'medium',
    svg: (
      <svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
        <rect x="5" y="5" width="30" height="30" stroke="#000" strokeWidth="2" fill="none"/>
        <path d="M12 20 L18 26 L28 14" stroke="#000" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: 'weekly-tests',
    title: 'Weekly Tests',
    desc: '10-question assessment every week. Covers all 5 days comprehensively.',
    size: 'medium',
  },
  {
    id: 'books',
    title: '325+',
    subtitle: 'Books in knowledge base',
    size: 'small-dark',
  },
  {
    id: 'monaco',
    title: 'Monaco Code Editor',
    desc: 'Write and test code in-browser.',
    size: 'small',
  },
  {
    id: 'progress',
    title: 'Progress Dashboard',
    desc: 'Streak tracking, confidence scores, concept mastery — all in one view.',
    size: 'large',
    svg: (
      <svg viewBox="0 0 80 50" xmlns="http://www.w3.org/2000/svg">
        <rect x="5" y="5" width="70" height="40" stroke="#000" strokeWidth="2" fill="none"/>
        <rect x="15" y="30" width="8" height="10" fill="#000"/>
        <rect x="30" y="20" width="8" height="20" fill="#000"/>
        <rect x="45" y="25" width="8" height="15" fill="#000"/>
        <rect x="60" y="15" width="8" height="25" fill="#000"/>
      </svg>
    ),
  },
  {
    id: 'certificates',
    title: 'Certificates',
    desc: 'PDF certificate generated on completion. Shareable proof of learning.',
    size: 'medium-dark',
  },
  {
    id: 'dashboard-lokesh',
    title: 'LEARNING DASHBOARD',
    size: 'dashboard',
    userData: {
      name: 'Lokesh',
      streak: 12,
      course: 'React Development',
      progress: 65,
      weekProgress: [1, 1, 1, 1, 0, 0, 0],
      avgScore: 78,
      skills: [
        { name: 'Components', percent: 70 },
        { name: 'Hooks', percent: 55 },
        { name: 'State', percent: 40 },
      ],
    },
  },
  {
    id: 'dashboard-harsh',
    title: 'LEARNING DASHBOARD',
    size: 'dashboard',
    userData: {
      name: 'Harsh',
      streak: 7,
      course: 'Python Programming',
      progress: 80,
      weekProgress: [1, 1, 1, 1, 1, 0, 0],
      avgScore: 84,
      skills: [
        { name: 'Variables', percent: 80 },
        { name: 'Functions', percent: 60 },
        { name: 'Recursion', percent: 30 },
      ],
    },
  },
  {
    id: 'dashboard-jayesh',
    title: 'LEARNING DASHBOARD',
    size: 'dashboard',
    userData: {
      name: 'Jayesh',
      streak: 21,
      course: 'Data Structures',
      progress: 45,
      weekProgress: [1, 1, 1, 0, 0, 0, 0],
      avgScore: 92,
      skills: [
        { name: 'Arrays', percent: 90 },
        { name: 'Linked Lists', percent: 75 },
        { name: 'Trees', percent: 35 },
      ],
    },
  },
  {
    id: 'dashboard-aditya',
    title: 'LEARNING DASHBOARD',
    size: 'dashboard',
    userData: {
      name: 'Aditya',
      streak: 3,
      course: 'Machine Learning',
      progress: 25,
      weekProgress: [1, 1, 0, 0, 0, 0, 0],
      avgScore: 71,
      skills: [
        { name: 'Linear Regression', percent: 60 },
        { name: 'Neural Nets', percent: 25 },
        { name: 'CNNs', percent: 15 },
      ],
    },
  },
];

interface UserData {
  name: string;
  streak: number;
  course: string;
  progress: number;
  weekProgress: number[];
  avgScore: number;
  skills: { name: string; percent: number }[];
}

function DashboardCard({ userData }: { userData: UserData }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  return (
    <div className={styles.dashboardCard} ref={ref}>
      <div className={styles.dashboardHeader}>
        <span className={styles.dashboardName}>{userData.name}</span>
        <span className={styles.dashboardStreak}>FIRE {userData.streak} days</span>
      </div>
      <div className={styles.dashboardCourse}>Course: {userData.course}</div>
      
      <div className={styles.dashboardProgress}>
        <span className={styles.progressLabel}>Progress</span>
        <div className={styles.progressBar}>
          <motion.div 
            className={styles.progressFill}
            initial={{ width: 0 }}
            animate={isInView ? { width: `${userData.progress}%` } : {}}
            transition={{ duration: 1, delay: 0.2 }}
          />
        </div>
        <span className={styles.progressPercent}>{userData.progress}%</span>
      </div>

      <div className={styles.weekGrid}>
        {userData.weekProgress.map((filled, i) => (
          <div key={i} className={`${styles.weekBox} ${filled ? styles.weekFilled : ''}`} />
        ))}
      </div>

      <div className={styles.dashboardStat}>Avg quiz score: {userData.avgScore}%</div>

      <div className={styles.knowledgeBars}>
        {userData.skills.map((skill, index) => (
          <div key={skill.name} className={styles.knowledgeRow}>
            <span className={styles.knowledgeLabel}>{skill.name}</span>
            <div className={styles.knowledgeBar}>
              <motion.div 
                className={`${styles.knowledgeFill} ${skill.percent < 40 ? styles.knowledgeWeak : ''}`} 
                initial={{ width: 0 }} 
                animate={isInView ? { width: `${skill.percent}%` } : {}} 
                transition={{ duration: 0.8, delay: 0.3 + index * 0.1 }} 
              />
            </div>
            <span className={styles.knowledgePercent}>{skill.percent}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function FeaturesGrid() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section id="features" className={styles.section} ref={ref}>
      <div className={styles.container}>
        <div className={styles.label}>── 03 / FEATURES ──</div>
        
        <motion.h2
          className={styles.title}
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
        >
          Everything you need.
        </motion.h2>

        <div className={styles.grid}>
          {features.map((feature, index) => (
            <motion.div
              key={feature.id}
              className={`${styles.card} ${styles[feature.size.replace('-', '')] || ''} ${feature.size.includes('dark') ? styles.darkCard : ''} ${feature.size === 'dashboard' ? styles.dashboardWrapper : ''}`}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: index * 0.08 }}
              whileHover={feature.size !== 'dashboard' ? { x: -4, y: -4 } : {}}
            >
              {feature.size === 'dashboard' && feature.userData ? (
                <DashboardCard userData={feature.userData} />
              ) : (
                <>
                  {feature.svg && <div className={styles.svg}>{feature.svg}</div>}
                  <h3 className={styles.cardTitle}>{feature.title}</h3>
                  {feature.subtitle && (
                    <p className={styles.subtitle}>{feature.subtitle}</p>
                  )}
                  {feature.desc && (
                    <p className={styles.cardDesc}>{feature.desc}</p>
                  )}
                </>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
