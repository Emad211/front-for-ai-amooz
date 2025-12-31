'use client';

import { Badge } from '@/components/ui/badge';
import { CheckCircle, XCircle } from 'lucide-react';

const statusConfig: Record<string, { label: string; color: string; icon: any }> = {
  active: { label: 'فعال', color: 'bg-green-500/10 text-green-700 dark:text-green-400', icon: CheckCircle },
  inactive: { label: 'غیرفعال', color: 'bg-gray-500/10 text-gray-700 dark:text-gray-400', icon: XCircle },
};

export function StudentStatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || statusConfig.active;
  return (
    <Badge className={config.color}>
      {config.label}
    </Badge>
  );
}
