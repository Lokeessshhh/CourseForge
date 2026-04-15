'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { useUser } from '@clerk/nextjs';
import { useApiClient } from '@/app/hooks/useApiClient';
import { useGenerationProgress } from '@/app/components/GenerationProgressProvider/GenerationProgressProvider';
import { WebcamASCII } from '@/app/components/WebcamASCII';
import { MemoryGame, ReactionGame, MathGame, NumberGuessGame, ClickSpeedGame } from '@/app/components/MiniGames';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  ReferenceLine,
  ComposedChart,
} from 'recharts';
import styles from './page.module.css';

// Types
interface Course {
  id: string;
  course_name: string;
  topic: string;
  level: string;
  duration_weeks: number;
  progress: number;
  current_week: number;
  current_day: number;
  status: string;
  generation_status?: string;
  generation_progress?: number;
  total_days?: number;
  created_at: string;
  weekly_test_pending?: boolean;
}

interface UserProgress {
  overall: {
    courses_active: number;
    current_streak: number;
    avg_quiz_score: number;
    total_study_hours: number;
  };
  courses: Array<{
    course_id: string;
    weeks: Array<{
      week: number;
      completed_days: number;
      total_days: number;
      test_score: number | null;
    }>;
  }>;
  concepts: Array<{
    concept: string;
    mastery: number;
  }>;
}

interface UserProfile {
  id: string;
  email: string;
  name: string;
  skill_level: number;
}

interface DailyActivity {
  date: string;
  minutes: number;
  days_completed: number;
  quizzes_taken: number;
}

interface ProgressOverTime {
  label: string;
  progress: number;
  courseId: string;
  courseName: string;
}

interface QuizAttempt {
  date: string;
  score: number;
  course_name: string;
  passed: boolean;
}

interface QuizAttemptBackend {
  id: string;
  question: {
    id: string;
    course: string;
    week_number: number;
    day_number: number;
    question_text: string;
    question_type: string;
    options: any;
    difficulty: number;
    concept_tags: string[];
  };
  user_answer: string;
  is_correct: boolean;
  attempted_at: string;
}

interface AIQuote {
  id: number;
  text: string;
  category: string;
  personalized: boolean;
}

// Utility functions
const getGreeting = (): string => {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'GOOD MORNING';
  if (hour >= 12 && hour < 17) return 'GOOD AFTERNOON';
  if (hour >= 17 && hour < 21) return 'GOOD EVENING';
  return 'BURNING MIDNIGHT OIL';
};

const calculateXP = (progress: UserProgress | null, courses: Course[]): number => {
  if (!progress) return 0;
  const completedDays = progress.courses.reduce(
    (acc, c) => acc + c.weeks.reduce((wAcc, w) => wAcc + w.completed_days, 0),
    0
  );
  const quizBonus = progress.overall.avg_quiz_score * 10;
  const streakBonus = progress.overall.current_streak * 50;
  return Math.floor(completedDays * 100 + quizBonus + streakBonus);
};

const getLevelTitle = (xp: number): string => {
  if (xp < 500) return 'NOVICE';
  if (xp < 1500) return 'LEARNER';
  if (xp < 3000) return 'BUILDER';
  if (xp < 6000) return 'CODER';
  return 'MASTER';
};

const getNextLevelXP = (xp: number): number => {
  if (xp < 500) return 500;
  if (xp < 1500) return 1500;
  if (xp < 3000) return 3000;
  if (xp < 6000) return 6000;
  return 10000;
};

const formatRelativeTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
};

// Transform backend quiz attempts to chart format
const transformQuizAttemptsToChartFormat = (attempts: QuizAttemptBackend[]): QuizAttempt[] => {
  if (!attempts || attempts.length === 0) return [];

  // Group attempts by date and calculate daily scores
  const groupedByDate = new Map<string, QuizAttemptBackend[]>();

  attempts.forEach(attempt => {
    // Use full date-time for unique identification
    const dateObj = new Date(attempt.attempted_at);
    const formattedDate = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

    if (!groupedByDate.has(formattedDate)) {
      groupedByDate.set(formattedDate, []);
    }
    groupedByDate.get(formattedDate)!.push(attempt);
  });

  // Calculate scores and prepare result
  const result: QuizAttempt[] = [];

  groupedByDate.forEach((dailyAttempts, date) => {
    const correctCount = dailyAttempts.filter(attempt => attempt.is_correct).length;
    const totalCount = dailyAttempts.length;
    const avgScore = totalCount > 0 ? Math.round((correctCount / totalCount) * 100) : 0;

    // Get course name from the first attempt in the group
    const courseName = dailyAttempts[0].question.course || 'Unknown Course';

    result.push({
      date,
      score: avgScore,
      course_name: courseName,
      passed: avgScore >= 70,
    });
  });

  // Sort by date/time
  result.sort((a, b) => {
    return new Date(a.date).getTime() - new Date(b.date).getTime();
  });

  return result;
};

