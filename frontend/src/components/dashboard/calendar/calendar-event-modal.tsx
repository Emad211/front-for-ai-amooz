'use client';

import { X, Clock, MapPin, BookOpen, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { EVENT_TYPE_CONFIG, PERSIAN_MONTHS, type CalendarEvent } from '@/constants/mock';

interface CalendarEventModalProps {
  event: CalendarEvent | null;
  isOpen: boolean;
  onClose: () => void;
}

export function CalendarEventModal({ event, isOpen, onClose }: CalendarEventModalProps) {
  if (!event) return null;

  const config = EVENT_TYPE_CONFIG[event.type];
  const dateParts = event.date.split('-');
  const day = parseInt(dateParts[2]);
  const month = PERSIAN_MONTHS[parseInt(dateParts[1]) - 1];
  const year = dateParts[0];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md rounded-3xl p-0 overflow-hidden">
        {/* Header with colored background */}
        <div className={cn('p-6 pb-10', config.bgColor)}>
          <DialogHeader>
            <div className="flex items-start justify-between">
              <span className={cn('text-xs font-bold px-3 py-1 rounded-full bg-background/80', config.color)}>
                {config.label}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                className="h-8 w-8 rounded-full bg-background/50 hover:bg-background/80"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
            <DialogTitle className={cn('text-2xl font-bold mt-4 text-start', config.color)}>
              {event.title}
            </DialogTitle>
          </DialogHeader>
        </div>

        {/* Content */}
        <div className="p-6 -mt-4 bg-card rounded-t-3xl relative">
          {/* Date Badge */}
          <div className={cn(
            'absolute -top-8 start-6 w-16 h-16 rounded-2xl flex flex-col items-center justify-center',
            'bg-card border-4 border-background shadow-lg',
          )}>
            <span className={cn('text-2xl font-bold leading-none', config.color)}>{day}</span>
            <span className="text-xs text-muted-foreground mt-0.5">{month}</span>
          </div>

          {/* Details */}
          <div className="mt-10 space-y-4">
            {event.description && (
              <p className="text-muted-foreground">{event.description}</p>
            )}

            <div className="space-y-3">
              {event.time && (
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-xl">
                  <div className="p-2 bg-background rounded-lg">
                    <Clock className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">زمان</p>
                    <p className="font-medium">
                      ساعت {event.time}
                      {event.endTime && ` تا ${event.endTime}`}
                    </p>
                  </div>
                </div>
              )}

              {event.location && (
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-xl">
                  <div className="p-2 bg-background rounded-lg">
                    <MapPin className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">مکان</p>
                    <p className="font-medium">{event.location}</p>
                  </div>
                </div>
              )}

              {event.subject && (
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-xl">
                  <div className="p-2 bg-background rounded-lg">
                    <BookOpen className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">درس</p>
                    <p className="font-medium">{event.subject}</p>
                  </div>
                </div>
              )}

              {event.priority === 'high' && (
                <div className="flex items-center gap-2 p-3 bg-red-500/10 rounded-xl text-red-500">
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-sm font-medium">اولویت بالا</span>
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 mt-6">
            <Button className="flex-1 h-12 rounded-xl" onClick={onClose}>
              متوجه شدم
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
