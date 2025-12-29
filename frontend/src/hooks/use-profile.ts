import { useState, useEffect } from 'react';
import { PROFILE_TABS, ProfileTabId } from '@/constants/mock/profile-data';
import { DashboardService } from '@/services/dashboard-service';

export const useProfile = () => {
  const [activeTab, setActiveTab] = useState<ProfileTabId>('personal');
  const [user, setUser] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setIsLoading(true);
        const data = await DashboardService.getUserProfile();
        setUser(data);
      } catch (error) {
        console.error('Error fetching profile:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const updateProfile = async (data: any) => {
    setIsLoading(true);
    try {
      await DashboardService.updateUserProfile(data);
      setUser((prev: any) => ({ ...prev, ...data }));
    } catch (error) {
      console.error('Error updating profile:', error);
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
  };
};
