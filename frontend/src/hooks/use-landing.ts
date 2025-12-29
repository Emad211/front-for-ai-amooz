import { useState, useEffect } from 'react';
import { LandingService } from '@/services/landing-service';
import { SITE_CONFIG } from '@/constants/site';
import { 
  MOCK_FEATURES, 
  MOCK_TESTIMONIALS, 
  MOCK_FAQS, 
  MOCK_STEPS 
} from '@/constants/mock';

/**
 * Hook to access landing page configuration and mock data.
 * Centralizes all content for the marketing pages.
 * 
 * @returns {Object} Landing page configuration including hero, features, stats, etc.
 */
export const useLanding = () => {
  const [data, setData] = useState<any>({
    config: SITE_CONFIG,
    features: MOCK_FEATURES,
    testimonials: MOCK_TESTIMONIALS,
    faqs: MOCK_FAQS,
    steps: MOCK_STEPS,
    stats: SITE_CONFIG.stats,
    hero: SITE_CONFIG.hero,
    cta: SITE_CONFIG.cta,
    isLoading: true
  });

  useEffect(() => {
    const fetchLandingData = async () => {
      try {
        // Simulate network delay for consistency with other services
        await new Promise(resolve => setTimeout(resolve, 300));
        
        const [config, features, testimonials, faqs, steps] = await Promise.all([
          LandingService.getConfig(),
          LandingService.getFeatures(),
          LandingService.getTestimonials(),
          LandingService.getFaqs(),
          LandingService.getSteps()
        ]);

        setData({
          config,
          features,
          testimonials,
          faqs,
          steps,
          stats: config.stats,
          hero: config.hero,
          cta: config.cta,
          isLoading: false
        });
      } catch (error) {
        console.error('Error fetching landing data:', error);
        setData(prev => ({ ...prev, isLoading: false }));
      }
    };

    fetchLandingData();
  }, []);

  return data;
};
