'use client';

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useLanding } from '@/hooks/use-landing';
import { motion } from 'framer-motion';
import { Quote, Star, Heart } from 'lucide-react';

const TestimonialCard = ({ 
    name, 
    role, 
    content, 
    image, 
    index 
}: { 
    name: string; 
    role: string; 
    content: string; 
    image: string;
    index: number;
}) => (
    <motion.div 
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-50px" }}
        transition={{ duration: 0.5, delay: index * 0.15 }}
        whileHover={{ y: -8 }}
        className="group relative"
    >
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-purple-500/10 rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-all duration-500" />
        
        <div className="relative p-6 md:p-8 rounded-3xl bg-gradient-to-br from-card/80 to-card/50 border border-border/50 backdrop-blur-sm transition-all duration-300 hover:border-primary/40 h-full">
            {/* Quote Icon */}
            <div className="absolute top-6 left-6 w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Quote className="w-5 h-5 text-primary" />
            </div>
            
            {/* Stars */}
            <div className="flex gap-1 mb-4 justify-end">
                {[1, 2, 3, 4, 5].map((star) => (
                    <Star key={star} className="w-4 h-4 fill-yellow-500 text-yellow-500" />
                ))}
            </div>
            
            {/* Content */}
            <p className="text-sm md:text-base text-foreground leading-relaxed mb-6 md:mb-8">
                {content}
            </p>
            
            {/* Author */}
            <div className="flex items-center gap-3 md:gap-4 pt-4 border-t border-border/50">
                <div className="relative">
                    <Avatar className="w-12 h-12 md:w-14 md:h-14 border-2 border-primary/30">
                        <AvatarImage src={image} alt={name} />
                        <AvatarFallback className="bg-primary/20 text-primary font-bold">{name[0]}</AvatarFallback>
                    </Avatar>
                    <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-green-500 border-2 border-background flex items-center justify-center">
                        <Heart className="w-3 h-3 text-white fill-white" />
                    </div>
                </div>
                <div>
                    <div className="font-bold text-base md:text-lg text-foreground">{name}</div>
                    <div className="text-xs md:text-sm text-muted-foreground">{role}</div>
                </div>
            </div>
        </div>
    </motion.div>
);

export const TestimonialSection = ({ testimonialImage }: { testimonialImage: any }) => {
    const { testimonials } = useLanding();

    return (
        <section className="py-20 md:py-32 relative overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 bg-gradient-to-b from-background via-primary/5 to-background" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(var(--primary-rgb),0.1),transparent_60%)]" />
            
            <div className="container mx-auto px-4 relative z-10">
                {/* Section Header */}
                <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-12 md:mb-20"
                >
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                        <Heart className="w-4 h-4 text-primary fill-primary" />
                        <span className="text-sm font-medium text-primary">نظرات همسفران</span>
                    </div>
                    <h2 className="text-3xl md:text-5xl lg:text-6xl font-black text-foreground mb-4">
                        داستان{' '}
                        <span className="bg-gradient-to-l from-primary to-purple-500 bg-clip-text text-transparent">
                            موفقیت
                        </span>
                    </h2>
                    <p className="text-base md:text-xl text-muted-foreground max-w-2xl mx-auto">
                        ببینید همسفران ما چه می‌گویند
                    </p>
                </motion.div>
                
                {/* Testimonial Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 max-w-6xl mx-auto">
                    {testimonials.map((t, i) => (
                        <TestimonialCard 
                            key={i} 
                            {...t} 
                            image={i === 0 && testimonialImage?.imageUrl ? testimonialImage.imageUrl : t.image}
                            index={i}
                        />
                    ))}
                </div>
                
                {/* Social Proof */}
                <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6, delay: 0.3 }}
                    className="flex flex-col sm:flex-row items-center justify-center gap-4 mt-12 md:mt-16"
                >
                    <div className="flex -space-x-3 space-x-reverse">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <motion.div 
                                key={i} 
                                initial={{ scale: 0 }}
                                whileInView={{ scale: 1 }}
                                viewport={{ once: true }}
                                transition={{ delay: 0.5 + i * 0.1, type: "spring" }}
                                className="w-10 h-10 md:w-12 md:h-12 rounded-full bg-card border-3 border-background overflow-hidden shadow-lg"
                            >
                                <img src={`https://i.pravatar.cc/100?img=${i+10}`} alt="avatar" className="w-full h-full object-cover" />
                            </motion.div>
                        ))}
                        <motion.div 
                            initial={{ scale: 0 }}
                            whileInView={{ scale: 1 }}
                            viewport={{ once: true }}
                            transition={{ delay: 1, type: "spring" }}
                            className="w-10 h-10 md:w-12 md:h-12 rounded-full bg-gradient-to-br from-primary to-purple-600 border-3 border-background flex items-center justify-center text-xs font-bold text-white shadow-lg"
                        >
                            +۵۰۰
                        </motion.div>
                    </div>
                    <span className="text-muted-foreground text-sm md:text-base">دانش‌آموز راضی و موفق</span>
                </motion.div>
            </div>
        </section>
    );
};
