'use client';

import { ScrollArea } from '@/components/ui/scroll-area';
import { TicketStatusBadge, TicketPriorityBadge } from './ticket-badges';
import { TicketMessageBubble } from './ticket-message-bubble';
import { TicketReplyInput } from './ticket-reply-input';
import type { Ticket } from '@/types';

interface TicketDetailProps {
  ticket: Ticket;
  onClose: () => void;
  onReply: (ticketId: string, message: string) => void;
  isAdmin?: boolean;
}

export function TicketDetail({ ticket, onClose, onReply, isAdmin = false }: TicketDetailProps) {
  const handleSendReply = (message: string) => {
    onReply(ticket.id, message);
  };

  return (
    <div className="flex flex-col h-full" dir="rtl">
      {/* Header */}
      <div className="p-4 sm:p-5 border-b bg-card">
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className="text-xs text-muted-foreground font-mono bg-muted/50 px-2 py-0.5 rounded">
            #{ticket.id}
          </span>
          <TicketStatusBadge status={ticket.status} />
          <TicketPriorityBadge priority={ticket.priority} />
        </div>
        <h2 className="font-bold text-base sm:text-lg text-foreground leading-tight">
          {ticket.subject}
        </h2>
        <p className="text-xs sm:text-sm text-muted-foreground mt-1">
          {ticket.department}
        </p>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1">
        <div className="p-4 sm:p-5 space-y-4 sm:space-y-5">
          {ticket.messages.map((message) => (
            <TicketMessageBubble
              key={message.id}
              message={message}
              isOwnMessage={isAdmin ? message.isAdmin : !message.isAdmin}
            />
          ))}
        </div>
      </ScrollArea>

      {/* Reply Input */}
      {ticket.status !== 'closed' ? (
        <TicketReplyInput onSend={handleSendReply} />
      ) : (
        <div className="p-4 border-t bg-muted/30 text-center">
          <p className="text-sm text-muted-foreground">این تیکت بسته شده است</p>
        </div>
      )}
    </div>
  );
}
