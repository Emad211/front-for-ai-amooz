'use client';

import { Button } from '@/components/ui/button';
import { ArrowLeft, Play, Sparkles, BookOpen, Users, Zap } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { useLanding } from '@/hooks/use-landing';
import { motion } from 'framer-motion';

interface HeroSectionProps {
  heroImage: {
    imageUrl: string;
    description: string;
  };
}

export const HeroSection = ({ heroImage }: HeroSectionProps) => {
  const { hero, stats } = useLanding();

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden py-20 md:py-0 bg-gradient-to-b from-background via-background to-primary/5">
      {/* Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {/* Floating Orbs */}
        <motion.div 
          className="absolute top-20 right-[10%] w-72 h-72 bg-primary/20 rounded-full blur-[100px]"
          animate={{ 
            y: [0, -30, 0],
            scale: [1, 1.1, 1],
            opacity: [0.3, 0.5, 0.3]
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div 
          className="absolute bottom-40 left-[5%] w-96 h-96 bg-purple-500/10 rounded-full blur-[120px]"
          animate={{ 
            y: [0, 40, 0],
            scale: [1, 1.2, 1],
            opacity: [0.2, 0.4, 0.2]
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
        />
        <motion.div 
          className="absolute top-1/2 right-[60%] w-64 h-64 bg-cyan-500/10 rounded-full blur-[80px]"
          animate={{ 
            x: [0, 30, 0],
            opacity: [0.2, 0.3, 0.2]
          }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 2 }}
        />
        
        {/* Decorative Grid */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(var(--primary-rgb),0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(var(--primary-rgb),0.03)_1px,transparent_1px)] bg-[size:60px_60px] [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_70%)]" />
        
        {/* Floating Icons */}
        <motion.div
          className="absolute top-32 left-[15%] text-primary/20"
          animate={{ y: [0, -20, 0], rotate: [0, 10, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        >
          <BookOpen className="w-12 h-12" />
        </motion.div>
        <motion.div
          className="absolute bottom-32 right-[20%] text-primary/15"
          animate={{ y: [0, 15, 0], rotate: [0, -15, 0] }}
          transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}
        >
          <Users className="w-16 h-16" />
        </motion.div>
        <motion.div
          className="absolute top-1/3 right-[8%] text-yellow-500/20"
          animate={{ y: [0, -25, 0], scale: [1, 1.2, 1] }}
          transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
        >
          <Zap className="w-10 h-10" />
        </motion.div>
      </div>

      <div className="container mx-auto px-4 pt-20 md:pt-24 pb-12 relative z-10">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-primary/20 via-primary/10 to-primary/20 border border-primary/30 mb-6 md:mb-8 backdrop-blur-sm"
          >
            <motion.div
              animate={{ rotate: [0, 360] }}
              transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
            >
              <Sparkles className="w-4 h-4 text-primary" />
            </motion.div>
            <span className="text-sm font-medium text-primary">{hero.badge}</span>
          </motion.div>

          {/* Main Title */}
          <motion.h1 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="text-4xl sm:text-5xl md:text-7xl lg:text-8xl font-black tracking-tight mb-6 leading-[1.1]"
          >
            <span className="text-foreground">{hero.title.main}</span>
            <br />
            <motion.span 
              className="relative inline-block"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.4 }}
            >
              <span className="bg-gradient-to-l from-primary via-primary to-purple-500 text-transparent bg-clip-text">
                {hero.title.highlight}
              </span>
              {/* Underline decoration */}
              <motion.svg 
                className="absolute -bottom-2 left-0 w-full" 
                viewBox="0 0 300 12" 
                fill="none"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 1, delay: 0.8 }}
              >
                <motion.path 
                  d="M2 8C50 3 100 3 150 6C200 9 250 7 298 4" 
                  stroke="url(#gradient)" 
                  strokeWidth="4" 
                  strokeLinecap="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 1, delay: 0.8 }}
                />
                <defs>
                  <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="hsl(var(--primary))" />
                    <stop offset="100%" stopColor="#a855f7" />
                  </linearGradient>
                </defs>
              </motion.svg>
            </motion.span>
          </motion.h1>

          {/* Description */}
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="text-base md:text-xl text-muted-foreground max-w-2xl mx-auto mb-8 md:mb-12 leading-relaxed px-4"
          >
            {hero.description}
          </motion.p>

          {/* CTA Buttons */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16 md:mb-20 px-6 sm:px-0"
          >
            <Button
              asChild
              size="lg"
              className="group relative w-full sm:w-auto h-14 md:h-16 px-10 text-lg md:text-xl bg-gradient-to-r from-primary to-primary/90 text-primary-foreground hover:from-primary/90 hover:to-primary shadow-2xl shadow-primary/30 transition-all duration-300 hover:scale-105 hover:shadow-primary/40 overflow-hidden"
            >
              <Link href="/login">
                <span className="relative z-10 flex items-center">
                  {hero.cta.primary}
                  <ArrowLeft className="mr-2 h-5 w-5 transition-transform group-hover:-translate-x-1" />
                </span>
                <motion.div
                  className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0"
                  initial={{ x: '-100%' }}
                  whileHover={{ x: '100%' }}
                  transition={{ duration: 0.6 }}
                />
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              size="lg"
              className="w-full sm:w-auto h-14 md:h-16 px-10 text-lg md:text-xl border-2 border-border/50 hover:bg-card/80 hover:border-primary/50 backdrop-blur-sm transition-all duration-300"
            >
              <Link href="#features">
                <Play className="ml-2 h-5 w-5" />
                {hero.cta.secondary}
              </Link>
            </Button>
          </motion.div>

          {/* Stats */}
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.7 }}
            className="grid grid-cols-3 gap-4 md:gap-8 max-w-2xl mx-auto"
          >
            {[
              { value: stats.students, label: 'دانش‌آموز فعال', icon: Users },
              { value: stats.satisfaction, label: 'رضایت کاربران', icon: Sparkles },
              { value: stats.support, label: 'پشتیبانی هوشمند', icon: Zap },
            ].map((stat, index) => (
              <motion.div 
                key={stat.label}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: 0.8 + index * 0.1 }}
                className="relative group"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                <div className="relative p-4 md:p-6 rounded-2xl bg-card/50 border border-border/50 backdrop-blur-sm hover:border-primary/30 transition-all duration-300">
                  <stat.icon className="w-5 h-5 md:w-6 md:h-6 text-primary mx-auto mb-2" />
                  <div className="text-2xl md:text-4xl font-bold text-foreground">{stat.value}</div>
                  <div className="text-xs md:text-sm text-muted-foreground mt-1">{stat.label}</div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>

        {/* Hero Image */}
        {heroImage && (
          <motion.div 
            initial={{ opacity: 0, y: 60 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.9 }}
            className="mt-16 md:mt-24 max-w-6xl mx-auto px-2 md:px-0"
          >
            <div className="relative group">
              {/* Glow Effect */}
              <div className="absolute -inset-4 bg-gradient-to-r from-primary/30 via-purple-500/20 to-primary/30 rounded-3xl blur-2xl opacity-40 group-hover:opacity-60 transition-all duration-700" />
              
              {/* Browser Frame */}
              <div className="relative rounded-2xl md:rounded-3xl border border-border/50 bg-gradient-to-br from-card to-card/80 backdrop-blur-xl p-2 md:p-3 shadow-2xl">
                {/* Browser Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-border/30">
                  <div className="flex gap-2">
                    <span className="w-3 h-3 rounded-full bg-red-500/80"></span>
                    <span className="w-3 h-3 rounded-full bg-yellow-500/80"></span>
                    <span className="w-3 h-3 rounded-full bg-green-500/80"></span>
                  </div>
                  <div className="flex-1 mx-4">
                    <div className="bg-muted/50 rounded-lg py-1.5 px-4 text-center text-xs text-muted-foreground">
                      ai-amooz.ir/dashboard
                    </div>
                  </div>
                  <div className="w-16"></div>
                </div>
                
                {/* Image */}
                <div className="relative overflow-hidden rounded-xl md:rounded-2xl">
                  <Image
                    src={heroImage.imageUrl}
                    alt={heroImage.description}
                    width={1400}
                    height={900}
                    className="w-full transition-transform duration-700 group-hover:scale-[1.02]"
                    priority
                  />
                  {/* Overlay gradient */}
                  <div className="absolute inset-0 bg-gradient-to-t from-background/20 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </div>
      
      {/* Scroll Indicator */}
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 hidden md:block"
      >
        <motion.div
          animate={{ y: [0, 10, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          className="flex flex-col items-center gap-2 text-muted-foreground/50"
        >
          <span className="text-xs">اسکرول کنید</span>
          <div className="w-6 h-10 rounded-full border-2 border-muted-foreground/30 flex justify-center pt-2">
            <motion.div
              animate={{ y: [0, 12, 0], opacity: [1, 0.3, 1] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
              className="w-1.5 h-1.5 rounded-full bg-primary"
            />
          </div>
        </motion.div>
      </motion.div>
    </section>
  );
};
