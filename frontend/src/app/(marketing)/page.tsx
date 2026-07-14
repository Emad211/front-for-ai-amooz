'use client';

import { LandingFooter } from '@/components/landing/footer';
import { LandingHeader } from '@/components/landing/header';
import {
  FAQSection,
  FeaturesSection,
  FinalCTASection,
  HeroSection,
  TeacherCtaSection,
  TestimonialSection,
  WhyUsSection,
} from '@/components/landing/sections';
import { MOCK_PLACEHOLDER_IMAGES } from '@/constants/mock';

export default function LandingPage() {
  const testimonialImage = MOCK_PLACEHOLDER_IMAGES.find((image) => image.id === 'testimonial-avatar');

  return (
    <div className="min-h-screen bg-[hsl(var(--landing-page))] text-foreground">
      <LandingHeader />
      <main>
        <HeroSection
          heroImage={{
            imageUrl: '/landing/mac-studio-dark.png',
            description: 'نمای داشبورد هوشمند AI-Amooz',
          }}
        />
        <WhyUsSection />
        <FeaturesSection />
        <TestimonialSection testimonialImage={testimonialImage} />
        <TeacherCtaSection />
        <FAQSection />
        <FinalCTASection />
      </main>
      <LandingFooter />
    </div>
  );
}
