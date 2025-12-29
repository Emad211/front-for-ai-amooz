import { 
  SITE_CONFIG,
  MOCK_FEATURES, 
  MOCK_TESTIMONIALS, 
  MOCK_FAQS, 
  MOCK_STEPS 
} from '@/constants/mock';

/**
 * Landing Service
 * Handles data for the marketing/landing pages.
 */
export const LandingService = {
  getConfig: async () => {
    return SITE_CONFIG;
  },

  getFeatures: async () => {
    return MOCK_FEATURES;
  },

  getTestimonials: async () => {
    return MOCK_TESTIMONIALS;
  },

  getFaqs: async () => {
    return MOCK_FAQS;
  },

  getSteps: async () => {
    return MOCK_STEPS;
  }
};
