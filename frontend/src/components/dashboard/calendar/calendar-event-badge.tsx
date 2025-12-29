'use client';

import { cn } from '@/lib/utils';
import { EVENT_TYPE_CONFIG } from '@/constants/mock';
import type { CalendarEvent } from '@/types';

interface CalendarEventBadgeProps {
  event: CalendarEvent;
  compact?: boolean;
  onClick?: () => void;
}

export function CalendarEventBadge({ event, compact = false, onClick }: CalendarEventBadgeProps) {
  const config = EVENT_TYPE_CONFIG[event.type];

  if (compact) {
    return (
      <div
        onClick={onClick}
        className={cn(
          'w-1.5 h-1.5 rounded-full cursor-pointer',
          event.type === 'exam' && 'bg-red-500',
          event.type === 'assignment' && 'bg-orange-500',
          event.type === 'class' && 'bg-blue-500',
          event.type === 'holiday' && 'bg-green-500',
          event.type === 'reminder' && 'bg-purple-500'
        )}
        title={event.title}
      />
    );
  }

  return (
    <div
      onClick={onClick}
      className={cn(
        'text-[10px] sm:text-xs px-1.5 py-0.5 rounded-md truncate cursor-pointer transition-all hover:scale-105',
        config.bgColor,
        config.color
      )}
    >
      {event.title}
    </div>
  );
}
