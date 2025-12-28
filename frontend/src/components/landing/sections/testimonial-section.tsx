'use client';

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { MOCK_TESTIMONIALS } from '@/constants/mock';

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
                    {MOCK_TESTIMONIALS.map((t, i) => (
                        <TestimonialCard 
                            key={i} 
                            {...t} 
                            image={i === 0 && testimonialImage?.imageUrl ? testimonialImage.imageUrl : t.image}
                        />
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
