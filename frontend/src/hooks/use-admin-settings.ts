import { useEffect, useState } from 'react';
import { AdminService } from '@/services/admin-service';
import type { AdminNotificationSettings, AdminProfileSettings, AdminSecuritySettings } from '@/types';

const DEFAULT_PROFILE: AdminProfileSettings = {
  name: '',
  email: '',
  phone: '',
  bio: '',
  location: '',
  avatar: '',
};

const DEFAULT_SECURITY: AdminSecuritySettings = {
  twoFactorEnabled: false,
  lastPasswordChange: '',
};

const DEFAULT_NOTIFICATIONS: AdminNotificationSettings = {
  emailNotifications: false,
  browserNotifications: false,
  smsNotifications: false,
  marketingEmails: false,
};

/**
 * Hook to manage admin settings state and simulated updates.
 * Handles profile, security, and notification preferences.
 * 
 * @returns {Object} Settings state and update functions.
 */
export const useAdminSettings = () => {
  const [profile, setProfile] = useState<AdminProfileSettings>(DEFAULT_PROFILE);
  const [security, setSecurity] = useState<AdminSecuritySettings>(DEFAULT_SECURITY);
  const [notifications, setNotifications] = useState<AdminNotificationSettings>(DEFAULT_NOTIFICATIONS);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchSettings = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const [profileSettings, securitySettings, notificationSettings] = await Promise.all([
          AdminService.getProfileSettings(),
          AdminService.getSecuritySettings(),
          AdminService.getNotificationSettings(),
        ]);

        if (cancelled) return;
        setProfile(profileSettings);
        setSecurity(securitySettings);
        setNotifications(notificationSettings);
      } catch (e) {
        console.error('Error fetching admin settings:', e);
        if (!cancelled) setError('خطا در دریافت تنظیمات');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    fetchSettings();
    return () => {
      cancelled = true;
    };
  }, []);

  /**
   * Simulates updating the admin profile.
   * @param {Partial<typeof MOCK_ADMIN_PROFILE>} data - The new profile data.
   */
  const updateProfile = async (data: Partial<AdminProfileSettings>) => {
    setIsLoading(true);
    try {
      setError(null);
      await AdminService.updateProfileSettings(data);
      setProfile((prev) => ({ ...prev, ...data }));
    } catch (e) {
      console.error('Error updating admin profile settings:', e);
      setError('خطا در بروزرسانی پروفایل');
    } finally {
      setIsLoading(false);
    }
  };

  const updateSecurity = async (data: Partial<AdminSecuritySettings>) => {
    setIsLoading(true);
    try {
      setError(null);
      await AdminService.updateSecuritySettings(data);
      setSecurity((prev) => ({ ...prev, ...data }));
    } catch (e) {
      console.error('Error updating admin security settings:', e);
      setError('خطا در بروزرسانی امنیت');
    } finally {
      setIsLoading(false);
    }
  };

  const updateNotifications = async (data: Partial<AdminNotificationSettings>) => {
    setIsLoading(true);
    try {
      setError(null);
      await AdminService.updateNotificationSettings(data);
      setNotifications((prev) => ({ ...prev, ...data }));
    } catch (e) {
      console.error('Error updating admin notification settings:', e);
      setError('خطا در بروزرسانی اعلان‌ها');
    } finally {
      setIsLoading(false);
    }
  };

  return {
    profile,
    security,
    notifications,
    isLoading,
    error,
    updateProfile,
    updateSecurity,
    updateNotifications,
  };
};
