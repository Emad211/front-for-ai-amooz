import {
  TEACHER_ANALYTICS_STATS,
  TEACHER_CHART_DATA,
  TEACHER_DISTRIBUTION_DATA,
  TEACHER_RECENT_ACTIVITIES,
  TEACHER_STUDENTS,
  TEACHER_COURSES,
  TEACHER_MESSAGE_RECIPIENTS,
  TEACHER_PROFILE_SETTINGS,
  TEACHER_SECURITY_SETTINGS,
  TEACHER_NOTIFICATION_SETTINGS,
  TEACHER_CLASS_DETAILS,
} from '@/mock-data/teacher-data';
import type {
  AdminAnalyticsStat,
  AdminChartData,
  AdminDistributionData,
  AdminRecentActivity,
  AdminProfileSettings,
  AdminSecuritySettings,
  AdminNotificationSettings,
  ClassDetail,
  Course,
} from '@/types';

export const TeacherService = {
  getAnalyticsStats: async (): Promise<AdminAnalyticsStat[]> => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return TEACHER_ANALYTICS_STATS;
  },

  getChartData: async (): Promise<AdminChartData[]> => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return TEACHER_CHART_DATA;
  },

  getDistributionData: async (): Promise<AdminDistributionData[]> => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return TEACHER_DISTRIBUTION_DATA;
  },

  getRecentActivities: async (): Promise<AdminRecentActivity[]> => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return TEACHER_RECENT_ACTIVITIES;
  },

  getStudents: async () => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return TEACHER_STUDENTS;
  },

  getCourses: async () => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return TEACHER_COURSES;
  },

  getMessageRecipients: async () => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    return TEACHER_MESSAGE_RECIPIENTS;
  },

  getProfileSettings: async (): Promise<AdminProfileSettings> => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    return TEACHER_PROFILE_SETTINGS;
  },

  getSecuritySettings: async (): Promise<AdminSecuritySettings> => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    return TEACHER_SECURITY_SETTINGS;
  },

  getNotificationSettings: async (): Promise<AdminNotificationSettings> => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    return TEACHER_NOTIFICATION_SETTINGS;
  },

  updateProfileSettings: async (data: Partial<AdminProfileSettings>) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return { success: true, data };
  },

  updateSecuritySettings: async (data: Partial<AdminSecuritySettings>) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return { success: true, data };
  },

  updateNotificationSettings: async (data: Partial<AdminNotificationSettings>) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return { success: true, data };
  },

  getClassDetail: async (classId: string): Promise<ClassDetail | null> => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return (TEACHER_CLASS_DETAILS as Record<string, ClassDetail | undefined>)[classId] || null;
  },

  getClassStudents: async (classId: string) => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    const classDetail = (TEACHER_CLASS_DETAILS as Record<string, ClassDetail | undefined>)[classId];
    return classDetail?.enrolledStudents || [];
  },

  updateClass: async (classId: string, data: Partial<Course>) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return { success: true, data: { id: classId, ...data } };
  },

  deleteClass: async (classId: string) => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return { success: true, classId };
  },

  removeStudentFromClass: async (classId: string, studentId: string) => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    return { success: true, classId, studentId };
  },

  addStudentToClass: async (classId: string, studentEmail: string) => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    return { success: true, classId, studentEmail };
  },
};
