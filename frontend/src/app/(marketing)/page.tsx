'use client';

import { LandingHeader } from '@/components/landing/header';
import { 
    HeroSection, 
    FeaturesSection, 
    HowItWorksSection, 
    TestimonialSection, 
    FAQSection, 
    FinalCTASection 
} from '@/components/landing/sections';
import { MOCK_PLACEHOLDER_IMAGES } from '@/constants/mock';
import { LandingFooter } from '@/components/landing/footer';

export default function LandingPage() {
    const heroImage = {
        imageUrl: '/landing.png',
        description: 'AI-Amooz Dashboard Preview'
    };
    const testimonialImage = MOCK_PLACEHOLDER_IMAGES.find(img => img.id === 'testimonial-avatar');

  return (
    <div className="flex flex-col min-h-screen bg-background text-text-light">
      <LandingHeader />
      
      <main className="flex-grow">
        <HeroSection heroImage={heroImage} />
        <FeaturesSection />
        <HowItWorksSection />
        <TestimonialSection testimonialImage={testimonialImage} />
        <FAQSection />
        <FinalCTASection />
      </main>

      <LandingFooter />
    </div>
  );
}
