import { useEffect, useState } from 'react';
import { AdminService } from '@/services/admin-service';

type BackupItem = {
  id: string;
  createdAt: string;
  size: string;
  type: 'full' | 'incremental';
  status: string;
};

type BackupInfo = {
  dbSize: string;
  tableCount: number;
  note: string;
};

export function useAdminBackups(service = AdminService) {
  const [items, setItems] = useState<BackupItem[]>([]);
  const [info, setInfo] = useState<BackupInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      setIsLoading(true);
      const res = await service.getBackups();
      if (res && typeof res === 'object' && 'backups' in res) {
        setItems((res.backups ?? []) as BackupItem[]);
        setInfo({
          dbSize: res.db_size ?? '?',
          tableCount: res.table_count ?? 0,
          note: res.note ?? '',
        });
      } else {
        setItems(res as unknown as BackupItem[]);
      }
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

  return { items, info, isLoading, error, reload: load, trigger };
}
