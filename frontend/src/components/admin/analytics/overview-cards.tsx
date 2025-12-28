'use client';

import { Users, BookOpen, GraduationCap, TrendingUp } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { MOCK_ANALYTICS_STATS } from '@/constants/mock';

const ICON_MAP = {
  users: Users,
  book: BookOpen,
  graduation: GraduationCap,
  trending: TrendingUp,
};

export function OverviewCards() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
      {MOCK_ANALYTICS_STATS.map((stat, index) => {
        const Icon = ICON_MAP[stat.icon as keyof typeof ICON_MAP];
        return (
          <Card key={index} className="bg-card border-border/60 hover:border-primary/30 transition-all duration-300">
            <CardContent className="p-4 sm:p-6">
              <div className="flex items-center justify-between mb-3 sm:mb-4">
                <div className="p-1.5 sm:p-2 bg-muted rounded-lg">
                  <Icon className="w-4 h-4 sm:w-5 sm:h-5 text-muted-foreground" />
                </div>
                <span className={`text-[10px] sm:text-xs font-medium px-1.5 sm:px-2 py-0.5 sm:py-1 rounded-full ${
                  stat.trend === 'up' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-rose-500/10 text-rose-600'
                }`}>
                  {stat.change}
                </span>
              </div>
              <div>
                <p className="text-[10px] sm:text-sm font-medium text-muted-foreground">{stat.title}</p>
                <h3 className="text-lg sm:text-2xl font-bold text-foreground mt-0.5 sm:mt-1">{stat.value}</h3>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
