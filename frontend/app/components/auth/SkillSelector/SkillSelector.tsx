'use client';

import { motion } from 'framer-motion';
import styles from './SkillSelector.module.css';

interface SkillSelectorProps {
  value: 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED';
  onChange: (level: 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED') => void;
}

const levels: ('BEGINNER' | 'INTERMEDIATE' | 'ADVANCED')[] = ['BEGINNER', 'INTERMEDIATE', 'ADVANCED'];

export default function SkillSelector({ value, onChange }: SkillSelectorProps) {
  return (
    <div className={styles.container}>
      <label className={styles.label}>YOUR SKILL LEVEL</label>
      <div className={styles.options}>
        {levels.map((level) => (
          <motion.button
            key={level}
            type="button"
            className={`${styles.option} ${value === level ? styles.selected : ''}`}
            onClick={() => onChange(level)}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            layout
          >
            {level}
          </motion.button>
        ))}
      </div>
    </div>
  );
}
