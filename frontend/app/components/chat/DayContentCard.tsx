'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import MarkdownRenderer from '@/app/components/dashboard/MarkdownRenderer/MarkdownRenderer';
import styles from './DayContentCard.module.css';

interface DayContentCardProps {
  courseName: string;
  weekNumber: number;
  dayNumber: number;
  dayTitle?: string;
  theoryContent: string;
  codeContent: string;
  quizzes?: any[];
  tasks?: any;
  isLoading?: boolean;
}

export default function DayContentCard({
  courseName,
  weekNumber,
  dayNumber,
  dayTitle,
  theoryContent,
  codeContent,
  quizzes,
  tasks,
  isLoading = false,
}: DayContentCardProps) {
  const [activeTab, setActiveTab] = useState<'theory' | 'code' | 'quiz'>('theory');
  const [showQuizAnswers, setShowQuizAnswers] = useState(false);

  if (isLoading) {
    return (
      <motion.div
        className={styles.card}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <div className={styles.loading}>
          <div className={styles.loadingSpinner}></div>
          <p>Loading day content...</p>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      className={styles.card}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <span className={styles.courseName}>{courseName}</span>
          <span className={styles.weekDay}>
            Week {weekNumber} • Day {dayNumber}
          </span>
          {dayTitle && <span className={styles.dayTitle}>{dayTitle}</span>}
        </div>
      </div>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'theory' ? styles.active : ''}`}
          onClick={() => setActiveTab('theory')}
        >
          📖 Theory
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'code' ? styles.active : ''}`}
          onClick={() => setActiveTab('code')}
        >
          💻 Code
        </button>
        {quizzes && quizzes.length > 0 && (
          <button
            className={`${styles.tab} ${activeTab === 'quiz' ? styles.active : ''}`}
            onClick={() => setActiveTab('quiz')}
          >
            📝 Quiz ({quizzes.length})
          </button>
        )}
      </div>

      <div className={styles.content}>
        {activeTab === 'theory' && (
          <div className={styles.theoryContent}>
            <MarkdownRenderer content={theoryContent} />
          </div>
        )}

        {activeTab === 'code' && (
          <div className={styles.codeContent}>
            <MarkdownRenderer content={codeContent} />
          </div>
        )}

        {activeTab === 'quiz' && quizzes && quizzes.length > 0 && (
          <div className={styles.quizContent}>
            {quizzes.map((quiz, index) => (
              <div key={index} className={styles.quizQuestion}>
                <p className={styles.questionText}>
                  <strong>Q{quiz.question_number}:</strong> {quiz.question_text}
                </p>
                <div className={styles.options}>
                  {Object.entries(quiz.options).map(([key, value]) => (
                    <div
                      key={key}
                      className={`${styles.option} ${
                        showQuizAnswers && key === quiz.correct_answer
                          ? styles.correct
                          : ''
                      }`}
                    >
                      <span className={styles.optionKey}>{key}.</span>
                      <span className={styles.optionText}>{value as string}</span>
                    </div>
                  ))}
                </div>
                {showQuizAnswers && quiz.explanation && (
                  <div className={styles.explanation}>
                    <strong>Explanation:</strong> {quiz.explanation}
                  </div>
                )}
              </div>
            ))}
            <button
              className={styles.toggleAnswersBtn}
              onClick={() => setShowQuizAnswers(!showQuizAnswers)}
            >
              {showQuizAnswers ? 'Hide Answers' : 'Show Answers'}
            </button>
          </div>
        )}
      </div>

      {tasks && (
        <div className={styles.tasks}>
          <h4 className={styles.tasksTitle}>📋 Tasks</h4>
          {tasks.concepts && (
            <div className={styles.taskSection}>
              <strong>Concepts:</strong>
              <ul>
                {tasks.concepts.map((concept: string, i: number) => (
                  <li key={i}>{concept}</li>
                ))}
              </ul>
            </div>
          )}
          {tasks.key_points && (
            <div className={styles.taskSection}>
              <strong>Key Points:</strong>
              <ul>
                {tasks.key_points.map((point: string, i: number) => (
                  <li key={i}>{point}</li>
                ))}
              </ul>
            </div>
          )}
          {tasks.practice && (
            <div className={styles.taskSection}>
              <strong>Practice:</strong>
              <p>{tasks.practice}</p>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
