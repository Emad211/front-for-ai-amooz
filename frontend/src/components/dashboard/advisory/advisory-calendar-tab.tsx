'use client';

/**
 * The «تقویم» tab of the student advisor page: the shared Jalali calendar
 * suite fed by the merged loader (exercise deadlines, exam-prep sessions,
 * study-plan rows, monthly-outlook entries, challenge days) — so everything
 * the advisor plans and everything the classes impose lands on one grid.
 */
import { useMemo } from 'react';

import {
  CalendarHeader,
  CalendarGrid,
  CalendarSidebar,
  CalendarMobileEvents,
  CalendarEventModal,
} from '@/components/dashboard/calendar';
import { useCalendar } from '@/hooks/use-calendar';
import {
  getAdvisorCalendarEvents,
  advisorCalendarSources,
} from '@/services/advisor-calendar-service';

const mergedCalendarService = {
  getCalendarEvents: (year: number, month: number) =>
    getAdvisorCalendarEvents(year, month, advisorCalendarSources),
};

export function AdvisoryCalendarTab() {
  const {
    currentMonth,
    currentYear,
    calendarDays,
    upcomingEvents,
    selectedDay,
    selectedEvents,
    selectedEvent,
    isModalOpen,
    setIsModalOpen,
    handlePrevMonth,
    handleNextMonth,
    handleToday,
    handleDayClick,
    handleEventClick,
    handleBackFromEvents,
  } = useCalendar(
    useMemo(() => mergedCalendarService, []),
  );

  return (
    <div className="space-y-4">
      <CalendarHeader
        currentMonth={currentMonth}
        currentYear={currentYear}
        onPrevMonth={handlePrevMonth}
        onNextMonth={handleNextMonth}
        onToday={handleToday}
      />

      <div className="flex flex-col lg:flex-row gap-4 md:gap-5 lg:gap-6">
        <div className="flex-1">
          {/* Desktop: always the grid */}
          <div className="hidden lg:block">
            <CalendarGrid
              days={calendarDays}
              onDayClick={handleDayClick}
              onEventClick={handleEventClick}
            />
          </div>

          {/* Mobile: grid + selected-day list below */}
          <div className="lg:hidden">
            <CalendarGrid
              days={calendarDays}
              onDayClick={handleDayClick}
              onEventClick={handleEventClick}
            />
            <div className="mt-6">
              <CalendarMobileEvents
                selectedDay={selectedDay}
                selectedEvents={selectedEvents ?? []}
                upcomingEvents={upcomingEvents}
                onBack={handleBackFromEvents}
                onEventClick={handleEventClick}
              />
            </div>
          </div>
        </div>

        <CalendarSidebar upcomingEvents={upcomingEvents} onEventClick={handleEventClick} />
      </div>

      <CalendarEventModal
        event={selectedEvent}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
}
