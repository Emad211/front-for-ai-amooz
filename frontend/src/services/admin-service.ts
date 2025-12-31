import { 
  MOCK_ANALYTICS_STATS, 
  MOCK_CHART_DATA, 
  MOCK_DISTRIBUTION_DATA, 
  MOCK_RECENT_ACTIVITIES,
  MOCK_TICKETS,
  MOCK_MESSAGE_RECIPIENTS,
  MOCK_ADMIN_PROFILE,
  MOCK_ADMIN_SECURITY,
  MOCK_ADMIN_NOTIFICATIONS,
} from '@/constants/mock';
import { 
  MOCK_SERVER_HEALTH,
  MOCK_BACKUPS,
  MOCK_MAINTENANCE_TASKS,
  MOCK_SERVER_SETTINGS,
} from '@/constants/mock';
import type { AdminNotificationSettings, AdminProfileSettings, AdminSecuritySettings } from '@/types';

/**
 * Admin Service
 * Handles all data fetching for the admin dashboard and management.
 */
export const AdminService = {
  getAnalyticsStats: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_ANALYTICS_STATS;
  },

  getChartData: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_CHART_DATA;
  },

  getDistributionData: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_DISTRIBUTION_DATA;
  },

  getRecentActivities: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_RECENT_ACTIVITIES;
  },

  getTickets: async () => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return MOCK_TICKETS;
  },

  getMessageRecipients: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_MESSAGE_RECIPIENTS;
  },

  getProfileSettings: async (): Promise<AdminProfileSettings> => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_ADMIN_PROFILE;
  },

  getSecuritySettings: async (): Promise<AdminSecuritySettings> => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_ADMIN_SECURITY;
  },

  getNotificationSettings: async (): Promise<AdminNotificationSettings> => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_ADMIN_NOTIFICATIONS;
  },

  updateProfileSettings: async (data: Partial<AdminProfileSettings>) => {
    await new Promise(resolve => setTimeout(resolve, 800));
    return { success: true, data };
  },

  updateSecuritySettings: async (data: Partial<AdminSecuritySettings>) => {
    await new Promise(resolve => setTimeout(resolve, 800));
    return { success: true, data };
  },

  updateNotificationSettings: async (data: Partial<AdminNotificationSettings>) => {
    await new Promise(resolve => setTimeout(resolve, 800));
    return { success: true, data };
  },

  // ============================================================================
  // Ops & Maintenance
  // ============================================================================

  getServerHealth: async () => {
    await new Promise(resolve => setTimeout(resolve, 300));
    return MOCK_SERVER_HEALTH;
  },

  getMaintenanceTasks: async () => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_MAINTENANCE_TASKS;
  },

  getBackups: async () => {
    await new Promise(resolve => setTimeout(resolve, 350));
    return MOCK_BACKUPS;
  },

  triggerBackup: async (type: 'full' | 'incremental') => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return { success: true, type, id: `new-${Date.now()}` };
  },

  getServerSettings: async () => {
    await new Promise(resolve => setTimeout(resolve, 300));
    return MOCK_SERVER_SETTINGS;
  },

  updateServerSettings: async (data: Partial<typeof MOCK_SERVER_SETTINGS>) => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return { success: true, data: { ...MOCK_SERVER_SETTINGS, ...data } };
  },
};
