'use client';

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

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
        <section className="py-20 md:py-32 relative bg-primary/10 dark:bg-primary/5">
            
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
