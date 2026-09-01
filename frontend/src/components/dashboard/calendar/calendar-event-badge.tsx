'use client';

import { cn } from '@/lib/utils';
import { EVENT_TYPE_CONFIG } from '@/constants/calendar';
import { MathText } from '@/components/content/math-text';
import type { CalendarEvent } from '@/types';

interface CalendarEventBadgeProps {
  event: CalendarEvent;
  compact?: boolean;
  onClick?: () => void;
}

export function CalendarEventBadge({ event, compact = false, onClick }: CalendarEventBadgeProps) {
  const config = EVENT_TYPE_CONFIG[event.type];

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    onClick?.();
  };

  if (compact) {
    return (
      <div
        role="button"
        tabIndex={0}
        onClick={onClick}
        onKeyDown={handleKeyDown}
        className={cn(
          'w-1.5 h-1.5 rounded-full cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          config.dot,
        )}
        title={event.title}
        aria-label={event.title}
      />
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      className={cn(
        'text-[10px] sm:text-xs px-1.5 py-0.5 rounded-md truncate cursor-pointer transition-all hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        config.bgColor,
        config.color,
      )}
    >
      <MathText text={event.title} />
    </div>
  );
}
