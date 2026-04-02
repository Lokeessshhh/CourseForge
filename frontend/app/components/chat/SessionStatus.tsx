'use client';

import styles from './SessionStatus.module.css';

interface Props {
  isConnected: boolean;
  isSessionSwitching: boolean;
}

export default function SessionStatus({ isConnected, isSessionSwitching }: Props) {
  // Show switching state when session is changing
  const isSwitching = isSessionSwitching;
  const isDisconnected = !isConnected;

  return (
    <div className={styles.container}>
      <div className={`${styles.statusBadge} ${isSwitching ? styles.switching : isDisconnected ? styles.disconnected : styles.connected}`}>
        <span className={styles.statusDot}></span>
        <span className={styles.statusText}>
          {isSwitching ? 'SWITCHING SESSION...' : isDisconnected ? 'SESSION DISCONNECTED' : 'SESSION ACTIVE'}
        </span>
      </div>
    </div>
  );
}
