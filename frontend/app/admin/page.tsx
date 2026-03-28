'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import styles from './page.module.css';

interface AdminStats {
  total_users: number;
  total_courses: number;
  avg_completion_rate: number;
  most_popular_topics: string[];
  total_certificates: number;
  active_users_7d: number;
  courses_by_status: Record<string, number>;
}

interface User {
  id: string;
  email: string;
  name: string;
  courses_count: number;
  avg_completion: number;
  created_at: string;
}

function LoadingSkeleton() {
  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.skeletonBox} style={{ width: '300px', height: '40px', marginBottom: '32px' }} />
        <div className={styles.statsGrid}>
          {[1, 2, 3, 4].map(i => (
            <div key={i} className={styles.skeletonBox} style={{ width: '100%', height: '120px' }} />
          ))}
        </div>
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

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'stats' | 'users'>('stats');

  const fetchData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = localStorage.getItem('admin_token');
      if (!token) {
        throw new Error('Admin authentication required');
      }

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };

      const [statsRes, usersRes] = await Promise.all([
        fetch('http://localhost:8000/api/admin/stats/', { headers }),
        fetch('http://localhost:8000/api/admin/users/', { headers }),
      ]);

      if (!statsRes.ok || !usersRes.ok) {
        throw new Error('Failed to fetch admin data');
      }

      const statsData = await statsRes.json();
      const usersData = await usersRes.json();

      setStats(statsData.data);
      setUsers(usersData.data.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorBox message={error} onRetry={fetchData} />;

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.header}>
          <h1 className={styles.title}>ADMIN PANEL</h1>
          <div className={styles.tabs}>
            <button
              className={`${styles.tab} ${activeTab === 'stats' ? styles.active : ''}`}
              onClick={() => setActiveTab('stats')}
            >
              STATS
            </button>
            <button
              className={`${styles.tab} ${activeTab === 'users' ? styles.active : ''}`}
              onClick={() => setActiveTab('users')}
            >
              USERS
            </button>
          </div>
        </div>

        {activeTab === 'stats' && stats && (
          <motion.div
            className={styles.content}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <div className={styles.statsGrid}>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>TOTAL USERS</span>
                <span className={styles.statValue}>{stats.total_users}</span>
              </div>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>TOTAL COURSES</span>
                <span className={styles.statValue}>{stats.total_courses}</span>
              </div>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>AVG COMPLETION</span>
                <span className={styles.statValue}>{stats.avg_completion_rate}%</span>
              </div>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>CERTIFICATES</span>
                <span className={styles.statValue}>{stats.total_certificates}</span>
              </div>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>ACTIVE USERS (7D)</span>
                <span className={styles.statValue}>{stats.active_users_7d}</span>
              </div>
            </div>

            <div className={styles.section}>
              <div className={styles.sectionHeader}>
                <span className={styles.sectionTitle}>POPULAR TOPICS</span>
              </div>
              <div className={styles.topicsList}>
                {stats.most_popular_topics.map((topic, index) => (
                  <div key={index} className={styles.topicItem}>
                    <span className={styles.topicIndex}>{index + 1}.</span>
                    <span className={styles.topicName}>{topic}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className={styles.section}>
              <div className={styles.sectionHeader}>
                <span className={styles.sectionTitle}>COURSES BY STATUS</span>
              </div>
              <div className={styles.statusList}>
                {Object.entries(stats.courses_by_status).map(([status, count]) => (
                  <div key={status} className={styles.statusItem}>
                    <span className={styles.statusName}>{status.toUpperCase()}</span>
                    <span className={styles.statusCount}>{count}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'users' && (
          <motion.div
            className={styles.content}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <div className={styles.section}>
              <div className={styles.sectionHeader}>
                <span className={styles.sectionTitle}>USERS ({users.length})</span>
              </div>
              <div className={styles.usersList}>
                {users.map((user, index) => (
                  <div key={user.id} className={styles.userCard}>
                    <div className={styles.userIndex}>{index + 1}</div>
                    <div className={styles.userInfo}>
                      <span className={styles.userName}>{user.name}</span>
                      <span className={styles.userEmail}>{user.email}</span>
                    </div>
                    <div className={styles.userStats}>
                      <div className={styles.userStat}>
                        <span className={styles.userStatLabel}>COURSES</span>
                        <span className={styles.userStatValue}>{user.courses_count}</span>
                      </div>
                      <div className={styles.userStat}>
                        <span className={styles.userStatLabel}>COMPLETION</span>
                        <span className={styles.userStatValue}>{user.avg_completion}%</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
