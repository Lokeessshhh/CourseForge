'use client';

import styles from './WebSearchToggle.module.css';

interface Props {
  enabled: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

export default function WebSearchToggle({ enabled, onToggle, disabled = false }: Props) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className={`${styles.toggleBtn} ${enabled ? styles.enabled : ''} ${disabled ? styles.disabled : ''}`}
      title={enabled ? 'Web search enabled - AI will search the internet' : 'Enable web search for real-time information'}
    >
      <span className={styles.toggleIcon}>
        {enabled ? '🌐' : '🌍'}
      </span>
      <span className={styles.toggleLabel}>
        {enabled ? 'Web Search ON' : 'Web Search'}
      </span>
    </button>
  );
}
