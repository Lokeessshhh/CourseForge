'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import styles from './Navbar.module.css';

interface NavbarProps {
  isAuthenticated: boolean;
}

export default function Navbar({ isAuthenticated }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <motion.nav
      className={`${styles.navbar} ${scrolled ? styles.scrolled : ''}`}
      initial={{ y: -60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
    >
      <div className={styles.container}>
        <div className={styles.left}>
          <span className={styles.logo}>CourseForge</span>
          <span className={styles.beta}>[BETA]</span>
        </div>

        <div className={styles.right}>
          <a href="#how-it-works" className={styles.link}>How it works</a>
          <a href="#features" className={styles.link}>Features</a>
          {isAuthenticated ? (
            <motion.a
              href="/dashboard"
              className={`${styles.cta} ${styles.dashboardCta}`}
              whileHover={{ x: -3, y: -3 }}
              transition={{ type: 'spring', stiffness: 400 }}
            >
              GO TO DASHBOARD →
            </motion.a>
          ) : (
            <motion.a
              href="/login"
              className={styles.cta}
              whileHover={{ x: -3, y: -3 }}
              transition={{ type: 'spring', stiffness: 400 }}
            >
              START BUILDING →
            </motion.a>
          )}
        </div>
      </div>
    </motion.nav>
  );
}
