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
import { MOCK_TICKETS, type Ticket, type TicketMessage, type TicketStatus, type TicketPriority } from '@/constants/tickets-data';

export default function AdminTicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>(MOCK_TICKETS);
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

  const handleReply = (ticketId: string, message: string) => {
    const newMessage: TicketMessage = {
      id: `m-${Date.now()}`,
      content: message,
      isAdmin: true,
      createdAt: new Date().toISOString(),
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
  };

  const handleStatusChange = (ticketId: string, status: TicketStatus) => {
    setTickets((prev) =>
      prev.map((t) =>
        t.id === ticketId ? { ...t, status, updatedAt: new Date().toISOString() } : t
      )
    );

    if (selectedTicket?.id === ticketId) {
      setSelectedTicket((prev) => (prev ? { ...prev, status } : null));
    }

    toast.success('وضعیت تیکت تغییر کرد');
  };

  const handlePriorityChange = (ticketId: string, priority: TicketPriority) => {
    setTickets((prev) =>
      prev.map((t) =>
        t.id === ticketId ? { ...t, priority, updatedAt: new Date().toISOString() } : t
      )
    );

    if (selectedTicket?.id === ticketId) {
      setSelectedTicket((prev) => (prev ? { ...prev, priority } : null));
    }

    toast.success('اولویت تیکت تغییر کرد');
  };

  return (
    <div className="max-w-5xl mx-auto">
      <AdminTicketHeader
        totalCount={tickets.length}
        openCount={openCount}
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
      />

      <Card className="rounded-2xl">
        <CardContent className="p-4">
          <AdminTicketList tickets={filteredTickets} onTicketClick={handleTicketClick} />
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
