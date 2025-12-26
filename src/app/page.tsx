'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { GraduationCap, ArrowLeft, Bot, Target, BookCheck, StepForward, Goal, Sparkles } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { PlaceHolderImages } from '@/lib/placeholder-images';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';


const LandingHeader = () => (
  <header className="absolute top-0 left-0 right-0 z-20 p-4 md:px-8 bg-transparent">
    <div className="container mx-auto flex justify-between items-center">
      <Link href="/" className="flex items-center gap-2">
        <GraduationCap className="h-7 w-7 text-primary" />
        <span className="text-xl font-bold text-text-light">AI-Amooz</span>
      </Link>
      <Button asChild variant="outline" className="bg-card/80 backdrop-blur-sm border-border hover:bg-card">
        <Link href="/login">ورود</Link>
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
            <p className="text-text-muted text-sm leading-7">{description}</p>
        </CardContent>
    </Card>
);

const HowItWorksStep = ({ icon, title, description, step }) => (
    <div className="relative flex flex-col items-center text-center">
        <div className="absolute top-8 left-1/2 w-px h-full border-l-2 border-dashed border-border -z-10 hidden md:block"></div>
        <div className="relative bg-background p-2 rounded-full z-10">
            <div className="bg-primary/10 text-primary p-5 rounded-full ring-4 ring-background">
                {icon}
            </div>
        </div>
        <h3 className="mt-6 text-xl font-bold text-text-light">{title}</h3>
        <p className="mt-2 text-text-muted max-w-xs">{description}</p>
    </div>
);


