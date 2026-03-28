'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import styles from './StickyNav.module.css';

const sections: { id: string; label: string }[] = [
  { id: 'hero', label: 'HERO' },
  { id: 'problem', label: 'PROBLEM' },
  { id: 'process', label: 'PROCESS' },
  { id: 'preview', label: 'PREVIEW' },
  { id: 'features', label: 'FEATURES' },
  { id: 'testimonials', label: 'TESTIMONIALS' },
  { id: 'stats', label: 'STATS' },
  { id: 'faq', label: 'FAQ' },
  { id: 'cta', label: 'START' },
];

export default function StickyNav() {
  const [activeSection, setActiveSection] = useState<string>('hero');

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        });
      },
      {
        threshold: 0.5,
        rootMargin: '-20% 0px -60% 0px',
      }
    );

    // Observe all sections
    sections.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  const scrollToSection = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (el) {
      window.scrollTo({
        top: el.offsetTop - 80,
        behavior: 'smooth',
      });
    }
  }, []);

  return (
    <nav className={styles.nav}>
      <div className={styles.line}>
        {sections.map((section) => {
          const isActive = activeSection === section.id;
          return (
            <motion.button
              key={section.id}
              className={styles.dotWrapper}
              onClick={() => scrollToSection(section.id)}
              whileHover={{ scale: 1.1 }}
              title={section.label}
            >
              <motion.div
                className={styles.dot}
                animate={{
                  backgroundColor: isActive ? '#000' : '#fff',
                }}
                transition={{ duration: 0.15 }}
              />
              <span className={styles.label}>{section.label}</span>
            </motion.button>
          );
        })}
      </div>
    </nav>
  );
}
