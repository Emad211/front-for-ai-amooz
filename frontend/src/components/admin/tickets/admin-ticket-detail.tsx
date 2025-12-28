'use client';

import { useState } from 'react';
import { Send, User, Headphones } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AdminTicketDetailHeader } from './admin-ticket-detail-header';
import { cn } from '@/lib/utils';
import type { Ticket, TicketMessage, TicketStatus, TicketPriority } from '@/constants/tickets-data';

interface AdminTicketDetailProps {
  ticket: Ticket;
  onClose: () => void;
  onReply: (ticketId: string, message: string) => void;
  onStatusChange: (ticketId: string, status: TicketStatus) => void;
  onPriorityChange: (ticketId: string, priority: TicketPriority) => void;
}

function MessageBubble({ message }: { message: TicketMessage }) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('fa-IR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className={cn('flex gap-3', message.isAdmin ? 'flex-row-reverse' : '')}>
      <div className={cn(
        'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
        message.isAdmin ? 'bg-primary/10' : 'bg-muted'
      )}>
        {message.isAdmin ? (
          <Headphones className="w-4 h-4 text-primary" />
        ) : (
          <User className="w-4 h-4 text-muted-foreground" />
        )}
      </div>
      <div className={cn(
        'max-w-[80%] rounded-2xl p-3',
        message.isAdmin 
          ? 'bg-primary text-primary-foreground rounded-ee-sm' 
          : 'bg-muted rounded-es-sm'
      )}>
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        <span className={cn(
          'text-[10px] mt-1 block',
          message.isAdmin ? 'text-primary-foreground/70' : 'text-muted-foreground'
        )}>
          {formatDate(message.createdAt)}
        </span>
      </div>
    </div>
  );
}

export function AdminTicketDetail({
  ticket,
  onClose,
  onReply,
  onStatusChange,
  onPriorityChange,
}: AdminTicketDetailProps) {
  const [replyText, setReplyText] = useState('');

  const handleSendReply = () => {
    if (replyText.trim()) {
      onReply(ticket.id, replyText);
      setReplyText('');
    }
  };

  return (
    <div className="flex flex-col h-full">
      <AdminTicketDetailHeader
        ticket={ticket}
        onClose={onClose}
        onStatusChange={(status) => onStatusChange(ticket.id, status)}
        onPriorityChange={(priority) => onPriorityChange(ticket.id, priority)}
      />

      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {ticket.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </div>
      </ScrollArea>

      {ticket.status !== 'closed' && (
        <div className="p-4 border-t">
          <div className="flex gap-2">
            <Textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              placeholder="پاسخ خود را بنویسید..."
              rows={2}
              className="rounded-xl resize-none flex-1"
            />
            <Button
              onClick={handleSendReply}
              disabled={!replyText.trim()}
              size="icon"
              className="rounded-xl h-auto aspect-square"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
