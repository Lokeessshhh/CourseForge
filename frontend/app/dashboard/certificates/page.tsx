'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { useApiClient } from '@/app/hooks/useApiClient';
import styles from './certificates.module.css';

interface Certificate {
  id: string | null;
  course_id: string;
  course_name: string;
  topic: string;
  is_unlocked: boolean;
  issued_at: string | null;
  quiz_score_avg: number;
  test_score_avg: number;
  total_study_hours: number;
  status?: string;
}

function CertificateCard({ cert, index }: { cert: Certificate; index: number }) {
  return (
    <motion.div
      className={`${styles.certCard} ${cert.is_unlocked ? styles.unlocked : styles.locked}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1 }}
    >
      {/* Certificate Preview */}
      <div className={styles.certPreview}>
        <div className={styles.certInner}>
          <div className={styles.certHeader}>
            <span className={styles.certLogo}>COURSEFORGE</span>
          </div>
          <div className={styles.certBody}>
            <span className={styles.certTitle}>CERTIFICATE</span>
            <span className={`${styles.certCourse} ${!cert.is_unlocked ? styles.blur : ''}`}>
              {cert.course_name}
            </span>
            {!cert.is_unlocked && (
              <div className={styles.lockOverlay}>
                <span className={styles.lockIcon}>LOCK</span>
              </div>
            )}
          </div>
          <div className={styles.certFooter}>
            {cert.is_unlocked ? (
              <span className={styles.certStatus}>✓ EARNED</span>
            ) : (
              <span className={styles.certStatusLocked}>LOCKED</span>
            )}
          </div>
        </div>
      </div>

      {/* Certificate Info */}
      <div className={styles.certInfo}>
        <h4 className={styles.certCourseName}>{cert.course_name}</h4>
        <p className={styles.certTopic}>{cert.topic}</p>
        
        {cert.is_unlocked ? (
          <>
            <div className={styles.certStats}>
              <span className={styles.stat}>Score: {cert.quiz_score_avg}%</span>
              <span className={styles.stat}>{cert.total_study_hours}h</span>
            </div>
            <p className={styles.issueDate}>
              Issued: {new Date(cert.issued_at!).toLocaleDateString()}
            </p>
            <Link href={`/dashboard/certificates/${cert.course_id}`}>
              <motion.button
                className={styles.viewBtn}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                VIEW CERTIFICATE →
              </motion.button>
            </Link>
          </>
        ) : (
          <>
            <div className={styles.requirements}>
              <span className={styles.reqItem}>⬜ Complete all lessons</span>
              <span className={styles.reqItem}>⬜ Pass quizzes (70%+)</span>
              <span className={styles.reqItem}>⬜ Complete tests</span>
            </div>
            <Link href={`/dashboard/courses/${cert.course_id}`}>
              <motion.button
                className={styles.continueBtn}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                CONTINUE COURSE →
              </motion.button>
            </Link>
          </>
        )}
      </div>
    </motion.div>
  );
}

export default function CertificatesPage() {
  const api = useApiClient();
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCertificates = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await api.get<Certificate[]>('/api/certificates/');
        setCertificates(response || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    };

    fetchCertificates();
  }, [api]);

  const unlockedCerts = certificates.filter(c => c.is_unlocked);
  const lockedCerts = certificates.filter(c => !c.is_unlocked);

  return (
    <div className={styles.page}>
      <div className={styles.sectionLabel}>
        <span className={styles.labelIcon}>►</span>
        MY CERTIFICATES
      </div>

      {error ? (
        <div className={styles.errorBox}>
          <span className={styles.errorText}>✗ {error.toUpperCase()}</span>
          <button className={styles.retryBtn} onClick={() => window.location.reload()}>RETRY →</button>
        </div>
      ) : certificates.length === 0 ? (
        <div className={styles.emptyBox}>
          <span className={styles.emptyText}>NO CERTIFICATES AVAILABLE</span>
          <p className={styles.emptySubtext}>Create courses to start earning certificates.</p>
          <Link href="/dashboard/courses">
            <motion.button
              className={styles.createBtn}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              VIEW COURSES →
            </motion.button>
          </Link>
        </div>
      ) : (
        <div className={styles.certificatesContainer}>
          {/* Unlocked Certificates */}
          {unlockedCerts.length > 0 && (
            <div className={styles.certSection}>
              <h3 className={styles.sectionTitle}>✓ EARNED CERTIFICATES</h3>
              <div className={styles.certGrid}>
                {unlockedCerts.map((cert, index) => (
                  <CertificateCard key={cert.id} cert={cert} index={index} />
                ))}
              </div>
            </div>
          )}

          {/* Locked Certificates */}
          {lockedCerts.length > 0 && (
            <div className={styles.certSection}>
              <h3 className={styles.sectionTitle}>LOCKED CERTIFICATES</h3>
              <div className={styles.certGrid}>
                {lockedCerts.map((cert, index) => (
                  <CertificateCard key={cert.course_id} cert={cert} index={unlockedCerts.length + index} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
