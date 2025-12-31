'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { UserPlus, BookOpen, MessageSquare, Award, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

const ICON_MAP = {
  'user-plus': UserPlus,
  'book': BookOpen,
  'message': MessageSquare,
  'award': Award,
};

interface RecentActivityProps {
  activities: any[];
}

export function RecentActivity({ activities }: RecentActivityProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="lg:col-span-1"
    >
      <Card className="bg-card border-border/40 shadow-sm rounded-3xl h-full flex flex-col">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-xl font-black text-foreground">فعالیت‌های اخیر</CardTitle>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="ghost" size="sm" className="text-xs font-bold text-primary hover:bg-primary/5 rounded-xl">
                مشاهده همه
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px] rounded-3xl">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-xl font-black">
                  همه فعالیت‌ها
                </DialogTitle>
              </DialogHeader>
              <ScrollArea className="h-[500px] pr-4">
                <div className="space-y-5 py-4">
                  {activities.map((activity, idx) => {
                    const Icon = ICON_MAP[activity.icon as keyof typeof ICON_MAP] || BookOpen;
                    return (
                      <div 
                        key={activity.id} 
                        className="flex items-start gap-4 group cursor-pointer"
                      >
                        <div className={`p-3 rounded-2xl ${activity.bg} group-hover:scale-110 transition-transform duration-300 shadow-sm`}>
                          <Icon className={`w-4 h-4 ${activity.color}`} />
                        </div>
                        <div className="flex-1 space-y-1 border-b border-border/40 pb-4 group-last:border-0">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">
                              {activity.user}
                            </p>
                            <span className="text-[10px] font-bold text-muted-foreground/60 bg-muted/50 px-2 py-0.5 rounded-lg">
                              {activity.time}
                            </span>
                          </div>
                          <p className="text-xs font-medium text-muted-foreground leading-relaxed">
                            {activity.action}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent className="flex-1">
          <div className="space-y-5 mt-2">
            {activities.map((activity, idx) => {
              const Icon = ICON_MAP[activity.icon as keyof typeof ICON_MAP] || BookOpen;
              return (
                <motion.div 
                  key={activity.id} 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 + (idx * 0.1) }}
                  className="flex items-start gap-4 group cursor-pointer"
                >
                  <div className={`p-3 rounded-2xl ${activity.bg} group-hover:scale-110 transition-transform duration-300 shadow-sm`}>
                    <Icon className={`w-4 h-4 ${activity.color}`} />
                  </div>
                  <div className="flex-1 space-y-1 border-b border-border/40 pb-4 group-last:border-0">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">
                        {activity.user}
                      </p>
                      <span className="text-[10px] font-bold text-muted-foreground/60 bg-muted/50 px-2 py-0.5 rounded-lg">
                        {activity.time}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-muted-foreground leading-relaxed">
                      {activity.action}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </CardContent>
        <div className="p-4 mt-auto">
          <Button className="w-full rounded-2xl bg-muted/50 hover:bg-muted text-foreground border-none h-11 font-bold text-sm gap-2">
            گزارش کامل فعالیت‌ها
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}
