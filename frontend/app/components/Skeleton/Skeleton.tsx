'use client';

import { motion } from 'framer-motion';
import styles from './Skeleton.module.css';

interface SkeletonProps {
  width?: string;
  height?: string;
  className?: string;
}

export function Skeleton({ width = '100%', height = '60px', className = '' }: SkeletonProps) {
  return (
    <div
      className={`${styles.skeleton} ${className}`}
      style={{ width, height }}
    />
  );
}

export function DashboardSkeleton() {
  return (
    <div className={styles.page}>
      {/* Top Strip */}
      <div className={styles.topStrip}>
        <Skeleton width="200px" height="24px" />
        <div className={styles.statsRow}>
          {[1, 2, 3, 4].map(i => (
            <Skeleton key={i} width="140px" height="80px" />
          ))}
        </div>
      </div>

      {/* Active Course */}
      <div className={styles.section}>
        <Skeleton width="100%" height="300px" />
      </div>

      {/* Knowledge State */}
      <div className={styles.section}>
        <Skeleton width="100%" height="200px" />
      </div>

      {/* All Courses */}
      <div className={styles.section}>
        {[1, 2, 3].map(i => (
          <Skeleton key={i} width="100%" height="60px" />
        ))}
      </div>
    </div>
  );
}

export function CourseCardSkeleton() {
  return (
    <div className={styles.courseCard}>
      <Skeleton width="60%" height="24px" />
      <Skeleton width="30%" height="16px" />
      <Skeleton width="100%" height="12px" className={styles.progressBar} />
      <Skeleton width="40%" height="14px" />
    </div>
  );
}

export function ChatSkeleton() {
  return (
    <div className={styles.chat}>
      {[1, 2, 3].map(i => (
        <div key={i} className={styles.message}>
          <Skeleton width="100%" height="40px" />
        </div>
      ))}
    </div>
  );
}

export function SidebarSkeleton() {
  return (
    <div className={styles.sidebar}>
      <Skeleton width="100%" height="40px" />
      <div className={styles.userSection}>
        <Skeleton width="100%" height="20px" />
        <Skeleton width="80%" height="16px" />
      </div>
      {[1, 2, 3, 4, 5].map(i => (
        <Skeleton key={i} width="100%" height="40px" />
      ))}
    </div>
  );
}
