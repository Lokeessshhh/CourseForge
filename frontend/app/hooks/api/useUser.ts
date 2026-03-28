import { api } from '@/app/lib/api';
import { useState, useEffect, useCallback } from 'react';

// Types
export interface User {
  id: string;
  name: string;
  email: string;
  skill_level: 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED';
  streak: number;
  avatar_url: string | null;
  created_at: string;
}

export interface UserSettings {
  email_notifications: boolean;
  streak_reminders: boolean;
  weekly_report: boolean;
}

export interface UpdateUserData {
  name?: string;
  skill_level?: 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED';
}

export interface UpdateSettingsData {
  email_notifications?: boolean;
  streak_reminders?: boolean;
  weekly_report?: boolean;
}

// API Functions
export const userApi = {
  getMe: () =>
    api.get<User>('/api/users/me/'),

  updateMe: (data: UpdateUserData) =>
    api.put<User>('/api/users/me/', data),

  getSettings: () =>
    api.get<UserSettings>('/api/users/me/settings/'),

  updateSettings: (data: UpdateSettingsData) =>
    api.put<UserSettings>('/api/users/me/settings/', data),

  exportData: () =>
    api.post<{ message: string; download_url?: string }>('/api/users/me/export/'),

  deleteAccount: () =>
    api.delete('/api/users/me/'),
};

// Hooks
export function useUser() {
  const [data, setData] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUser = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await userApi.getMe();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const update = useCallback(async (updateData: UpdateUserData) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await userApi.updateMe(updateData);
      setData(result);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { data, isLoading, error, refetch: fetchUser, update };
}

export function useUserSettings() {
  const [data, setData] = useState<UserSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await userApi.getSettings();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const update = useCallback(async (updateData: UpdateSettingsData) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await userApi.updateSettings(updateData);
      setData(result);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { data, isLoading, error, refetch: fetchSettings, update };
}

export function useUserActions() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exportData = useCallback(async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await userApi.exportData();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const deleteAccount = useCallback(async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      await userApi.deleteAccount();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  return { exportData, deleteAccount, isSubmitting, error };
}
