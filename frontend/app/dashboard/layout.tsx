'use client';

import { useState } from 'react';
import { useUser } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import Sidebar from '../components/dashboard/Sidebar/Sidebar';
import BottomBar from '../components/dashboard/BottomBar/BottomBar';
import { ToastProvider } from '../components/Toast';
import { SidebarSkeleton } from '../components/Skeleton';
import styles from './layout.module.css';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { isLoaded, isSignedIn } = useUser();
  const router = useRouter();

  // Redirect to login if not authenticated
  if (isLoaded && !isSignedIn) {
    router.push('/login');
    return null;
  }

  // Show loading while checking auth
  if (!isLoaded) {
    return (
      <div className={styles.layout}>
        <aside className={styles.sidebar}>
          <SidebarSkeleton />
        </aside>
        <main className={styles.main}>
          <div className={styles.loading}>Loading...</div>
        </main>
      </div>
    );
  }

  return (
    <ToastProvider>
      <div className={styles.layout}>
        {/* Left Sidebar */}
        <motion.aside
          className={styles.sidebar}
          initial={{ x: -240 }}
          animate={{ x: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        >
          <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
        </motion.aside>

        {/* Main Content Area */}
        <main className={styles.main}>
          <motion.div
            className={styles.content}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            {children}
          </motion.div>
        </main>

        {/* Bottom Bar - Fixed at bottom */}
        <div className={styles.bottomBar}>
          <BottomBar />
        </div>
      </div>
    </ToastProvider>
  );
}
