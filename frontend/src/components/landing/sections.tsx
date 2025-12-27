'use client';

import { Button } from '@/components/ui/button';
import { ArrowLeft, Bot, Target, BookCheck, Sparkles, Play } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

export const HeroSection = ({ heroImage }: { heroImage: any }) => (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden py-20 md:py-0">
        {/* Background Effects */}
        <div className="absolute inset-0 bg-gradient-to-b from-primary/5 via-background to-background"></div>
        <div className="absolute top-1/4 right-1/4 w-64 h-64 md:w-96 md:h-96 bg-primary/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-1/4 left-1/4 w-48 h-48 md:w-64 md:h-64 bg-primary/5 rounded-full blur-3xl"></div>
        
        <div className="container mx-auto px-4 pt-20 md:pt-24 pb-12 relative z-10">
            <div className="max-w-4xl mx-auto text-center">
                {/* Badge */}
                <div className="inline-flex items-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-full bg-primary/10 border border-primary/20 mb-6 md:mb-8">
                    <Sparkles className="w-3.5 h-3.5 md:w-4 md:h-4 text-primary" />
                    <span className="text-xs md:text-sm font-medium text-primary">پلتفرم آموزشی نسل جدید</span>
                </div>
                
                <h1 className="text-3xl sm:text-4xl md:text-6xl lg:text-7xl font-black tracking-tight mb-6 leading-[1.2]">
                    <span className="text-foreground">یادگیری هوشمند</span>
                    <br />
                    <span className="bg-gradient-to-l from-primary via-primary to-primary/70 text-transparent bg-clip-text">
                        با قدرت AI
                    </span>
                </h1>
                
                <p className="text-base md:text-xl text-muted-foreground max-w-2xl mx-auto mb-8 md:mb-10 leading-relaxed px-4">
                    دستیار هوشمند شخصی شما برای تسلط بر هر مبحثی. 
                    مسیر یادگیری اختصاصی، پاسخ‌گویی ۲۴ ساعته و آزمون‌های تطبیقی.
                </p>
                
                <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12 md:mb-16 px-6 sm:px-0">
                    <Button asChild size="lg" className="w-full sm:w-auto h-12 md:h-14 px-8 text-base md:text-lg bg-primary text-primary-foreground hover:bg-primary/90 shadow-xl shadow-primary/25 transition-all hover:scale-105">
                        <Link href="/login">
                            شروع رایگان
                            <ArrowLeft className="mr-2 h-5 w-5" />
                        </Link>
                    </Button>
                    <Button asChild variant="outline" size="lg" className="w-full sm:w-auto h-12 md:h-14 px-8 text-base md:text-lg border-border/50 hover:bg-card/50">
                        <Link href="#features">
                            <Play className="ml-2 h-4 w-4" />
                            مشاهده دمو
                        </Link>
                    </Button>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 md:flex items-center justify-center gap-6 md:gap-16 text-center">
                    <div className="col-span-1">
                        <div className="text-2xl md:text-4xl font-bold text-foreground">۵۰۰۰+</div>
                        <div className="text-xs md:text-sm text-muted-foreground mt-1">دانش‌آموز فعال</div>
                    </div>
                    <div className="w-px h-12 bg-border hidden md:block"></div>
                    <div className="col-span-1">
                        <div className="text-2xl md:text-4xl font-bold text-foreground">۹۸٪</div>
                        <div className="text-xs md:text-sm text-muted-foreground mt-1">رضایت کاربران</div>
                    </div>
                    <div className="w-px h-12 bg-border hidden md:block"></div>
                    <div className="col-span-2 md:col-span-1">
                        <div className="text-2xl md:text-4xl font-bold text-foreground">۲۴/۷</div>
                        <div className="text-xs md:text-sm text-muted-foreground mt-1">پشتیبانی هوشمند</div>
                    </div>
                </div>
            </div>

            {/* Hero Image */}
            {heroImage && (
                <div className="mt-16 md:mt-20 max-w-6xl mx-auto px-2 md:px-0">
                    <div className="relative group">
                        <div className="absolute -inset-1 bg-gradient-to-r from-primary/20 via-primary/10 to-primary/20 rounded-3xl blur-xl opacity-50 group-hover:opacity-75 transition-opacity"></div>
                        <div className="relative rounded-xl md:rounded-2xl border border-border/50 bg-card/80 backdrop-blur-sm p-1.5 md:p-2 shadow-2xl">
                            <div className="absolute top-3 left-3 md:top-4 md:left-4 flex gap-1.5 md:gap-2 z-10">
                                <span className="w-2 h-2 md:w-3 md:h-3 rounded-full bg-red-500"></span>
                                <span className="w-2 h-2 md:w-3 md:h-3 rounded-full bg-yellow-500"></span>
                                <span className="w-2 h-2 md:w-3 md:h-3 rounded-full bg-green-500"></span>
                            </div>
                            <Image
                                src={heroImage.imageUrl}
                                alt={heroImage.description}
                                width={1400}
                                height={900}
                                className="rounded-lg md:rounded-xl"
                                priority
                            />
                        </div>
                    </div>
                </div>
            )}
        </div>
    </section>
);

