'use client';

import { useState } from 'react';
import { useUser } from '@clerk/nextjs';
import { useRouter, usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import Sidebar from '../components/dashboard/Sidebar/Sidebar';
import BottomBar from '../components/dashboard/BottomBar/BottomBar';
import { ToastProvider } from '../components/Toast';
import { GenerationProgressProvider } from '../context/GenerationProgressContext';
import GlobalGenerationToastWrapper from '../components/GenerationProgressToast/GlobalGenerationToastWrapper';
import GenerationProgressBridge from '../components/GenerationProgressProvider/GenerationProgressBridge';
import { SidebarSkeleton } from '../components/Skeleton';
import styles from './layout.module.css';

function DashboardContent({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { isLoaded, isSignedIn } = useUser();
  const router = useRouter();
  const pathname = usePathname();

  // Check if current page is chat (full-page layout)
  const isChatPage = pathname === '/dashboard/chat';

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

  // Full-page layout for chat - no sidebar or bottom bar
  if (isChatPage) {
    return (
      <ToastProvider>
        <GenerationProgressProvider>
          <GenerationProgressBridge />
          {children}
          <AnimatePresence>
            <GlobalGenerationToastWrapper />
          </AnimatePresence>
        </GenerationProgressProvider>
      </ToastProvider>
    );
  }

  // Standard dashboard layout with sidebar and bottom bar
  return (
    <ToastProvider>
      <GenerationProgressProvider>
        <GenerationProgressBridge />
        <div className={styles.layout}>
          {/* Mobile Menu Toggle Button */}
          <button
            className={styles.mobileMenuToggle}
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>

          {/* Mobile Overlay Backdrop */}
          <div
            className={`${styles.sidebarOverlay} ${sidebarOpen ? styles.open : ''}`}
            onClick={() => setSidebarOpen(false)}
          />

          {/* Left Sidebar */}
          <aside className={`${styles.sidebar} ${sidebarOpen ? styles.open : ''}`}>
            <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
          </aside>

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

          {/* Generation Progress Toast - Top Right (shows on all non-chat pages) */}
          <AnimatePresence>
            <GlobalGenerationToastWrapper />
          </AnimatePresence>
        </div>
      </GenerationProgressProvider>
    </ToastProvider>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardContent>{children}</DashboardContent>;
}
