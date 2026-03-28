'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import OtpInput from '../OtpInput/OtpInput';
import styles from './VerifyEmail.module.css';

interface VerifyEmailProps {
  email: string;
  onVerify: (code: string) => Promise<void>;
  onResend: () => Promise<void>;
  error: string;
  isLoading: boolean;
}

export default function VerifyEmail({ email, onVerify, onResend, error, isLoading }: VerifyEmailProps) {
  const [code, setCode] = useState('');
  const [cooldown, setCooldown] = useState(0);
  const [localError, setLocalError] = useState('');

  useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [cooldown]);

  const handleVerify = async (verificationCode: string) => {
    setCode(verificationCode);
    if (verificationCode.length === 6) {
      setLocalError('');
      await onVerify(verificationCode);
    }
  };

  const handleResend = async () => {
    if (cooldown > 0) return;
    setCooldown(45);
    setLocalError('');
    await onResend();
  };

  const displayError = error || localError;

  return (
    <motion.div
      className={styles.container}
      initial={{ opacity: 0, x: 50 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -50 }}
    >
      <div className={styles.header}>
        <span className={styles.label}>── VERIFY EMAIL ──</span>
      </div>

      <p className={styles.text}>
        We sent a 6-digit code to <strong>{email}</strong>
      </p>

      <OtpInput
        length={6}
        onComplete={handleVerify}
        error={displayError}
      />

      <motion.button
        className={styles.verifyBtn}
        onClick={() => onVerify(code)}
        disabled={isLoading || code.length !== 6}
        whileHover={{ x: -2, y: -2 }}
        whileTap={{ scale: 0.98 }}
      >
        {isLoading ? 'VERIFYING...' : 'VERIFY →'}
      </motion.button>

      <div className={styles.resend}>
        {cooldown > 0 ? (
          <span className={styles.cooldown}>RESEND IN {cooldown}s</span>
        ) : (
          <button className={styles.resendBtn} onClick={handleResend}>
            Didn't receive it? RESEND →
          </button>
        )}
      </div>
    </motion.div>
  );
}
