import { useState, useEffect } from 'react';
import { LandingService } from '@/services/landing-service';
import { SITE_CONFIG } from '@/constants/site';

type LandingConfig = Awaited<ReturnType<typeof LandingService.getConfig>>;
type LandingFeature = Awaited<ReturnType<typeof LandingService.getFeatures>>[number];
type LandingTestimonial = Awaited<ReturnType<typeof LandingService.getTestimonials>>[number];
type LandingFaq = Awaited<ReturnType<typeof LandingService.getFaqs>>[number];
type LandingStep = Awaited<ReturnType<typeof LandingService.getSteps>>[number];

/**
 * Hook to access landing page configuration and mock data.
 * Centralizes all content for the marketing pages.
 * 
 * @returns {Object} Landing page configuration including hero, features, stats, etc.
 */
export const useLanding = () => {
  const [config, setConfig] = useState<LandingConfig>(SITE_CONFIG as LandingConfig);
  const [features, setFeatures] = useState<LandingFeature[]>([]);
  const [testimonials, setTestimonials] = useState<LandingTestimonial[]>([]);
  const [faqs, setFaqs] = useState<LandingFaq[]>([]);
  const [steps, setSteps] = useState<LandingStep[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchLandingData = async () => {
      try {
        setError(null);
        setIsLoading(true);

        // Simulate network delay for consistency with other services
        await new Promise(resolve => setTimeout(resolve, 300));
        
        const [config, features, testimonials, faqs, steps] = await Promise.all([
          LandingService.getConfig(),
          LandingService.getFeatures(),
          LandingService.getTestimonials(),
          LandingService.getFaqs(),
          LandingService.getSteps()
        ]);

        if (cancelled) return;
        setConfig(config);
        setFeatures(features);
        setTestimonials(testimonials);
        setFaqs(faqs);
        setSteps(steps);
      } catch (error) {
        console.error('Error fetching landing data:', error);
        if (cancelled) return;
        setError('خطا در دریافت اطلاعات صفحه اصلی');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    fetchLandingData();

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    config,
    features,
    testimonials,
    faqs,
    steps,
    stats: config.stats,
    hero: config.hero,
    cta: config.cta,
    isLoading,
    error,
  };
};
