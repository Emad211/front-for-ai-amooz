'use client';

import { Clock, MapPin, BookOpen } from 'lucide-react';
import { cn } from '@/lib/utils';
import { EVENT_TYPE_CONFIG, PERSIAN_MONTHS } from '@/constants/calendar';
import type { CalendarEvent } from '@/types';

interface CalendarEventCardProps {
  event: CalendarEvent;
  onClick?: () => void;
  compact?: boolean;
}

export function CalendarEventCard({ event, onClick, compact = false }: CalendarEventCardProps) {
  const config = EVENT_TYPE_CONFIG[event.type];

  // Extract day and month from date for display
  const dateParts = event.date.split('-');
  const day = parseInt(dateParts[2]);
  const month = PERSIAN_MONTHS[parseInt(dateParts[1]) - 1];

  if (compact) {
    return (
      <div
        onClick={onClick}
        className={cn(
          'flex items-center gap-3 p-3 rounded-xl bg-card border border-border/50 cursor-pointer',
          'hover:shadow-md hover:border-border transition-all'
        )}
      >
        {/* Date Badge */}
        <div className={cn('w-12 h-12 rounded-xl flex flex-col items-center justify-center shrink-0', config.bgColor)}>
          <span className={cn('text-lg font-bold leading-none', config.color)}>{day}</span>
          <span className={cn('text-[10px] mt-0.5', config.color)}>{month}</span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h4 className="font-bold text-sm truncate">{event.title}</h4>
          <div className="flex items-center gap-2 mt-1">
            {event.time && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="w-3 h-3" />
                {event.time}
              </span>
            )}
            {event.subject && (
              <span className={cn('text-xs px-1.5 py-0.5 rounded', config.bgColor, config.color)}>
                {event.subject}
              </span>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      onClick={onClick}
      className={cn(
        'flex gap-4 p-4 rounded-2xl bg-card border border-border/50 cursor-pointer',
        'hover:shadow-lg hover:border-border transition-all'
      )}
    >
      {/* Date Badge */}
      <div className={cn('w-16 h-16 rounded-2xl flex flex-col items-center justify-center shrink-0', config.bgColor)}>
        <span className={cn('text-2xl font-bold leading-none', config.color)}>{day}</span>
        <span className={cn('text-xs mt-1', config.color)}>{month}</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <h4 className="font-bold text-base">{event.title}</h4>
          <span className={cn('text-xs px-2 py-1 rounded-lg shrink-0', config.bgColor, config.color)}>
            {config.label}
          </span>
        </div>
        
        {event.description && (
          <p className="text-sm text-muted-foreground mt-1 line-clamp-1">{event.description}</p>
        )}

        <div className="flex items-center gap-3 mt-3 flex-wrap">
          {event.time && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded-lg">
              <Clock className="w-3.5 h-3.5" />
              ساعت {event.time}
              {event.endTime && ` - ${event.endTime}`}
            </span>
          )}
          {event.location && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded-lg">
              <MapPin className="w-3.5 h-3.5" />
              {event.location}
            </span>
          )}
          {event.subject && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded-lg">
              <BookOpen className="w-3.5 h-3.5" />
              {event.subject}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
