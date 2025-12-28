'use client';

import { useState, useEffect } from 'react';
import { AdminService } from '@/services/admin-service';
import { MessageRecipient } from '@/types';

export function useMessageRecipients() {
  const [recipients, setRecipients] = useState<MessageRecipient[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRecipients = async () => {
      try {
        setIsLoading(true);
        const data = await AdminService.getMessageRecipients();
        setRecipients(data);
      } catch (err) {
        setError('خطا در دریافت لیست مخاطبین');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchRecipients();
  }, []);

  return {
    recipients,
    isLoading,
    error
  };
}
