'use client';

import { useState, useMemo, useEffect } from 'react';
import { CalendarEvent, CalendarDay } from '@/types';
import { generateMonthDays, getUpcomingEvents } from '@/lib/calendar';
import { DashboardService } from '@/services/dashboard-service';

type CalendarService = {
  getCalendarEvents: () => Promise<CalendarEvent[]>;
};

export function useCalendar(service: CalendarService = DashboardService) {
  // State for current month/year (Jalali)
  const [currentMonth, setCurrentMonth] = useState(10); // دی
  const [currentYear, setCurrentYear] = useState(1404);
  
  // State for selected day and events
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<number | undefined>();
  const [selectedEvents, setSelectedEvents] = useState<CalendarEvent[]>([]);
  const [showMobileEvents, setShowMobileEvents] = useState(false);

  const upcomingEvents = useMemo(() => getUpcomingEvents(events, 10), [events]);
  
  // State for event modal
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchEvents = async () => {
      try {
        setIsLoading(true);
        const data = await service.getCalendarEvents();
        if (!cancelled) setEvents(data);
      } catch (error) {
        console.error('Error fetching calendar events:', error);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    fetchEvents();

    return () => {
      cancelled = true;
    };
  }, [service]);

  // Generate calendar days
  const calendarDays = useMemo(() => 
    generateMonthDays(currentYear, currentMonth, events), 
    [currentYear, currentMonth, events]
  );

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
    // In a real app, this would get the current Jalali date
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

  return {
    currentMonth,
    currentYear,
    calendarDays,
    upcomingEvents,
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
  };
}
