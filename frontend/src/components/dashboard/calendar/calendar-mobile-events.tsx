'use client';

import { CalendarDays, ChevronLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CalendarEventCard } from './calendar-event-card';
import { getUpcomingEvents } from '@/constants/mock';
import type { CalendarEvent } from '@/types';

interface CalendarMobileEventsProps {
  selectedDay?: number;
  selectedEvents?: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
  onBack: () => void;
}

export function CalendarMobileEvents({
  selectedDay,
  selectedEvents,
  onEventClick,
  onBack,
}: CalendarMobileEventsProps) {
  const upcomingEvents = getUpcomingEvents(10);
  const safeSelectedEvents = selectedEvents ?? [];
  const eventsToShow = selectedDay ? safeSelectedEvents : upcomingEvents;
  const title = selectedDay ? `رویدادهای ${selectedDay}ام` : 'رویدادهای پیش رو';

  return (
    <div className="lg:hidden">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        {selectedDay && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onBack}
            className="h-9 w-9 rounded-xl"
          >
            <ChevronLeft className="w-5 h-5" />
          </Button>
        )}
        <div className="flex items-center gap-2">
          <CalendarDays className="w-5 h-5 text-primary" />
          <h3 className="font-bold text-lg">{title}</h3>
        </div>
        <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded-lg">
          {eventsToShow.length} رویداد
        </span>
      </div>

      {/* Events List */}
      <div className="space-y-3">
        {eventsToShow.length > 0 ? (
          eventsToShow.map((event) => (
            <CalendarEventCard
              key={event.id}
              event={event}
              onClick={() => onEventClick(event)}
            />
          ))
        ) : (
          <div className="text-center py-12 text-muted-foreground bg-card rounded-2xl border border-border/50">
            <CalendarDays className="w-16 h-16 mx-auto mb-4 opacity-20" />
            <p className="font-medium">رویدادی برای این روز وجود ندارد</p>
            <p className="text-sm mt-1">روز دیگری را انتخاب کنید</p>
          </div>
        )}
      </div>
    </div>
  );
}
