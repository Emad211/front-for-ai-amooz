import { useState } from 'react';
import { 
  MOCK_ADMIN_PROFILE, 
  MOCK_ADMIN_SECURITY, 
  MOCK_ADMIN_NOTIFICATIONS 
} from '@/constants/mock';

/**
 * Hook to manage admin settings state and simulated updates.
 * Handles profile, security, and notification preferences.
 * 
 * @returns {Object} Settings state and update functions.
 */
export const useAdminSettings = () => {
  const [profile, setProfile] = useState(MOCK_ADMIN_PROFILE);
  const [security, setSecurity] = useState(MOCK_ADMIN_SECURITY);
  const [notifications, setNotifications] = useState(MOCK_ADMIN_NOTIFICATIONS);
  const [isLoading, setIsLoading] = useState(false);

  /**
   * Simulates updating the admin profile.
   * @param {Partial<typeof MOCK_ADMIN_PROFILE>} data - The new profile data.
   */
  const updateProfile = async (data: Partial<typeof MOCK_ADMIN_PROFILE>) => {
    setIsLoading(true);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setProfile(prev => ({ ...prev, ...data }));
    setIsLoading(false);
  };

  const updateSecurity = async (data: Partial<typeof MOCK_ADMIN_SECURITY>) => {
    setIsLoading(true);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setSecurity(prev => ({ ...prev, ...data }));
    setIsLoading(false);
  };

  const updateNotifications = async (data: Partial<typeof MOCK_ADMIN_NOTIFICATIONS>) => {
    setIsLoading(true);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setNotifications(prev => ({ ...prev, ...data }));
    setIsLoading(false);
  };

  return {
    profile,
    security,
    notifications,
    isLoading,
    updateProfile,
    updateSecurity,
    updateNotifications,
  };
};
