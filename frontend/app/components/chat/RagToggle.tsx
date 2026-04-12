'use client';

import styles from './RagToggle.module.css';

interface Props {
  enabled: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

export default function RagToggle({ enabled, onToggle, disabled = false }: Props) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className={`${styles.toggleBtn} ${enabled ? styles.enabled : ''} ${disabled ? styles.disabled : ''}`}
      title={enabled ? 'Knowledge Base enabled - AI will use your uploaded documents' : 'Enable Knowledge Base to use uploaded documents for answers'}
    >
      <span className={styles.toggleIcon}>
        {enabled ? '' : ''}
      </span>
      <span className={styles.toggleLabel}>
        {enabled ? 'Knowledge Base ON' : 'Knowledge Base'}
      </span>
    </button>
  );
}
