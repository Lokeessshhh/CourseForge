'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import styles from './CourseUpdateModal.module.css';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (updateType: 'percentage' | 'extend' | 'compact', options: UpdateOptions) => Promise<void>;
  courseName: string;
  currentDurationWeeks: number;
  isSubmitting?: boolean;
}

interface UpdateOptions {
  percentage?: 50 | 75;
  extendWeeks?: number;
  targetWeeks?: number;
}

export type UpdateType = 'percentage' | 'extend' | 'compact';

export default function CourseUpdateModal({
  isOpen,
  onClose,
  onSubmit,
  courseName,
  currentDurationWeeks,
  isSubmitting = false,
}: Props) {
  const [selectedType, setSelectedType] = useState<UpdateType | null>(null);
  const [percentage, setPercentage] = useState<50 | 75>(50);
  const [extendWeeks, setExtendWeeks] = useState<string>('');
  const [targetWeeks, setTargetWeeks] = useState<string>('');
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string>('');

  const resetState = () => {
    setSelectedType(null);
    setPercentage(50);
    setExtendWeeks('');
    setTargetWeeks('');
    setIsConfirming(false);
    setError('');
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handleSelectType = (type: UpdateType) => {
    setSelectedType(type);
    setError('');
  };

  const handleContinue = () => {
    if (!selectedType) return;

    // Validate inputs based on type
    if (selectedType === 'extend') {
      const weeks = parseInt(extendWeeks, 10);
      if (isNaN(weeks) || weeks < 1) {
        setError('Please enter a valid number of weeks');
        return;
      }
      if (weeks > 52) {
        setError('Maximum 52 weeks allowed');
        return;
      }
    }

    if (selectedType === 'compact') {
      const weeks = parseInt(targetWeeks, 10);
      if (isNaN(weeks) || weeks < 1) {
        setError('Please enter a valid number of weeks');
        return;
      }
      if (weeks >= currentDurationWeeks) {
        setError(`Target weeks must be less than ${currentDurationWeeks}`);
        return;
      }
    }

    setIsConfirming(true);
    setError('');
  };

  const handleBack = () => {
    setIsConfirming(false);
    setError('');
  };

  const handleConfirm = async () => {
    if (!selectedType) return;

    const options: UpdateOptions = {};

    if (selectedType === 'percentage') {
      options.percentage = percentage;
    } else if (selectedType === 'extend') {
      options.extendWeeks = parseInt(extendWeeks, 10);
    } else if (selectedType === 'compact') {
      options.targetWeeks = parseInt(targetWeeks, 10);
    }

    try {
      await onSubmit(selectedType, options);
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed');
      setIsConfirming(false);
    }
  };

  const getNewDuration = () => {
    if (!selectedType) return currentDurationWeeks;

    if (selectedType === 'percentage') {
      return currentDurationWeeks;
    } else if (selectedType === 'extend') {
      const weeks = parseInt(extendWeeks, 10) || 0;
      return currentDurationWeeks + weeks;
    } else if (selectedType === 'compact') {
      const weeks = parseInt(targetWeeks, 10) || currentDurationWeeks;
      return weeks;
    }
    return currentDurationWeeks;
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className={styles.modalOverlay} onClick={handleClose}>
        <motion.div
          className={styles.modal}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.2 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className={styles.modalHeader}>
            <h2 className={styles.modalTitle}>UPDATE COURSE</h2>
            <button className={styles.closeBtn} onClick={handleClose} disabled={isSubmitting}>
              ×
            </button>
          </div>

          <div className={styles.modalBody}>
            {/* Course Info */}
            <div className={styles.courseInfo}>
              <span className={styles.courseLabel}>COURSE:</span>
              <span className={styles.courseValue}>{courseName}</span>
              <span className={styles.durationLabel}>CURRENT:</span>
              <span className={styles.durationValue}>{currentDurationWeeks} WEEKS</span>
            </div>

            {!isConfirming ? (
              <>
                {/* Update Type Selection */}
                <div className={styles.field}>
                  <label className={styles.label}>UPDATE TYPE *</label>
                  <div className={styles.typeOptions}>
                    {/* Option 1: Update Current (50%/75%) */}
                    <div
                      className={`${styles.typeOption} ${selectedType === 'percentage' ? styles.selected : ''}`}
                      onClick={() => handleSelectType('percentage')}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleSelectType('percentage');
                        }
                      }}
                      aria-disabled={isSubmitting}
                    >
                      <div className={styles.typeOptionHeader}>
                        <span className={styles.typeNumber}>1</span>
                        <span className={styles.typeLabel}>UPDATE CURRENT</span>
                      </div>
                      <p className={styles.typeDescription}>
                        Replace percentage of course with new content
                      </p>
                      {selectedType === 'percentage' && (
                        <div className={styles.percentageSelector}>
                          <button
                            className={`${styles.percentageBtn} ${percentage === 50 ? styles.selected : ''}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setPercentage(50);
                            }}
                            disabled={isSubmitting}
                          >
                            50%
                          </button>
                          <button
                            className={`${styles.percentageBtn} ${percentage === 75 ? styles.selected : ''}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setPercentage(75);
                            }}
                            disabled={isSubmitting}
                          >
                            75%
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Option 2: Extend + Update */}
                    <div
                      className={`${styles.typeOption} ${selectedType === 'extend' ? styles.selected : ''}`}
                      onClick={() => handleSelectType('extend')}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleSelectType('extend');
                        }
                      }}
                      aria-disabled={isSubmitting}
                    >
                      <div className={styles.typeOptionHeader}>
                        <span className={styles.typeNumber}>2</span>
                        <span className={styles.typeLabel}>EXTEND + UPDATE</span>
                      </div>
                      <p className={styles.typeDescription}>
                        Keep all content and add more weeks
                      </p>
                      {selectedType === 'extend' && (
                        <div className={styles.extendInput}>
                          <label className={styles.inputLabel}>ADD WEEKS:</label>
                          <input
                            type="number"
                            className={styles.numberInput}
                            value={extendWeeks}
                            onChange={(e) => {
                              e.stopPropagation();
                              setExtendWeeks(e.target.value);
                              setError('');
                            }}
                            onClick={(e) => e.stopPropagation()}
                            min="1"
                            max="52"
                            placeholder="6"
                            disabled={isSubmitting}
                          />
                        </div>
                      )}
                    </div>

                    {/* Option 3: Compact Course */}
                    <div
                      className={`${styles.typeOption} ${selectedType === 'compact' ? styles.selected : ''}`}
                      onClick={() => handleSelectType('compact')}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleSelectType('compact');
                        }
                      }}
                      aria-disabled={isSubmitting}
                    >
                      <div className={styles.typeOptionHeader}>
                        <span className={styles.typeNumber}>3</span>
                        <span className={styles.typeLabel}>COMPACT COURSE</span>
                      </div>
                      <p className={styles.typeDescription}>
                        Compress course into fewer weeks
                      </p>
                      {selectedType === 'compact' && (
                        <div className={styles.compactInput}>
                          <label className={styles.inputLabel}>TARGET WEEKS:</label>
                          <input
                            type="number"
                            className={styles.numberInput}
                            value={targetWeeks}
                            onChange={(e) => {
                              e.stopPropagation();
                              setTargetWeeks(e.target.value);
                              setError('');
                            }}
                            onClick={(e) => e.stopPropagation()}
                            min="1"
                            max={currentDurationWeeks - 1}
                            placeholder={`1-${currentDurationWeeks - 1}`}
                            disabled={isSubmitting}
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {error && <p className={styles.errorText}>{error}</p>}
                </div>

                {/* Duration Preview */}
                {selectedType && (
                  <div className={styles.durationPreview}>
                    <span className={styles.previewLabel}>NEW DURATION:</span>
                    <span className={styles.previewValue}>
                      {currentDurationWeeks} → {getNewDuration()} WEEKS
                    </span>
                  </div>
                )}
              </>
            ) : (
              /* Confirmation Screen */
              <div className={styles.confirmBox}>
                <div className={styles.confirmHeader}>
                  <span className={styles.confirmIcon}>⚠️</span>
                  <h4 className={styles.confirmTitle}>CONFIRM UPDATE</h4>
                </div>

                <div className={styles.confirmContent}>
                  <p className={styles.confirmText}>
                    You're about to update this course with:
                  </p>
                  <div className={styles.confirmSummary}>
                    {selectedType === 'percentage' && (
                      <>
                        <strong>UPDATE CURRENT ({percentage}%)</strong>
                        <p>Replace last {percentage}% of course content</p>
                        <p>Duration: {currentDurationWeeks} weeks (unchanged)</p>
                      </>
                    )}
                    {selectedType === 'extend' && (
                      <>
                        <strong>EXTEND + UPDATE</strong>
                        <p>Add {extendWeeks} weeks to current duration</p>
                        <p>Duration: {currentDurationWeeks} → {getNewDuration()} weeks</p>
                      </>
                    )}
                    {selectedType === 'compact' && (
                      <>
                        <strong>COMPACT COURSE</strong>
                        <p>Compress to {targetWeeks} weeks</p>
                        <p>Duration: {currentDurationWeeks} → {getNewDuration()} weeks</p>
                      </>
                    )}
                  </div>
                  <div className={styles.confirmNote}>
                    <strong>Note:</strong> Your progress in updated weeks will be reset.
                  </div>
                </div>

                {error && <p className={styles.errorText}>{error}</p>}
              </div>
            )}
          </div>

          <div className={styles.modalFooter}>
            {!isConfirming ? (
              <>
                <button
                  className={styles.cancelBtn}
                  onClick={handleClose}
                  disabled={isSubmitting}
                >
                  CANCEL
                </button>
                <button
                  className={`${styles.submitBtn} ${!selectedType ? styles.disabled : ''}`}
                  onClick={handleContinue}
                  disabled={!selectedType || isSubmitting}
                >
                  {isSubmitting ? 'PROCESSING...' : 'CONTINUE →'}
                </button>
              </>
            ) : (
              <>
                <button
                  className={styles.backBtn}
                  onClick={handleBack}
                  disabled={isSubmitting}
                >
                  ← BACK
                </button>
                <button
                  className={styles.confirmBtn}
                  onClick={handleConfirm}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'UPDATING...' : '✓ CONFIRM UPDATE'}
                </button>
              </>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
