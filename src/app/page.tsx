'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GraduationCap, ArrowLeft, Bot, Target, BookCheck } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { PlaceHolderImages } from '@/lib/placeholder-images';

const LandingHeader = () => (
  <header className="absolute top-0 left-0 right-0 z-10 p-4 md:px-8 bg-transparent">
    <div className="container mx-auto flex justify-between items-center">
      <Link href="/" className="flex items-center gap-2">
        <GraduationCap className="h-7 w-7 text-primary" />
        <span className="text-xl font-bold text-text-light">AI-Amooz</span>
      </Link>
      <Button asChild variant="outline" className="bg-card/80 backdrop-blur-sm border-border hover:bg-card">
        <Link href="/home">ورود به داشبورد</Link>
      </Button>
    </div>
  </header>
);

const FeatureCard = ({ icon, title, description }) => (
    <Card className="bg-card/50 border-border backdrop-blur-sm text-center transform transition-all duration-300 hover:-translate-y-2 hover:shadow-2xl hover:shadow-primary/10">
        <CardHeader className="items-center">
            <div className="bg-primary/10 text-primary p-4 rounded-full mb-4 ring-2 ring-primary/20">
                {icon}
            </div>
            <CardTitle className="text-xl font-bold text-text-light">{title}</CardTitle>
        </CardHeader>
        <CardContent>
            <p className="text-text-muted text-sm leading-6">{description}</p>
        </CardContent>
    </Card>
);


export default function LandingPage() {
    const heroImage = PlaceHolderImages.find(img => img.id === 'landing-hero');

  return (
    <div className="flex flex-col min-h-screen bg-background text-text-light">
      <LandingHeader />
      
      <main className="flex-grow">
        {/* Hero Section */}
        <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 flex items-center justify-center text-center overflow-hidden">
             <div className="absolute inset-0 bg-gradient-to-b from-background via-background to-card/40 z-0"></div>
             <div className="absolute inset-0 -top-1/2 opacity-20 [mask-image:radial-gradient(farthest-side_at_top_center,white,transparent)]">
                <div className="absolute inset-y-0 -inset-x-1/3 bg-[url('https://firebasestudio.near.workers.dev/api/v1/workspaces/genkit-918b9/apps/production/assets/grid.svg')] bg-repeat "></div>
            </div>

            <div className="container mx-auto px-4 relative z-10">
                <h1 className="text-4xl md:text-6xl font-extrabold tracking-tighter mb-4 bg-gradient-to-b from-text-light to-text-light/70 text-transparent bg-clip-text">
                    آینده یادگیری با هوش مصنوعی
                </h1>
                <p className="text-lg md:text-xl text-text-muted max-w-3xl mx-auto mb-8">
                    AI-Amooz با تحلیل هوشمند و ارائه محتوای شخصی‌سازی شده، مسیر یادگیری شما را متحول می‌کند. برای موفقیت در هر درسی آماده شوید.
                </p>
                <Button asChild size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all hover:scale-105">
                    <Link href="/home">شروع یادگیری هوشمند <ArrowLeft className="mr-2 h-5 w-5" /></Link>
                </Button>

                {heroImage && (
                    <div className="mt-12 max-w-5xl mx-auto">
                        <div className="relative rounded-2xl border border-border/50 p-2 bg-card/20 shadow-2xl shadow-primary/10">
                            <Image
                                src={heroImage.imageUrl}
                                alt={heroImage.description}
                                width={1200}
                                height={800}
                                data-ai-hint={heroImage.imageHint}
                                className="rounded-xl"
                                priority
                            />
                        </div>
                    </div>
                )}
            </div>
        </section>

        {/* Features Section */}
        <section className="py-20 md:py-24 bg-card/40">
            <div className="container mx-auto px-4">
                <div className="text-center max-w-2xl mx-auto mb-12">
                    <h2 className="text-3xl md:text-4xl font-bold text-text-light">چرا AI-Amooz؟</h2>
                    <p className="text-text-muted mt-4">ابزارهایی که برای تسلط بر هر مبحثی به آن‌ها نیاز دارید.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    <FeatureCard 
                        icon={<Target className="h-8 w-8" />}
                        title="مسیر یادگیری شخصی"
                        description="هوش مصنوعی سطح دانش شما را می‌سنجد و بهترین مسیر آموزشی را برای رسیدن به اهداف‌تان پیشنهاد می‌دهد."
                    />
                    <FeatureCard 
                        icon={<Bot className="h-8 w-8" />}
                        title="دستیار هوشمند ۲۴ ساعته"
                        description="در هر ساعتی از شبانه‌روز، سوالات درسی خود را بپرسید، راه‌حل‌های مختلف را بررسی کنید و اشکالات خود را رفع کنید."
                    />
                    <FeatureCard 
                        icon={<BookCheck className="h-8 w-8" />}
                        title="آزمون‌های تطبیقی"
                        description="با آزمون‌هایی که بر اساس نقاط ضعف و قوت شما طراحی می‌شوند، برای هر امتحانی آماده شوید و پیشرفت خود را بسنجید."
                    />
                </div>
            </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="bg-background py-6">
        <div className="container mx-auto px-4 text-center text-text-muted text-sm">
          <p>&copy; {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.</p>
        </div>
      </footer>
    </div>
  );
}
