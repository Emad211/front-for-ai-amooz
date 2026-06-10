'use client';

import { LandingHeader } from '@/components/landing/header';
import {
    HeroSection,
    WhyUsSection,
    FeaturesSection,
    TestimonialSection,
    TeacherCtaSection,
    FAQSection,
    FinalCTASection,
} from '@/components/landing/sections';
import { MOCK_PLACEHOLDER_IMAGES } from '@/constants/mock';
import { LandingFooter } from '@/components/landing/footer';

export default function LandingPage() {
    const heroImage = {
        imageUrl: '/landing.png',
        description: 'AI-Amooz Dashboard Preview',
    };
    const testimonialImage = MOCK_PLACEHOLDER_IMAGES.find((img) => img.id === 'testimonial-avatar');

    return (
        <div className="flex min-h-screen flex-col bg-background text-foreground">
            <LandingHeader />

            <main className="flex-grow">
                <HeroSection heroImage={heroImage} />
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
