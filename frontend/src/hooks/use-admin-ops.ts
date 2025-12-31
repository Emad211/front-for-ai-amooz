import { useCallback, useEffect, useState } from 'react';
import { AdminService } from '@/services/admin-service';

export function useAdminOps(service = AdminService) {
  const [health, setHealth] = useState<any>(null);
  const [maintenance, setMaintenance] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const [healthRes, maintRes] = await Promise.all([
        service.getServerHealth(),
        service.getMaintenanceTasks(),
      ]);
      setHealth(healthRes);
      setMaintenance(maintRes);
    } catch (e) {
      console.error(e);
      setError('خطا در دریافت وضعیت سرور');
    } finally {
      setIsLoading(false);
    }
  }, [service]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { health, maintenance, isLoading, error, reload };
}
