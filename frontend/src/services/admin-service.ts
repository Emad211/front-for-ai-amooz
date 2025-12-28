import { 
  MOCK_ANALYTICS_STATS, 
  MOCK_CHART_DATA, 
  MOCK_DISTRIBUTION_DATA, 
  MOCK_RECENT_ACTIVITIES,
  MOCK_STUDENTS,
  MOCK_COURSES,
  MOCK_TICKETS,
  MOCK_MESSAGE_RECIPIENTS
} from '@/constants/mock';

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
    return MOCK_STUDENTS;  },

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
    return MOCK_MESSAGE_RECIPIENTS;  }
};
