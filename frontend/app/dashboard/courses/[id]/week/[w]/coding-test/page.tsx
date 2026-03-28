'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Play, Code, Check, X, Loader2, Terminal } from 'lucide-react';
import { lessonApi } from '@/app/hooks/api/useLesson';
import styles from './page.module.css';

interface CodingProblem {
  problem_number: number;
  title: string;
  description: string;
  difficulty: 'easy' | 'medium' | 'hard';
  starter_code: string;
  test_cases: Array<{
    input: string;
    expected_output: string;
  }>;
}

interface CodingTest {
  week_number: number;
  total_problems: number;
  problems: CodingProblem[];
}

interface CodingTestAttempt {
  id: string;
  submissions: Record<number, {
    code: string;
    language: string;
    passed: boolean;
    output: string;
  }>;
  score: number;
  total: number;
  percentage: number;
  passed: boolean;
}

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

export default function CodingTestPage() {
  const params = useParams();
  const courseId = params.id as string;
  const week = parseInt(params.w as string);

  const [testData, setTestData] = useState<CodingTest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [selectedProblem, setSelectedProblem] = useState<number>(0);
  const [code, setCode] = useState('');
  const [language, setLanguage] = useState('python3');
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [testResult, setTestResult] = useState<CodingTestAttempt | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const languages = [
    { id: 'python3', name: 'Python 3' },
    { id: 'javascript', name: 'JavaScript' },
    { id: 'java', name: 'Java' },
    { id: 'cpp', name: 'C++' },
  ];

  useEffect(() => {
    loadCodingTest();
  }, [courseId, week]);

  const loadCodingTest = async () => {
    try {
      setIsLoading(true);
      const response = await lessonApi.getCodingTest(courseId, week);
      console.log('Coding test response:', response);
      setTestData(response);

      if (response.problems && response.problems.length > 0) {
        setCode(response.problems[0].starter_code);
      }
    } catch (err: any) {
      console.error('Failed to load coding test:', err);
      setError(err.message || 'Failed to load coding test');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartTest = async () => {
    try {
      const response = await lessonApi.startCodingTest(courseId, week);
      setAttemptId(response.attempt_id);
    } catch (err: any) {
      setError(err.message || 'Failed to start test');
    }
  };

  const handleExecuteCode = async () => {
    if (!testData || !attemptId) return;

    const problem = testData.problems[selectedProblem];
    const firstTestCase = problem.test_cases[0];

    try {
      setIsExecuting(true);
      setExecutionResult(null);

      const response = await lessonApi.executeCodingChallenge(
        courseId,
        week,
        attemptId,
        selectedProblem,
        code,
        language,
        firstTestCase.input,
        firstTestCase.expected_output
      );

      setExecutionResult(response);
    } catch (err: any) {
      setExecutionResult({
        error: err.message || 'Execution failed',
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const handleSubmitTest = async () => {
    if (!testData || !attemptId) return;

    try {
      setIsSubmitted(true);
      const response = await lessonApi.submitCodingTest(courseId, week, attemptId);
      setTestResult(response);
    } catch (err: any) {
      setError(err.message || 'Failed to submit test');
      setIsSubmitted(false);
    }
  };

  if (isLoading) return <LoadingSkeleton />;
  if (error) {
    return <ErrorBox message={error} onRetry={loadCodingTest} />;
  }

  if (!testData) {
    return (
      <div className={styles.page}>
        <div className={styles.errorBox}>
          <span className={styles.errorText}>✗ CODING TEST NOT FOUND</span>
          <Link href={`/dashboard/courses/${courseId}`}>
            <motion.button className={styles.retryBtn} whileHover={{ x: -2, y: -2 }}>
              BACK TO COURSE →
            </motion.button>
          </Link>
        </div>
      </div>
    );
  }

  if (testResult) {
    return (
      <div className={styles.page}>
        <div className={styles.resultsContainer}>
          <motion.div
            className={styles.resultCard}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className={styles.resultHeader}>
              <h1 className={styles.resultTitle}>
                {testResult.passed ? (
                  <span className={styles.passed}>✓ PASSED</span>
                ) : (
                  <span className={styles.failed}>✗ FAILED</span>
                )}
              </h1>
              <div className={styles.scoreSummary}>
                <span className={styles.score}>{testResult.score}/{testResult.total}</span>
                <span className={styles.percentage}>{testResult.percentage}%</span>
              </div>
            </div>

            <div className={styles.problemResults}>
              {testData.problems.map((problem, index) => {
                const submission = testResult.submissions[index];
                return (
                  <div key={index} className={styles.problemResult}>
                    <div className={styles.problemResultHeader}>
                      <span className={styles.problemNumber}>Problem {index + 1}</span>
                      {submission?.passed ? (
                        <Check className={styles.passedIcon} />
                      ) : (
                        <X className={styles.failedIcon} />
                      )}
                    </div>
                    <div className={styles.problemResultDetails}>
                      <p className={styles.problemTitle}>{problem.title}</p>
                      {submission && (
                        <div className={styles.executionDetails}>
                          <Terminal className={styles.terminalIcon} />
                          <span className={styles.outputText}>
                            {submission.output || 'No output'}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <Link href={`/dashboard/courses/${courseId}`}>
              <motion.button
                className={styles.continueBtn}
                whileHover={{ x: -2, y: -2 }}
              >
                CONTINUE →
              </motion.button>
            </Link>
          </motion.div>
        </div>
      </div>
    );
  }

  const currentProblem = testData.problems[selectedProblem];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>Week {week} Coding Test</h1>
          <p className={styles.subtitle}>{testData.total_problems} Problems</p>
        </div>
        {!attemptId && (
          <motion.button
            className={styles.startBtn}
            onClick={handleStartTest}
            whileHover={{ x: -2, y: -2 }}
            whileTap={{ scale: 0.98 }}
          >
            <Play className={styles.playIcon} />
            START TEST
          </motion.button>
        )}
      </div>

      {attemptId && (
        <div className={styles.content}>
          <div className={styles.sidebar}>
            <div className={styles.problemList}>
              {testData.problems.map((problem, index) => (
                <motion.button
                  key={index}
                  className={`${styles.problemTab} ${selectedProblem === index ? styles.active : ''}`}
                  onClick={() => setSelectedProblem(index)}
                  whileHover={{ x: 2 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <Code className={styles.problemIcon} />
                  <span className={styles.problemTabText}>Problem {index + 1}</span>
                  {problem.difficulty === 'easy' && <span className={styles.difficultyEasy}>Easy</span>}
                  {problem.difficulty === 'medium' && <span className={styles.difficultyMedium}>Medium</span>}
                  {problem.difficulty === 'hard' && <span className={styles.difficultyHard}>Hard</span>}
                </motion.button>
              ))}
            </div>

            <motion.button
              className={styles.submitBtn}
              onClick={handleSubmitTest}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              SUBMIT TEST →
            </motion.button>
          </div>

          <div className={styles.mainContent}>
            <div className={styles.problemPanel}>
              <div className={styles.problemHeader}>
                <h2 className={styles.problemTitle}>{currentProblem.title}</h2>
                <span className={`${styles.difficulty} ${styles[currentProblem.difficulty]}`}>
                  {currentProblem.difficulty}
                </span>
              </div>
              <div className={styles.problemDescription}>
                <p>{currentProblem.description}</p>
              </div>
              <div className={styles.testCases}>
                <h3 className={styles.testCasesTitle}>Test Cases</h3>
                {currentProblem.test_cases.map((testCase, index) => (
                  <div key={index} className={styles.testCase}>
                    <div className={styles.testCaseInput}>
                      <span className={styles.testCaseLabel}>Input:</span>
                      <code className={styles.testCaseCode}>{testCase.input}</code>
                    </div>
                    <div className={styles.testCaseOutput}>
                      <span className={styles.testCaseLabel}>Output:</span>
                      <code className={styles.testCaseCode}>{testCase.expected_output}</code>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className={styles.codePanel}>
              <div className={styles.codeHeader}>
                <select
                  className={styles.languageSelect}
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  {languages.map((lang) => (
                    <option key={lang.id} value={lang.id}>
                      {lang.name}
                    </option>
                  ))}
                </select>
                <motion.button
                  className={styles.executeBtn}
                  onClick={handleExecuteCode}
                  disabled={isExecuting}
                  whileHover={{ x: -2, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                >
                  {isExecuting ? (
                    <Loader2 className={styles.spinner} />
                  ) : (
                    <Play className={styles.playIcon} />
                  )}
                  {isExecuting ? 'RUNNING...' : 'RUN CODE'}
                </motion.button>
              </div>
              <textarea
                className={styles.codeEditor}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Write your code here..."
                spellCheck={false}
              />
              {executionResult && (
                <div className={styles.executionResult}>
                  <div className={styles.executionResultHeader}>
                    <Terminal className={styles.terminalIcon} />
                    <span>Output</span>
                  </div>
                  {executionResult.error ? (
                    <div className={styles.executionError}>
                      <X className={styles.errorIcon} />
                      <span>{executionResult.error}</span>
                    </div>
                  ) : (
                    <div className={styles.executionSuccess}>
                      {executionResult.is_correct ? (
                        <Check className={styles.successIcon} />
                      ) : (
                        <X className={styles.errorIcon} />
                      )}
                      <pre className={styles.outputText}>{executionResult.stdout || 'No output'}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
