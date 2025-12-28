import { useState, useEffect } from 'react';
import { AdminService } from '@/services/admin-service';
import { 
  AdminAnalyticsStat, 
  AdminChartData, 
  AdminDistributionData, 
  AdminRecentActivity 
} from '@/types';

export function useAdminAnalytics() {
  const [stats, setStats] = useState<AdminAnalyticsStat[]>([]);
  const [chartData, setChartData] = useState<AdminChartData[]>([]);
  const [distributionData, setDistributionData] = useState<AdminDistributionData[]>([]);
  const [activities, setActivities] = useState<AdminRecentActivity[]>([]);
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
