'use client';

import { useState, useRef, useEffect, KeyboardEvent, ClipboardEvent } from 'react';
import { motion } from 'framer-motion';
import styles from './OtpInput.module.css';

interface OtpInputProps {
  length?: number;
  onComplete: (code: string) => void;
  error?: string;
}

export default function OtpInput({ length = 6, onComplete, error }: OtpInputProps) {
  const [code, setCode] = useState<string[]>(Array(length).fill(''));
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    inputRefs.current = inputRefs.current.slice(0, length);
  }, [length]);

  const handleChange = (index: number, value: string) => {
    if (value.length > 1) {
      // Handle paste
      const digits = value.slice(0, length).split('');
      const newCode = [...code];
      digits.forEach((digit, i) => {
        if (index + i < length) {
          newCode[index + i] = digit;
        }
      });
      setCode(newCode);
      
      // Focus last filled input or next empty
      const lastFilledIndex = Math.min(index + digits.length - 1, length - 1);
      inputRefs.current[lastFilledIndex]?.focus();
      
      if (newCode.every(d => d !== '')) {
        onComplete(newCode.join(''));
      }
      return;
    }

    const digit = value.slice(-1);
    if (!/^\d*$/.test(digit)) return;

    const newCode = [...code];
    newCode[index] = digit;
    setCode(newCode);

    if (digit && index < length - 1) {
      inputRefs.current[index + 1]?.focus();
    }

    if (newCode.every(d => d !== '')) {
      onComplete(newCode.join(''));
    }
  };

  const handleKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').slice(0, length);
    if (!/^\d+$/.test(pastedData)) return;

    const digits = pastedData.split('');
    const newCode = [...code];
    digits.forEach((digit, i) => {
      if (i < length) {
        newCode[i] = digit;
      }
    });
    setCode(newCode);
    inputRefs.current[Math.min(digits.length - 1, length - 1)]?.focus();

    if (digits.length === length) {
      onComplete(pastedData);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.inputs}>
        {code.map((digit, index) => (
          <motion.input
            key={index}
            ref={(el) => { inputRefs.current[index] = el; }}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={(e) => handleChange(index, e.target.value)}
            onKeyDown={(e) => handleKeyDown(index, e)}
            onPaste={handlePaste}
            className={`${styles.input} ${error ? styles.error : ''}`}
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: index * 0.05, type: 'spring', stiffness: 300 }}
            whileFocus={{ scale: 1.05 }}
          />
        ))}
      </div>
      {error && (
        <motion.span
          className={styles.errorText}
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
           {error}
        </motion.span>
      )}
    </div>
  );
}
