'use client';

import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Sheet, SheetContent, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { toast } from 'sonner';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import { TicketPageHeader } from '@/components/dashboard/tickets';
import { TicketList, TicketDetail, NewTicketDialog } from '@/components/shared/tickets';
import { Ticket, TicketMessage } from '@/types';
import { useTickets } from '@/hooks/use-tickets';
import { DashboardService } from '@/services/dashboard-service';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';

export default function TicketsPage() {
  const { tickets, setTickets, isLoading, error, reload } = useTickets(false);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [isNewTicketOpen, setIsNewTicketOpen] = useState(false);

  /** Extract numeric PK from 'TKT-003' format. */
  const extractPk = (ticketId: string): number =>
    parseInt(ticketId.replace(/^TKT-0*/i, ''), 10);

  const handleNewTicket = async (data: { subject: string; department: string; message: string }) => {
    try {
      const result = await DashboardService.createTicket({
        subject: data.subject,
        department: data.department,
        content: data.message,
      });

      // Reload to get the full ticket with messages from server
      await reload();
      setIsNewTicketOpen(false);
      toast.success('تیکت با موفقیت ارسال شد');
    } catch {
      toast.error('خطا در ارسال تیکت');
    }
  };

  const handleReply = async (ticketId: string, message: string) => {
    try {
      const pk = extractPk(ticketId);
      const result = await DashboardService.replyToTicket(pk, message);

      const newMessage: TicketMessage = {
        id: result?.id ?? `m-${Date.now()}`,
        content: message,
        isAdmin: false,
        createdAt: result?.createdAt ?? new Date().toISOString(),
      };

      setTickets((prev) =>
        prev.map((t) =>
          t.id === ticketId
            ? {
                ...t,
                messages: [...t.messages, newMessage],
                updatedAt: new Date().toISOString(),
                status: 'pending',
              }
            : t
        )
      );

      if (selectedTicket?.id === ticketId) {
        setSelectedTicket((prev) =>
          prev ? { ...prev, messages: [...prev.messages, newMessage] } : null
        );
      }

      toast.success('پاسخ شما ارسال شد');
    } catch {
      toast.error('خطا در ارسال پاسخ');
    }
  };

  const handleTicketClick = (ticketId: string) => {
    const ticket = tickets.find((t) => t.id === ticketId);
    if (ticket) {
      setSelectedTicket(ticket);
    }
  };

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-0 py-10">
        <ErrorState title="خطا در دریافت تیکت‌ها" description={error} onRetry={reload} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-0">
      <TicketPageHeader onNewTicket={() => setIsNewTicketOpen(true)} />

      <Card className="rounded-2xl">
        <CardContent className="p-3 sm:p-4">
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-16 w-full rounded-xl" />
              <Skeleton className="h-16 w-full rounded-xl" />
              <Skeleton className="h-16 w-full rounded-xl" />
            </div>
          ) : (
            <TicketList
              tickets={tickets}
              onTicketClick={handleTicketClick}
              emptyMessage="هنوز تیکتی ارسال نکرده‌اید"
            />
          )}
        </CardContent>
      </Card>

      {/* New Ticket Dialog */}
      <NewTicketDialog
        open={isNewTicketOpen}
        onOpenChange={setIsNewTicketOpen}
        onSubmit={handleNewTicket}
      />

      {/* Ticket Detail Sheet */}
      <Sheet open={!!selectedTicket} onOpenChange={() => setSelectedTicket(null)}>
        <SheetContent side="left" className="w-full sm:max-w-lg p-0">
          <SheetTitle className="sr-only">جزئیات تیکت</SheetTitle>
          <SheetDescription className="sr-only">مشاهده پیام‌ها و پاسخ به تیکت</SheetDescription>
          {selectedTicket && (
            <TicketDetail
              ticket={selectedTicket}
              onClose={() => setSelectedTicket(null)}
              onReply={handleReply}
            />
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
