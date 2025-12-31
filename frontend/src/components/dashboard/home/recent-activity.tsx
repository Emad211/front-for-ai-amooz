'use client';

import { History, ArrowLeft, FileText, Video, BookOpen } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ActivityCard } from '@/components/dashboard/ui/activity-card';
import { DashboardActivity } from '@/types';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

interface RecentActivityProps {
  activities: DashboardActivity[];
}

export function RecentActivity({ activities }: RecentActivityProps) {
  return (
    <Card className="lg:col-span-2 bg-card border-border/50 rounded-2xl md:rounded-3xl overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between border-b border-border/50 bg-muted/20 px-4 md:px-6 py-3 md:py-4">
        <CardTitle className="flex items-center gap-2 md:gap-3 text-lg md:text-xl font-black">
          <div className="p-1.5 md:p-2 bg-primary/10 rounded-lg">
            <History className="h-4 w-4 md:h-5 md:w-5 text-primary"/>
          </div>
          فعالیت‌های اخیر
        </CardTitle>
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="ghost" size="sm" className="text-primary text-xs md:text-sm font-bold hover:bg-primary/10 rounded-xl h-8 md:h-10">
              مشاهده همه
              <ArrowLeft className="mr-1 md:mr-2 h-3 w-3 md:h-4 md:w-4"/>
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px] rounded-3xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-xl font-black">
                <History className="h-5 w-5 text-primary"/>
                همه فعالیت‌ها
              </DialogTitle>
            </DialogHeader>
            <ScrollArea className="h-[400px] pr-4">
              <div className="space-y-4 py-4">
                {activities.map((activity) => (
                  <ActivityCard 
                    key={activity.id}
                    title={activity.title} 
                    time={activity.time} 
                    type={activity.type} 
                    icon={
                      activity.icon === 'file' ? <FileText className="h-4 w-4 md:h-5 md:w-5"/> :
                      activity.icon === 'video' ? <Video className="h-4 w-4 md:h-5 md:w-5"/> :
                      activity.icon === 'book' ? <BookOpen className="h-4 w-4 md:h-5 md:w-5"/> :
                      <FileText className="h-4 w-4 md:h-5 md:w-5"/>
                    } 
                  />
                ))}
              </div>
            </ScrollArea>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent className="p-4 md:p-6 space-y-3 md:space-y-4">
        {activities.map((activity) => (
          <ActivityCard 
            key={activity.id}
            title={activity.title} 
            time={activity.time} 
            type={activity.type} 
            icon={
              activity.icon === 'file' ? <FileText className="h-4 w-4 md:h-5 md:w-5"/> :
              activity.icon === 'video' ? <Video className="h-4 w-4 md:h-5 md:w-5"/> :
              activity.icon === 'book' ? <BookOpen className="h-4 w-4 md:h-5 md:w-5"/> :
              <FileText className="h-4 w-4 md:h-5 md:w-5"/>
            } 
          />
        ))}
      </CardContent>
    </Card>
  );
}
