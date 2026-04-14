/**
 * Standalone API client — does NOT depend on React hooks.
 * Used by hooks and components that need direct API access.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE = (BASE_URL || '').replace('http', 'ws').replace('https', 'wss');

export const WS_URL = WS_BASE;

// Token getter — set by AuthTokenBridge / Clerk provider
let _tokenGetter: (() => Promise<string | null>) | null = null;

export function setAuthTokenGetter(getter: () => Promise<string | null>) {
  _tokenGetter = getter;
}

async function getToken(): Promise<string | null> {
  if (_tokenGetter) return _tokenGetter();
  return null;
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

async function request<T>(
  method: string,
  url: string,
  body?: unknown
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${url}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(data.error || data.message || `Request failed: ${res.status}`);
  }

  // Unwrap {success, data, error} structure from backend
  if (data && typeof data === 'object' && 'success' in data && 'data' in data) {
    if (data.success) {
      return data.data as T;
    } else {
      throw new Error(data.error || 'Request failed');
    }
  }

  return data as T;
}

export const api = {
  get: <T>(url: string) => request<T>('GET', url),
  post: <T>(url: string, body?: unknown) => request<T>('POST', url, body),
  put: <T>(url: string, body?: unknown) => request<T>('PUT', url, body),
  patch: <T>(url: string, body?: unknown) => request<T>('PATCH', url, body),
  delete: <T>(url: string) => request<T>('DELETE', url),
};
