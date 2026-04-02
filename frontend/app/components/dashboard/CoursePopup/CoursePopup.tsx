'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useGenerateCourse } from '@/app/hooks/api/useCourses';
import { useGenerationProgress } from '@/app/components/GenerationProgressProvider/GenerationProgressProvider';
import { useToast } from '@/app/components/Toast';
import styles from './CoursePopup.module.css';

interface CoursePopupProps {
  onClose: () => void;
}

const skillLevels = ['beginner', 'intermediate', 'advanced'] as const;

export default function CoursePopup({ onClose }: CoursePopupProps) {
  const router = useRouter();
  const { generate, isGenerating } = useGenerateCourse();
  const { startGeneration } = useGenerationProgress();
  const toast = useToast();

  const [topic, setTopic] = useState('');
  const [durationValue, setDurationValue] = useState('4');
  const [durationUnit, setDurationUnit] = useState<'weeks' | 'months'>('weeks');
  const [skillLevel, setSkillLevel] = useState<'beginner' | 'intermediate' | 'advanced'>('intermediate');
  const [description, setDescription] = useState('');
  const [durationError, setDurationError] = useState('');

  const handleDurationValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;

    // Only allow digits
    if (value && !/^\d*$/.test(value)) {
      return;
    }

    // Limit to 2 characters
    if (value.length > 2) {
      return;
    }

    setDurationValue(value);
    setDurationError('');

    // Auto-validate: if value > 12 and unit is months, show error
    const numValue = parseInt(value, 10);
    if (durationUnit === 'months' && numValue > 12) {
      setDurationError('Maximum 12 months allowed');
    }
  };

  const handleDurationUnitChange = (unit: 'weeks' | 'months') => {
    setDurationUnit(unit);
    setDurationError('');

    // Validate: if value > 12 and unit is months, show error
    const numValue = parseInt(durationValue, 10);
    if (unit === 'months' && numValue > 12) {
      setDurationError('Maximum 12 months allowed');
    }
  };

  const getDurationInWeeks = () => {
    const numValue = parseInt(durationValue, 10);
    if (isNaN(numValue) || numValue < 1) {
      return 4; // default
    }

    if (durationUnit === 'weeks') {
      return numValue;
    } else {
      return numValue * 4; // months to weeks
    }
  };

  const handleCreate = async () => {
    if (!topic.trim()) return;

    const numValue = parseInt(durationValue, 10);
    if (isNaN(numValue) || numValue < 1) {
      setDurationError('Please enter a valid duration');
      return;
    }

    if (durationUnit === 'months' && numValue > 12) {
      setDurationError('Maximum 12 months allowed');
      return;
    }

    const durationWeeks = getDurationInWeeks();

    try {
      const result = await generate({
        course_name: topic.trim(),
        duration_weeks: durationWeeks,
        level: skillLevel,
        description: description.trim() || undefined,  // Optional description
      });

      if (result?.id) {
        // Start generation tracking to show toast automatically
        startGeneration(result.id);

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
          <div className={styles.durationContainer}>
            <input
              type="text"
              inputMode="numeric"
              className={`${styles.durationInput} ${durationError ? styles.inputError : ''}`}
              placeholder="4"
              value={durationValue}
              onChange={handleDurationValueChange}
              disabled={isGenerating}
              maxLength={2}
            />
            <select
              className={styles.durationSelect}
              value={durationUnit}
              onChange={(e) => handleDurationUnitChange(e.target.value as 'weeks' | 'months')}
              disabled={isGenerating}
            >
              <option value="weeks">Weeks</option>
              <option value="months">Months</option>
            </select>
          </div>
          {durationError && <p className={styles.errorText}>{durationError}</p>}
          {!durationError && durationValue && (
            <p className={styles.durationHint}>
              = {getDurationInWeeks()} week{getDurationInWeeks() !== 1 ? 's' : ''} total
            </p>
          )}
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

        {/* Description */}
        <div className={styles.field}>
          <label className={styles.label}>DESCRIPTION (OPTIONAL)</label>
          <textarea
            className={styles.textarea}
            placeholder="Describe what you want to learn..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isGenerating}
            rows={3}
          />
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
