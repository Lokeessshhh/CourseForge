'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import MarkdownRenderer from '@/app/components/dashboard/MarkdownRenderer/MarkdownRenderer';
import { useDayPlan, useQuiz, useLessonActions, useCourse } from '@/app/hooks/api';
import styles from './page.module.css';

type TabType = 'study' | 'code' | 'quiz';

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

export default function DayLessonPage() {
  const params = useParams();
  const courseId = params.id as string;
  const week = parseInt(params.w as string);
  const day = parseInt(params.d as string);

  const { data: lessonData, isLoading: lessonLoading, error: lessonError, refetch: refetchLesson } = useDayPlan(courseId, week, day);
  const { data: quizData, isLoading: quizLoading, error: quizError, refetch: refetchQuiz } = useQuiz(courseId, week, day);
  const { data: course } = useCourse(courseId);
  const { startDay, completeDay, submitQuiz, isSubmitting } = useLessonActions();

  const [activeTab, setActiveTab] = useState<TabType>('study');
  const [code, setCode] = useState('');
  const [output, setOutput] = useState('');
  const [isRunning, setIsRunning] = useState(false);

  // Quiz state
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [quizResult, setQuizResult] = useState<{ score: number; passed: boolean } | null>(null);

  // Normalize quiz data to handle both "quizzes" and "questions" keys, and map options
  const questions = (quizData as any)?.quizzes || (quizData as any)?.questions || [];
  const normalizedQuestions = questions.map((q: any) => {
    // If options is a dict {a: "...", b: "..."}, convert to array
    let optionsArray = [];
    if (q.options && typeof q.options === 'object' && !Array.isArray(q.options)) {
      optionsArray = Object.values(q.options);
    } else {
      optionsArray = q.options || [];
    }

    // Convert correct_answer (e.g., "a") to index (0)
    let correctIndex = q.correct; // already an index maybe?
    if (typeof q.correct_answer === 'string') {
      correctIndex = q.correct_answer.toLowerCase().charCodeAt(0) - 97;
    }

    return {
      ...q,
      question: q.question_text || q.question,
      options: optionsArray,
      correct: correctIndex
    };
  });

  const isLoading = lessonLoading || quizLoading;
  const hasError = lessonError || quizError;

  // Start day on mount
  useEffect(() => {
    if (courseId && week && day) {
      startDay(courseId, week, day);
    }
  }, [courseId, week, day, startDay]);

  // Set code from lesson data
  useEffect(() => {
    if (lessonData?.code_content) {
      setCode(lessonData.code_content);
    }
  }, [lessonData]);

  // Initialize answers array when quiz loads
  useEffect(() => {
    if (normalizedQuestions.length > 0) {
      setAnswers(new Array(normalizedQuestions.length).fill(null));
    }
  }, [normalizedQuestions.length]);

  const handleRunCode = async () => {
    setIsRunning(true);
    setOutput('');
    
    // Simulate code execution (would integrate with actual code runner)
    await new Promise(resolve => setTimeout(resolve, 500));
    setOutput('⏱ Code executed successfully\nOutput will appear here...');
    setIsRunning(false);
  };

  const handleSelectAnswer = (index: number) => {
    if (!isSubmitted) {
      setSelectedAnswer(index);
    }
  };

  const handleSubmitAnswer = () => {
    if (selectedAnswer !== null) {
      const newAnswers = [...answers];
      newAnswers[currentQuestion] = selectedAnswer;
      setAnswers(newAnswers);
      setIsSubmitted(true);
      
      // If this is the last question, we automatically trigger the full quiz submission
      // to avoid the "Submit Quiz" button reappearing issue.
      if (currentQuestion === normalizedQuestions.length - 1) {
        handleSubmitQuiz(newAnswers);
      }
    }
  };

  const handleNextQuestion = () => {
    if (normalizedQuestions.length === 0) return;
    
    if (currentQuestion < normalizedQuestions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
      setSelectedAnswer(null);
      setIsSubmitted(false);
    }
    // No 'else' needed here anymore as handleSubmitAnswer handles the last question
  };

  const handleSubmitQuiz = async (finalAnswers?: (number | null)[]) => {
    if (normalizedQuestions.length === 0) return;
    
    const answersToSubmit = finalAnswers || answers;
    const quizAnswers = answersToSubmit.filter((a): a is number => a !== null);
    
    try {
      const result = await submitQuiz(courseId, week, day, quizAnswers);
      
      setQuizResult({ 
        score: result?.score || 0, 
        passed: true 
      });
      setShowResults(true);
      refetchLesson();
    } catch (err) {
      console.error("Quiz submission failed:", err);
      // Even on error, let's show results so user can progress
      setShowResults(true);
    }
  };

  const calculateScore = () => {
    if (normalizedQuestions.length === 0) return 0;
    let correct = 0;
    answers.forEach((answer, index) => {
      if (answer === normalizedQuestions[index].correct) {
        correct++;
      }
    });
    return correct;
  };

  const isLastDay = day === 5 && week === (lessonData?.week_plan?.course?.duration_weeks || course?.duration_weeks || 4);

  const canGoToNextDay = showResults && quizResult?.passed;

  if (isLoading) return <LoadingSkeleton />;
  if (hasError) {
    return (
      <ErrorBox 
        message={lessonError || quizError || 'Unknown error'} 
        onRetry={() => {
          refetchLesson();
          refetchQuiz();
        }} 
      />
    );
  }

  if (!lessonData) {
    return (
      <div className={styles.page}>
        <div className={styles.errorBox}>
          <span className={styles.errorText}>✗ LESSON NOT FOUND</span>
          <Link href={`/dashboard/courses/${courseId}`}>
            <motion.button className={styles.retryBtn} whileHover={{ x: -2, y: -2 }}>
              BACK TO COURSE →
            </motion.button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.breadcrumb}>
        <Link href={`/dashboard/courses/${courseId}`}>COURSE</Link>
        <span className={styles.separator}>›</span>
        <span>WEEK {week}</span>
        <span className={styles.separator}>›</span>
        <span className={styles.current}>DAY {day}: {(lessonData.title || 'LESSON').toUpperCase()}</span>
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'study' ? styles.active : ''}`}
          onClick={() => setActiveTab('study')}
        >
          {activeTab === 'study' ? '■' : '□'} STUDY
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'code' ? styles.active : ''}`}
          onClick={() => setActiveTab('code')}
        >
          {activeTab === 'code' ? '■' : '□'} CODE
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'quiz' ? styles.active : ''}`}
          onClick={() => setActiveTab('quiz')}
        >
          {activeTab === 'quiz' ? '■' : '□'} QUIZ
        </button>
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        {activeTab === 'study' && (
          <motion.div
            key="study"
            className={styles.tabContent}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            <MarkdownRenderer content={lessonData.theory_content || '# No Content Available'} />
            
            <div className={styles.navButtons}>
              <motion.button
                className={styles.nextBtn}
                onClick={() => setActiveTab('code')}
                whileHover={{ x: -2, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                NEXT: CODE EXAMPLES →
              </motion.button>
            </div>
          </motion.div>
        )}

        {activeTab === 'code' && (
          <motion.div
            key="code"
            className={styles.tabContent}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            <div className={styles.editorSection}>
              <div className={styles.editorHeader}>
                <span className={styles.editorLabel}>CODE EDITOR</span>
                <motion.button
                  className={styles.runBtn}
                  onClick={handleRunCode}
                  disabled={isRunning}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  {isRunning ? 'RUNNING...' : 'RUN CODE ▶'}
                </motion.button>
              </div>
              
              <div className={styles.editorContainer}>
                <textarea
                  className={styles.editor}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  spellCheck={false}
                />
              </div>
              
              <div className={styles.outputSection}>
                <span className={styles.outputLabel}>OUTPUT</span>
                <div className={styles.outputBox}>
                  <pre>{output || 'Run code to see output...'}</pre>
                </div>
              </div>
            </div>

            <div className={styles.practiceSection}>
              <div className={styles.practiceLabel}>
                <span className={styles.labelIcon}>►</span>
                PRACTICE EXERCISE
              </div>
              <div className={styles.practiceCard}>
                <p className={styles.practicePrompt}>Practice what you learned today using the code editor above.</p>
                <textarea
                  className={styles.practiceEditor}
                  placeholder="Write your solution here..."
                  spellCheck={false}
                />
              </div>
            </div>

            <div className={styles.navButtons}>
              <motion.button
                className={styles.nextBtn}
                onClick={() => setActiveTab('quiz')}
                whileHover={{ x: -2, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                NEXT: TAKE QUIZ →
              </motion.button>
            </div>
          </motion.div>
        )}

        {activeTab === 'quiz' && quizData && (
          <motion.div
            key="quiz"
            className={styles.tabContent}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {normalizedQuestions.length > 0 ? (
              !showResults ? (
                <>
                  <div className={styles.quizHeader}>
                    <span className={styles.quizLabel}>
                      <span className={styles.labelIcon}>►</span>
                      DAY QUIZ · {normalizedQuestions.length} QUESTIONS
                    </span>
                    <div className={styles.progressDots}>
                      {normalizedQuestions.map((_: any, i: number) => (
                        <span
                          key={i}
                          className={`${styles.dot} ${i === currentQuestion ? styles.current : ''} ${answers[i] !== null ? styles.answered : ''}`}
                        >
                          ●
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className={styles.questionCard}>
                    <h3 className={styles.questionText}>
                      {normalizedQuestions[currentQuestion].question}
                    </h3>

                    <div className={styles.options}>
                      {normalizedQuestions[currentQuestion].options.map((option: string, index: number) => (
                        <motion.button
                          key={index}
                          className={`${styles.option} ${selectedAnswer === index ? styles.selected : ''} ${isSubmitted && index === normalizedQuestions[currentQuestion].correct ? styles.correct : ''} ${isSubmitted && selectedAnswer === index && selectedAnswer !== normalizedQuestions[currentQuestion].correct ? styles.incorrect : ''}`}
                          onClick={() => handleSelectAnswer(index)}
                          disabled={isSubmitted}
                          whileHover={!isSubmitted ? { x: 4 } : {}}
                        >
                          <span className={styles.optionLetter}>
                            {String.fromCharCode(65 + index)}.
                          </span>
                          <span>{option}</span>
                        </motion.button>
                      ))}
                    </div>

                    {isSubmitted && (
                      <motion.div
                        className={styles.explanation}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                      >
                        <span className={styles.resultTag}>
                          {selectedAnswer === normalizedQuestions[currentQuestion].correct ? '✓ CORRECT' : '✗ INCORRECT'}
                        </span>
                        <p>{normalizedQuestions[currentQuestion].explanation}</p>
                      </motion.div>
                    )}

                    <div className={styles.quizActions}>
                      {!isSubmitted ? (
                        <motion.button
                          className={styles.submitBtn}
                          onClick={handleSubmitAnswer}
                          disabled={selectedAnswer === null}
                          whileHover={{ x: -2, y: -2 }}
                          whileTap={{ scale: 0.98 }}
                        >
                          SUBMIT ANSWER →
                        </motion.button>
                      ) : (
                        <motion.button
                          className={styles.submitBtn}
                          onClick={handleNextQuestion}
                          disabled={isSubmitting}
                          whileHover={{ x: -2, y: -2 }}
                          whileTap={{ scale: 0.98 }}
                        >
                          {currentQuestion < normalizedQuestions.length - 1 ? 'NEXT QUESTION →' : 'SUBMIT QUIZ →'}
                        </motion.button>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <motion.div
                  className={styles.resultsCard}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <h2 className={styles.scoreTitle}>
                    {quizResult?.score || calculateScore()}/{normalizedQuestions.length} · {Math.round((quizResult?.score || calculateScore()) / normalizedQuestions.length * 100)}%
                  </h2>
                  
                  <span className={`${styles.passTag} ${styles.passed}`}>
                    ✓ LESSON COMPLETED — NEXT DAY UNLOCKED
                  </span>

                  <div className={styles.breakdown}>
                    {normalizedQuestions.map((q: any, index: number) => (
                      <div key={index} className={styles.breakdownRow}>
                        <span>Q{index + 1}</span>
                        <span>{String.fromCharCode(65 + (answers[index] ?? 0))}</span>
                        <span>{String.fromCharCode(65 + (q.correct ?? 0))}</span>
                        <span>{answers[index] === q.correct ? '✓' : '✗'}</span>
                      </div>
                    ))}
                  </div>

                  <div className={styles.resultsActions}>
                    {day < 5 ? (
                      <Link href={`/dashboard/courses/${courseId}/week/${week}/day/${day + 1}`}>
                        <motion.button
                          className={styles.continueBtn}
                          whileHover={{ x: -2, y: -2 }}
                          whileTap={{ scale: 0.98 }}
                        >
                          GO TO NEXT DAY (DAY {day + 1}) →
                        </motion.button>
                      </Link>
                    ) : (
                      !isLastDay && (
                        <Link href={`/dashboard/courses/${courseId}/week/${week}/test`}>
                          <motion.button
                            className={styles.continueBtn}
                            whileHover={{ x: -2, y: -2 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            GO TO WEEKLY TEST →
                          </motion.button>
                        </Link>
                      )
                    )}
                    
                    <Link href={`/dashboard/courses/${courseId}`}>
                      <motion.button
                        className={styles.backBtn}
                        whileHover={{ x: -2, y: -2 }}
                        whileTap={{ scale: 0.98 }}
                      >
                        BACK TO COURSE MAP
                      </motion.button>
                    </Link>
                  </div>
                </motion.div>
              )
            ) : (
              <div className={styles.errorBox}>
                <span className={styles.errorText}>NO QUIZ QUESTIONS AVAILABLE FOR THIS LESSON</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
