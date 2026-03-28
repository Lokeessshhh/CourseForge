'use client';

import { useAuth } from '@clerk/nextjs';
import { useMemo, useRef } from 'react';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ApiError extends Error {
  status: number;
  data: unknown;
}

export function useApiClient() {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const inFlightRef = useRef<Map<string, Promise<unknown>>>(new Map());

  const request = async <T>(
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    url: string,
    body?: unknown
  ): Promise<T> => {
    // Wait for auth to be loaded
    if (!isLoaded) {
      // Return a promise that waits for isLoaded
      return new Promise((resolve, reject) => {
        const check = setInterval(() => {
          if (isLoaded) {
            clearInterval(check);
            if (!isSignedIn) {
              reject(new Error('Not authenticated'));
            } else {
              request<T>(method, url, body).then(resolve).catch(reject);
            }
          }
        }, 100);
      });
    }

    if (!isSignedIn) {
      throw new Error('Not authenticated');
    }

    const key = `${method}:${url}:${body ? JSON.stringify(body) : ''}`;
    const inFlight = inFlightRef.current;
    const existing = inFlight.get(key);
    if (existing) return existing as Promise<T>;

    const run = (async () => {
      const token = await getToken();
      if (!token) {
        throw new Error('Authentication token unavailable');
      }

      const res = await fetch(`${BASE_URL}${url}`, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const error = new Error(data.error || data.message || `Request failed: ${res.status}`) as ApiError;
        error.status = res.status;
        error.data = data;
        throw error;
      }

      // Unwrap {success, data, error} structure from backend
      if (data && typeof data === 'object' && 'success' in data && 'data' in data) {
        if ((data as any).success) {
          return (data as any).data as T;
        } else {
          throw new Error((data as any).error || 'Request failed');
        }
      }

      return data as T;
    })();

    inFlight.set(key, run as Promise<unknown>);
    try {
      return await run;
    } finally {
      inFlight.delete(key);
    }
  };

  return useMemo(
    () => ({
      get: <T>(url: string) => request<T>('GET', url),
      post: <T>(url: string, body?: unknown) => request<T>('POST', url, body),
      put: <T>(url: string, body?: unknown) => request<T>('PUT', url, body),
      patch: <T>(url: string, body?: unknown) => request<T>('PATCH', url, body),
      delete: <T>(url: string) => request<T>('DELETE', url),
    }),
    [isLoaded, isSignedIn, getToken]
  );
}
