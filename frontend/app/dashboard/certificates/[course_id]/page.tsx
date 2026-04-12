'use client';

import { motion } from 'framer-motion';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useCertificate } from '@/app/hooks/api';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
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
        <span className={styles.errorText}> FAILED TO LOAD · {message}</span>
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
        {/* Left: Big Blurred Certificate Preview */}
        <motion.div
          className={`${styles.certificatePreview} ${styles.bigPreviewContainer}`}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className={`${styles.certificate} ${styles.locked} ${styles.bigDemo}`}>
            {/* Corner Decorations */}
            <div className={`${styles.cornerDecoration} ${styles.topLeft}`}></div>
            <div className={`${styles.cornerDecoration} ${styles.topRight}`}></div>
            <div className={`${styles.cornerDecoration} ${styles.bottomLeft}`}></div>
            <div className={`${styles.cornerDecoration} ${styles.bottomRight}`}></div>

            {/* Watermark */}
            <div className={styles.watermark}>COURSEFORGE</div>

            {/* Full-size blurred certificate content */}
            <div className={`${styles.certificateInner} ${styles.blur}`}>
              {/* Header */}
              <div className={styles.demoHeader}>
                <h1 className={styles.demoLogo}>COURSEFORGE</h1>
                <p className={styles.demoAccreditation}>AI LEARNING PLATFORM</p>
              </div>

              {/* Title */}
              <div className={styles.demoTitleSection}>
                <div className={styles.decorativeDivider}></div>
                <h2 className={styles.demoTitle}>CERTIFICATE OF COMPLETION</h2>
                <div className={styles.ornamentalLine}>
                  <span className={styles.lineLeft}></span>
                  <span className={styles.lineCenter}></span>
                  <span className={styles.lineRight}></span>
                </div>
              </div>

              {/* Body */}
              <div className={styles.demoBody}>
                <p className={styles.demoCertifyText}>This certifies that</p>
                <div className={styles.nameContainer}>
                  <h3 className={styles.demoStudentName}>Student Name</h3>
                </div>
                <p className={styles.demoCompletedText}>has successfully completed the course</p>
                <div className={styles.demoCourseContainer}>
                  <div className={styles.demoCourseBorderLeft}></div>
                  <h4 className={styles.demoCourseName}>Course Name</h4>
                  <div className={styles.demoCourseBorderRight}></div>
                </div>
                <div className={styles.achievementBadge}>
                  <span className={styles.badgeIcon}>★</span>
                  <span className={styles.badgeText}>ACHIEVEMENT LEVEL: EXCELLENCE</span>
                </div>
              </div>

              {/* Stats */}
              <div className={styles.demoStatsSection}>
                <div className={styles.statsGrid}>
                  <div className={styles.statBox}>
                    <span className={styles.demoStatLabel}>FINAL SCORE</span>
                    <span className={styles.demoStatValue}>00%</span>
                  </div>
                  <div className={styles.statBox}>
                    <span className={styles.demoStatLabel}>STUDY HOURS</span>
                    <span className={styles.demoStatValue}>0h</span>
                  </div>
                  <div className={styles.statBox}>
                    <span className={styles.demoStatLabel}>TOTAL DAYS</span>
                    <span className={styles.demoStatValue}>0</span>
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className={styles.demoFooter}>
                <div className={styles.footerDivider}></div>
                <div className={styles.footerContent}>
                  <div className={styles.footerLeft}>
                    <span className={styles.footerLabel}>DATE OF ISSUANCE</span>
                    <span className={styles.footerValue}>Date</span>
                  </div>
                  <div className={styles.footerCenter}>
                    <span className={styles.footerLabel}>CERTIFICATE ID</span>
                    <span className={styles.footerValue}>XXXX-XXXX-XXXX</span>
                  </div>
                  <div className={styles.certSeal}>
                    <div className={styles.sealOuter}>
                      <div className={styles.sealInner}>
                        <span className={styles.sealText}>CERTIFIED</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div className={styles.signatureSection}>
                  <div className={styles.signatureBox}>
                    <div className={styles.signatureLine}></div>
                    <span className={styles.signatureName}>Dr. AURA (AI Unified Research Assistant)</span>
                    <span className={styles.signatureLabel}>Instructor</span>
                  </div>
                  <div className={styles.signatureBox}>
                    <div className={styles.signatureLine}></div>
                    <span className={styles.signatureName}>Prof. COGNITO (Cognitive Optimization & Guidance Intelligence)</span>
                    <span className={styles.signatureLabel}>Program Director</span>
                  </div>
                </div>
                <div className={styles.verificationFooter}>
                  <span className={styles.verificationText}>
                    Verified at: courseforge.com/verify/XXXX-XXXX-XXXX
                  </span>
                </div>
              </div>
            </div>

            {/* Overlay with text */}
            <div className={styles.lockOverlayBig}>
              <div className={styles.overlayContentBig}>
                <h3 className={styles.lockTitleTextBig}>Complete Course</h3>
                <Link href={`/dashboard/courses/${courseId}`}>
                  <motion.button
                    className={styles.continueCourseBtnBig}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    Continue Course →
                  </motion.button>
                </Link>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Right: Info Panel */}
        <motion.div
          className={styles.actionsPanel}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <h3 className={styles.panelTitle}>CERTIFICATE LOCKED</h3>

          <div className={styles.lockedInfo}>
            <p className={styles.lockedText}>
              This certificate will be unlocked once you complete the course.
            </p>
            <ul className={styles.requirementsList}>
              <li>Complete all lessons</li>
              <li>Pass all quizzes</li>
              <li>Complete weekly tests</li>
              <li>Finish coding challenges</li>
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

  const handleDownload = async () => {
    if (!certificate) return;

    try {
      const element = document.getElementById('printable-certificate');
      if (!element) return;

      // Show loading state
      const originalText = element.innerHTML;
      
      // Capture the certificate element
      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        backgroundColor: '#ffffff',
        logging: false,
      });

      // Get image data
      const imgData = canvas.toDataURL('image/png');

      // Create PDF (A4 landscape: 297mm × 210mm)
      const pdf = new jsPDF({
        orientation: 'landscape',
        unit: 'mm',
        format: 'a4',
      });

      // Add image to PDF
      pdf.addImage(imgData, 'PNG', 0, 0, 297, 210);

      // Generate filename
      const filename = `certificate-${certificate.course_id || 'courseforge'}.pdf`;

      // Download
      pdf.save(filename);
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Failed to generate PDF. Please try again.');
    }
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
            <span className={styles.errorText}>GENERATING CERTIFICATE</span>
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
        {/* Certificate Preview */}
        <motion.div
          className={styles.certificatePreview}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className={styles.certificate} id="printable-certificate">
            {/* Corner Decorations */}
            <div className={`${styles.cornerDecoration} ${styles.topLeft}`}></div>
            <div className={`${styles.cornerDecoration} ${styles.topRight}`}></div>
            <div className={`${styles.cornerDecoration} ${styles.bottomLeft}`}></div>
            <div className={`${styles.cornerDecoration} ${styles.bottomRight}`}></div>

            {/* Watermark */}
            <div className={styles.watermark}>COURSEFORGE</div>

            <div className={styles.certificateInner}>
              {/* Header */}
              <motion.div
                className={styles.demoHeader}
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
              >
                <h1 className={styles.demoLogo}>COURSEFORGE</h1>
                <p className={styles.demoAccreditation}>AI LEARNING PLATFORM</p>
              </motion.div>

              {/* Title */}
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

              {/* Body */}
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
                    {certificate.student_name}
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
                  <h4 className={styles.demoCourseName}>{certificate.course_name}</h4>
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
                  <span className={styles.badgeText}>
                    ACHIEVEMENT LEVEL: {certificate.final_score >= 90 ? 'EXCELLENCE' : certificate.final_score >= 75 ? 'DISTINCTION' : 'MERIT'}
                  </span>
                </motion.div>
              </motion.div>

              {/* Stats */}
              <motion.div
                className={styles.demoStatsSection}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.8 }}
              >
                <div className={styles.statsGrid}>
                  <div className={styles.statBox}>
                    <span className={styles.demoStatLabel}>FINAL SCORE</span>
                    <span className={styles.demoStatValue}>{certificate.final_score}%</span>
                  </div>
                  <div className={styles.statBox}>
                    <span className={styles.demoStatLabel}>STUDY HOURS</span>
                    <span className={styles.demoStatValue}>{certificate.total_study_hours}h</span>
                  </div>
                  <div className={styles.statBox}>
                    <span className={styles.demoStatLabel}>TOTAL DAYS</span>
                    <span className={styles.demoStatValue}>{certificate.total_days}</span>
                  </div>
                </div>
              </motion.div>

              {/* Footer */}
              <motion.div
                className={styles.demoFooter}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5, delay: 0.9 }}
              >
                <div className={styles.footerDivider}></div>

                <div className={styles.footerContent}>
                  <div className={styles.footerLeft}>
                    <span className={styles.footerLabel}>DATE OF ISSUANCE</span>
                    <span className={styles.footerValue}>{certificate.completion_date}</span>
                  </div>

                  <div className={styles.footerCenter}>
                    <span className={styles.footerLabel}>CERTIFICATE ID</span>
                    <span className={styles.footerValue}>{certificate.certificate_id}</span>
                  </div>

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
                    <span className={styles.signatureName}>{certificate.instructor_name}</span>
                    <span className={styles.signatureLabel}>Instructor</span>
                  </div>
                  <div className={styles.signatureBox}>
                    <div className={styles.signatureLine}></div>
                    <span className={styles.signatureName}>{certificate.director_name}</span>
                    <span className={styles.signatureLabel}>Program Director</span>
                  </div>
                </div>

                <div className={styles.verificationFooter}>
                  <span className={styles.verificationText}>
                    Verified at:{" "}
                    <a
                      href={`/verify/${certificate.certificate_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.verificationLink}
                    >
                      courseforge.com/verify/{certificate.certificate_id}
                    </a>
                  </span>
                </div>
              </motion.div>
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
          <h3 className={styles.panelTitle}> CERTIFICATE EARNED</h3>

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
