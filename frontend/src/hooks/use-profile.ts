import { useState, useEffect } from 'react';
import { PROFILE_TABS, ProfileTabId } from '@/constants/profile-tabs';
import { DashboardService } from '@/services/dashboard-service';
import type { UserProfile } from '@/types';

type ProfileService = {
  getUserProfile: () => Promise<UserProfile>;
  updateUserProfile: (data: Partial<UserProfile>) => Promise<void>;
};

export const useProfile = (service: ProfileService = DashboardService) => {
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
        const data = await service.getUserProfile();
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
  }, [service]);

  const updateProfile = async (data: Partial<UserProfile>) => {
    setIsLoading(true);
    try {
      await service.updateUserProfile(data);
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
