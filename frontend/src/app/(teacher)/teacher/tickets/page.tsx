'use client';

import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Sheet, SheetContent, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { toast } from 'sonner';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import { TicketList, TicketDetail, NewTicketDialog } from '@/components/shared/tickets';
import { Ticket, TicketMessage } from '@/types';
import { useTickets } from '@/hooks/use-tickets';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { Button } from '@/components/ui/button';
import { Plus, Ticket as TicketIcon } from 'lucide-react';
import { motion } from 'framer-motion';

export default function TeacherTicketsPage() {
  const { tickets, setTickets, isLoading, error, reload } = useTickets(false);
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
      userId: 'teacher-1',
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

  if (error) {
    return (
      <div className="max-w-5xl mx-auto py-10">
        <ErrorState title="خطا در دریافت تیکت‌ها" description={error} onRetry={reload} />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-foreground flex items-center gap-3">
            <TicketIcon className="w-8 h-8 text-primary" />
            تیکت‌های پشتیبانی
          </h1>
          <p className="text-muted-foreground font-bold mt-1">
            سوالات و مشکلات خود را با تیم پشتیبانی در میان بگذارید
          </p>
        </div>
        <Button 
          onClick={() => setIsNewTicketOpen(true)}
          className="rounded-2xl font-black h-12 px-6 shadow-lg shadow-primary/20 hover:shadow-primary/40 transition-all"
        >
          <Plus className="w-5 h-5 ml-2" />
          تیکت جدید
        </Button>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Card className="rounded-3xl border-border/40 shadow-sm overflow-hidden">
          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-6 space-y-4">
                <Skeleton className="h-20 w-full rounded-2xl" />
                <Skeleton className="h-20 w-full rounded-2xl" />
                <Skeleton className="h-20 w-full rounded-2xl" />
              </div>
            ) : (
              <TicketList tickets={tickets} onTicketClick={handleTicketClick} />
            )}
          </CardContent>
        </Card>
      </motion.div>

      <NewTicketDialog
        open={isNewTicketOpen}
        onOpenChange={setIsNewTicketOpen}
        onSubmit={handleNewTicket}
      />

      <Sheet open={!!selectedTicket} onOpenChange={(open) => !open && setSelectedTicket(null)}>
        <SheetContent side="left" className="w-full sm:max-w-xl p-0 border-r-0">
          <VisuallyHidden>
            <SheetTitle>جزئیات تیکت</SheetTitle>
            <SheetDescription>نمایش پیام‌ها و ارسال پاسخ</SheetDescription>
          </VisuallyHidden>
          {selectedTicket && (
            <TicketDetail
              ticket={selectedTicket}
              onClose={() => setSelectedTicket(null)}
              onReply={(ticketId, message) => handleReply(ticketId, message)}
            />
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
