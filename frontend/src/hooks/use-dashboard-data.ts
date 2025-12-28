import { useState, useEffect } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { DashboardStats, DashboardActivity, DashboardEvent } from '@/constants/mock/dashboard-data';
import { UserProfile } from '@/constants/mock/user-data';

export function useDashboardData() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activities, setActivities] = useState<DashboardActivity[]>([]);
  const [events, setEvents] = useState<DashboardEvent[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const [statsData, activitiesData, eventsData, profileData] = await Promise.all([
          DashboardService.getStats(),
          DashboardService.getActivities(),
          DashboardService.getUpcomingEvents(),
          DashboardService.getStudentProfile()
        ]);

        setStats(statsData);
        setActivities(activitiesData);
        setEvents(eventsData);
        setProfile(profileData);
      } catch (err) {
        setError('خطا در دریافت اطلاعات داشبورد');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  return {
    stats,
    activities,
    events,
    profile,
    isLoading,
    error
  };
}
