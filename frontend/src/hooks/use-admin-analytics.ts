import { useState, useEffect } from 'react';
import { AdminService } from '@/services/admin-service';

export function useAdminAnalytics() {
  const [stats, setStats] = useState<any[]>([]);
  const [chartData, setChartData] = useState<any[]>([]);
  const [distributionData, setDistributionData] = useState<any[]>([]);
  const [activities, setActivities] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const [statsData, chartDataRes, distributionDataRes, activitiesData] = await Promise.all([
          AdminService.getAnalyticsStats(),
          AdminService.getChartData(),
          AdminService.getDistributionData(),
          AdminService.getRecentActivities()
        ]);

        setStats(statsData);
        setChartData(chartDataRes);
        setDistributionData(distributionDataRes);
        setActivities(activitiesData);
      } catch (err) {
        setError('خطا در دریافت اطلاعات تحلیلی');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  return {
    stats,
    chartData,
    distributionData,
    activities,
    isLoading,
    error
  };
}
