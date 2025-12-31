import { useEffect, useState } from 'react';
import { AdminService } from '@/services/admin-service';

type BackupItem = {
  id: string;
  createdAt: string;
  size: string;
  type: 'full' | 'incremental';
  status: string;
};

export function useAdminBackups(service = AdminService) {
  const [items, setItems] = useState<BackupItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      setIsLoading(true);
      const res = await service.getBackups();
      setItems(res);
    } catch (e) {
      console.error(e);
      setError('خطا در دریافت لیست بک‌آپ‌ها');
    } finally {
      setIsLoading(false);
    }
  };

  const trigger = async (type: 'full' | 'incremental') => {
    try {
      setIsLoading(true);
      await service.triggerBackup(type);
      await load();
    } catch (e) {
      console.error(e);
      setError('خطا در ایجاد بک‌آپ جدید');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return { items, isLoading, error, reload: load, trigger };
}
