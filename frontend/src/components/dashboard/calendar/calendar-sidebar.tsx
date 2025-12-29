'use client';

import { CalendarDays } from 'lucide-react';
import { CalendarEventCard } from './calendar-event-card';
import { getUpcomingEvents } from '@/constants/mock';
import type { CalendarEvent } from '@/types';

interface CalendarSidebarProps {
  onEventClick: (event: CalendarEvent) => void;
}

export function CalendarSidebar({ onEventClick }: CalendarSidebarProps) {
  const upcomingEvents = getUpcomingEvents(5);

  return (
    <aside className="hidden lg:block w-80 xl:w-96 shrink-0">
      <div className="bg-card rounded-3xl border border-border/50 p-5 sticky top-24">
        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-primary/10 rounded-xl">
            <CalendarDays className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="font-bold text-lg">رویدادهای پیش رو</h3>
            <p className="text-xs text-muted-foreground">{upcomingEvents.length} رویداد</p>
          </div>
        </div>

        {/* Events List */}
        <div className="space-y-3">
          {upcomingEvents.length > 0 ? (
            upcomingEvents.map((event) => (
              <CalendarEventCard
                key={event.id}
                event={event}
                compact
                onClick={() => onEventClick(event)}
              />
            ))
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <CalendarDays className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm">رویدادی وجود ندارد</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
