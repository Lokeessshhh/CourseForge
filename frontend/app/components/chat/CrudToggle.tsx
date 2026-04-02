'use client';

import styles from './CrudToggle.module.css';

interface Props {
  enabled: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

export default function CrudToggle({ enabled, onToggle, disabled = false }: Props) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className={`${styles.toggleBtn} ${enabled ? styles.enabled : ''} ${disabled ? styles.disabled : ''}`}
      title={enabled ? 'Course management enabled - AI can create, delete, and manage courses' : 'Enable AI to manage courses (create, delete, view)'}
    >
      <span className={styles.toggleIcon}>
        {enabled ? '📚' : '📖'}
      </span>
      <span className={styles.toggleLabel}>
        {enabled ? 'Course Mgmt ON' : 'Course Mgmt'}
      </span>
    </button>
  );
}
