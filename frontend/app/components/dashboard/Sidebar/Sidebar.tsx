'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useUser, useClerk } from '@clerk/nextjs';
import { motion } from 'framer-motion';
import { useApiClient } from '@/app/hooks/useApiClient';
import { useState, useEffect } from 'react';
import { SidebarSkeleton } from '@/app/components/Skeleton';
import styles from './Sidebar.module.css';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

interface UserData {
  skill_level: string;
  streak: number;
}

const navItems = [
  { href: '/dashboard', label: 'DASHBOARD', icon: '■' },
  { href: '/dashboard/courses', label: 'MY COURSES', icon: '■' },
  { href: '/dashboard/progress', label: 'PROGRESS', icon: '■' },
  { href: '/dashboard/chat', label: 'CHAT', icon: '■' },
  { href: '/dashboard/certificates', label: 'CERTIFICATES', icon: '■' },
  { href: '/dashboard/settings', label: 'SETTINGS', icon: '■' },
];

export default function Sidebar({ isOpen, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();
  const api = useApiClient();
  
  const [userData, setUserData] = useState<UserData | null>(null);
  const [modelOnline, setModelOnline] = useState(false);

  // Fetch user data from backend
  useEffect(() => {
    if (!isLoaded || !user) return;
    
    api.get<UserData>('/api/users/me/')
      .then(data => setUserData(data))
      .catch(() => setUserData(null));
  }, [isLoaded, user, api]);

  // Check model health
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/health/`);
        setModelOnline(res.ok);
      } catch {
        setModelOnline(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleSignOut = async () => {
    await signOut(() => router.push('/'));
  };

  if (!isLoaded) {
    return <SidebarSkeleton />;
  }

  const firstName = user?.firstName || user?.username || 'User';
  const skillLevel = userData?.skill_level?.toUpperCase() || 'BEGINNER';
  const streak = userData?.streak || 0;

  return (
    <div className={styles.sidebar}>
      {/* Logo */}
      <div className={styles.logo}>
        <Link href="/dashboard">CourseForge</Link>
      </div>

      {/* User Info */}
      <div className={styles.userInfo}>
        <span className={styles.userName}>{firstName}</span>
        <span className={styles.userEmail}>{user?.primaryEmailAddress?.emailAddress}</span>
        <span className={styles.skillBadge}>{skillLevel}</span>
      </div>

      {/* Streak Badge */}
      <div className={styles.streakBadge}>
        🔥 {streak} DAYS
      </div>

      {/* Navigation */}
      <nav className={styles.nav}>
        {navItems.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== '/dashboard' && pathname.startsWith(item.href));
          
          return (
            <Link
              key={item.href}
              href={item.href}
              className={styles.navLink}
            >
              <motion.div
                className={`${styles.navItem} ${isActive ? styles.active : ''}`}
                whileHover={{ x: 4 }}
                transition={{ type: 'spring', stiffness: 400, damping: 20 }}
              >
                <span className={styles.navIcon}>{item.icon}</span>
                <span className={styles.navLabel}>{item.label}</span>
                {isActive && (
                  <motion.div
                    className={styles.activeIndicator}
                    layoutId="activeNav"
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
              </motion.div>
            </Link>
          );
        })}
      </nav>

      {/* Model Status */}
      <div className={styles.statusBox}>
        <div className={styles.statusHeader}>
          <span className={`${styles.statusDot} ${modelOnline ? styles.online : styles.offline}`}>
            {modelOnline ? '●' : '○'}
          </span>
          <span className={styles.statusText}>
            {modelOnline ? 'MODEL ONLINE' : 'MODEL OFFLINE'}
          </span>
        </div>
        {modelOnline && (
          <div className={styles.statusInfo}>
            QWEN 7B · &lt;200MS
          </div>
        )}
      </div>

      {/* Sign Out */}
      <button className={styles.signOutBtn} onClick={handleSignOut}>
        SIGN OUT →
      </button>
    </div>
  );
}
