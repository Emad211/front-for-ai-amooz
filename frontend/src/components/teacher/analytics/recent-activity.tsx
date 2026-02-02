'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { UserPlus, BookOpen, MessageSquare, Award } from 'lucide-react';
import { motion } from 'framer-motion';
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatPersianDateTime } from '@/lib/date-utils';

const ICON_MAP = {
  'user-plus': UserPlus,
  'book': BookOpen,
  'message': MessageSquare,
  'award': Award,
};

interface RecentActivityProps {
  activities: any[];
  isFullWidth?: boolean;
}

export function RecentActivity({ activities, isFullWidth = false }: RecentActivityProps) {
  const content = (
    <div className="space-y-5">
      {activities.map((activity, idx) => {
        const Icon = ICON_MAP[activity.icon as keyof typeof ICON_MAP] || BookOpen;
        const formattedDate = formatPersianDateTime(activity.time);
        
        return (
          <motion.div 
            key={activity.id || idx} 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.05 }}
            className="flex items-start gap-4 group cursor-pointer"
          >
            <div className={`p-3 rounded-2xl ${activity.bg || 'bg-primary/10'} group-hover:scale-110 transition-transform duration-300 shadow-sm`}>
              <Icon className={`w-4 h-4 ${activity.color || 'text-primary'}`} />
            </div>
            <div className="flex-1 space-y-1 border-b border-border/40 pb-4 group-last:border-0">
              <div className="flex items-center justify-between">
                <p className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">
                  {activity.user}
                </p>
                <span className="text-[10px] font-bold text-muted-foreground/60 bg-muted/50 px-2 py-0.5 rounded-lg whitespace-nowrap lowercase">
                  {formattedDate}
                </span>
              </div>
              <p className="text-xs font-medium text-muted-foreground leading-relaxed">
                {activity.action}
              </p>
            </div>
          </motion.div>
        );
      })}
      {activities.length === 0 && (
        <div className="text-center py-12">
          <p className="text-muted-foreground text-sm">فعالیتی یافت نشد</p>
        </div>
      )}
    </div>
  );

  if (isFullWidth) {
    return (
      <div className="p-6 text-right" dir="rtl">
        <h2 className="text-xl font-black mb-6 text-foreground">گزارش فعالیت‌های اخیر</h2>
        <ScrollArea className="h-[60vh] pr-4">
          {content}
        </ScrollArea>
      </div>
    );
  }

  return (
    <Card className="bg-card border-border/40 shadow-sm rounded-3xl h-full flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-xl font-black text-foreground">فعالیت‌های اخیر</CardTitle>
      </CardHeader>
      <CardContent className="flex-1">
        <ScrollArea className="h-[400px] pr-4">
          {content}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
