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

export default function LandingPage() {
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
        <TestimonialSection />
        <TeacherCtaSection />
        <FAQSection />
        <FinalCTASection />
      </main>
      <LandingFooter />
    </div>
  );
}
