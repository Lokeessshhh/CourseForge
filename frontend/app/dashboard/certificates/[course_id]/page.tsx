'use client';

import { motion } from 'framer-motion';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useCertificate } from '@/app/hooks/api';
import styles from './page.module.css';

function LoadingSkeleton() {
  return (
    <div className={styles.page}>
      <div className={styles.layout}>
        <div className={styles.skeletonBox} style={{ width: '600px', height: '500px' }} />
        <div className={styles.skeletonBox} style={{ width: '300px', height: '500px' }} />
      </div>
    </div>
  );
}

function ErrorBox({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className={styles.page}>
      <div className={styles.errorBox}>
        <span className={styles.errorText}>✗ FAILED TO LOAD · {message}</span>
        <motion.button
          className={styles.retryBtn}
          onClick={onRetry}
          whileHover={{ x: -2, y: -2 }}
        >
          RETRY →
        </motion.button>
      </div>
    </div>
  );
}

function LockedCertificate({ courseId }: { courseId: string }) {
  return (
    <div className={styles.page}>
      <div className={styles.layout}>
        {/* Left: Locked Certificate Preview */}
        <motion.div
          className={styles.certificatePreview}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className={`${styles.certificate} ${styles.locked}`}>
            <div className={styles.lockOverlay}>
              <span className={styles.lockIcon}>LOCK</span>
              <h3 className={styles.lockTitle}>CERTIFICATE LOCKED</h3>
              <p className={styles.lockSubtitle}>Complete the course to unlock your certificate</p>
            </div>
            <div className={styles.certificateInner}>
              <h1 className={styles.logo}>COURSEFORGE</h1>
              <h2 className={styles.title}>CERTIFICATE OF COMPLETION</h2>
              <div className={styles.borderFrame}>
                <p className={styles.intro}>This certifies that</p>
                <h3 className={`${styles.studentName} ${styles.blur}`}>Student Name</h3>
                <p className={styles.hasCompleted}>has completed</p>
                <h4 className={`${styles.courseName} ${styles.blur}`}>Course Name</h4>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Right: Actions Panel */}
        <motion.div
          className={styles.actionsPanel}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <h3 className={styles.panelTitle}>LOCKED</h3>
          
          <div className={styles.lockedInfo}>
            <p className={styles.lockedText}>
              This certificate is locked until you complete the course.
            </p>
            <ul className={styles.requirementsList}>
              <li>✓ Complete all lessons</li>
              <li>✓ Pass all quizzes (min 70%)</li>
              <li>✓ Complete weekly tests</li>
              <li>✓ Finish coding challenges</li>
            </ul>
          </div>

          <Link href={`/dashboard/courses/${courseId}`}>
            <motion.button
              className={styles.downloadBtn}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              CONTINUE COURSE →
            </motion.button>
          </Link>

          <Link href="/dashboard/certificates">
            <motion.button
              className={styles.backBtn}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              BACK TO CERTIFICATES →
            </motion.button>
          </Link>
        </motion.div>
      </div>
    </div>
  );
}

