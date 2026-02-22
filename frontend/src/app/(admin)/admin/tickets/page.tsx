'use client';

import { useState, useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Sheet, SheetContent, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { toast } from 'sonner';
import {
  AdminTicketHeader,
  AdminTicketList,
  AdminTicketDetail,
} from '@/components/admin/tickets';
import { Ticket, TicketMessage, TicketStatus, TicketPriority } from '@/types';
import { useTickets } from '@/hooks/use-tickets';
import { AdminService } from '@/services/admin-service';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';

export default function AdminTicketsPage() {
  const { tickets, setTickets, isLoading, error, reload } = useTickets(true);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const openCount = useMemo(
    () => tickets.filter((t) => t.status === 'open' || t.status === 'pending').length,
    [tickets]
  );

  const filteredTickets = useMemo(() => {
    return tickets.filter((ticket) => {
      const matchesSearch =
        ticket.subject.includes(searchTerm) ||
        ticket.id.includes(searchTerm) ||
        ticket.userName?.includes(searchTerm) ||
        ticket.userEmail?.includes(searchTerm);

      const matchesStatus = statusFilter === 'all' || ticket.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [tickets, searchTerm, statusFilter]);

  const handleTicketClick = (ticketId: string) => {
    const ticket = tickets.find((t) => t.id === ticketId);
    if (ticket) {
      setSelectedTicket(ticket);
    }
  };

  /** Extract numeric PK from 'TKT-003' format. */
  const extractPk = (ticketId: string): number =>
    parseInt(ticketId.replace(/^TKT-0*/i, ''), 10);

  const handleReply = async (ticketId: string, message: string) => {
    try {
      const pk = extractPk(ticketId);
      const result = await AdminService.replyToTicket(pk, message);

      const newMessage: TicketMessage = {
        id: result?.id ?? `m-${Date.now()}`,
        content: message,
        isAdmin: true,
        createdAt: result?.createdAt ?? new Date().toISOString(),
      };

      setTickets((prev) =>
        prev.map((t) =>
          t.id === ticketId
            ? {
                ...t,
                messages: [...t.messages, newMessage],
                updatedAt: new Date().toISOString(),
                status: 'answered' as TicketStatus,
              }
            : t
        )
      );

      if (selectedTicket?.id === ticketId) {
        setSelectedTicket((prev) =>
          prev
            ? { ...prev, messages: [...prev.messages, newMessage], status: 'answered' }
            : null
        );
      }

      toast.success('پاسخ ارسال شد');
    } catch {
      toast.error('خطا در ارسال پاسخ');
    }
  };

  const handleStatusChange = async (ticketId: string, newStatus: TicketStatus) => {
    try {
      const pk = extractPk(ticketId);
      await AdminService.updateTicket(pk, { status: newStatus });

      setTickets((prev) =>
        prev.map((t) =>
          t.id === ticketId ? { ...t, status: newStatus, updatedAt: new Date().toISOString() } : t
        )
      );

      if (selectedTicket?.id === ticketId) {
        setSelectedTicket((prev) => (prev ? { ...prev, status: newStatus } : null));
      }

      toast.success('وضعیت تیکت تغییر کرد');
    } catch {
      toast.error('خطا در تغییر وضعیت');
    }
  };

  const handlePriorityChange = async (ticketId: string, newPriority: TicketPriority) => {
    try {
      const pk = extractPk(ticketId);
      await AdminService.updateTicket(pk, { priority: newPriority });

      setTickets((prev) =>
        prev.map((t) =>
          t.id === ticketId ? { ...t, priority: newPriority, updatedAt: new Date().toISOString() } : t
        )
      );

      if (selectedTicket?.id === ticketId) {
        setSelectedTicket((prev) => (prev ? { ...prev, priority: newPriority } : null));
      }

      toast.success('اولویت تیکت تغییر کرد');
    } catch {
      toast.error('خطا در تغییر اولویت');
    }
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="خطا در دریافت تیکت‌ها" description={error} onRetry={reload} />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-0">
      <AdminTicketHeader
        totalCount={tickets.length}
        openCount={openCount}
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
      />

      <Card className="rounded-2xl">
        <CardContent className="p-3 sm:p-4">
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-16 w-full rounded-xl" />
              <Skeleton className="h-16 w-full rounded-xl" />
              <Skeleton className="h-16 w-full rounded-xl" />
            </div>
          ) : (
            <AdminTicketList tickets={filteredTickets} onTicketClick={handleTicketClick} />
          )}
        </CardContent>
      </Card>

      <Sheet open={!!selectedTicket} onOpenChange={() => setSelectedTicket(null)}>
        <SheetContent side="left" className="w-full sm:max-w-xl p-0">
          <SheetTitle className="sr-only">مدیریت تیکت</SheetTitle>
          <SheetDescription className="sr-only">بررسی و پاسخ به تیکت کاربر</SheetDescription>
          {selectedTicket && (
            <AdminTicketDetail
              ticket={selectedTicket}
              onClose={() => setSelectedTicket(null)}
              onReply={handleReply}
              onStatusChange={handleStatusChange}
              onPriorityChange={handlePriorityChange}
            />
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

