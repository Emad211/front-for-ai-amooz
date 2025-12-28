'use client';

import { Send, User, Headphones } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { TicketStatusBadge, TicketPriorityBadge } from './ticket-badges';
import { cn } from '@/lib/utils';
import type { Ticket, TicketMessage } from '@/constants/tickets-data';

interface TicketDetailProps {
  ticket: Ticket;
  onClose: () => void;
  onReply: (ticketId: string, message: string) => void;
  isAdmin?: boolean;
}

function MessageBubble({ message, isAdmin }: { message: TicketMessage; isAdmin?: boolean }) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('fa-IR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const isOwnMessage = isAdmin ? message.isAdmin : !message.isAdmin;

  return (
    <div className={cn('flex gap-3', isOwnMessage ? 'flex-row-reverse' : '')}>
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
        isOwnMessage 
          ? 'bg-primary text-primary-foreground rounded-ee-sm' 
          : 'bg-muted rounded-es-sm'
      )}>
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        <span className={cn(
          'text-[10px] mt-1 block',
          isOwnMessage ? 'text-primary-foreground/70' : 'text-muted-foreground'
        )}>
          {formatDate(message.createdAt)}
        </span>
      </div>
    </div>
  );
}

export function TicketDetail({ ticket, onClose, onReply, isAdmin = false }: TicketDetailProps) {
  const [replyText, setReplyText] = useState('');

  const handleSendReply = () => {
    if (replyText.trim()) {
      onReply(ticket.id, replyText);
      setReplyText('');
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 p-4 border-b">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="text-xs text-muted-foreground font-mono">
              #{ticket.id}
            </span>
            <TicketStatusBadge status={ticket.status} />
            <TicketPriorityBadge priority={ticket.priority} />
          </div>
          <h2 className="font-bold text-foreground">{ticket.subject}</h2>
          <p className="text-xs text-muted-foreground mt-1">{ticket.department}</p>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {ticket.messages.map((message) => (
            <MessageBubble key={message.id} message={message} isAdmin={isAdmin} />
          ))}
        </div>
      </ScrollArea>

      {/* Reply Input */}
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
