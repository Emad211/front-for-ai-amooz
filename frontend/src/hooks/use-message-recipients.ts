'use client';

import { useCallback, useEffect, useState } from 'react';
import { AdminService } from '@/services/admin-service';
import { MessageRecipient } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

export function useMessageRecipients() {
  const mountedRef = useMountedRef();
  const [recipients, setRecipients] = useState<MessageRecipient[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await AdminService.getMessageRecipients();
      if (mountedRef.current) setRecipients(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت لیست مخاطبین');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef]);

  useEffect(() => {
    reload();
  }, [reload]);

  return {
    recipients,
    isLoading,
    error,
    reload
  };
}
