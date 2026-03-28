'use client';

import { useAuth } from '@clerk/nextjs';
import { useEffect } from 'react';
import { setAuthTokenGetter } from '@/app/lib/api';

/**
 * Bridge component that connects Clerk authentication to our global API client.
 * This ensures that any call made via the 'api' object in lib/api.ts 
 * automatically includes the latest Clerk JWT token.
 */
export function AuthTokenBridge() {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      // Register the token getter with the API client
      setAuthTokenGetter(async () => {
        try {
          return await getToken();
        } catch (error) {
          console.error('Failed to get Clerk token for API request:', error);
          return null;
        }
      });
    } else if (isLoaded && !isSignedIn) {
      // Clear the token getter if user signs out
      setAuthTokenGetter(null);
    }
  }, [isLoaded, isSignedIn, getToken]);

  // This component doesn't render anything
  return null;
}