const FeatureCard = ({ icon, title, description, gradient }: { icon: React.ReactNode, title: string, description: string, gradient: string }) => (
    <div className="group relative">
        <div className={`absolute inset-0 bg-gradient-to-br ${gradient} rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500`}></div>
        <div className="relative h-full p-6 md:p-8 rounded-3xl bg-card/50 border border-border/50 backdrop-blur-sm transition-all duration-300 hover:border-primary/30 hover:-translate-y-1">
            <div className="w-12 h-12 md:w-14 md:h-14 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-5 md:mb-6">
                {icon}
            </div>
            <h3 className="text-lg md:text-xl font-bold text-foreground mb-2 md:mb-3">{title}</h3>
            <p className="text-sm md:text-base text-muted-foreground leading-relaxed">{description}</p>
        </div>
    </div>
);

export const FeaturesSection = () => (
    <section id="features" className="py-20 md:py-32 relative">
        <div className="container mx-auto px-4">
            <div className="text-center max-w-2xl mx-auto mb-12 md:mb-20">
                <span className="text-primary font-semibold text-xs md:text-sm tracking-wider uppercase">ویژگی‌ها</span>
                <h2 className="text-2xl md:text-5xl font-bold text-foreground mt-3 md:mt-4">
                    چرا AI-Amooz متفاوت است؟
                </h2>
                <p className="text-sm md:text-lg text-muted-foreground mt-4 md:mt-6">
                    ابزارهای هوشمندی که یادگیری را برای شما شخصی‌سازی می‌کنند
                </p>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 md:gap-8">
                <FeatureCard 
                    icon={<Target className="h-6 w-6 md:h-7 md:w-7" />}
                    title="مسیر یادگیری شخصی"
                    description="هوش مصنوعی سطح دانش شما را می‌سنجد و بهترین مسیر آموزشی را برای رسیدن به اهداف‌تان طراحی می‌کند."
                    gradient="from-blue-500/20 to-cyan-500/20"
                />
                <FeatureCard 
                    icon={<Bot className="h-6 w-6 md:h-7 md:w-7" />}
                    title="دستیار هوشمند ۲۴/۷"
                    description="در هر لحظه سوالات درسی بپرسید، راه‌حل‌های مختلف را بررسی کنید و اشکالات خود را رفع کنید."
                    gradient="from-primary/20 to-emerald-500/20"
                />
                <FeatureCard 
                    icon={<BookCheck className="h-6 w-6 md:h-7 md:w-7" />}
                    title="آزمون‌های تطبیقی"
                    description="آزمون‌هایی که بر اساس نقاط ضعف و قوت شما طراحی می‌شوند تا پیشرفت واقعی داشته باشید."
                    gradient="from-purple-500/20 to-pink-500/20"
                />
            </div>
        </div>
    </section>
);

