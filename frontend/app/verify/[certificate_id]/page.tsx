'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { useApiClient } from '@/app/hooks/useApiClient';
import styles from './verify.module.css';

interface VerificationResult {
  valid: boolean;
  certificate_id?: string;
  student_name?: string;
  course_name?: string;
  course_topic?: string;
  issued_at?: string;
  final_score?: number;
  total_study_hours?: number;
  is_unlocked?: boolean;
  message?: string;
}

export default function VerifyCertificatePage() {
  const params = useParams();
  const router = useRouter();
  const api = useApiClient();
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const verifyCertificate = async () => {
      const certificateId = params.certificate_id as string;
      if (!certificateId) {
        setError('No certificate ID provided');
        setIsLoading(false);
        return;
      }

      try {
        // Use public endpoint (no auth required)
        const response = await fetch(`/api/certificates/verify/${certificateId}/`);
        const data = await response.json();
        
        if (data.success) {
          setResult(data.data);
        } else {
          setError(data.error || 'Failed to verify certificate');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    };

    verifyCertificate();
  }, [params.certificate_id, api]);

  if (isLoading) {
    return (
      <div className={styles.page}>
        <div className={styles.loadingBox}>
          <div className={styles.spinner}></div>
          <p className={styles.loadingText}>VERIFYING CERTIFICATE...</p>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className={styles.page}>
        <div className={styles.errorBox}>
          <span className={styles.errorIcon}></span>
          <h2 className={styles.errorTitle}>INVALID CERTIFICATE</h2>
          <p className={styles.errorMessage}>{error || 'Certificate not found'}</p>
          <button 
            className={styles.backBtn}
            onClick={() => router.push('/')}
          >
            BACK TO HOME →
          </button>
        </div>
      </div>
    );
  }

  if (!result.valid) {
    return (
      <div className={styles.page}>
        <div className={styles.errorBox}>
          <span className={styles.errorIcon}></span>
          <h2 className={styles.errorTitle}>CERTIFICATE NOT FOUND</h2>
          <p className={styles.errorMessage}>{result.message}</p>
          <button 
            className={styles.backBtn}
            onClick={() => router.push('/')}
          >
            BACK TO HOME →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.verificationContainer}>
        {/* Verification Badge */}
        <div className={styles.verificationBadge}>
          <span className={styles.checkmark}></span>
          <h1 className={styles.verifiedTitle}>CERTIFICATE VERIFIED</h1>
          <p className={styles.verifiedSubtitle}>This is a valid CourseForge certificate</p>
        </div>

        {/* Certificate Details */}
        <div className={styles.certificateDetails}>
          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>CERTIFICATE ID</span>
            <span className={styles.detailValue}>{result.certificate_id}</span>
          </div>

          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>AWARDED TO</span>
            <span className={styles.detailValue}>{result.student_name}</span>
          </div>

          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>COURSE</span>
            <span className={styles.detailValue}>{result.course_name}</span>
          </div>

          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>TOPIC</span>
            <span className={styles.detailValue}>{result.course_topic}</span>
          </div>

          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>ISSUED ON</span>
            <span className={styles.detailValue}>
              {result.issued_at ? new Date(result.issued_at).toLocaleDateString() : 'N/A'}
            </span>
          </div>

          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>FINAL SCORE</span>
            <span className={styles.detailValue}>{result.final_score}%</span>
          </div>

          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>STUDY HOURS</span>
            <span className={styles.detailValue}>{result.total_study_hours}h</span>
          </div>

          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>STATUS</span>
            <span className={`${styles.detailValue} ${styles.statusBadge} ${result.is_unlocked ? styles.unlocked : styles.locked}`}>
              {result.is_unlocked ? ' UNLOCKED' : 'LOCKED'}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <p className={styles.footerText}>
            Verified by CourseForge Certificate System
          </p>
          <a 
            href="/" 
            className={styles.homeLink}
          >
            BACK TO COURSEFORGE →
          </a>
        </div>
      </div>
    </div>
  );
}
