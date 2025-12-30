'use client';

import {
  CalendarHeader,
  CalendarGrid,
  CalendarSidebar,
  CalendarMobileEvents,
  CalendarEventModal,
} from '@/components/dashboard/calendar';
import { useCalendar } from '@/hooks/use-calendar';

export default function CalendarPage() {
  const {
    currentMonth,
    currentYear,
    calendarDays,
    selectedDay,
    selectedEvents,
    showMobileEvents,
    selectedEvent,
    isModalOpen,
    setIsModalOpen,
    handlePrevMonth,
    handleNextMonth,
    handleToday,
    handleDayClick,
    handleEventClick,
    handleBackFromEvents,
  } = useCalendar();

  return (
    <main className="min-h-screen bg-background/50" dir="rtl">
      <div className="container max-w-7xl mx-auto px-4 py-6 md:py-10">
        {/* Header */}
        <CalendarHeader
          currentMonth={currentMonth}
          currentYear={currentYear}
          onPrevMonth={handlePrevMonth}
          onNextMonth={handleNextMonth}
          onToday={handleToday}
        />

        {/* Main Content */}
        <div className="flex gap-6">
          {/* Calendar Section */}
          <div className="flex-1">
            {/* Desktop: Always show calendar */}
            <div className="hidden lg:block">
              <CalendarGrid
                days={calendarDays}
                onDayClick={handleDayClick}
                onEventClick={handleEventClick}
              />
            </div>

            {/* Mobile: Toggle between calendar and events view */}
            <div className="lg:hidden">
              {showMobileEvents ? (
                <CalendarMobileEvents
                  selectedDay={selectedDay}
                  selectedEvents={selectedEvents ?? []}
                  onBack={handleBackFromEvents}
                  onEventClick={handleEventClick}
                />
              ) : (
                <>
                  <CalendarGrid
                    days={calendarDays}
                    onDayClick={handleDayClick}
                    onEventClick={handleEventClick}
                  />

                  {/* Mobile Events Section - Below Calendar */}
                  <div className="mt-6">
                    <CalendarMobileEvents
                      selectedDay={selectedDay}
                      selectedEvents={selectedEvents ?? []}
                      onBack={handleBackFromEvents}
                      onEventClick={handleEventClick}
                    />
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Sidebar - Desktop Only */}
          <CalendarSidebar onEventClick={handleEventClick} />
        </div>
      </div>

      {/* Event Detail Modal */}
      <CalendarEventModal
        event={selectedEvent}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </main>
  );
}