const StepItem = ({ number, title, description, align }: { number: string, title: string, description: string, align: 'right' | 'left' }) => (
    <div className={`relative flex items-center gap-6 md:gap-8 ${align === 'left' ? 'md:flex-row-reverse' : ''}`}>
        <div className={`flex-1 ${align === 'left' ? 'md:text-left' : 'md:text-right'} text-right pr-14 md:pr-0`}>
            <div className="p-5 md:p-6 rounded-2xl bg-card/50 border border-border/50 inline-block transition-transform hover:scale-[1.02] duration-300">
                <h3 className="text-lg md:text-xl font-bold text-foreground mb-1 md:mb-2">{title}</h3>
                <p className="text-sm md:text-base text-muted-foreground">{description}</p>
            </div>
        </div>
        <div className="absolute right-0 md:right-1/2 md:translate-x-1/2 w-10 h-10 md:w-12 md:h-12 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-lg md:text-xl font-bold shadow-lg shadow-primary/30 z-10">
            {number}
        </div>
        <div className="flex-1 hidden md:block"></div>
    </div>
);

export const HowItWorksSection = () => (
    <section id="how-it-works" className="py-20 md:py-32 bg-card/30">
        <div className="container mx-auto px-4">
            <div className="text-center max-w-2xl mx-auto mb-12 md:mb-20">
                <span className="text-primary font-semibold text-xs md:text-sm tracking-wider uppercase">نحوه کار</span>
                <h2 className="text-2xl md:text-5xl font-bold text-foreground mt-3 md:mt-4">
                    شروع در ۳ مرحله ساده
                </h2>
            </div>
            
            <div className="max-w-4xl mx-auto">
                <div className="relative">
                    {/* Connection Line */}
                    <div className="absolute top-0 bottom-0 right-5 md:right-1/2 w-px bg-gradient-to-b from-primary via-primary/50 to-primary/20 z-0"></div>
                    
                    <div className="space-y-12 md:space-y-24">
                        <StepItem 
                            number="۱"
                            title="ثبت‌نام و تعیین هدف"
                            description="به ما بگویید در چه درسی و برای چه هدفی به کمک نیاز دارید. کنکور، امتحان نهایی یا تقویت پایه."
                            align="right"
                        />
                        <StepItem 
                            number="۲"
                            title="دریافت نقشه راه"
                            description="هوش مصنوعی یک مسیر یادگیری مخصوص شما شامل درسنامه، تمرین و آزمون ایجاد می‌کند."
                            align="left"
                        />
                        <StepItem 
                            number="۳"
                            title="شروع یادگیری"
                            description="با همراهی دستیار هوشمند مراحل را طی کنید و پیشرفت خود را لحظه به لحظه ببینید."
                            align="right"
                        />
                    </div>
                </div>
            </div>
        </div>
    </section>
);

const TestimonialCard = ({ name, role, content, image }: { name: string, role: string, content: string, image: string }) => (
    <div className="relative p-6 md:p-8 rounded-3xl bg-card/50 border border-border/50 backdrop-blur-sm transition-all duration-300 hover:border-primary/30 hover:-translate-y-1">
        <div className="absolute -top-4 right-8 text-5xl md:text-6xl text-primary/20 font-serif">"</div>
        <p className="text-sm md:text-base text-foreground leading-relaxed mb-6 md:mb-8 relative z-10">
            {content}
        </p>
        <div className="flex items-center gap-3 md:gap-4">
            <Avatar className="w-10 h-10 md:w-12 md:h-12 border-2 border-primary/20">
                <AvatarImage src={image} alt={name} />
                <AvatarFallback>{name[0]}</AvatarFallback>
            </Avatar>
            <div>
                <div className="font-bold text-sm md:text-base text-foreground">{name}</div>
                <div className="text-[10px] md:text-xs text-muted-foreground">{role}</div>
            </div>
        </div>
    </div>
);

