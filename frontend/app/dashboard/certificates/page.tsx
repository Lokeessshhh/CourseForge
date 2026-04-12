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
  completion_percentage?: number;
}

function CertificateCard({ cert, index }: { cert: Certificate; index: number }) {
  const progress = cert.completion_percentage || 0;

  // Debug logging
  console.log(`CertificateCard - Course: ${cert.course_name}, Progress: ${progress}%, Is Unlocked: ${cert.is_unlocked}`);

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
              <span className={styles.certStatus}> EARNED</span>
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
            {/* Progress Bar for Locked Certificates */}
            <div className={styles.progressSection}>
              <div className={styles.progressHeader}>
                <span className={styles.progressLabel}>PROGRESS</span>
                <span className={styles.progressValue}>{Math.round(progress)}%</span>
              </div>
              <div className={styles.progressBar}>
                <motion.div
                  className={styles.progressFill}
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                  key={`progress-${cert.course_id}-${progress}`}
                />
              </div>
              <p className={styles.progressHint}>
                Complete course to unlock certificate
              </p>
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
        console.log('API Response - Certificates:', response);
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
          <span className={styles.errorText}> {error.toUpperCase()}</span>
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
          {/* Big Demo Certificate Preview */}
          <motion.div
            className={styles.bigDemoCertificate}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          >
            <div className={styles.demoCertPreview}>
              {/* Corner Decorations */}
              <div className={styles.cornerDecoration + ' ' + styles.topLeft}></div>
              <div className={styles.cornerDecoration + ' ' + styles.topRight}></div>
              <div className={styles.cornerDecoration + ' ' + styles.bottomLeft}></div>
              <div className={styles.cornerDecoration + ' ' + styles.bottomRight}></div>

              {/* Watermark */}
              <div className={styles.watermark}>COURSEFORGE</div>

              <div className={styles.demoCertInner}>
                {/* Header Section */}
                <motion.div
                  className={styles.demoHeader}
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.2 }}
                >
                  <h1 className={styles.demoLogo}>COURSEFORGE</h1>
                  <p className={styles.demoAccreditation}>AI LEARNING PLATFORM</p>
                </motion.div>

                {/* Title Section */}
                <motion.div
                  className={styles.demoTitleSection}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.5, delay: 0.3 }}
                >
                  <div className={styles.decorativeDivider}></div>
                  <h2 className={styles.demoTitle}>CERTIFICATE OF COMPLETION</h2>
                  <div className={styles.ornamentalLine}>
                    <span className={styles.lineLeft}></span>
                    <span className={styles.lineCenter}></span>
                    <span className={styles.lineRight}></span>
                  </div>
                </motion.div>

                {/* Body Section */}
                <motion.div
                  className={styles.demoBody}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.5, delay: 0.4 }}
                >
                  <p className={styles.demoCertifyText}>This certifies that</p>

                  <div className={styles.nameContainer}>
                    <motion.h3
                      className={styles.demoStudentName}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.6, delay: 0.5 }}
                    >
                      Student Name
                    </motion.h3>
                  </div>

                  <p className={styles.demoCompletedText}>has successfully completed the course</p>

                  <motion.div
                    className={styles.demoCourseContainer}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.6 }}
                  >
                    <div className={styles.demoCourseBorderLeft}></div>
                    <h4 className={styles.demoCourseName}>Course Name</h4>
                    <div className={styles.demoCourseBorderRight}></div>
                  </motion.div>

                  {/* Achievement Level Badge */}
                  <motion.div
                    className={styles.achievementBadge}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5, delay: 0.7, type: "spring", stiffness: 200 }}
                  >
                    <span className={styles.badgeIcon}>★</span>
                    <span className={styles.badgeText}>ACHIEVEMENT LEVEL: EXCELLENCE</span>
                  </motion.div>
                </motion.div>

                {/* Stats Section */}
                <motion.div
                  className={styles.demoStatsSection}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.8 }}
                >
                  <div className={styles.statsGrid}>
                    <div className={styles.statBox}>
                      <span className={styles.demoStatLabel}>FINAL SCORE</span>
                      <span className={styles.demoStatValue}>95%</span>
                    </div>
                    <div className={styles.statBox}>
                      <span className={styles.demoStatLabel}>STUDY HOURS</span>
                      <span className={styles.demoStatValue}>40h</span>
                    </div>
                    <div className={styles.statBox}>
                      <span className={styles.demoStatLabel}>TOTAL DAYS</span>
                      <span className={styles.demoStatValue}>28</span>
                    </div>
                  </div>
                </motion.div>

                {/* Footer Section */}
                <motion.div
                  className={styles.demoFooter}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.5, delay: 0.9 }}
                >
                  <div className={styles.footerDivider}></div>

                  <div className={styles.footerContent}>
                    {/* Left: Date */}
                    <div className={styles.footerLeft}>
                      <span className={styles.footerLabel}>DATE OF ISSUANCE</span>
                      <span className={styles.footerValue}>April 11, 2026</span>
                    </div>

                    {/* Center: Certificate ID */}
                    <div className={styles.footerCenter}>
                      <span className={styles.footerLabel}>CERTIFICATE ID</span>
                      <span className={styles.footerValue}>XXXX-XXXX-XXXX</span>
                    </div>

                    {/* Right: Seal */}
                    <motion.div
                      className={styles.certSeal}
                      initial={{ opacity: 0, rotate: -180, scale: 0 }}
                      animate={{ opacity: 1, rotate: 0, scale: 1 }}
                      transition={{ duration: 0.8, delay: 1, type: "spring", stiffness: 150 }}
                    >
                      <div className={styles.sealOuter}>
                        <div className={styles.sealInner}>
                          <span className={styles.sealText}>CERTIFIED</span>
                        </div>
                      </div>
                    </motion.div>
                  </div>

                  <div className={styles.signatureSection}>
                    <div className={styles.signatureBox}>
                      <div className={styles.signatureLine}></div>
                      <span className={styles.signatureLabel}>Instructor</span>
                    </div>
                    <div className={styles.signatureBox}>
                      <div className={styles.signatureLine}></div>
                      <span className={styles.signatureLabel}>Program Director</span>
                    </div>
                  </div>

                  <div className={styles.verificationFooter}>
                    <span className={styles.verificationText}>
                      Verified at: courseforge.com/verify/XXXX-XXXX-XXXX
                    </span>
                  </div>
                </motion.div>
              </div>
            </div>
          </motion.div>

          {/* Unlocked Certificates */}
          {unlockedCerts.length > 0 && (
            <div className={styles.certSection}>
              <h3 className={styles.sectionTitle}> EARNED CERTIFICATES</h3>
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
