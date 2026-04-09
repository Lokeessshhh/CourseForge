'use client';

import { useEffect, useState, useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { useScrambleText, useMousePosition, useParallax } from '@/app/hooks';
import styles from './Hero.module.css';

const terminalLines = [
  { text: '> courseforge generate', delay: 0 },
  { text: '> topic: "Python for beginners"', delay: 600 },
  { text: '> duration: "4 weeks"', delay: 1200 },
  { text: '> skill: "beginner"', delay: 1800 },
  { text: '✓ Course generated in 3.2s', delay: 2400, success: true },
  { text: '✓ 20 lessons created', delay: 3000, success: true },
  { text: '✓ 60 quiz questions ready', delay: 3600, success: true },
  { text: '✓ Certificate unlocked', delay: 4200, success: true },
];

const stickers = [
  { text: '7B PARAMS', rotation: -5, top: '15%', right: '8%', factor: 0.05 },
  { text: '325 BOOKS', rotation: 3, top: '35%', right: '5%', factor: 0.03 },
  { text: '9 RAG COMPONENTS', rotation: -2, top: '55%', right: '10%', factor: 0.02 },
];

function ScrambleWord({ word, delay }: { word: string; delay: number }) {
  const { displayText } = useScrambleText(word, { duration: 800, delay });
  return <span>{displayText}</span>;
}

interface HeroProps {
  isAuthenticated: boolean;
}

function ParallaxSticker({ sticker, isInView, mouseX, mouseY }: {
  sticker: typeof stickers[0];
  isInView: boolean;
  mouseX: ReturnType<typeof useMousePosition>['mouseX'];
  mouseY: ReturnType<typeof useMousePosition>['mouseY'];
}) {
  const { x, y } = useParallax(mouseX, mouseY, sticker.factor);
  return (
    <motion.div
      className={styles.sticker}
      style={{ top: sticker.top, right: sticker.right, x, y }}
      initial={{ opacity: 0, scale: 0.8, rotate: sticker.rotation }}
      animate={isInView ? { opacity: 1, scale: 1, rotate: sticker.rotation } : {}}
      transition={{ duration: 0.4, delay: 0.5 + stickers.indexOf(sticker) * 0.1 }}
      whileHover={{ rotate: 0, scale: 1.05 }}
    >
      {sticker.text}
    </motion.div>
  );
}

export default function Hero({ isAuthenticated }: HeroProps) {
  const [displayedLines, setDisplayedLines] = useState<number[]>([]);
  const [charCounts, setCharCounts] = useState<{ [key: number]: number }>({});
  const [courseCount, setCourseCount] = useState(1247);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  const { mouseX, mouseY } = useMousePosition();

  // Live counter increment
  useEffect(() => {
    const interval = setInterval(() => {
      setCourseCount(prev => prev + 1);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Terminal typewriter
  useEffect(() => {
    terminalLines.forEach((line, index) => {
      setTimeout(() => {
        setDisplayedLines(prev => [...prev, index]);
        setCharCounts(prev => ({ ...prev, [index]: 0 }));
        
        let charIndex = 0;
        const interval = setInterval(() => {
          if (charIndex <= line.text.length) {
            setCharCounts(prev => ({ ...prev, [index]: charIndex }));
            charIndex++;
          } else {
            clearInterval(interval);
          }
        }, 30);
      }, line.delay);
    });
  }, []);

  return (
    <section id="hero" className={styles.hero} ref={ref}>
      {/* Background SVG decorations */}
      <svg className={styles.bgStar} viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <path d="M50 10 L55 40 L85 45 L55 50 L50 80 L45 50 L15 45 L45 40 Z" stroke="#000" strokeWidth="2" fill="none" opacity="0.12"/>
      </svg>
      <svg className={styles.bgArrow} viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg">
        <path d="M5 20 Q30 20 40 10 M40 10 L35 15 M40 10 L45 15" stroke="#000" strokeWidth="3" fill="none" opacity="0.12" strokeLinecap="round"/>
      </svg>
      <div className={styles.container}>
        <div className={styles.left}>
          <motion.div
            className={styles.badge}
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5 }}
          >
            ► AI-POWERED LEARNING PLATFORM
          </motion.div>

          <motion.h1
            className={styles.headline}
            initial={{ opacity: 0, y: 30 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <span><ScrambleWord word="Build" delay={0} /> <ScrambleWord word="Your" delay={200} /></span>
            <span className={styles.underlined}>
              <ScrambleWord word="Learning" delay={400} />
              <svg className={styles.underline} viewBox="0 0 200 20" xmlns="http://www.w3.org/2000/svg">
                <path d="M5 15 Q 50 5, 100 12 T 195 8" stroke="#000" strokeWidth="4" fill="none" strokeLinecap="round"/>
              </svg>
            </span>
            <span className={styles.circled}>
              <ScrambleWord word="Path." delay={600} />
              <svg className={styles.circle} viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg">
                <ellipse cx="60" cy="40" rx="55" ry="35" stroke="#000" strokeWidth="3" fill="none" transform="rotate(-5 60 40)"/>
              </svg>
            </span>
          </motion.h1>

          <motion.p
            className={styles.subtext}
            initial={{ opacity: 0, y: 30 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            CourseForge generates personalized coding courses from a single prompt. Learn smarter, not harder.
          </motion.p>

          <motion.div
            className={styles.buttons}
            initial={{ opacity: 0, y: 30 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            <motion.a
              href={isAuthenticated ? "/dashboard" : "/login"}
              className={styles.primaryBtn}
              whileHover={{ x: -3, y: -3 }}
              transition={{ type: 'spring', stiffness: 400 }}
            >
              {isAuthenticated ? "GO TO MY COURSE →" : "CREATE MY COURSE →"}
            </motion.a>
            <motion.a
              href="#how-it-works"
              className={styles.secondaryBtn}
              whileHover={{ x: -3, y: -3 }}
              transition={{ type: 'spring', stiffness: 400 }}
            >
              SEE HOW IT WORKS ↓
            </motion.a>
          </motion.div>

          <motion.div
            className={styles.proof}
            initial={{ opacity: 0 }}
            animate={isInView ? { opacity: 1 } : {}}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            ── Powered by fine-tuned 7B model ──
          </motion.div>
        </div>

        <div className={styles.right}>
          <motion.div
            className={styles.terminal}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={isInView ? { opacity: 1, scale: 1 } : {}}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <div className={styles.terminalHeader}>
              <span className={styles.dot}></span>
              <span className={styles.dot}></span>
              <span className={styles.dot}></span>
              <span className={styles.terminalTitle}>courseforge</span>
            </div>
            <div className={styles.terminalBody}>
              {displayedLines.map((index) => {
                const line = terminalLines[index];
                const visibleText = line.text.slice(0, charCounts[index] || 0);
                return (
                  <div key={index} className={`${styles.terminalLine} ${line.success ? styles.success : ''}`}>
                    {visibleText}
                    {charCounts[index] < line.text.length && (
                      <span className={styles.cursor}>▌</span>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>

          {/* Live counter */}
          <motion.div
            className={styles.liveCounter}
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.8 }}
          >
            <span className={styles.counterLabel}>COURSES GENERATED:</span>
            <span className={styles.counterValue}>{courseCount.toLocaleString()}</span>
          </motion.div>

          {stickers.map((sticker, index) => (
            <ParallaxSticker 
              key={sticker.text} 
              sticker={sticker} 
              isInView={isInView}
              mouseX={mouseX}
              mouseY={mouseY}
            />
          ))}
        </div>
      </div>

      <motion.div
        className={styles.scrollIndicator}
        animate={{ y: [0, 8, 0] }}
        transition={{ repeat: Infinity, duration: 1.5 }}
      >
        ↓ SCROLL
      </motion.div>
    </section>
  );
}
