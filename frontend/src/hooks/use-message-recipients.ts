'use client';

import { useState, useEffect } from 'react';
import { AdminService } from '@/services/admin-service';

export interface Recipient {
  id: string;
  name: string;
  role: string;
  avatar?: string;
}

export function useMessageRecipients() {
  const [recipients, setRecipients] = useState<Recipient[]>([]);
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
