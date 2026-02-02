'use client';

import { Users, BookOpen, GraduationCap, TrendingUp } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { motion } from 'framer-motion';

const ICON_MAP = {
  users: { icon: Users, color: 'text-blue-500', bg: 'bg-blue-500/10' },
  book: { icon: BookOpen, color: 'text-purple-500', bg: 'bg-purple-500/10' },
  graduation: { icon: GraduationCap, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  trending: { icon: TrendingUp, color: 'text-amber-500', bg: 'bg-amber-500/10' },
};

interface OverviewCardsProps {
  stats: any[];
}

export function OverviewCards({ stats }: OverviewCardsProps) {
  const gridCols = stats.length === 1 ? 'lg:grid-cols-1' : 
                   stats.length === 2 ? 'lg:grid-cols-2' :
                   stats.length === 3 ? 'lg:grid-cols-3' : 'lg:grid-cols-4';

  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 ${gridCols} gap-4 md:gap-6`}>
      {stats.map((stat, index) => {
        const config = ICON_MAP[stat.icon as keyof typeof ICON_MAP] || ICON_MAP.users;
        const Icon = config.icon;
        
        return (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Card className="group relative overflow-hidden bg-card border-border/40 hover:border-primary/40 hover:shadow-xl hover:shadow-primary/5 transition-all duration-500 rounded-3xl">
              <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full -mr-12 -mt-12 transition-transform group-hover:scale-150 duration-700" />
              
              <CardContent className="p-5 sm:p-7 relative z-10">
                <div className="flex items-center justify-between mb-5">
                  <div className={`p-3 ${config.bg} rounded-2xl group-hover:scale-110 transition-transform duration-300`}>
                    <Icon className={`w-5 h-5 sm:w-6 sm:h-6 ${config.color}`} />
                  </div>
                </div>
                
                <div className="space-y-1">
                  <p className="text-xs sm:text-sm font-bold text-muted-foreground/80 tracking-tight">
                    {stat.title}
                  </p>
                  <div className="flex items-baseline gap-1">
                    <h3 className="text-2xl sm:text-3xl font-black text-foreground tracking-tighter">
                      {stat.value}
                    </h3>
                    <span className="text-[10px] font-bold text-muted-foreground/50">واحد</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}
