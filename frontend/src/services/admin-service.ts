import { 
  MOCK_ANALYTICS_STATS, 
  MOCK_CHART_DATA, 
  MOCK_DISTRIBUTION_DATA, 
  MOCK_RECENT_ACTIVITIES,
  MOCK_STUDENTS,
  MOCK_COURSES,
  MOCK_TICKETS,
  MOCK_MESSAGE_RECIPIENTS,
  MOCK_ADMIN_PROFILE,
  MOCK_ADMIN_SECURITY,
  MOCK_ADMIN_NOTIFICATIONS,
  MOCK_CLASS_DETAILS
} from '@/constants/mock';
import { 
  MOCK_SERVER_HEALTH,
  MOCK_BACKUPS,
  MOCK_MAINTENANCE_TASKS,
  MOCK_SERVER_SETTINGS,
} from '@/constants/mock';
import type { AdminNotificationSettings, AdminProfileSettings, AdminSecuritySettings, ClassDetail, Course } from '@/types';

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

  getStudents: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_STUDENTS;
  },

  getCourses: async () => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return MOCK_COURSES;
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
  // Class Detail Methods - متدهای جزئیات کلاس
  // ============================================================================

  getClassDetail: async (classId: string): Promise<ClassDetail | null> => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_CLASS_DETAILS[classId] || null;
  },

  getClassStudents: async (classId: string) => {
    await new Promise(resolve => setTimeout(resolve, 400));
    const classDetail = MOCK_CLASS_DETAILS[classId];
    return classDetail?.enrolledStudents || [];
  },

  updateClass: async (classId: string, data: Partial<Course>) => {
    await new Promise(resolve => setTimeout(resolve, 800));
    // In real implementation, this would update the class in the database
    return { success: true, data: { id: classId, ...data } };
  },

  deleteClass: async (classId: string) => {
    await new Promise(resolve => setTimeout(resolve, 600));
    // In real implementation, this would delete the class from the database
    return { success: true, classId };
  },

  removeStudentFromClass: async (classId: string, studentId: string) => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return { success: true, classId, studentId };
  },

  addStudentToClass: async (classId: string, studentEmail: string) => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return { success: true, classId, studentEmail };
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