export const TestimonialSection = ({ testimonialImage }: { testimonialImage: any }) => {
    const testimonials = [
        {
            name: "آرش راد",
            role: "دانش‌آموز پایه دوازدهم • رتبه ۱۲۳ کنکور",
            content: "با AI-Amooz تونستم مفاهیم پیچیده ریاضی رو به سادگی یاد بگیرم. دستیار هوشمندش همیشه برای رفع اشکال کنارم بود و باعث شد با اعتماد به نفس بیشتری برای کنکور آماده بشم.",
            image: testimonialImage?.imageUrl || "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?q=80&w=200&h=200&auto=format&fit=crop"
        },
        {
            name: "ثنا جاوید",
            role: "دانش‌آموز پایه یازدهم تجربی",
            content: "مسیر یادگیری شخصی‌سازی شده واقعاً به من کمک کرد تا روی نقاط ضعفم تمرکز کنم. قبلاً ساعت‌ها وقتم رو برای پیدا کردن منابع هدر می‌دادم، اما الان همه چیز آماده‌ست.",
            image: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=200&h=200&auto=format&fit=crop"
        },
        {
            name: "بردیا نیک‌بین",
            role: "دانش‌آموز پایه دهم ریاضی",
            content: "آزمون‌های تطبیقی فوق‌العاده هستن. هر بار که اشتباه می‌کنم، هوش مصنوعی دقیقاً همون مبحث رو دوباره با مثال‌های ساده‌تر برام توضیح میده تا کاملاً یاد بگیرم.",
            image: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=200&h=200&auto=format&fit=crop"
        }
    ];

    return (
        <section className="py-20 md:py-32 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-full">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] md:w-[600px] h-[300px] md:h-[600px] bg-primary/5 rounded-full blur-3xl"></div>
            </div>
            
            <div className="container mx-auto px-4 relative z-10">
                <div className="text-center mb-12 md:mb-20">
                    <span className="text-primary font-semibold text-xs md:text-sm tracking-wider uppercase">نظرات کاربران</span>
                    <h2 className="text-2xl md:text-5xl font-bold text-foreground mt-3 md:mt-4">
                        داستان موفقیت دانش‌آموزان
                    </h2>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 max-w-6xl mx-auto">
                    {testimonials.map((t, i) => (
                        <TestimonialCard key={i} {...t} />
                    ))}
                </div>
                
                {/* More Testimonials Avatars */}
                <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mt-12 md:mt-16">
                    <div className="flex -space-x-3 space-x-reverse">
                        {[1, 2, 3, 4].map((i) => (
                            <div key={i} className="w-8 h-8 md:w-10 md:h-10 rounded-full bg-card border-2 border-background overflow-hidden">
                                <img src={`https://i.pravatar.cc/100?img=${i+10}`} alt="avatar" className="w-full h-full object-cover" />
                            </div>
                        ))}
                        <div className="w-8 h-8 md:w-10 md:h-10 rounded-full bg-primary/20 border-2 border-background flex items-center justify-center text-[10px] md:text-xs font-bold text-primary">+۵۰۰</div>
                    </div>
                    <span className="text-muted-foreground text-xs md:text-sm">دانش‌آموز موفق دیگر</span>
                </div>
            </div>
        </section>
    );
};

