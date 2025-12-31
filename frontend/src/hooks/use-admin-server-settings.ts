import { useEffect, useState } from 'react';
import { AdminService } from '@/services/admin-service';

export function useAdminServerSettings(service = AdminService) {
  const [settings, setSettings] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      setIsLoading(true);
      const res = await service.getServerSettings();
      setSettings(res);
    } catch (e) {
      console.error(e);
      setError('خطا در دریافت تنظیمات سرور');
    } finally {
      setIsLoading(false);
    }
  };

  const update = async (data: any) => {
    try {
      setError(null);
      setIsLoading(true);
      const res = await service.updateServerSettings(data);
      setSettings(res.data);
    } catch (e) {
      console.error(e);
      setError('خطا در بروزرسانی تنظیمات');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return { settings, isLoading, error, reload: load, update };
}