// Stat Counter Component with animation
function StatCounter({
  value,
  label,
  delay,
  highlight = false,
  showProgress = false,
}: {
  value: number;
  label: string;
  delay: number;
  highlight?: boolean;
  showProgress?: boolean;
}) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    if (value === 0) {
      setDisplayValue(0);
      return;
    }
    const duration = 1200;
    const steps = 40;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setDisplayValue(value);
        clearInterval(timer);
      } else {
        setDisplayValue(Math.floor(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value]);

  const progressWidth = value > 0 ? value : 0;

  // Debug logging
  useEffect(() => {
    if (showProgress) {
      console.log('[StatCounter] Progress bar enabled:', { label, value, progressWidth });
    }
  }, [showProgress, label, value, progressWidth]);

  return (
    <motion.div
      className={`${styles.statBox} ${highlight ? styles.highlighted : ''}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
    >
      <span className={styles.statValue}>{displayValue}</span>
      <span className={styles.statLabel}>{label}</span>
      {showProgress && (
        <div 
          className={styles.statProgressBar} 
          data-testid="stat-progress-bar"
          style={{ 
            width: '100%', 
            height: '8px', 
            background: '#e0e0e0', 
            border: '2px solid #000',
            marginTop: '12px',
            display: 'block',
            visibility: 'visible',
            opacity: 1
          }}
        >
          <div
            className={styles.statProgressFill}
            style={{ 
              width: `${progressWidth}%`,
              height: '100%',
              background: '#000',
              display: 'block',
              visibility: 'visible',
              opacity: 1
            }}
            data-testid="stat-progress-fill"
          />
        </div>
      )}
    </motion.div>
  );
}

// Section Skeleton
function SectionSkeleton({ height = 200 }: { height?: number }) {
  return (
    <div className={styles.skeletonSection} style={{ height: `${height}px` }}>
      <div className={styles.skeletonBox} />
    </div>
  );
}

// Empty State Component
function EmptyState({
  icon,
  title,
  subtitle,
  action,
}: {
  icon: string;
  title: string;
  subtitle: string;
  action?: { label: string; href: string };
}) {
  return (
    <div className={styles.emptyState}>
      <span className={styles.emptyIcon}>{icon}</span>
      <h3 className={styles.emptyTitle}>{title}</h3>
      <p className={styles.emptySubtitle}>{subtitle}</p>
      {action && (
        <Link href={action.href} className={styles.actionButton}>
          {action.label}
        </Link>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { user, isLoaded } = useUser();
  const api = useApiClient();

  // State
  const [courses, setCourses] = useState<Course[]>([]);
  const [progress, setProgress] = useState<UserProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Use global generation progress provider
  const {
    generatingCourseId,
    isGenerating,
    startGeneration,
    completeGeneration,
    dismissGeneration,
  } = useGenerationProgress();

  // Derived state
  const [xp, setXp] = useState(0);
  const [dailyActivity, setDailyActivity] = useState<DailyActivity[]>([]);
  const [quizHistory, setQuizHistory] = useState<QuizAttempt[]>([]);
  const [aiQuotes, setAiQuotes] = useState<AIQuote[]>([]);
  const [currentQuoteIndex, setCurrentQuoteIndex] = useState(0);
  const [currentGame, setCurrentGame] = useState(0);
  const [progressOverTime, setProgressOverTime] = useState<ProgressOverTime[]>([]);

  // Update charts when courses data changes
  useEffect(() => {
    if (courses.length > 0 && progress) {
      // Generate progress over time
      const progressData = generateProgressOverTime(courses);
      setProgressOverTime(progressData);
    }
  }, [courses, progress]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch all data in parallel
  useEffect(() => {
    if (!isLoaded) return;

    const fetchAllData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Parallel API calls
        const [coursesData, progressData] = await Promise.all([
          api.get<Course[]>('/api/courses/').catch(() => []),
          api.get<UserProgress>('/api/users/me/progress/').catch(() => null),
        ]);

        // Debug logging
        console.log('[Dashboard] Progress data from API:', progressData);
        console.log('[Dashboard] avg_quiz_score:', progressData?.overall?.avg_quiz_score);

        setCourses(coursesData || []);
        setProgress(progressData);

        // Calculate XP
        const calculatedXP = calculateXP(progressData, coursesData || []);
        setXp(calculatedXP);

        // Find ALL courses that are ACTIVELY generating
        const generatingCourses = (coursesData || []).filter(
          c => c.generation_status === 'generating'
        );

        if (generatingCourses.length > 0) {
          // Start generation tracking for the first generating course
          console.log('[Dashboard] Found generating courses:', generatingCourses.map(c => c.id));
          startGeneration(generatingCourses[0].id);
        } else if (isGenerating) {
          // No courses generating - clear the state
          // The SSE toast will have received 'ready' event and dismissed itself
          console.log('[Dashboard] No generating courses, clearing state');
          completeGeneration();
        }

        // Fetch real daily activity from backend
        const dailyActivityData = await api.get<DailyActivity[]>('/api/users/me/daily-activity/').catch(() => []);
        // Format dates for chart display
        const formattedActivity = (dailyActivityData || []).map(item => ({
          ...item,
          date: new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        }));
        setDailyActivity(formattedActivity);

        // Fetch real quiz history from backend API
        const quizHistoryData = await api.get<QuizAttemptBackend[]>('/api/users/me/quiz-history/').catch(() => []);

        // Transform backend data to frontend format
        const quizzes = transformQuizAttemptsToChartFormat(quizHistoryData || []);
        setQuizHistory(quizzes);

        // Generate AI quotes based on user data
        const quotes = generateAIQuotes(coursesData || [], progressData, xp);
        setAiQuotes(quotes);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchAllData();
  }, [isLoaded, api]);

  // Helper function to get the correct progress value
  // During generation: shows generation_progress (AI creating content)
  // After generation: shows progress (user learning progress)
  const getDisplayProgress = (course: Course): number => {
    // Safety check: if course is undefined or missing critical fields, return 0
    if (!course) return 0;
    
    // If course is actively being generated, show generation progress
    if (course.generation_status === 'generating') {
      // Match the SSE progress calculation exactly
      // SSE progression for 1-week course:
      // - theme: 9%, titles: 18%, web: 27%, RAG: 36%
      // - day 1: 45%, day 2: 55%, day 3: 64%, day 4: 73%, day 5: 82%
      // - tests: 91-100%
      // 
      // Formula: 36% + (completedDays / totalDays) * 46%
      // Where 36% is base (theme+titles+web+RAG) and 46% is for all days (82-36)
      const weeks = course.duration_weeks || 1;
      const totalDays = weeks * 5;
      const completedDays = course.generation_progress ?? 0;
      
      if (completedDays > 0) {
        const dayProgress = Math.round(36 + (completedDays / totalDays) * 46);
        return Math.min(82, dayProgress); // Cap at 82% (before tests)
      }
      // Before days start, show base progress
      return 36;
    }
    // After generation complete, show user learning progress
    return course.progress ?? 0;
  };

  // Refresh dashboard data (called when course generation completes)
  const refreshDashboard = useCallback(async () => {
    console.log('[Dashboard] Refreshing data...');
    try {
      const [coursesData, progressData] = await Promise.all([
        api.get<Course[]>('/api/courses/').catch(() => []),
        api.get<UserProgress>('/api/users/me/progress/').catch(() => null),
      ]);

      setCourses(coursesData || []);
      setProgress(progressData);

      // Recalculate XP
      const calculatedXP = calculateXP(progressData, coursesData || []);
      setXp(calculatedXP);

      // Find ALL courses that are ACTIVELY generating
      const generatingCourses = (coursesData || []).filter(
        c => c.generation_status === 'generating'
      );

      if (generatingCourses.length > 0) {
        // Still generating - ensure we're tracking the right course
        if (!isGenerating || generatingCourseId !== generatingCourses[0].id) {
          startGeneration(generatingCourses[0].id);
        }
      } else if (isGenerating) {
        // No courses generating - clear the state
        console.log('[Dashboard] No generating courses, clearing state');
        completeGeneration();
      }

      // Refresh quiz history
      const quizHistoryData = await api.get<QuizAttemptBackend[]>('/api/users/me/quiz-history/').catch(() => []);
      const quizzes = transformQuizAttemptsToChartFormat(quizHistoryData || []);
      setQuizHistory(quizzes);

      // Refresh daily activity
      const dailyActivityData = await api.get<DailyActivity[]>('/api/users/me/daily-activity/').catch(() => []);
      const formattedActivity = (dailyActivityData || []).map(item => ({
        ...item,
        date: new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      }));
      setDailyActivity(formattedActivity);
    } catch (err) {
      console.error('[Dashboard] Refresh failed:', err);
    }
  }, [api, isGenerating, generatingCourseId, completeGeneration, startGeneration]);

  // Poll for dashboard updates every 3 seconds - always poll to catch newly generating courses
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    // Start polling immediately
    console.log('[Dashboard] Starting initial polling...');
    interval = setInterval(() => {
      refreshDashboard();
    }, 3000);

    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [refreshDashboard]);

  // Generate daily activity based on real study time from progress
  const generateDailyActivity = useCallback(
    (coursesData: Course[], progressData: UserProgress | null): DailyActivity[] => {
      const days: DailyActivity[] = [];
      const today = new Date();
      
      // Get total study time from progress (in minutes)
      const totalStudyMinutes = progressData?.overall.total_study_hours 
        ? Math.round(progressData.overall.total_study_hours * 60) 
        : 0;
      
      // Get completed days count
      const completedDays = coursesData.reduce((acc, c) => {
        // Estimate completed days from progress percentage
        const estimatedDays = Math.ceil((c.progress / 100) * (c.duration_weeks * 5));
        return acc + estimatedDays;
      }, 0);
      
      // Distribute study time across recent days based on completed days
      const activeDays = Math.max(completedDays, 1);
      const minutesPerActiveDay = Math.ceil(totalStudyMinutes / activeDays);
      
      for (let i = 29; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(date.getDate() - i);
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        
        // Simulate activity on some days (in real implementation, this would come from backend)
        // For now, distribute based on completion percentage
        const dayIndex = 29 - i;
        const isActiveDay = dayIndex < activeDays && dayIndex % 2 === 0; // Every other day until all active days used

        days.push({
          date: dateStr,
          minutes: isActiveDay ? minutesPerActiveDay : 0,
          days_completed: isActiveDay ? 1 : 0,
          quizzes_taken: isActiveDay ? Math.round(Math.random()) : 0
        });
      }

      return days;
    },
    []
  );

  // Generate progress over time data for line chart - based on actual course progress
  const generateProgressOverTime = useCallback((coursesData: Course[]): ProgressOverTime[] => {
    if (!coursesData || coursesData.length === 0) return [];
    
    // Create data points based on actual course progress
    const dataPoints: ProgressOverTime[] = [];
    
    // Get the most progressed course
    const mainCourse = coursesData.reduce((max, course) => 
      course.progress > max.progress ? course : max, coursesData[0]);
    
    // Calculate weeks completed based on progress
    const totalWeeks = mainCourse.duration_weeks || 4;
    const currentProgress = mainCourse.progress;
    
    // Generate data points for each week
    for (let week = 0; week <= totalWeeks; week++) {
      const weekProgress = week === totalWeeks 
        ? currentProgress 
        : Math.min(currentProgress, Math.round((week / totalWeeks) * 100));
      
      dataPoints.push({
        label: week === 0 ? 'Start' : week === totalWeeks ? 'Current' : `Week ${week}`,
        progress: weekProgress,
        courseId: mainCourse.id,
        courseName: mainCourse.course_name,
      });
    }

    return dataPoints;
  }, []);

  // Generate AI-powered personalized quotes
  const generateAIQuotes = useCallback((coursesData: Course[], progressData: UserProgress | null, userXP: number): AIQuote[] => {
    const quotes: AIQuote[] = [];
    const levelTitle = getLevelTitle(userXP);
    
    // Quote templates based on different metrics
    const templates = [
      // Progress-based
      {
        category: 'PROGRESS',
        texts: [
          `You've completed {progress}% of your courses. Consistency is your superpower!`,
          `Every lesson completed is a step closer to mastery. Keep going!`,
          `Your dedication shows in your {progress}% progress. The compound effect is real!`,
        ]
      },
      // Streak-based
      {
        category: 'STREAK',
        texts: [
          `{streak} days in a row! You're building an unbreakable habit.`,
          `Your {streak}-day streak proves you're committed. Champions are made daily!`,
          `Day {streak}: Your future self is thanking you right now.`,
        ]
      },
      // Level-based
      {
        category: 'LEVEL',
        texts: [
          `Level {level}: {levelTitle}. You're not just learning, you're leveling up in life!`,
          `{levelTitle} status achieved. The next level is waiting.`,
          `You've reached {levelTitle} with {xp} XP. Time to push for the next milestone!`,
        ]
      },
      // Quiz performance
      {
        category: 'PERFORMANCE',
        texts: [
          `{avgScore}% average quiz score. Your brain is absorbing knowledge like a sponge!`,
          `Your quiz performance shows {avgScore}% mastery. Excellence is a habit!`,
          `Scoring {avgScore}% on average? You're not just studying, you're mastering!`,
        ]
      },
      // Study time
      {
        category: 'DEDICATION',
        texts: [
          `{hours} hours of focused learning. That's {hoursFormatted} of pure investment in yourself!`,
          `Time spent learning is never wasted. {hours} hours and counting!`,
          `Your {hours} study hours are compounding into skills that last a lifetime.`,
        ]
      },
      // Course-specific
      {
        category: 'FOCUS',
        texts: [
          `Currently tackling {courseName}. Every expert was once a beginner!`,
          `{courseName} is no match for your determination. Keep pushing!`,
          `Learning {courseName}? You're building skills that AI can't replace!`,
        ]
      },
      // Motivational
      {
        category: 'WISDOM',
        texts: [
          `The expert in anything was once a beginner. You're on that journey right now.`,
          `Learning is not a sprint, it's a marathon. And you're pacing perfectly.`,
          `Every code you write, every concept you master, is building your future.`,
          `The best time to start was yesterday. The second best time is now. You're doing it!`,
          `Knowledge is the only investment that always gives returns. Keep investing!`,
        ]
      },
    ];

    // Helper to pick random text from template
    const pickText = (texts: string[]) => texts[Math.floor(Math.random() * texts.length)];

    // Generate 5 quotes based on actual user data
    const streak = progressData?.overall.current_streak || 0;
    const progress = Math.round(coursesData.reduce((acc, c) => acc + c.progress, 0) / (coursesData.length || 1));
    const avgScore = Math.round(progressData?.overall.avg_quiz_score || 0);
    const hours = Math.round(progressData?.overall.total_study_hours || 0);
    const hoursFormatted = hours < 10 ? `0${hours}` : hours;

    // 1. Progress quote
    quotes.push({
      id: 1,
      text: pickText(templates[0].texts).replace('{progress}', progress.toString()),
      category: 'PROGRESS',
      personalized: true,
    });

    // 2. Streak quote (if streak > 0)
    if (streak > 0) {
      quotes.push({
        id: 2,
        text: pickText(templates[1].texts).replace('{streak}', streak.toString()),
        category: 'STREAK',
        personalized: true,
      });
    } else {
      quotes.push({
        id: 2,
        text: 'Start a streak today! Just 5 minutes of learning can change everything.',
        category: 'MOTIVATION',
        personalized: false,
      });
    }

    // 3. Level quote
    quotes.push({
      id: 3,
      text: pickText(templates[2].texts)
        .replace('{level}', levelTitle === 'NOVICE' ? '1' : levelTitle === 'LEARNER' ? '2' : levelTitle === 'BUILDER' ? '3' : levelTitle === 'CODER' ? '4' : '5+')
        .replace('{levelTitle}', levelTitle)
        .replace('{xp}', userXP.toString()),
      category: 'LEVEL',
      personalized: true,
    });

    // 4. Performance quote
    if (avgScore > 0) {
      quotes.push({
        id: 4,
        text: pickText(templates[3].texts).replace('{avgScore}', avgScore.toString()),
        category: 'PERFORMANCE',
        personalized: true,
      });
    } else {
      quotes.push({
        id: 4,
        text: 'Take your first quiz! It\'s not about perfection, it\'s about progress.',
        category: 'MOTIVATION',
        personalized: false,
      });
    }

    // 5. Course-specific or wisdom quote
    if (coursesData.length > 0) {
      const randomCourse = coursesData[Math.floor(Math.random() * coursesData.length)];
      quotes.push({
        id: 5,
        text: pickText(templates[5].texts).replace('{courseName}', randomCourse.topic.split(' ').slice(0, 2).join(' ')),
        category: 'FOCUS',
        personalized: true,
      });
    } else {
      quotes.push({
        id: 5,
        text: pickText(templates[6].texts),
        category: 'WISDOM',
        personalized: false,
      });
    }

    return quotes.slice(0, 5);
  }, []);

  // Auto-rotate quotes every 7 seconds
  useEffect(() => {
    if (aiQuotes.length === 0) return;

    const interval = setInterval(() => {
      setCurrentQuoteIndex((prev) => (prev + 1) % aiQuotes.length);
    }, 7000); // 7 seconds

    return () => clearInterval(interval);
  }, [aiQuotes.length]);


  // Find most active course
  const activeCourse = useMemo(() => {
    if (courses.length === 0) return null;
    return courses.reduce((max, course) =>
      course.progress > max.progress ? course : max
    );
  }, [courses]);

  // Custom tooltip for charts
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className={styles.chartTooltip}>
          <p className={styles.tooltipLabel}>{label}</p>
          <p className={styles.tooltipValue}>
            {payload[0].value}
            {payload[0].name === 'minutes' ? ' min' : '%'}
          </p>
        </div>
      );
    }
    return null;
  };

  if (!isLoaded || isLoading) {
    return (
      <WebcamASCII 
        isLoading={true} 
        message="INITIALIZING DASHBOARD..." 
      />
    );
  }

  const firstName = user?.firstName || user?.primaryEmailAddress?.emailAddress?.split('@')[0] || 'User';
  const levelTitle = getLevelTitle(xp);
  const nextLevelXP = getNextLevelXP(xp);
  const xpProgress = ((xp % nextLevelXP) / nextLevelXP) * 100;

  return (
    <div className={styles.page}>
      {/* Hero Strip */}
      <motion.div
        className={styles.heroStrip}
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className={styles.heroLeft}>
          <h1 className={styles.greeting}>
            {getGreeting()}, {firstName.toUpperCase()}.
          </h1>
          <div className={styles.levelBadge}>
            <span className={styles.levelTitle}>{levelTitle}</span>
            <span className={styles.levelXp}>
              {xp.toLocaleString()} XP → {nextLevelXP.toLocaleString()} XP
            </span>
          </div>
        </div>

        <div className={styles.xpContainer}>
          <div className={styles.xpBar}>
            <motion.div
              className={styles.xpFill}
              initial={{ width: 0 }}
              animate={{ width: `${xpProgress}%` }}
              transition={{ duration: 1.2, ease: 'easeOut' }}
            />
          </div>
        </div>
      </motion.div>

      {/* Stats Grid */}
      <div className={styles.statsGrid}>
        <StatCounter
          value={courses.length}
          label="ACTIVE COURSES"
          delay={0.1}
        />
        <StatCounter
          value={progress?.overall.current_streak || 0}
          label="DAY STREAK"
          delay={0.15}
          highlight={(progress?.overall.current_streak || 0) > 0}
        />
        <StatCounter
          value={Math.round(progress?.overall.avg_quiz_score || 0)}
          label="AVG QUIZ %"
          delay={0.2}
          showProgress={true}
        />
        <StatCounter
          value={Math.round(progress?.overall.total_study_hours || 0)}
          label="HOURS STUDIED"
          delay={0.25}
        />
      </div>

      {/* Generation progress toast is now shown globally in dashboard layout */}

      {/* AI Personal Insights - Carousel */}
      <motion.div
        className={styles.aiQuotesWidget}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <div className={styles.widgetHeader}>
          <span className={styles.widgetTitle}>AI PERSONAL INSIGHTS</span>
          <div className={styles.quoteControls}>
            <div className={styles.quoteDots}>
              {aiQuotes.map((_, index) => (
                <button
                  key={index}
                  className={`${styles.quoteDot} ${index === currentQuoteIndex ? styles.active : ''}`}
                  onClick={() => setCurrentQuoteIndex(index)}
                  aria-label={`Show quote ${index + 1}`}
                  type="button"
                />
              ))}
            </div>
            <span className={styles.aiBadge}>AI</span>
          </div>
        </div>
        <div className={styles.aiQuotesCarousel}>
          <AnimatePresence mode="wait">
            {aiQuotes.length > 0 && (
              <motion.div
                key={currentQuoteIndex}
                className={styles.aiQuoteCard}
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -50 }}
                transition={{ duration: 0.5 }}
              >
                <div className={styles.quoteCategory}>{aiQuotes[currentQuoteIndex].category}</div>
                <p className={styles.quoteText}>"{aiQuotes[currentQuoteIndex].text}"</p>
                {aiQuotes[currentQuoteIndex].personalized && (
                  <div className={styles.personalizedBadge}>Based on your progress</div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>

      {/* Study Activity + Course Progress - Side by Side */}
      <div className={styles.activityAndProgressGrid}>
        {/* Study Activity Bar Chart */}
        <motion.div
          className={styles.widget}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <div className={styles.widgetHeader}>
            <span className={styles.widgetTitle}>STUDY ACTIVITY - LAST 30 DAYS</span>
          </div>
          {dailyActivity.some((d) => d.minutes > 0) ? (
            <div className={styles.chartContainer}>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={dailyActivity}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}
                    stroke="#666"
                    interval={4}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}
                    stroke="#666"
                    label={{ value: 'MIN', angle: -90, position: 'insideLeft', style: { fontSize: 10 } }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="minutes" fill="#000" stroke="#000" strokeWidth={1} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState
              icon="ACTIVITY"
              title="NO ACTIVITY YET"
              subtitle="Start studying to see your activity graph"
            />
          )}
        </motion.div>

        {/* Course Progress Line Chart */}
        <motion.div
          className={styles.widget}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35 }}
        >
          <div className={styles.widgetHeader}>
            <span className={styles.widgetTitle}>COURSE PROGRESS OVER TIME</span>
          </div>
          {progressOverTime.length > 0 ? (
            <div className={styles.chartContainer}>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={progressOverTime}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}
                    stroke="#666"
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}
                    stroke="#666"
                    label={{ value: 'PROGRESS %', angle: -90, position: 'insideLeft', style: { fontSize: 10 } }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  {courses.map((course, index) => (
                    <Line
                      key={course.id}
                      type="monotone"
                      dataKey="progress"
                      stroke="#000"
                      strokeWidth={2}
                      dot={{ fill: '#000', r: 4 }}
                      activeDot={{ r: 6 }}
                      name={course.course_name.length > 15 ? course.course_name.slice(0, 15) + '...' : course.course_name}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState
              icon="PROGRESS"
              title="NO PROGRESS DATA YET"
              subtitle="Complete lessons to see your progress over time"
            />
          )}
        </motion.div>
      </div>

      {/* Row 5: Continue Where You Left Off */}
      <motion.div
        className={styles.widget}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.4 }}
      >
        <div className={styles.widgetHeader}>
          <span className={styles.widgetTitle}>CONTINUE WHERE YOU LEFT OFF</span>
        </div>
        {courses.length > 0 ? (
          <div className={styles.coursesContinueGrid}>
            {courses.map((course, index) => (
              <motion.div
                key={course.id}
                className={styles.courseContinueCard}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: index * 0.05 }}
              >
                <div className={styles.courseContinueHeader}>
                  <h3 className={styles.courseContinueName}>{course.course_name}</h3>
                  {course.weekly_test_pending ? (
                    <div className={`${styles.courseContinueBadge} ${styles.testBadge}`}>
                      WEEK {course.current_week} · TEST
                    </div>
                  ) : (
                    <div className={styles.courseContinueBadge}>
                      WEEK {course.current_week} · DAY {course.current_day}
                    </div>
                  )}
                </div>
                <p className={styles.courseContinueTopic}>{course.topic}</p>
                <div className={styles.courseContinueProgress}>
                  <div className={styles.progressLabel}>
                    <span>{course.generation_status === 'generating' ? 'GENERATING' : 'PROGRESS'}</span>
                    <span>{getDisplayProgress(course)}%</span>
                  </div>
                  <div className={styles.progressBar}>
                    <motion.div
                      className={styles.progressFill}
                      initial={{ width: 0 }}
                      animate={{ width: `${getDisplayProgress(course)}%` }}
                      transition={{ duration: 1, delay: 0.3 + index * 0.05 }}
                    />
                  </div>
                </div>
                <div className={styles.courseContinueFooter}>
                  <span className={styles.lastStudied}>
                    Last studied: {formatRelativeTime(new Date().toISOString())}
                  </span>
                  <Link
                    href={`/dashboard/courses/${course.id}`}
                    className={styles.resumeButton}
                  >
                    RESUME →
                  </Link>
                </div>
              </motion.div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon="COURSES"
            title="YOUR LEARNING JOURNEY STARTS HERE"
            subtitle="Create your first course to begin learning"
            action={{ label: 'CREATE FIRST COURSE', href: '/dashboard/generate' }}
          />
        )}
      </motion.div>

      {/* Row 6: Quiz Scores + Brain Games - Side by Side */}
      <div className={styles.scoresAndGamesGrid}>
        {/* Quiz Performance Trend */}
        <motion.div
          className={styles.widget}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <div className={styles.widgetHeader}>
            <span className={styles.widgetTitle}>QUIZ SCORES OVER TIME</span>
          </div>
          {quizHistory.length > 0 ? (
            <div className={styles.chartContainer}>
              <ResponsiveContainer width="100%" height={250}>
                <ComposedChart data={quizHistory}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9, fontFamily: 'var(--font-mono)' }}
                    stroke="#666"
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 9, fontFamily: 'var(--font-mono)' }}
                    stroke="#666"
                    label={{ value: 'SCORE %', angle: -90, position: 'insideLeft', style: { fontSize: 9 } }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine y={70} stroke="#666" strokeDasharray="3 3" />
                  <ReferenceLine y={80} stroke="#333" strokeDasharray="3 3" />
                  {/* Bar chart for daily scores */}
                  <Bar
                    dataKey="score"
                    fill="#666"
                    opacity={0.5}
                  />
                  {/* Line chart for trend */}
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#FFD600"
                    strokeWidth={3}
                    dot={{ fill: '#FFD600', r: 4, strokeWidth: 2, stroke: '#000' }}
                    activeDot={{ r: 6, strokeWidth: 2, stroke: '#000' }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState
              icon="QUIZ"
              title="NO QUIZ HISTORY"
              subtitle="Complete lessons to unlock quizzes"
            />
          )}
        </motion.div>

        {/* Mini Games Section */}
        <motion.div
          className={styles.widget}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.55 }}
        >
          <div className={styles.widgetHeader}>
            <span className={styles.widgetTitle}>BRAIN GAMES</span>
            <div className={styles.gameControls}>
              <button
                className={styles.gameNavBtn}
                onClick={() => setCurrentGame(prev => prev > 0 ? prev - 1 : 4)}
              >
                ←
              </button>
              <span className={styles.gameIndicator}>{currentGame + 1}/5</span>
              <button
                className={styles.gameNavBtn}
                onClick={() => setCurrentGame(prev => prev < 4 ? prev + 1 : 0)}
              >
                →
              </button>
            </div>
          </div>
          <div className={styles.compactGameContainer}>
            {currentGame === 0 && <MemoryGame compact />}
            {currentGame === 1 && <ReactionGame compact />}
            {currentGame === 2 && <MathGame compact />}
            {currentGame === 3 && <NumberGuessGame compact />}
            {currentGame === 4 && <ClickSpeedGame compact />}
          </div>
        </motion.div>
      </div>

      {/* Row 7: All Courses Overview */}
      <motion.div
        className={styles.widget}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.6 }}
      >
        <div className={styles.widgetHeader}>
          <span className={styles.widgetTitle}>ALL COURSES</span>
        </div>
        {courses.length > 0 ? (
          <div className={styles.coursesTable}>
            <div className={styles.tableHeader}>
              <span className={styles.tableCol}>TOPIC</span>
              <span className={styles.tableCol}>LEVEL</span>
              <span className={styles.tableCol}>PROGRESS</span>
              <span className={styles.tableCol}>WEEK</span>
              <span className={styles.tableCol}>ACTION</span>
            </div>
            {courses.map((course) => (
              <div key={course.id} className={styles.tableRow}>
                <span className={styles.tableCell}>{course.topic.slice(0, 30)}{course.topic.length > 30 ? '...' : ''}</span>
                <span className={styles.tableCell}>{course.level.toUpperCase()}</span>
                <span className={styles.tableCell}>
                  <div className={styles.tableProgress}>
                    <div className={styles.tableProgressBar}>
                      <div
                        className={styles.tableProgressFill}
                        style={{ width: `${getDisplayProgress(course)}%` }}
                      />
                    </div>
                    <span className={styles.tableProgressPercent}>
                      {getDisplayProgress(course)}%
                      {course.generation_status === 'generating' && (
                        <span className={styles.generatingBadge}> </span>
                      )}
                    </span>
                  </div>
                </span>
                <span className={styles.tableCell}>
                  {course.current_week}/{course.duration_weeks}
                </span>
                <span className={styles.tableCell}>
                  <Link
                    href={`/dashboard/courses/${course.id}`}
                    className={styles.tableAction}
                  >
                    RESUME →
                  </Link>
                </span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon="LIBRARY"
            title="NO COURSES YET"
            subtitle="Create your first course to start learning"
            action={{ label: 'CREATE COURSE', href: '/dashboard/generate' }}
          />
        )}
      </motion.div>
    </div>
  );
}
