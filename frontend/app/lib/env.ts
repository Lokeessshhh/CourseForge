/**
 * Environment variable validation for production builds.
 * Validates required environment variables at build/runtime.
 */

interface EnvConfig {
  NEXT_PUBLIC_API_URL: string;
  NEXT_PUBLIC_WS_URL: string;
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: string;
}

function validateEnv(): EnvConfig {
  const requiredEnvVars = {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
  };

  const missing: string[] = [];

  for (const [key, value] of Object.entries(requiredEnvVars)) {
    if (!value) {
      missing.push(key);
    }
  }

  if (missing.length > 0 && process.env.NODE_ENV === 'production') {
    throw new Error(
      `Missing required environment variables: ${missing.join(', ')}\n` +
      'Please check your .env.local file or deployment environment.'
    );
  }

  return {
    NEXT_PUBLIC_API_URL: requiredEnvVars.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: requiredEnvVars.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: requiredEnvVars.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || '',
  };
}

export const env = validateEnv();

// Typed environment access
export const API_URL = env.NEXT_PUBLIC_API_URL;
export const WS_URL = env.NEXT_PUBLIC_WS_URL;
export const CLERK_KEY = env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
