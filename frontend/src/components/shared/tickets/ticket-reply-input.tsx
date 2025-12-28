'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Paperclip } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface TicketReplyInputProps {
  onSend: (message: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function TicketReplyInput({
  onSend,
  placeholder = 'پاسخ خود را بنویسید...',
  disabled = false,
  className,
}: TicketReplyInputProps) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [message]);

  const handleSend = () => {
    if (message.trim() && !disabled) {
      onSend(message.trim());
      setMessage('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={cn('p-3 sm:p-4 border-t bg-background/50 backdrop-blur-sm', className)}>
      <div className="flex items-end gap-2 sm:gap-3">
        {/* Text Input Container */}
        <div className="flex-1 relative">
          <div className="flex items-end bg-muted/50 rounded-2xl border border-border/50 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/10 transition-all">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={disabled}
              rows={1}
              className={cn(
                'flex-1 bg-transparent border-0 resize-none py-3 px-4',
                'text-sm placeholder:text-muted-foreground/70',
                'focus:outline-none focus:ring-0',
                'min-h-[44px] max-h-[120px]',
                'text-right',
                disabled && 'opacity-50 cursor-not-allowed'
              )}
              dir="rtl"
            />
          </div>
          <p className="text-[10px] text-muted-foreground/60 mt-1 px-2 hidden sm:block">
            برای ارسال Enter بزنید • برای خط جدید Shift+Enter
          </p>
        </div>

        {/* Send Button */}
        <Button
          onClick={handleSend}
          disabled={!message.trim() || disabled}
          size="icon"
          className={cn(
            'h-11 w-11 rounded-xl shrink-0 transition-all',
            'bg-primary hover:bg-primary/90',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            message.trim() && 'shadow-lg shadow-primary/25'
          )}
        >
          <Send className="w-4 h-4 rtl:rotate-180" />
        </Button>
      </div>
    </div>
  );
}
