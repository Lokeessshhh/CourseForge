'use client';

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import styles from './PasswordStrength.module.css';

interface PasswordStrengthProps {
  password: string;
}

export default function PasswordStrength({ password }: PasswordStrengthProps) {
  const strength = useMemo(() => {
    let score = 0;
    if (password.length >= 8) score++;
    if (/\d/.test(password)) score++;
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) score++;
    if (/[A-Z]/.test(password)) score++;
    return score;
  }, [password]);

  const labels = ['', 'WEAK', 'FAIR', 'GOOD', 'STRONG'];
  const label = labels[strength];

  if (!password) return null;

  return (
    <div className={styles.container}>
      <div className={styles.bars}>
        {[1, 2, 3, 4].map((i) => (
          <motion.div
            key={i}
            className={`${styles.bar} ${i <= strength ? styles.filled : ''}`}
            initial={{ width: 0 }}
            animate={{ width: i <= strength ? '100%' : '100%' }}
            transition={{ duration: 0.2, delay: i * 0.05 }}
          />
        ))}
      </div>
      {label && (
        <motion.span
          className={styles.label}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {label}
        </motion.span>
      )}
    </div>
  );
}
