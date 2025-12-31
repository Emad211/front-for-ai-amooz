import { useEffect, useState } from 'react';
import { TeacherService } from '@/services/teacher-service';
import { AdminAnalyticsStat } from '@/types';

export function useTeacherDashboard() {
  const [stats, setStats] = useState<AdminAnalyticsStat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await TeacherService.getAnalyticsStats();
        if (!cancelled) setStats(res);
      } catch (e) {
        console.error(e);
        if (!cancelled) setError('خطا در دریافت داده‌های داشبورد معلم');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { stats, isLoading, error };
}
