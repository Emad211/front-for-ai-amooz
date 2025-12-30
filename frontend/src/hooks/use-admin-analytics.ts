"use client";

import { useCallback, useEffect, useState } from 'react';
import { AdminService } from '@/services/admin-service';
import { 
  AdminAnalyticsStat, 
  AdminChartData, 
  AdminDistributionData, 
  AdminRecentActivity 
} from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

export function useAdminAnalytics() {
  const mountedRef = useMountedRef();
  const [stats, setStats] = useState<AdminAnalyticsStat[]>([]);
  const [chartData, setChartData] = useState<AdminChartData[]>([]);
  const [distributionData, setDistributionData] = useState<AdminDistributionData[]>([]);
  const [activities, setActivities] = useState<AdminRecentActivity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const [statsData, chartDataRes, distributionDataRes, activitiesData] = await Promise.all([
        AdminService.getAnalyticsStats(),
        AdminService.getChartData(),
        AdminService.getDistributionData(),
        AdminService.getRecentActivities(),
      ]);

      if (!mountedRef.current) return;
      setStats(statsData);
      setChartData(chartDataRes);
      setDistributionData(distributionDataRes);
      setActivities(activitiesData);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اطلاعات تحلیلی');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef]);

  useEffect(() => {
    reload();
  }, [reload]);

  return {
    stats,
    chartData,
    distributionData,
    activities,
    isLoading,
    error,
    reload
  };
}
