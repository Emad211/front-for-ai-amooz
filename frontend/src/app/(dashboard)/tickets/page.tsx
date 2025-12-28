'use client';

import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Sheet, SheetContent, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { toast } from 'sonner';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import { TicketPageHeader } from '@/components/dashboard/tickets';
import { TicketList, TicketDetail, NewTicketDialog } from '@/components/shared/tickets';
import { MOCK_TICKETS, type Ticket, type TicketMessage } from '@/constants/tickets-data';

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>(
    MOCK_TICKETS.filter((t) => t.userId === 'user-1') // فیلتر تیکت‌های کاربر فعلی
  );
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [isNewTicketOpen, setIsNewTicketOpen] = useState(false);

  const handleNewTicket = (data: { subject: string; department: string; message: string }) => {
    const newTicket: Ticket = {
      id: `TKT-${String(Date.now()).slice(-3)}`,
      subject: data.subject,
      status: 'open',
      priority: 'medium',
      department: data.department,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      userId: 'user-1',
      messages: [
        {
          id: `m-${Date.now()}`,
          content: data.message,
          isAdmin: false,
          createdAt: new Date().toISOString(),
        },
      ],
    };

    setTickets((prev) => [newTicket, ...prev]);
    toast.success('تیکت با موفقیت ارسال شد');
  };

  const handleReply = (ticketId: string, message: string) => {
    const newMessage: TicketMessage = {
      id: `m-${Date.now()}`,
      content: message,
      isAdmin: false,
      createdAt: new Date().toISOString(),
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
  };

  const handleTicketClick = (ticketId: string) => {
    const ticket = tickets.find((t) => t.id === ticketId);
    if (ticket) {
      setSelectedTicket(ticket);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <TicketPageHeader onNewTicket={() => setIsNewTicketOpen(true)} />

      <Card className="rounded-2xl">
        <CardContent className="p-4">
          <TicketList
            tickets={tickets}
            onTicketClick={handleTicketClick}
            emptyMessage="هنوز تیکتی ارسال نکرده‌اید"
          />
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
