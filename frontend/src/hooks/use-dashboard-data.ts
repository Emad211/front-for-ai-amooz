"use client";

import { useCallback, useEffect, useState } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { DashboardStats, DashboardActivity, DashboardEvent, UserProfile } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

type DashboardDataService = {
  getStats: () => Promise<DashboardStats>;
  getActivities: () => Promise<DashboardActivity[]>;
  getUpcomingEvents: () => Promise<DashboardEvent[]>;
  getStudentProfile: () => Promise<UserProfile>;
};

export function useDashboardData(service: DashboardDataService = DashboardService) {
  const mountedRef = useMountedRef();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activities, setActivities] = useState<DashboardActivity[]>([]);
  const [events, setEvents] = useState<DashboardEvent[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const [statsData, activitiesData, eventsData, profileData] = await Promise.all([
        service.getStats(),
        service.getActivities(),
        service.getUpcomingEvents(),
        service.getStudentProfile()
      ]);

      if (!mountedRef.current) return;
      setStats(statsData);
      setActivities(activitiesData);
      setEvents(eventsData);
      setProfile(profileData);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اطلاعات داشبورد');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, service]);

  useEffect(() => {
    reload();
  }, [reload]);

  return {
    stats,
    activities,
    events,
    profile,
    isLoading,
    error,
    reload
  };
}
