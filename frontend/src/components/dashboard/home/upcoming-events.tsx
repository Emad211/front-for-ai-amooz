'use client';

import { Calendar, Clock, FileText } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EventCard } from '@/components/dashboard/ui/event-card';
import Link from 'next/link';
import { DashboardEvent } from '@/types';

interface UpcomingEventsProps {
  events: DashboardEvent[];
}

export function UpcomingEvents({ events }: UpcomingEventsProps) {
  return (
    <Card className="bg-card border-border/50 rounded-2xl md:rounded-3xl overflow-hidden">
      <CardHeader className="border-b border-border/50 bg-muted/20 px-4 md:px-6 py-3 md:py-4">
        <CardTitle className="flex items-center gap-2 md:gap-3 text-lg md:text-xl font-black">
          <div className="p-1.5 md:p-2 bg-primary/10 rounded-lg">
            <Calendar className="h-4 w-4 md:h-5 md:w-5 text-primary"/>
          </div>
          رویدادهای پیش رو
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 md:p-6 space-y-3 md:space-y-4">
        {events.map((event) => (
          <EventCard 
            key={event.id}
            title={event.title} 
            status={event.status} 
            date={event.date} 
            month={event.month} 
            icon={event.icon === 'clock' ? <Clock className="h-3 w-3 md:h-4 md:w-4"/> : <FileText className="h-3 w-3 md:h-4 md:w-4"/>}
          />
        ))}
        <Button variant="outline" className="w-full h-10 md:h-12 border-primary/30 text-primary text-xs md:text-sm font-bold hover:bg-primary/10 hover:border-primary rounded-xl md:rounded-2xl mt-2 transition-all" asChild>
          <Link href="/calendar">مشاهده تقویم کامل</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
