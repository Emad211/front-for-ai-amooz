import { 
  MOCK_DASHBOARD_STATS, 
  MOCK_ACTIVITIES, 
  MOCK_UPCOMING_EVENTS, 
  MOCK_STUDENT_PROFILE,
  MOCK_COURSES,
  MOCK_EXAMS,
  MOCK_TICKETS,
  MOCK_NOTIFICATIONS,
  MOCK_CALENDAR_EVENTS,
  MOCK_COURSE_CONTENT,
  MOCK_LESSON_DETAIL,
  MOCK_USER_PROFILE
} from '@/constants/mock';

/**
 * Dashboard Service
 * Handles all data fetching for the student dashboard.
 * Currently returns mock data, but ready to be replaced with API calls.
 */
export const DashboardService = {
  getStats: async () => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_DASHBOARD_STATS;
  },

  getActivities: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_ACTIVITIES;
  },

  getUpcomingEvents: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_UPCOMING_EVENTS;
  },

  getStudentProfile: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_STUDENT_PROFILE;
  },

  getCourses: async () => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return MOCK_COURSES;
  },

  getExams: async () => {
    await new Promise(resolve => setTimeout(resolve, 700));
    return MOCK_EXAMS;
  },

  getTickets: async () => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return MOCK_TICKETS;
  },

  getNotifications: async () => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_NOTIFICATIONS;
  },

  getCalendarEvents: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_CALENDAR_EVENTS;
  },

  getCourseContent: async (courseId?: string) => {
    await new Promise(resolve => setTimeout(resolve, 800));
    return MOCK_COURSE_CONTENT;
  },

  getLessonDetail: async (lessonId: string) => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_LESSON_DETAIL;
  },

  getUserProfile: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_USER_PROFILE;
  },

  updateUserProfile: async (data: any) => {
    await new Promise(resolve => setTimeout(resolve, 1000));
    return { success: true, data };
  }
};
