'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useGenerateCourse } from '@/app/hooks/api/useCourses';
import { useToast } from '@/app/components/Toast';
import styles from './CoursePopup.module.css';

interface CoursePopupProps {
  onClose: () => void;
}

const durations = [
  { value: '1wk', label: '1WK', weeks: 1 },
  { value: '2wk', label: '2WK', weeks: 2 },
  { value: '1mo', label: '1MO', weeks: 4 },
  { value: '2mo', label: '2MO', weeks: 8 },
  { value: '3mo', label: '3MO', weeks: 12 },
];

const skillLevels = ['beginner', 'intermediate', 'advanced'] as const;

export default function CoursePopup({ onClose }: CoursePopupProps) {
  const router = useRouter();
  const { generate, isGenerating } = useGenerateCourse();
  const toast = useToast();
  
  const [topic, setTopic] = useState('');
  const [duration, setDuration] = useState('2wk');
  const [skillLevel, setSkillLevel] = useState<'beginner' | 'intermediate' | 'advanced'>('intermediate');

  const handleCreate = async () => {
    if (!topic.trim()) return;

    const durationWeeks = durations.find(d => d.value === duration)?.weeks || 2;
    
    try {
      const result = await generate({
        course_name: topic.trim(),
        duration_weeks: durationWeeks,
        level: skillLevel,
      });

      if (result?.id) {
        toast.success('Course generation started!');
        router.push(`/dashboard/generate?id=${result.id}`);
        onClose();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create course');
    }
  };

  return (
    <motion.div
      className={styles.overlay}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className={styles.popup}
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.95 }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <span className={styles.headerIcon}>►</span>
          <span className={styles.headerTitle}>CREATE YOUR COURSE</span>
        </div>

        {/* Topic */}
        <div className={styles.field}>
          <label className={styles.label}>TOPIC</label>
          <input
            type="text"
            className={styles.input}
            placeholder="e.g. Python Programming"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            autoFocus
            disabled={isGenerating}
          />
        </div>

        {/* Duration */}
        <div className={styles.field}>
          <label className={styles.label}>DURATION</label>
          <div className={styles.options}>
            {durations.map((d) => (
              <button
                key={d.value}
                className={`${styles.optionBtn} ${duration === d.value ? styles.selected : ''}`}
                onClick={() => setDuration(d.value)}
                disabled={isGenerating}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>

        {/* Skill Level */}
        <div className={styles.field}>
          <label className={styles.label}>SKILL LEVEL</label>
          <div className={styles.options}>
            {skillLevels.map((level) => (
              <button
                key={level}
                className={`${styles.optionBtn} ${skillLevel === level ? styles.selected : ''}`}
                onClick={() => setSkillLevel(level)}
                disabled={isGenerating}
              >
                {level.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Create Button */}
        <motion.button
          className={styles.createBtn}
          onClick={handleCreate}
          whileHover={{ x: -2, y: -2 }}
          whileTap={{ scale: 0.98 }}
          disabled={!topic.trim() || isGenerating}
        >
          {isGenerating ? 'GENERATING...' : 'CREATE COURSE →'}
        </motion.button>
      </motion.div>
    </motion.div>
  );
}
