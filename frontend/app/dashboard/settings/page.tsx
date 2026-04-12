'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useUser, useUserSettings, useUserActions } from '@/app/hooks/api';
import styles from './page.module.css';

const skillLevels = ['BEGINNER', 'INTERMEDIATE', 'ADVANCED'] as const;

function LoadingSkeleton() {
  return (
    <div className={styles.page}>
      <div className={styles.container}>
        {[1, 2, 3, 4].map(i => (
          <div key={i} className={styles.skeletonBox} style={{ width: '100%', height: '200px', marginBottom: '24px' }} />
        ))}
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

export default function SettingsPage() {
  const { data: user, isLoading, error, refetch, update } = useUser();
  const { data: settings, refetch: refetchSettings, update: updateSettings } = useUserSettings();
  const { exportData, deleteAccount, isSubmitting, error: actionsError } = useUserActions();

  const [name, setName] = useState('');
  const [skillLevel, setSkillLevel] = useState<typeof skillLevels[number]>('INTERMEDIATE');
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [streakReminders, setStreakReminders] = useState(true);
  const [weeklyReport, setWeeklyReport] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Initialize form when user data loads
  useEffect(() => {
    if (user) {
      setName(user.name);
      setSkillLevel(user.skill_level as typeof skillLevels[number]);
    }
    if (settings) {
      setEmailNotifications(settings.email_notifications);
      setStreakReminders(settings.streak_reminders);
      setWeeklyReport(settings.weekly_report);
    }
  }, [user, settings]);

  const handleSaveProfile = async () => {
    setIsSaving(true);
    await update({ name, skill_level: skillLevel });
    await updateSettings({ email_notifications: emailNotifications, streak_reminders: streakReminders, weekly_report: weeklyReport });
    setIsSaving(false);
  };

  const handleExportData = async () => {
    const result = await exportData();
    if (result) {
      alert('Your data export has been initiated. You will receive an email when ready.');
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmText === 'DELETE') {
      const result = await deleteAccount();
      if (result) {
        alert('Account deletion initiated. This action cannot be undone.');
        setShowDeleteConfirm(false);
      }
    }
  };

  if (isLoading) return <LoadingSkeleton />;
  if (error) {
    return <ErrorBox message={error} onRetry={refetch} />;
  }

  if (!user) {
    return (
      <div className={styles.page}>
        <div className={styles.errorBox}>
          <span className={styles.errorText}> USER NOT FOUND</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        {/* Profile Section */}
        <section className={styles.section}>
          <div className={styles.sectionLabel}>
            <span className={styles.labelIcon}>►</span>
            PROFILE
          </div>
          
          <div className={styles.sectionContent}>
            <div className={styles.field}>
              <label className={styles.label}>NAME</label>
              <input
                type="text"
                className={styles.input}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            
            <div className={styles.field}>
              <label className={styles.label}>EMAIL</label>
              <input
                type="email"
                className={styles.input}
                value={user.email}
                disabled
              />
              <span className={styles.hint}>Email cannot be changed</span>
            </div>
            
            <div className={styles.field}>
              <label className={styles.label}>SKILL LEVEL</label>
              <div className={styles.options}>
                {skillLevels.map((level) => (
                  <button
                    key={level}
                    className={`${styles.optionBtn} ${skillLevel === level ? styles.selected : ''}`}
                    onClick={() => setSkillLevel(level)}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>
            
            <motion.button
              className={styles.saveBtn}
              onClick={handleSaveProfile}
              disabled={isSaving}
              whileHover={{ x: -2, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              {isSaving ? 'SAVING...' : 'SAVE →'}
            </motion.button>
          </div>
        </section>

        {/* Preferences Section */}
        <section className={styles.section}>
          <div className={styles.sectionLabel}>
            <span className={styles.labelIcon}>►</span>
            PREFERENCES
          </div>
          
          <div className={styles.sectionContent}>
            <div className={styles.toggleRow}>
              <div className={styles.toggleInfo}>
                <span className={styles.toggleLabel}>Email notifications</span>
                <span className={styles.toggleDesc}>Receive updates about your courses</span>
              </div>
              <button
                className={`${styles.toggle} ${emailNotifications ? styles.on : ''}`}
                onClick={() => setEmailNotifications(!emailNotifications)}
              >
                <span className={styles.toggleSlider} />
              </button>
            </div>
            
            <div className={styles.toggleRow}>
              <div className={styles.toggleInfo}>
                <span className={styles.toggleLabel}>Streak reminders</span>
                <span className={styles.toggleDesc}>Daily reminders to maintain your streak</span>
              </div>
              <button
                className={`${styles.toggle} ${streakReminders ? styles.on : ''}`}
                onClick={() => setStreakReminders(!streakReminders)}
              >
                <span className={styles.toggleSlider} />
              </button>
            </div>
            
            <div className={styles.toggleRow}>
              <div className={styles.toggleInfo}>
                <span className={styles.toggleLabel}>Weekly progress report</span>
                <span className={styles.toggleDesc}>Summary of your learning progress</span>
              </div>
              <button
                className={`${styles.toggle} ${weeklyReport ? styles.on : ''}`}
                onClick={() => setWeeklyReport(!weeklyReport)}
              >
                <span className={styles.toggleSlider} />
              </button>
            </div>
          </div>
        </section>

        {/* Account Section */}
        <section className={styles.section}>
          <div className={styles.sectionLabel}>
            <span className={styles.labelIcon}>►</span>
            ACCOUNT
          </div>
          
          <div className={styles.sectionContent}>
            <div className={styles.accountButtons}>
              <motion.button
                className={styles.accountBtn}
                whileHover={{ x: -2, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                CHANGE PASSWORD →
              </motion.button>
              
              <motion.button
                className={styles.accountBtn}
                whileHover={{ x: -2, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                MANAGE SUBSCRIPTION →
              </motion.button>
              
              <motion.button
                className={styles.accountBtn}
                onClick={handleExportData}
                whileHover={{ x: -2, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                EXPORT MY DATA →
              </motion.button>
            </div>
          </div>
        </section>

        {/* Danger Zone */}
        <section className={`${styles.section} ${styles.dangerSection}`}>
          <div className={styles.sectionLabel}>
            <span className={styles.labelIcon}>►</span>
            DANGER ZONE
          </div>
          
          <div className={styles.dangerContent}>
            <h4 className={styles.dangerTitle}>DELETE ACCOUNT</h4>
            <p className={styles.dangerText}>
              This will permanently delete all your courses, progress, and certificates.
              This action cannot be undone.
            </p>
            
            {!showDeleteConfirm ? (
              <motion.button
                className={styles.deleteBtn}
                onClick={() => setShowDeleteConfirm(true)}
                whileHover={{ x: -2, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                DELETE MY ACCOUNT
              </motion.button>
            ) : (
              <div className={styles.deleteConfirm}>
                <p className={styles.confirmText}>
                  Type "DELETE" to confirm account deletion:
                </p>
                <input
                  type="text"
                  className={styles.confirmInput}
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  placeholder="DELETE"
                />
                <div className={styles.confirmButtons}>
                  <button
                    className={styles.cancelBtn}
                    onClick={() => {
                      setShowDeleteConfirm(false);
                      setDeleteConfirmText('');
                    }}
                  >
                    CANCEL
                  </button>
                  <button
                    className={`${styles.confirmDeleteBtn} ${deleteConfirmText === 'DELETE' ? '' : styles.disabled}`}
                    onClick={handleDeleteAccount}
                    disabled={deleteConfirmText !== 'DELETE'}
                  >
                    CONFIRM DELETE
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
