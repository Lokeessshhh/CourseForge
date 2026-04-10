'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useWeeklyTest, useLessonActions } from '@/app/hooks/api';
import styles from './page.module.css';

function LoadingSkeleton() {
  return (
    <div className={styles.page}>
      <div className={styles.skeletonBox} style={{ width: '300px', height: '20px', marginBottom: '24px' }} />
      <div className={styles.skeletonBox} style={{ width: '100%', height: '400px' }} />
    </div>
  );
}

function ErrorBox({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className={styles.page}>
      <div className={styles.errorBox}>
        <span className={styles.errorText}>✗ FAILED TO LOAD · {message}</span>
        <motion.button
          className={styles.retryBtn}
          onClick={onRetry}
          whileHover={{ x: -2, y: -2 }}
        >
          RETRY →
        </motion.button>
      </div>
    </div>
  );
}

export default function WeeklyTestPage() {
  const params = useParams();
  const courseId = params.id as string;
  const week = parseInt(params.w as string);

  const { data: testData, isLoading, error, refetch } = useWeeklyTest(courseId, week);
  const { submitWeeklyTest, isSubmitting } = useLessonActions();

  // Debug logging
  useEffect(() => {
    console.log('Weekly test data:', testData);
    console.log('Is loading:', isLoading);
    console.log('Error:', error);
  }, [testData, isLoading, error]);

  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [startTime] = useState(Date.now());
  const [elapsedTime, setElapsedTime] = useState(0);
  const [testResult, setTestResult] = useState<{ score: number; passed: boolean } | null>(null);

  // Initialize answers when test loads
  useEffect(() => {
    if (testData?.questions) {
      setAnswers(new Array(testData.questions.length).fill(null));
    }
  }, [testData]);

  // Update timer
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isSubmitted) {
        setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime, isSubmitted]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSelectAnswer = (questionIndex: number, answerIndex: number) => {
    if (!isSubmitted) {
      const newAnswers = [...answers];
      newAnswers[questionIndex] = answerIndex;
      setAnswers(newAnswers);
    }
  };

  const handleSubmit = async () => {
    if (!testData?.questions) return;
    if (!answers.every(a => a !== null)) return;

    const result = await submitWeeklyTest(courseId, week, answers.filter((a): a is number => a !== null));
    if (result) {
      setTestResult({ score: result.score, passed: result.passed });
      setIsSubmitted(true);
    }
  };

  const calculateScore = () => {
    if (!testData?.questions) return 0;
    let correct = 0;
    answers.forEach((answer, index) => {
      if (answer === testData.questions[index].correct) {
        correct++;
      }
    });
    return correct;
  };

  const getWeakDays = () => {
    if (!testData?.questions) return [];
    // Return empty array since day_reference is not available in API
    return [];
  };

  if (isLoading) return <LoadingSkeleton />;
  if (error) {
    return <ErrorBox message={error} onRetry={refetch} />;
  }

  if (!testData) {
    return (
      <div className={styles.page}>
        <div className={styles.errorBox}>
          <span className={styles.errorText}>✗ TEST NOT FOUND</span>
          <Link href={`/dashboard/courses/${courseId}`}>
            <motion.button className={styles.retryBtn} whileHover={{ x: -2, y: -2 }}>
              BACK TO COURSE →
            </motion.button>
          </Link>
        </div>
      </div>
    );
  }

  const answeredCount = answers.filter(a => a !== null).length;
  const score = testResult?.score ?? calculateScore();
  const passed = testResult?.passed ?? score >= Math.ceil(testData.questions.length * 0.7);
  const weakDays = getWeakDays();

  if (isSubmitted) {
    return (
      <div className={styles.page}>
        <div className={styles.resultsHeader}>
          <h1 className={styles.resultsTitle}>WEEK {week} TEST · RESULTS</h1>
          <span className={styles.timer}>{formatTime(elapsedTime)}</span>
        </div>

        <motion.div
          className={styles.resultsCard}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className={styles.scoreSection}>
            <span className={styles.scoreBig}>{score}/{testData.questions.length}</span>
            <span className={styles.scorePercent}>· {Math.round(score / testData.questions.length * 100)}%</span>
          </div>

          <span className={`${styles.passBadge} ${passed ? styles.passed : styles.failed}`}>
            {passed ? '✓ PASSED · WEEK ' + (week + 1) + ' UNLOCKED' : '✗ FAILED · RETRY REQUIRED'}
          </span>

          {passed && (
            <div className={styles.weekBadge}>
              WEEK {week} COMPLETE
            </div>
          )}

          <div className={styles.breakdownTable}>
            <div className={styles.tableHeader}>
              <span>Q</span>
              <span>YOUR ANSWER</span>
              <span>CORRECT</span>
              <span>RESULT</span>
            </div>
            {testData.questions.map((q, index) => (
              <div key={index} className={styles.tableRow}>
                <span>{index + 1}</span>
                <span>{answers[index] !== null ? String.fromCharCode(65 + answers[index]!) : '-'}</span>
                <span>{String.fromCharCode(65 + q.correct)}</span>
                <span className={answers[index] === q.correct ? styles.correct : styles.incorrect}>
                  {answers[index] === q.correct ? '✓' : '✗'}
                </span>
              </div>
            ))}
          </div>

          {weakDays.length > 0 && (
            <div className={styles.weakSection}>
              <span className={styles.weakLabel}>REVIEW SUGGESTED</span>
              <p className={styles.weakText}>
                Review the questions you missed to improve your understanding.
              </p>
              <Link href={`/dashboard/courses/${courseId}/week/${week}/day/1`}>
                <motion.button
                  className={styles.reviewBtn}
                  whileHover={{ x: -2, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                >
                  REVIEW WEEK →
                </motion.button>
              </Link>
            </div>
          )}

          <div className={styles.actionButtons}>
            {!passed && (
              <Link href={`/dashboard/courses/${courseId}/week/${week}/test`}>
                <motion.button
                  className={styles.retryBtn}
                  whileHover={{ x: -2, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                >
                  RETRY TEST →
                </motion.button>
              </Link>
            )}
            <Link href={passed ? `/dashboard/courses/${courseId}/week/${week}/coding-test/1` : `/dashboard/courses/${courseId}`}>
              <motion.button
                className={styles.continueBtn}
                whileHover={{ x: -2, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                {passed ? 'CONTINUE TO CODING TEST 1 →' : 'BACK TO COURSE →'}
              </motion.button>
            </Link>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.testHeader}>
        <h1 className={styles.testTitle}>WEEK {week} TEST · {testData.questions.length} QUESTIONS</h1>
        <span className={styles.timer}>{formatTime(elapsedTime)}</span>
      </div>

      <div className={styles.progressStrip}>
        <span className={styles.progressText}>{answeredCount}/{testData.questions.length} ANSWERED</span>
        <div className={styles.progressBar}>
          <motion.div
            className={styles.progressFill}
            initial={{ width: 0 }}
            animate={{ width: `${(answeredCount / testData.questions.length) * 100}%` }}
          />
        </div>
      </div>

      <div className={styles.questionsList}>
        {testData.questions.map((q, qIndex) => (
          <motion.div
            key={q.id}
            className={styles.questionCard}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: qIndex * 0.05 }}
          >
            <div className={styles.questionHeader}>
              <span className={styles.questionNumber}>Q{qIndex + 1}.</span>
              <span className={styles.questionText}>{q.question}</span>
            </div>

            <div className={styles.optionsGrid}>
              {q.options.map((option, oIndex) => (
                <button
                  key={oIndex}
                  className={`${styles.optionBtn} ${answers[qIndex] === oIndex ? styles.selected : ''}`}
                  onClick={() => handleSelectAnswer(qIndex, oIndex)}
                >
                  <span className={styles.radioBox}>
                    {answers[qIndex] === oIndex ? '■' : '□'}
                  </span>
                  <span className={styles.optionLetter}>{String.fromCharCode(65 + oIndex)}.</span>
                  <span>{option}</span>
                </button>
              ))}
            </div>
          </motion.div>
        ))}
      </div>

      <div className={styles.submitSection}>
        <motion.button
          className={`${styles.submitBtn} ${answeredCount === testData.questions.length ? '' : styles.disabled}`}
          onClick={handleSubmit}
          disabled={answeredCount !== testData.questions.length || isSubmitting}
          whileHover={answeredCount === testData.questions.length ? { x: -2, y: -2 } : {}}
          whileTap={{ scale: 0.98 }}
        >
          {isSubmitting ? 'SUBMITTING...' : 'SUBMIT TEST →'}
        </motion.button>
        {answeredCount < testData.questions.length && (
          <p className={styles.submitHint}>Answer all {testData.questions.length} questions to submit</p>
        )}
      </div>
    </div>
  );
}
