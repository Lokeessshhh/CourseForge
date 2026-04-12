'use client';

import React, { useState } from 'react';
import styles from './CourseUpdateOptions.module.css';

export interface UpdateOption {
  type: '50%' | '75%' | 'extend_50%' | 'compact' | 'custom_update';
  label: string;
  description: string;
  duration_change: string;
  requires_input?: boolean;
  input_label?: string;
  input_placeholder?: string;
  input_min?: number;
  input_max?: number;
  available?: boolean;
  coming_soon?: boolean;
  badge?: string;
}

interface CourseUpdateOptionsProps {
  courseId: string;
  courseName: string;
  userQuery: string;
  updateOptions: UpdateOption[];
  currentDurationWeeks?: number;
  onSelect: (updateType: '50%' | '75%' | 'extend_50%' | 'compact' | 'custom_update', targetWeeks?: number) => void;
  onCancel?: () => void;
}

/**
 * CourseUpdateOptions Component
 * Matches the brutalist/retro theme of CourseCreationForm
 * Dynamically renders options from backend
 */
export function CourseUpdateOptions({
  courseId,
  courseName,
  userQuery,
  updateOptions,
  currentDurationWeeks = 4,
  onSelect,
  onCancel,
}: CourseUpdateOptionsProps) {
  const [selectedOption, setSelectedOption] = useState<UpdateOption | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [targetWeeks, setTargetWeeks] = useState<string>('2');

  const handleOptionClick = (option: UpdateOption) => {
    if (!option.available) return;
    setSelectedOption(option);
    if (option.requires_input) {
      setIsConfirming(false); // Show input first
    } else {
      setIsConfirming(true); // Show confirmation
    }
  };

  const handleConfirmInput = () => {
    setIsConfirming(true);
  };

  const handleFinalConfirm = () => {
    if (selectedOption) {
      if (selectedOption.requires_input) {
        const weeks = parseInt(targetWeeks) || 2;
        onSelect(selectedOption.type, weeks);
      } else {
        onSelect(selectedOption.type);
      }
      setIsConfirming(false);
      setSelectedOption(null);
    }
  };

  const handleCancel = () => {
    setIsConfirming(false);
    setSelectedOption(null);
    onCancel?.();
  };

  const handleBack = () => {
    if (isConfirming && selectedOption?.requires_input) {
      setIsConfirming(false);
    } else {
      handleCancel();
    }
  };

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <span className={styles.icon}></span>
        <div>
          <h3 className={styles.title}>Update Course</h3>
          <p className={styles.courseName}>{courseName}</p>
        </div>
      </div>

      {/* Update Request */}
      <div className={styles.requestBox}>
        <span className={styles.requestLabel}>Update Request:</span>{' '}
        <span className={styles.requestValue}>{userQuery}</span>
      </div>

      {!isConfirming || (isConfirming && selectedOption?.requires_input && !targetWeeks) ? (
        <>
          {/* Options - Dynamically rendered from backend */}
          <div className={styles.options}>
            {updateOptions.map((option, index) => (
              <div
                key={option.type}
                className={`${styles.optionCard} ${!option.available ? styles.optionCardDisabled : ''}`}
              >
                <div className={styles.optionHeader}>
                  <span className={styles.optionNumber}>{index + 1}</span>
                  <h4 className={styles.optionLabel}>
                    {option.label}
                    {option.badge && <span className={styles.comingSoonBadge}>{option.badge}</span>}
                  </h4>
                </div>
                <p className={styles.optionDescription}>{option.description}</p>

                {/* Input for Compact Course */}
                {option.requires_input && (
                  <div className={styles.inputContainer}>
                    <label className={styles.inputLabel}>
                      {option.input_label || 'Target weeks'}
                    </label>
                    <input
                      type="number"
                      min={option.input_min || 1}
                      max={option.input_max || currentDurationWeeks}
                      value={targetWeeks}
                      onChange={(e) => setTargetWeeks(e.target.value)}
                      className={styles.numberInput}
                      placeholder={option.input_placeholder || `Enter 1-${currentDurationWeeks}`}
                    />
                  </div>
                )}

                {/* Duration Change Info */}
                <div className={styles.optionInfo}>
                  <span className={styles.infoBadge}>{option.duration_change}</span>
                </div>

                {/* Action Button */}
                {option.available ? (
                  option.requires_input ? (
                    <button
                      onClick={() => handleOptionClick(option)}
                      className={styles.selectBtn}
                    >
                      {isConfirming ? 'Change Weeks' : 'Select & Continue'}
                    </button>
                  ) : (
                    <button
                      onClick={() => handleOptionClick(option)}
                      className={styles.selectBtn}
                    >
                      Select This Option
                    </button>
                  )
                ) : (
                  <button className={styles.selectBtnDisabled} disabled>
                    {option.coming_soon ? 'Coming Soon' : 'Not Available'}
                  </button>
                )}
              </div>
            ))}
          </div>

          {onCancel && (
            <div className={styles.actions}>
              <button onClick={handleCancel} className={styles.cancelBtn}>
                Cancel
              </button>
            </div>
          )}
        </>
      ) : selectedOption?.requires_input ? (
        /* Input Confirmation */
        <div className={styles.confirmBox}>
          <div className={styles.confirmHeader}>
            <span className={styles.confirmIcon}></span>
            <h4 className={styles.confirmTitle}>Compact Course</h4>
          </div>
          <p className={styles.confirmText}>
            You're about to compress your {currentDurationWeeks}-week course into {targetWeeks} weeks.
            This will redesign the entire course with focused, high-impact content.
          </p>
          <div className={styles.confirmNote}>
            <strong>Note:</strong> All weeks will be regenerated with compressed content. Your progress will be reset.
          </div>
          <div className={styles.confirmActions}>
            <button onClick={handleFinalConfirm} className={styles.confirmBtn}>
               Confirm Compact to {targetWeeks} Weeks
            </button>
            <button onClick={handleBack} className={styles.backBtn}>
              ← Go Back
            </button>
          </div>
        </div>
      ) : (
        /* Final Confirmation */
        <div className={styles.confirmBox}>
          <div className={styles.confirmHeader}>
            <span className={styles.confirmIcon}></span>
            <h4 className={styles.confirmTitle}>Confirm Update</h4>
          </div>
          <p className={styles.confirmText}>
            You're about to update this course with: <strong>{selectedOption?.label}</strong>
          </p>
          <p className={styles.confirmSubtext}>
            {selectedOption?.description}
          </p>
          <div className={styles.confirmNote}>
            <strong>Note:</strong> Your progress in the updated weeks will be reset.
          </div>
          <div className={styles.confirmActions}>
            <button onClick={handleFinalConfirm} className={styles.confirmBtn}>
               Confirm Update
            </button>
            <button onClick={handleBack} className={styles.backBtn}>
              ← Go Back
            </button>
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className={styles.infoBox}>
        <div className={styles.infoHeader}>
          <span className={styles.infoIcon}>ℹ</span>
          <h5 className={styles.infoTitle}>Available Options:</h5>
        </div>
        <ul className={styles.infoList}>
          <li><strong>Update Current (50%/75%):</strong> Replaces percentage of course with new content</li>
          <li><strong>Compact Course:</strong> Compress entire course into fewer weeks</li>
          <li><strong>Extend + Update:</strong> Keep all content and add more weeks</li>
          <li><strong>Custom Update:</strong> Select specific weeks (Coming Soon)</li>
        </ul>
      </div>
    </div>
  );
}

export default CourseUpdateOptions;