export default function LandingPage() {
    const heroImage = PlaceHolderImages.find(img => img.id === 'landing-hero');
    const testimonialImage = PlaceHolderImages.find(img => img.id === 'testimonial-avatar');

  return (
    <div className="flex flex-col min-h-screen bg-background text-text-light">
      <LandingHeader />
      
      <main className="flex-grow">
        {/* Hero Section */}
        <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 flex items-center justify-center text-center overflow-hidden">
             <div className="absolute inset-0 bg-gradient-to-b from-background via-background/90 to-card/50 z-0"></div>
             <div className="absolute inset-0 -top-1/2 opacity-10 dark:[&>div]:bg-[url('https://firebasestudio.near.workers.dev/api/v1/workspaces/genkit-918b9/apps/production/assets/grid.svg')] light:[&>div]:bg-[url('https://firebasestudio.near.workers.dev/api/v1/workspaces/genkit-918b9/apps/production/assets/grid-black.svg')]">
                <div className="absolute inset-y-0 -inset-x-1/3 bg-repeat"></div>
            </div>

            <div className="container mx-auto px-4 relative z-10">
                <h1 className="text-4xl md:text-6xl font-extrabold tracking-tighter mb-4 bg-gradient-to-b from-text-light to-text-light/70 text-transparent bg-clip-text">
                    آینده یادگیری با هوش مصنوعی
                </h1>
                <p className="text-lg md:text-xl text-text-muted max-w-3xl mx-auto mb-8">
                    AI-Amooz با تحلیل هوشمند و ارائه محتوای شخصی‌سازی شده، مسیر یادگیری شما را متحول می‌کند. برای موفقیت در هر درسی آماده شوید.
                </p>
                <Button asChild size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all hover:scale-105 active:scale-95">
                    <Link href="/login">ورود <ArrowLeft className="mr-2 h-5 w-5" /></Link>
                </Button>

                {heroImage && (
                    <div className="mt-16 max-w-5xl mx-auto group">
                        <div className="relative rounded-2xl border border-border/50 p-2 bg-card/30 shadow-2xl shadow-primary/10 backdrop-blur-sm transition-all duration-500 group-hover:scale-[1.02]">
                             <div className="absolute top-2 left-2 flex gap-1.5 z-10">
                                <span className="w-3 h-3 rounded-full bg-red-500/80"></span>
                                <span className="w-3 h-3 rounded-full bg-yellow-500/80"></span>
                                <span className="w-3 h-3 rounded-full bg-green-500/80"></span>
                            </div>
                            <Image
                                src={heroImage.imageUrl}
                                alt={heroImage.description}
                                width={1200}
                                height={800}
                                data-ai-hint={heroImage.imageHint}
                                className="rounded-lg border border-black/5"
                                priority
                            />
                        </div>
                    </div>
                )}
            </div>
        </section>

        {/* Features Section */}
        <section id="features" className="py-20 md:py-24 bg-card/50">
            <div className="container mx-auto px-4">
                <div className="text-center max-w-2xl mx-auto mb-16">
                    <h2 className="text-3xl md:text-4xl font-bold text-text-light">چرا AI-Amooz؟</h2>
                    <p className="text-text-muted mt-4 text-lg">ابزارهایی هوشمند که برای تسلط بر هر مبحثی به آن‌ها نیاز دارید.</p>
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
        
        {/* How it works */}
        <section id="how-it-works" className="py-20 md:py-24 bg-background">
            <div className="container mx-auto px-4">
                <div className="text-center max-w-2xl mx-auto mb-16">
                    <h2 className="text-3xl md:text-4xl font-bold text-text-light">شروع یادگیری در ۳ مرحله ساده</h2>
                    <p className="text-text-muted mt-4 text-lg">مسیر موفقیت شما از اینجا شروع می‌شود.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8">
                    <HowItWorksStep 
                        icon={<Goal className="w-8 h-8" />}
                        title="۱. هدف خود را مشخص کنید"
                        description="ثبت‌نام کنید و به ما بگویید در چه درسی و برای چه هدفی (کنکور، امتحان نهایی، ...) به کمک نیاز دارید."
                    />
                    <HowItWorksStep 
                        icon={<Sparkles className="w-8 h-8" />}
                        title="۲. مسیر شخصی خود را دریافت کنید"
                        description="هوش مصنوعی AI-Amooz یک نقشه راه یادگیری مخصوص شما، شامل درسنامه‌ها، تمرین‌ها و آزمون‌ها، ایجاد می‌کند."
                    />
                    <HowItWorksStep 
                        icon={<StepForward className="w-8 h-8" />}
                        title="۳. یادگیری را شروع کنید"
                        description="با همراهی دستیار هوشمند، مراحل را یکی‌یکی طی کنید، تمرین حل کنید و پیشرفت خود را مشاهده نمایید."
                    />
                </div>
            </div>
        </section>

        {/* Testimonial Section */}
        <section id="testimonial" className="py-20 md:py-24 bg-card/50">
            <div className="container mx-auto px-4">
                <div className="max-w-3xl mx-auto text-center">
                    {testimonialImage && (
                         <Avatar className="w-24 h-24 mx-auto mb-6 border-4 border-primary/20">
                            <AvatarImage src={testimonialImage.imageUrl} alt="Testimonial Avatar" />
                            <AvatarFallback>S.A</AvatarFallback>
                        </Avatar>
                    )}
                    <blockquote className="text-xl md:text-2xl leading-relaxed text-text-light font-medium">
                        "با AI-Amooz بالاخره تونستم مفاهیم پیچیده ریاضی رو به سادگی یاد بگیرم. دستیار هوشمندش همیشه برای رفع اشکال کنارم بود و باعث شد با اعتماد به نفس بیشتری برای کنکور آماده بشم."
                    </blockquote>
                    <p className="mt-6 font-bold text-text-light">سارا احمدی</p>
                    <p className="text-sm text-text-muted">دانش‌آموز سال دوازدهم</p>
                </div>
            </div>
        </section>

        {/* FAQ Section */}
        <section id="faq" className="py-20 md:py-24 bg-background">
            <div className="container mx-auto px-4">
                 <div className="text-center max-w-2xl mx-auto mb-16">
                    <h2 className="text-3xl md:text-4xl font-bold text-text-light">سوالات متداول</h2>
                    <p className="text-text-muted mt-4 text-lg">پاسخ سوالاتی که ممکن است برای شما پیش بیاید.</p>
                </div>
                <div className="max-w-3xl mx-auto">
                     <Accordion type="single" collapsible className="w-full space-y-4">
                        <AccordionItem value="item-1" className="bg-card/50 border-border rounded-lg">
                            <AccordionTrigger className="text-lg font-semibold p-6 text-right hover:no-underline">AI-Amooz برای چه مقاطع و درس‌هایی مناسب است؟</AccordionTrigger>
                            <AccordionContent className="p-6 pt-0 text-text-muted leading-7">
                                در حال حاضر، AI-Amooz بر روی دروس تخصصی مقطع متوسطه دوم (ریاضیات، فیزیک، و علوم کامپیوتر) متمرکز است. ما به طور مداوم در حال گسترش محتوای خود هستیم تا رشته‌ها و مقاطع بیشتری را پوشش دهیم.
                            </AccordionContent>
                        </AccordionItem>
                        <AccordionItem value="item-2" className="bg-card/50 border-border rounded-lg">
                            <AccordionTrigger className="text-lg font-semibold p-6 text-right hover:no-underline">آیا استفاده از دستیار هوشمند هزینه دارد؟</AccordionTrigger>
                            <AccordionContent className="p-6 pt-0 text-text-muted leading-7">
                                ثبت‌نام اولیه و استفاده از بخش قابل توجهی از امکانات AI-Amooz، از جمله مسیر یادگیری شخصی و تعدادی سوال از دستیار هوشمند، رایگان است. برای دسترسی نامحدود به تمامی امکانات، پلن‌های اشتراک مقرون‌به‌صرفه در نظر گرفته شده است.
                            </AccordionContent>
                        </AccordionItem>
                         <AccordionItem value="item-3" className="bg-card/50 border-border rounded-lg">
                            <AccordionTrigger className="text-lg font-semibold p-6 text-right hover:no-underline">چگونه هوش مصنوعی مسیر یادگیری را شخصی‌سازی می‌کند؟</AccordionTrigger>
                            <AccordionContent className="p-6 pt-0 text-text-muted leading-7">
                                سیستم هوشمند ما با یک آزمون تعیین سطح اولیه، نقاط قوت و ضعف شما را شناسایی می‌کند. سپس، با تحلیل عملکرد شما در طول یادگیری و حل تمرین‌ها، به طور مداوم نقشه راه را به‌روزرسانی کرده و محتوایی را پیشنهاد می‌دهد که دقیقاً به آن نیاز دارید.
                            </AccordionContent>
                        </AccordionItem>
                    </Accordion>
                </div>
            </div>
        </section>

        {/* Final CTA Section */}
        <section className="py-20 md:py-24 bg-card/50">
            <div className="container mx-auto px-4 text-center">
                 <h2 className="text-3xl md:text-4xl font-bold text-text-light">برای یک تحول آموزشی آماده‌اید؟</h2>
                 <p className="text-lg text-text-muted mt-4 max-w-2xl mx-auto">
                    همین امروز به هزاران دانش‌آموز موفق بپیوندید و یادگیری را به تجربه‌ای لذت‌بخش و مؤثر تبدیل کنید.
                </p>
                <div className="mt-8">
                     <Button asChild size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all hover:scale-105 active:scale-95">
                        <Link href="/login">همین حالا شروع کنید <ArrowLeft className="mr-2 h-5 w-5" /></Link>
                    </Button>
                </div>
            </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-background border-t border-border">
        <div className="container mx-auto px-4 py-8">
            <div className="flex flex-col md:flex-row justify-between items-center text-center md:text-right">
                 <div className="mb-4 md:mb-0">
                      <Link href="/" className="flex items-center gap-2 justify-center md:justify-start">
                        <GraduationCap className="h-7 w-7 text-primary" />
                        <span className="text-xl font-bold text-text-light">AI-Amooz</span>
                      </Link>
                      <p className="text-sm text-text-muted mt-2">آینده یادگیری، امروز در دستان شماست.</p>
                 </div>
                 <div className="flex gap-6 text-sm text-text-muted">
                    <Link href="#features" className="hover:text-primary">ویژگی‌ها</Link>
                    <Link href="#faq" className="hover:text-primary">سوالات متداول</Link>
                    <Link href="#" className="hover:text-primary">تماس با ما</Link>
                 </div>
            </div>
            <div className="mt-8 pt-6 border-t border-border/50 text-center text-sm text-text-muted">
                 <p>&copy; {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.</p>
            </div>
        </div>
      </footer>
    </div>
  );
}
