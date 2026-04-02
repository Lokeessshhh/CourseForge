'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useGenerateCourse } from '@/app/hooks/api/useCourses';
import { useGenerationProgress } from '@/app/components/GenerationProgressProvider/GenerationProgressProvider';
import styles from './GenerateCourseModal.module.css';

const skillLevels = ['beginner', 'intermediate', 'advanced'] as const;
const durationUnits = ['weeks', 'months'] as const;

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export default function GenerateCourseModal({ isOpen, onClose }: Props) {
  const router = useRouter();
  const { generate, isGenerating } = useGenerateCourse();
  const { startGeneration } = useGenerationProgress();

  const [topic, setTopic] = useState('');
  const [durationValue, setDurationValue] = useState('');
  const [durationUnit, setDurationUnit] = useState<'weeks' | 'months'>('weeks');
  const [skillLevel, setSkillLevel] = useState<(typeof skillLevels)[number]>('intermediate');
  const [goals, setGoals] = useState<string[]>([]);
  const [goalInput, setGoalInput] = useState('');
  const [hoursPerDay, setHoursPerDay] = useState(2);
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [durationError, setDurationError] = useState('');

  const handleAddGoal = () => {
    if (goalInput.trim() && goals.length < 5) {
      setGoals([...goals, goalInput.trim()]);
      setGoalInput('');
    }
  };

  const handleRemoveGoal = (index: number) => {
    setGoals(goals.filter((_, i) => i !== index));
  };

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

  const handleSubmit = async () => {
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

    setIsSubmitting(true);
    const durationWeeks = getDurationInWeeks();

    const result = await generate({
      course_name: topic,
      duration_weeks: durationWeeks,
      level: skillLevel,
      goals: goals.length > 0 ? goals : undefined,
      hours_per_day: hoursPerDay,
      description: description.trim() || undefined,  // Optional description
    });

    setIsSubmitting(false);

    if (result?.id) {
      // Start generation tracking
      startGeneration(result.id);

      // Close modal and redirect to generate page
      onClose();
      router.push(`/dashboard/generate?id=${result.id}`);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className={styles.modalOverlay} onClick={onClose}>
        <motion.div
          className={styles.modal}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.2 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className={styles.modalHeader}>
            <h2 className={styles.modalTitle}>CREATE NEW COURSE</h2>
            <button className={styles.closeBtn} onClick={onClose} disabled={isSubmitting}>
              ×
            </button>
          </div>

          <div className={styles.modalBody}>
            {/* Topic */}
            <div className={styles.field}>
              <label className={styles.label}>TOPIC *</label>
              <input
                type="text"
                className={styles.input}
                placeholder="e.g. Python Programming"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                disabled={isSubmitting}
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
                  disabled={isSubmitting}
                  maxLength={2}
                />
                <select
                  className={styles.durationSelect}
                  value={durationUnit}
                  onChange={(e) => handleDurationUnitChange(e.target.value as 'weeks' | 'months')}
                  disabled={isSubmitting}
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
                    disabled={isSubmitting}
                  >
                    {level.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* Goals */}
            <div className={styles.field}>
              <label className={styles.label}>GOALS (MAX 5)</label>
              <div className={styles.goalsInput}>
                <input
                  type="text"
                  className={styles.input}
                  placeholder="Type a goal and press Enter"
                  value={goalInput}
                  onChange={(e) => setGoalInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddGoal();
                    }
                  }}
                  disabled={isSubmitting}
                />
              </div>
              {goals.length > 0 && (
                <div className={styles.goalsList}>
                  {goals.map((goal, index) => (
                    <span key={index} className={styles.goalTag}>
                      {goal}
                      <button onClick={() => handleRemoveGoal(index)} disabled={isSubmitting}>
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Hours Per Day */}
            <div className={styles.field}>
              <label className={styles.label}>HOURS PER DAY</label>
              <div className={styles.options}>
                {[1, 2, 3, 4].map((h) => (
                  <button
                    key={h}
                    className={`${styles.optionBtn} ${hoursPerDay === h ? styles.selected : ''}`}
                    onClick={() => setHoursPerDay(h)}
                    disabled={isSubmitting}
                  >
                    {h}
                  </button>
                ))}
              </div>
            </div>

            {/* Description */}
            <div className={styles.field}>
              <label className={styles.label}>COURSE DESCRIPTION (OPTIONAL)</label>
              <textarea
                className={styles.textarea}
                placeholder="Describe what you want to learn in this course, specific topics, projects, or goals..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isSubmitting}
                rows={4}
              />
            </div>
          </div>

          <div className={styles.modalFooter}>
            <motion.button
              className={styles.submitBtn}
              onClick={handleSubmit}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
              disabled={!topic.trim() || !durationValue || isSubmitting || isGenerating || !!durationError}
            >
              {isSubmitting || isGenerating ? 'CREATING...' : 'CREATE COURSE'} →
            </motion.button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