export default function CertificatePage() {
  const params = useParams();
  const courseId = params.course_id as string;

  const { data: certificate, isLoading, error, refetch } = useCertificate(courseId);

  const handleDownload = () => {
    if (!certificate?.download_url) return;
    // Create download link
    const link = document.createElement('a');
    link.href = certificate.download_url;
    link.download = `certificate-${certificate.certificate_id}.pdf`;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleCopyLink = () => {
    if (!certificate) return;
    const url = `${window.location.origin}/verify/${certificate.certificate_id}`;
    navigator.clipboard.writeText(url);
    alert('Verification link copied to clipboard!');
  };

  const handleShareLinkedIn = () => {
    if (!certificate) return;
    const url = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(
      `${window.location.origin}/verify/${certificate.certificate_id}`
    )}`;
    window.open(url, '_blank');
  };

  if (isLoading) return <LoadingSkeleton />;
  if (error) {
    return <ErrorBox message={error} onRetry={refetch} />;
  }

  // Show locked certificate view
  if (!certificate || !certificate.is_unlocked) {
    return <LockedCertificate courseId={courseId} />;
  }

  // Show generating state
  if (certificate.status === 'generating') {
    return (
      <div className={styles.page}>
        <div className={styles.layout}>
          <div className={styles.errorBox}>
            <span className={styles.errorText}>⏳ GENERATING CERTIFICATE</span>
            <p className={styles.errorSubtext}>Your certificate is being prepared. Please refresh in a moment.</p>
            <motion.button 
              className={styles.retryBtn} 
              onClick={refetch}
              whileHover={{ x: -2, y: -2 }}
            >
              REFRESH →
            </motion.button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.layout}>
        {/* Left: Certificate Preview */}
        <motion.div
          className={styles.certificatePreview}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className={styles.certificate}>
            <div className={styles.certificateInner}>
              <h1 className={styles.logo}>COURSEFORGE</h1>

              <h2 className={styles.title}>CERTIFICATE OF COMPLETION</h2>

              <div className={styles.borderFrame}>
                <p className={styles.intro}>This certifies that</p>

                <h3 className={styles.studentName}>{certificate.student_name}</h3>

                <p className={styles.hasCompleted}>has completed</p>

                <h4 className={styles.courseName}>{certificate.course_name}</h4>

                <div className={styles.stats}>
                  <div className={styles.statItem}>
                    <span className={styles.statLabel}>FINAL SCORE</span>
                    <span className={styles.statValue}>{certificate.final_score}%</span>
                  </div>
                  <div className={styles.statDivider}>·</div>
                  <div className={styles.statItem}>
                    <span className={styles.statLabel}>STUDY HOURS</span>
                    <span className={styles.statValue}>{certificate.total_study_hours}</span>
                  </div>
                </div>

                <p className={styles.completionDate}>
                  Completed on {certificate.completion_date}
                </p>

                <div className={styles.certificateId}>
                  <span className={styles.idLabel}>CERTIFICATE ID</span>
                  <span className={styles.idValue}>{certificate.certificate_id}</span>
                </div>
              </div>

              <div className={styles.doubleBorder}></div>
            </div>
          </div>
        </motion.div>

        {/* Right: Actions Panel */}
        <motion.div
          className={styles.actionsPanel}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <h3 className={styles.panelTitle}>✓ CERTIFICATE EARNED</h3>

          <div className={styles.actionButtons}>
            <motion.button
              className={styles.downloadBtn}
              onClick={handleDownload}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              DOWNLOAD PDF →
            </motion.button>

            <motion.button
              className={styles.outlineBtn}
              onClick={handleCopyLink}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              COPY VERIFICATION LINK →
            </motion.button>

            <motion.button
              className={styles.outlineBtn}
              onClick={handleShareLinkedIn}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              SHARE ON LINKEDIN →
            </motion.button>
          </div>

          <div className={styles.statsBreakdown}>
            <h4 className={styles.breakdownTitle}>ACHIEVEMENT STATS</h4>

            <div className={styles.breakdownList}>
              <div className={styles.breakdownRow}>
                <span className={styles.breakdownLabel}>Quiz Score</span>
                <span className={styles.breakdownValue}>{certificate.final_score}%</span>
              </div>
              <div className={styles.breakdownRow}>
                <span className={styles.breakdownLabel}>Test Score</span>
                <span className={styles.breakdownValue}>{certificate.avg_test_score}%</span>
              </div>
              <div className={styles.breakdownRow}>
                <span className={styles.breakdownLabel}>Study Hours</span>
                <span className={styles.breakdownValue}>{certificate.total_study_hours}</span>
              </div>
              <div className={styles.breakdownRow}>
                <span className={styles.breakdownLabel}>Total Days</span>
                <span className={styles.breakdownValue}>{certificate.total_days}</span>
              </div>
              <div className={styles.breakdownRow}>
                <span className={styles.breakdownLabel}>Completed</span>
                <span className={styles.breakdownValue}>{certificate.completion_date}</span>
              </div>
            </div>
          </div>

          <div className={styles.verificationInfo}>
            <p className={styles.verificationText}>
              LOCK This certificate can be verified at:
            </p>
            <code className={styles.verificationUrl}>
              /verify/{certificate.certificate_id}
            </code>
          </div>

          <Link href="/dashboard/certificates">
            <motion.button
              className={styles.backBtn}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              BACK TO CERTIFICATES →
            </motion.button>
          </Link>
        </motion.div>
      </div>
    </div>
  );
}
