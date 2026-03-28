'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import styles from './Footer.module.css';

export default function Footer() {
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);

  const handleSubscribe = () => {
    if (email) {
      setSubscribed(true);
      setEmail('');
    }
  };

  return (
    <footer className={styles.footer}>
      <div className={styles.container}>
        {/* Newsletter */}
        <div className={styles.newsletter}>
          <label className={styles.newsletterLabel}>GET UPDATES ON THE BUILD</label>
          <div className={styles.newsletterInput}>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              className={styles.emailInput}
            />
            <motion.button
              className={styles.subscribeBtn}
              onClick={handleSubscribe}
              whileHover={{ x: -2, y: -2 }}
            >
              {subscribed ? '✓ SUBSCRIBED' : 'SUBSCRIBE →'}
            </motion.button>
          </div>
        </div>

        {/* Hand-drawn divider */}
        <svg className={styles.divider} viewBox="0 0 1400 20" xmlns="http://www.w3.org/2000/svg">
          <path d="M0 10 Q 100 5, 200 12 T 400 8 T 600 14 T 800 6 T 1000 10 T 1200 8 T 1400 12" stroke="#000" strokeWidth="2" fill="none" opacity="0.2"/>
        </svg>

        {/* Main footer content */}
        <div className={styles.main}>
          <div className={styles.left}>
            <span className={styles.logo}>CourseForge</span>
            <span className={styles.copyright}>© 2026</span>
          </div>

          <div className={styles.center}>
            <a href="/" className={styles.link}>Home</a>
            <span className={styles.dot}>·</span>
            <a href="#process" className={styles.link}>How it works</a>
            <span className={styles.dot}>·</span>
            <a href="/login" className={styles.link}>Login</a>
          </div>

          <div className={styles.right}>
            Built with Fine-tuned Qwen 7B · AMD MI300x ROCm
          </div>
        </div>

        {/* Status strip */}
        <div className={styles.statusStrip}>
          <span className={styles.statusDot}>●</span>
          <span className={styles.statusText}>LIVE</span>
          <span className={styles.statusInfo}>MODEL: QWEN 7B · STATUS: ONLINE · LATENCY: &lt;200MS · UPTIME: 99.9%</span>
        </div>
      </div>
    </footer>
  );
}
