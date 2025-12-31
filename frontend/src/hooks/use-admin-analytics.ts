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

type AnalyticsService = {
  getAnalyticsStats: () => Promise<AdminAnalyticsStat[]>;
  getChartData: () => Promise<AdminChartData[]>;
  getDistributionData: () => Promise<AdminDistributionData[]>;
  getRecentActivities: () => Promise<AdminRecentActivity[]>;
};

export function useAdminAnalytics(service: AnalyticsService = AdminService) {
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
        service.getAnalyticsStats(),
        service.getChartData(),
        service.getDistributionData(),
        service.getRecentActivities(),
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
