'use client';

import { ChevronRight, ChevronLeft, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { PERSIAN_MONTHS } from '@/constants/mock';

interface CalendarHeaderProps {
  currentMonth: number;
  currentYear: number;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onToday: () => void;
}

export function CalendarHeader({
  currentMonth,
  currentYear,
  onPrevMonth,
  onNextMonth,
  onToday,
}: CalendarHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
      {/* Title */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 bg-primary/10 rounded-xl">
          <Calendar className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">تقویم آموزشی</h1>
          <p className="text-sm text-muted-foreground mt-0.5">برنامه‌ریزی و مدیریت رویدادها</p>
        </div>
      </div>

      {/* Navigation Controls */}
      <div className="flex items-center gap-2 w-full sm:w-auto">
        <Button
          variant="outline"
          size="sm"
          onClick={onToday}
          className="rounded-xl h-10 px-4 font-medium"
        >
          امروز
        </Button>
        
        <div className="flex items-center gap-1 bg-muted/50 rounded-xl p-1 flex-1 sm:flex-none">
          <Button
            variant="ghost"
            size="icon"
            onClick={onNextMonth}
            className="h-8 w-8 rounded-lg hover:bg-background"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
          
          <div className="min-w-[140px] text-center">
            <span className="font-bold text-base">
              {PERSIAN_MONTHS[currentMonth - 1]} {currentYear}
            </span>
          </div>
          
          <Button
            variant="ghost"
            size="icon"
            onClick={onPrevMonth}
            className="h-8 w-8 rounded-lg hover:bg-background"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