export const FAQSection = () => (
    <section id="faq" className="py-20 md:py-32 bg-card/30">
        <div className="container mx-auto px-4">
            <div className="text-center max-w-2xl mx-auto mb-12 md:mb-16">
                <span className="text-primary font-semibold text-xs md:text-sm tracking-wider uppercase">سوالات متداول</span>
                <h2 className="text-2xl md:text-5xl font-bold text-foreground mt-3 md:mt-4">
                    پاسخ به سوالات شما
                </h2>
            </div>
            
            <div className="max-w-3xl mx-auto">
                <Accordion type="single" collapsible className="space-y-3 md:space-y-4">
                    <AccordionItem value="item-1" className="bg-card/50 border border-border/50 rounded-xl md:rounded-2xl px-4 md:px-6 overflow-hidden">
                        <AccordionTrigger className="text-base md:text-lg font-semibold py-4 md:py-6 text-right hover:no-underline hover:text-primary transition-colors">
                            AI-Amooz برای چه مقاطع و درس‌هایی مناسب است؟
                        </AccordionTrigger>
                        <AccordionContent className="pb-4 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed">
                            در حال حاضر روی دروس تخصصی متوسطه دوم (ریاضیات، فیزیک و علوم کامپیوتر) متمرکز هستیم. 
                            به طور مداوم در حال گسترش محتوا برای رشته‌ها و مقاطع بیشتر هستیم.
                        </AccordionContent>
                    </AccordionItem>
                    
                    <AccordionItem value="item-2" className="bg-card/50 border border-border/50 rounded-xl md:rounded-2xl px-4 md:px-6 overflow-hidden">
                        <AccordionTrigger className="text-base md:text-lg font-semibold py-4 md:py-6 text-right hover:no-underline hover:text-primary transition-colors">
                            آیا استفاده از دستیار هوشمند رایگان است؟
                        </AccordionTrigger>
                        <AccordionContent className="pb-4 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed">
                            بله! ثبت‌نام و استفاده از بخش قابل توجهی از امکانات رایگان است. 
                            برای دسترسی نامحدود، پلن‌های اشتراک مقرون‌به‌صرفه داریم.
                        </AccordionContent>
                    </AccordionItem>
                    
                    <AccordionItem value="item-3" className="bg-card/50 border border-border/50 rounded-xl md:rounded-2xl px-4 md:px-6 overflow-hidden">
                        <AccordionTrigger className="text-base md:text-lg font-semibold py-4 md:py-6 text-right hover:no-underline hover:text-primary transition-colors">
                            چگونه مسیر یادگیری شخصی‌سازی می‌شود؟
                        </AccordionTrigger>
                        <AccordionContent className="pb-4 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed">
                            با یک آزمون تعیین سطح اولیه، نقاط قوت و ضعف شما شناسایی می‌شود. 
                            سپس با تحلیل مداوم عملکرد، نقشه راه به‌روزرسانی می‌شود.
                        </AccordionContent>
                    </AccordionItem>
                    
                    <AccordionItem value="item-4" className="bg-card/50 border border-border/50 rounded-xl md:rounded-2xl px-4 md:px-6 overflow-hidden">
                        <AccordionTrigger className="text-base md:text-lg font-semibold py-4 md:py-6 text-right hover:no-underline hover:text-primary transition-colors">
                            آیا می‌توانم از موبایل استفاده کنم؟
                        </AccordionTrigger>
                        <AccordionContent className="pb-4 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed">
                            بله! پلتفرم کاملاً ریسپانسیو است و می‌توانید از هر دستگاهی استفاده کنید. 
                            اپلیکیشن موبایل هم به زودی منتشر می‌شود.
                        </AccordionContent>
                    </AccordionItem>
                </Accordion>
            </div>
        </div>
    </section>
);

export const FinalCTASection = () => (
    <section className="py-20 md:py-32 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-t from-primary/10 via-transparent to-transparent"></div>
        
        <div className="container mx-auto px-4 relative z-10">
            <div className="max-w-3xl mx-auto text-center">
                <h2 className="text-2xl md:text-5xl font-bold text-foreground mb-4 md:mb-6">
                    آماده تحول در یادگیری هستید؟
                </h2>
                <p className="text-base md:text-lg text-muted-foreground mb-8 md:mb-10 max-w-xl mx-auto px-4">
                    همین امروز به هزاران دانش‌آموز موفق بپیوندید و یادگیری را به تجربه‌ای لذت‌بخش تبدیل کنید.
                </p>
                <div className="flex flex-col sm:flex-row items-center justify-center gap-4 px-6 sm:px-0">
                    <Button asChild size="lg" className="w-full sm:w-auto h-12 md:h-14 px-10 text-base md:text-lg bg-primary text-primary-foreground hover:bg-primary/90 shadow-xl shadow-primary/25 transition-all hover:scale-105">
                        <Link href="/login">
                            همین حالا شروع کنید
                            <ArrowLeft className="mr-2 h-5 w-5" />
                        </Link>
                    </Button>
                </div>
                <p className="text-xs md:text-sm text-muted-foreground mt-6">
                    بدون نیاز به کارت اعتباری • شروع رایگان
                </p>
            </div>
        </div>
    </section>
);
