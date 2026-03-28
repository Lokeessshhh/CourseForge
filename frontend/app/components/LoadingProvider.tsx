'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { WebcamASCII } from '@/app/components/WebcamASCII';
import { usePathname } from 'next/navigation';

interface LoadingContextType {
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

const LoadingContext = createContext<LoadingContextType | undefined>(undefined);

// Initial load time
const INITIAL_LOAD_TIME = 2000;
// Route change load time
const ROUTE_LOAD_TIME = 800;

export function LoadingProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [isClient, setIsClient] = useState(false);
  const pathname = usePathname();
  const [prevPathname, setPrevPathname] = useState<string | null>(null);

  // Mark client-side ready
  useEffect(() => {
    setIsClient(true);
    
    // Initial page load
    const timer = setTimeout(() => {
      setIsLoading(false);
    }, INITIAL_LOAD_TIME);
    
    return () => clearTimeout(timer);
  }, []);

  // Detect route changes and show loading
  useEffect(() => {
    if (!isClient || !pathname) return;
    
    // Check if pathname actually changed (not just query params)
    const currentPath = pathname.split('?')[0];
    const prevPath = prevPathname ? prevPathname.split('?')[0] : null;
    
    if (currentPath !== prevPath && prevPath !== null) {
      // Route changed - show loading
      setIsLoading(true);
      
      // Hide after route load time
      const timer = setTimeout(() => {
        setIsLoading(false);
      }, ROUTE_LOAD_TIME);
      
      return () => clearTimeout(timer);
    }
    
    setPrevPathname(pathname);
  }, [pathname, isClient, prevPathname]);

  return (
    <LoadingContext.Provider value={{ isLoading, setIsLoading }}>
      <WebcamASCII 
        isLoading={isLoading} 
        message={isLoading ? "INITIALIZING..." : "LOADING..."} 
      />
      {children}
    </LoadingContext.Provider>
  );
}

export function useLoading() {
  const context = useContext(LoadingContext);
  if (context === undefined) {
    throw new Error('useLoading must be used within a LoadingProvider');
  }
  return context;
}
