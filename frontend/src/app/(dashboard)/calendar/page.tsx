'use client';

import { useState } from 'react';
import {
  CalendarHeader,
  CalendarGrid,
  CalendarSidebar,
  CalendarMobileEvents,
  CalendarEventModal,
} from '@/components/dashboard/calendar';
import { generateMonthDays, type CalendarEvent } from '@/constants/mock';

export default function CalendarPage() {
  // State for current month/year
  const [currentMonth, setCurrentMonth] = useState(10); // دی
  const [currentYear, setCurrentYear] = useState(1404);
  
  // State for selected day and events
  const [selectedDay, setSelectedDay] = useState<number | undefined>();
  const [selectedEvents, setSelectedEvents] = useState<CalendarEvent[]>([]);
  const [showMobileEvents, setShowMobileEvents] = useState(false);
  
  // State for event modal
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Generate calendar days
  const calendarDays = generateMonthDays(currentYear, currentMonth);

  // Navigation handlers
  const handlePrevMonth = () => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear(currentYear - 1);
    } else {
      setCurrentMonth(currentMonth - 1);
    }
  };

  const handleNextMonth = () => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear(currentYear + 1);
    } else {
      setCurrentMonth(currentMonth + 1);
    }
  };

  const handleToday = () => {
    setCurrentMonth(10); // دی
    setCurrentYear(1404);
  };

  // Day click handler
  const handleDayClick = (day: number, events: CalendarEvent[]) => {
    setSelectedDay(day);
    setSelectedEvents(events);
    setShowMobileEvents(true);
  };

  // Event click handler
  const handleEventClick = (event: CalendarEvent) => {
    setSelectedEvent(event);
    setIsModalOpen(true);
  };

  // Back from mobile events
  const handleBackFromEvents = () => {
    setSelectedDay(undefined);
    setSelectedEvents([]);
    setShowMobileEvents(false);
  };

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
            {/* Mobile: Show calendar or events based on state */}
            <div className={showMobileEvents ? 'hidden lg:block' : 'block'}>
              <CalendarGrid
                days={calendarDays}
                onDayClick={handleDayClick}
                onEventClick={handleEventClick}
              />
              
              {/* Mobile Events Section - Below Calendar */}
              <div className="mt-6">
                <CalendarMobileEvents
                  selectedDay={selectedDay}
                  selectedEvents={selectedEvents}
                  onEventClick={handleEventClick}
                  onBack={handleBackFromEvents}
                />
              </div>
            </div>

            {/* Mobile Events Full View */}
            {showMobileEvents && (
              <div className="lg:hidden">
                <CalendarMobileEvents
                  selectedDay={selectedDay}
                  selectedEvents={selectedEvents}
                  onEventClick={handleEventClick}
                  onBack={handleBackFromEvents}
                />
              </div>
            )}
          </div>

          {/* Desktop Sidebar */}
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
