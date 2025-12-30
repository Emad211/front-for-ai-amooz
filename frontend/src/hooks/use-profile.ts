import { useState, useEffect } from 'react';
import { PROFILE_TABS, ProfileTabId } from '@/constants/profile-tabs';
import { DashboardService } from '@/services/dashboard-service';
import type { UserProfile } from '@/types';

export const useProfile = () => {
  const [activeTab, setActiveTab] = useState<ProfileTabId>('personal');
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchProfile = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await DashboardService.getUserProfile();
        if (!cancelled) setUser(data);
      } catch (error) {
        console.error('Error fetching profile:', error);
        if (!cancelled) setError('خطا در دریافت اطلاعات پروفایل');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    fetchProfile();

    return () => {
      cancelled = true;
    };
  }, []);

  const updateProfile = async (data: Partial<UserProfile>) => {
    setIsLoading(true);
    try {
      await DashboardService.updateUserProfile(data);
      setUser((prev) => (prev ? { ...prev, ...data } : prev));
    } catch (error) {
      console.error('Error updating profile:', error);
      setError('خطا در بروزرسانی اطلاعات پروفایل');
    } finally {
      setIsLoading(false);
    }
  };

  return {
    activeTab,
    setActiveTab,
    tabs: PROFILE_TABS,
    user,
    updateProfile,
    isLoading,
    error,
  };
};
