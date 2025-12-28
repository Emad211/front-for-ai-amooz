'use client';

import { User, Headphones } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TicketMessage } from '@/constants/mock';

interface TicketMessageBubbleProps {
  message: TicketMessage;
  isOwnMessage?: boolean;
}

export function TicketMessageBubble({ message, isOwnMessage = false }: TicketMessageBubbleProps) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('fa-IR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className={cn('flex gap-2 sm:gap-3', isOwnMessage ? 'flex-row-reverse' : '')}>
      {/* Avatar */}
      <div className={cn(
        'w-8 h-8 sm:w-9 sm:h-9 rounded-full flex items-center justify-center shrink-0',
        message.isAdmin ? 'bg-primary/10' : 'bg-muted'
      )}>
        {message.isAdmin ? (
          <Headphones className="w-4 h-4 text-primary" />
        ) : (
          <User className="w-4 h-4 text-muted-foreground" />
        )}
      </div>

      {/* Message Bubble */}
      <div className={cn(
        'max-w-[85%] sm:max-w-[75%] rounded-2xl p-3 sm:p-4 text-right',
        isOwnMessage 
          ? 'bg-primary text-primary-foreground rounded-ee-md' 
          : 'bg-muted/70 rounded-es-md'
      )} dir="rtl">
        {/* Sender Label */}
        <span className={cn(
          'text-[10px] sm:text-xs font-medium mb-1 block',
          isOwnMessage ? 'text-primary-foreground/80' : 'text-muted-foreground'
        )}>
          {message.isAdmin ? 'پشتیبانی' : 'شما'}
        </span>

        {/* Message Content */}
        <p className={cn(
          'text-sm sm:text-base whitespace-pre-wrap leading-relaxed',
          isOwnMessage ? 'text-primary-foreground' : 'text-foreground'
        )}>
          {message.content}
        </p>

        {/* Time */}
        <span className={cn(
          'text-[10px] mt-2 block opacity-70',
          isOwnMessage ? 'text-primary-foreground/60' : 'text-muted-foreground/70'
        )}>
          {formatDate(message.createdAt)}
        </span>
      </div>
    </div>
  );
}
