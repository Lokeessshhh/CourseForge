'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import styles from './Footer.module.css';

interface FooterProps {
  isAuthenticated: boolean;
}

export default function Footer({ isAuthenticated }: FooterProps) {
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);

  const handleSubscribe = () => {
    if (email) {
      setSubscribed(true);
      setEmail('');
    }
  };

  const currentYear = new Date().getFullYear();

  return (
    <footer className={styles.footer}>
      <div className={styles.container}>
        {/* Top section with newsletter and branding */}
        <div className={styles.topSection}>
          {/* Brand column */}
          <div className={styles.brandColumn}>
            <span className={styles.logo}>CourseForge</span>
            <p className={styles.tagline}>AI-POWERED COURSES</p>
            <p className={styles.description}>
              Create comprehensive courses in minutes with AI.
              Built with Fine-tuned Qwen 7B · AMD MI300x ROCm
            </p>
          </div>

          {/* Quick links */}
          <div className={styles.linksColumn}>
            <h4 className={styles.linksTitle}>QUICK LINKS</h4>
            <a href="/" className={styles.linkItem}>Home</a>
            <a href="#process" className={styles.linkItem}>How it Works</a>
            <a href={isAuthenticated ? "/dashboard" : "/login"} className={styles.linkItem}>
              {isAuthenticated ? 'Dashboard' : 'Login'}
            </a>
          </div>

          {/* Newsletter */}
          <div className={styles.newsletterColumn}>
            <h4 className={styles.linksTitle}>STAY UPDATED</h4>
            <p className={styles.newsletterDesc}>Get updates on new features and improvements</p>
            <div className={styles.newsletterInput}>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className={styles.emailInput}
                disabled={subscribed}
              />
              <motion.button
                className={styles.subscribeBtn}
                onClick={handleSubscribe}
                whileHover={{ x: -2, y: -2 }}
                disabled={subscribed}
              >
                {subscribed ? '✓' : '→'}
              </motion.button>
            </div>
            {subscribed && <p className={styles.subscribedMsg}>Thanks for subscribing!</p>}
          </div>
        </div>

        {/* Hand-drawn divider */}
        <svg className={styles.divider} viewBox="0 0 1400 20" xmlns="http://www.w3.org/2000/svg">
          <path d="M0 10 Q 100 5, 200 12 T 400 8 T 600 14 T 800 6 T 1000 10 T 1200 8 T 1400 12" stroke="#000" strokeWidth="2" fill="none" opacity="0.2"/>
        </svg>

        {/* Bottom bar */}
        <div className={styles.bottomBar}>
          <div className={styles.bottomLeft}>
            <span className={styles.copyright}>© {currentYear} CourseForge. All rights reserved.</span>
            <a href="#" className={styles.legalLink}>Privacy</a>
            <a href="#" className={styles.legalLink}>Terms</a>
          </div>

          {/* Status indicator */}
          <div className={styles.statusIndicator}>
            <span className={styles.statusDot}>●</span>
            <span className={styles.statusText}>All Systems Operational</span>
          </div>

          {/* Social links */}
          <div className={styles.socialLinks}>
            <a href="https://github.com" target="_blank" rel="noopener noreferrer" className={styles.socialLink} title="GitHub">
              <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
              </svg>
            </a>
            <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className={styles.socialLink} title="Twitter">
              <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
              </svg>
            </a>
            <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer" className={styles.socialLink} title="LinkedIn">
              <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
              </svg>
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
