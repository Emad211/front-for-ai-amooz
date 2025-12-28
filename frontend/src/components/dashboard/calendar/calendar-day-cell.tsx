'use client';

import { cn } from '@/lib/utils';
import type { CalendarDay, CalendarEvent } from '@/constants/mock';
import { CalendarEventBadge } from './calendar-event-badge';

interface CalendarDayCellProps {
  dayData: CalendarDay;
  onDayClick: (day: number, events: CalendarEvent[]) => void;
  onEventClick: (event: CalendarEvent) => void;
}

export function CalendarDayCell({ dayData, onDayClick, onEventClick }: CalendarDayCellProps) {
  const { day, isCurrentMonth, isToday, isWeekend, events } = dayData;

  return (
    <div
      onClick={() => isCurrentMonth && onDayClick(day, events)}
      className={cn(
        'min-h-[80px] sm:min-h-[100px] p-1.5 sm:p-2 border-b border-e border-border/50 transition-colors',
        isCurrentMonth ? 'bg-card hover:bg-muted/30 cursor-pointer' : 'bg-muted/20',
        isToday && 'bg-primary/5 ring-2 ring-primary/20 ring-inset',
      )}
    >
      {/* Day Number */}
      <div className="flex items-center justify-between mb-1">
        <span
          className={cn(
            'w-7 h-7 sm:w-8 sm:h-8 flex items-center justify-center rounded-full text-sm font-medium',
            !isCurrentMonth && 'text-muted-foreground/40',
            isCurrentMonth && isWeekend && 'text-red-500',
            isToday && 'bg-primary text-primary-foreground font-bold'
          )}
        >
          {day}
        </span>
        
        {/* Event count badge for mobile */}
        {events.length > 0 && (
          <span className="sm:hidden w-5 h-5 flex items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold">
            {events.length}
          </span>
        )}
      </div>

      {/* Events - Desktop */}
      <div className="hidden sm:flex flex-col gap-1">
        {events.slice(0, 2).map((event) => (
          <CalendarEventBadge
            key={event.id}
            event={event}
            onClick={() => onEventClick(event)}
          />
        ))}
        {events.length > 2 && (
          <span className="text-[10px] text-muted-foreground">
            +{events.length - 2} مورد دیگر
          </span>
        )}
      </div>

      {/* Events Dots - Mobile */}
      <div className="flex sm:hidden items-center gap-0.5 flex-wrap">
        {events.slice(0, 4).map((event) => (
          <CalendarEventBadge
            key={event.id}
            event={event}
            compact
            onClick={() => onEventClick(event)}
          />
        ))}
      </div>
    </div>
  );
}
