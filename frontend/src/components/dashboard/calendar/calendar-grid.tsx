'use client';

import { PERSIAN_WEEKDAYS_SHORT } from '@/constants/calendar';
import type { CalendarDay, CalendarEvent } from '@/types';
import { CalendarDayCell } from './calendar-day-cell';
import { cn } from '@/lib/utils';

interface CalendarGridProps {
  days: CalendarDay[];
  onDayClick: (day: number, events: CalendarEvent[]) => void;
  onEventClick: (event: CalendarEvent) => void;
}

export function CalendarGrid({ days, onDayClick, onEventClick }: CalendarGridProps) {
  return (
    <div className="bg-card rounded-2xl sm:rounded-3xl border border-border/50 overflow-hidden shadow-sm">
      {/* Weekday Headers */}
      <div className="grid grid-cols-7 bg-muted/50 border-b border-border/50">
        {PERSIAN_WEEKDAYS_SHORT.map((weekday, index) => (
          <div
            key={weekday}
            className={cn(
              'py-3 sm:py-4 text-center text-xs sm:text-sm font-bold',
              index === 6 ? 'text-red-500' : 'text-muted-foreground'
            )}
          >
            {weekday}
          </div>
        ))}
      </div>

      {/* Calendar Days Grid */}
      <div className="grid grid-cols-7">
        {days.map((dayData, index) => (
          <CalendarDayCell
            key={index}
            dayData={dayData}
            onDayClick={onDayClick}
            onEventClick={onEventClick}
          />
        ))}
      </div>
    </div>
  );
}
