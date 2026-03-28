'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useClerk } from '@clerk/nextjs';
import { motion, AnimatePresence } from 'framer-motion';
import PasswordStrength from '../PasswordStrength/PasswordStrength';
import SkillSelector from '../SkillSelector/SkillSelector';
import VerifyEmail from '../VerifyEmail/VerifyEmail';
import styles from './SignUpForm.module.css';

interface SignUpFormProps {
  onSwitchToSignIn: () => void;
}

export default function SignUpForm({ onSwitchToSignIn }: SignUpFormProps) {
  const { client, setActive } = useClerk();
  const router = useRouter();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [skillLevel, setSkillLevel] = useState<'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED'>('INTERMEDIATE');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [step, setStep] = useState<'form' | 'verify'>('form');

  const emailValid = email.includes('@') && email.includes('.');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    setIsLoading(true);
    setError('');

    try {
      const result = await client.signUp.create({
        emailAddress: email,
        password,
        firstName: name,
      });

      if (result.status === 'complete') {
        await setActive({ session: result.createdSessionId });
        router.push('/dashboard');
      } else if (result.status === 'missing_requirements') {
        // Need email verification
        await client.signUp.prepareEmailAddressVerification();
        setStep('verify');
      }
    } catch (err: unknown) {
      const clerkError = err as { errors?: { message: string }[] };
      setError(clerkError.errors?.[0]?.message || 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerify = async (code: string) => {
    setIsLoading(true);
    setError('');

    try {
      const result = await client.signUp.attemptEmailAddressVerification({ code });

      if (result.status === 'complete') {
        await setActive({ session: result.createdSessionId });
        router.push('/dashboard');
      } else {
        setError('Invalid verification code');
      }
    } catch (err: unknown) {
      const clerkError = err as { errors?: { message: string }[] };
      setError(clerkError.errors?.[0]?.message || 'Verification failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    await client.signUp.prepareEmailAddressVerification();
  };

  const handleGoogleSignUp = async () => {
    try {
      // Use signIn for OAuth - it handles both sign-in and sign-up automatically
      await client.signIn.authenticateWithRedirect({
        strategy: 'oauth_google',
        redirectUrl: '/sso-callback',
        redirectUrlComplete: '/dashboard',
      });
    } catch (err: unknown) {
      const clerkError = err as { errors?: { message: string }[] };
      setError(clerkError.errors?.[0]?.message || 'Google sign up failed');
    }
  };

  return (
    <AnimatePresence mode="wait">
      {step === 'form' ? (
        <motion.div
          key="form"
          className={styles.container}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, x: -50 }}
        >
          <div className={styles.header}>
            <span className={styles.label}>── CREATE ACCOUNT ──</span>
          </div>

          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>FULL NAME</label>
              <input
                type="text"
                className={styles.input}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoComplete="name"
              />
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>EMAIL ADDRESS</label>
              <div className={styles.inputWithIcon}>
                <input
                  type="email"
                  className={styles.input}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
                {email && (
                  <motion.span
                    className={styles.validIcon}
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                  >
                    {emailValid ? '✓' : ''}
                  </motion.span>
                )}
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>PASSWORD</label>
              <div className={styles.passwordWrapper}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  className={styles.input}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className={styles.toggleBtn}
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
              <PasswordStrength password={password} />
            </div>

            <SkillSelector value={skillLevel} onChange={setSkillLevel} />

            <motion.button
              type="submit"
              className={styles.submitBtn}
              disabled={isLoading}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              {isLoading ? 'CREATING ACCOUNT...' : 'CREATE ACCOUNT →'}
            </motion.button>
          </form>

          <AnimatePresence>
            {error && (
              <motion.div
                className={styles.errorBox}
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                ✗ {error}
              </motion.div>
            )}
          </AnimatePresence>

          <div className={styles.divider}>
            <span>─────── OR ───────</span>
          </div>

          <motion.button
            type="button"
            className={styles.googleBtn}
            onClick={handleGoogleSignUp}
            whileHover={{ x: -2, y: -2 }}
            whileTap={{ scale: 0.98 }}
          >
            <span className={styles.googleIcon}>G</span>
            CONTINUE WITH GOOGLE
          </motion.button>

          <p className={styles.switchText}>
            Have an account?{' '}
            <button type="button" className={styles.switchBtn} onClick={onSwitchToSignIn}>
              SIGN IN →
            </button>
          </p>
        </motion.div>
      ) : (
        <VerifyEmail
          key="verify"
          email={email}
          onVerify={handleVerify}
          onResend={handleResend}
          error={error}
          isLoading={isLoading}
        />
      )}
    </AnimatePresence>
  );
}
