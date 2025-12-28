'use client';

import { cn } from '@/lib/utils';
import type { TicketStatus, TicketPriority } from '@/constants/tickets-data';

interface TicketStatusBadgeProps {
  status: TicketStatus;
}

const statusConfig: Record<TicketStatus, { label: string; className: string }> = {
  open: { label: 'باز', className: 'bg-blue-500/10 text-blue-500' },
  pending: { label: 'در انتظار پاسخ', className: 'bg-amber-500/10 text-amber-500' },
  answered: { label: 'پاسخ داده شده', className: 'bg-green-500/10 text-green-500' },
  closed: { label: 'بسته شده', className: 'bg-muted text-muted-foreground' },
};

export function TicketStatusBadge({ status }: TicketStatusBadgeProps) {
  const config = statusConfig[status];
  return (
    <span className={cn('px-2.5 py-1 rounded-full text-xs font-medium', config.className)}>
      {config.label}
    </span>
  );
}

interface TicketPriorityBadgeProps {
  priority: TicketPriority;
}

const priorityConfig: Record<TicketPriority, { label: string; className: string }> = {
  low: { label: 'کم', className: 'bg-slate-500/10 text-slate-500' },
  medium: { label: 'متوسط', className: 'bg-amber-500/10 text-amber-500' },
  high: { label: 'بالا', className: 'bg-red-500/10 text-red-500' },
};

export function TicketPriorityBadge({ priority }: TicketPriorityBadgeProps) {
  const config = priorityConfig[priority];
  return (
    <span className={cn('px-2.5 py-1 rounded-full text-xs font-medium', config.className)}>
      {config.label}
    </span>
  );
}
