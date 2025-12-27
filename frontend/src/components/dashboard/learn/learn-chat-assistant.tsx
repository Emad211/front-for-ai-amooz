'use client';

import React from 'react';
import { Bot, PanelRightClose, Send, Paperclip, Mic, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { SheetClose } from '@/components/ui/sheet';

interface ChatMessageProps {
  sender: 'ai' | 'user';
  time: string;
  message: string;
  isFormula?: boolean;
}

export const ChatMessage = ({ sender, time, message, isFormula = false }: ChatMessageProps) => {
  const isAI = sender === 'ai';
  return (
    <div className={`flex flex-col gap-1 ${!isAI && 'items-end'}`}>
      <div className={`flex items-start gap-2 ${!isAI && 'flex-row-reverse'}`}>
        {isAI && (
          <div className="h-7 w-7 rounded-full bg-secondary flex-shrink-0 flex items-center justify-center border border-border mt-1">
            <Bot className="text-primary h-4 w-4" />
          </div>
        )}
        <div
          className={cn(
            'p-3 rounded-2xl leading-6 shadow-sm border max-w-[90%]',
            isAI ? 'bg-card text-foreground rounded-tr-none border-border/50' : 'bg-primary/10 text-foreground rounded-tl-none border-primary/20'
          )}
        >
          <p className="text-sm" dangerouslySetInnerHTML={{ __html: message }}></p>
        </div>
      </div>
      <span className={`text-[9px] text-muted-foreground ${isAI ? 'pr-11' : 'pl-1'}`}>{time}</span>
    </div>
  );
};

interface ChatAssistantProps {
  onToggle: () => void;
  isOpen: boolean;
  className?: string;
  isMobile?: boolean;
}

export const ChatAssistant = ({ onToggle, isOpen, className, isMobile = false }: ChatAssistantProps) => {
  const [message, setMessage] = React.useState('');
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const handleInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(event.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  // Scroll to bottom on open or new messages
  React.useEffect(() => {
    if (isOpen && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [isOpen]);

  return (
    <aside
      className={cn(
        'flex-shrink-0 flex-col bg-card border border-border overflow-hidden transition-all duration-300 ease-in-out',
        isMobile ? 'fixed inset-0 z-[100] w-full h-[100dvh] rounded-none border-none flex' : 'rounded-2xl shadow-xl h-full',
        !isMobile && 'hidden md:flex',
        !isMobile && (isOpen ? 'w-96' : 'w-0 p-0 border-none'),
        className
      )}
    >
      <div
        className={cn(
          'p-3 border-b border-border flex items-center justify-between bg-secondary/30 backdrop-blur-sm h-14 flex-shrink-0',
          !isOpen && !isMobile && 'hidden'
        )}
      >
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary/20 to-purple-500/20 flex items-center justify-center relative ring-1 ring-foreground/10">
            <Bot className="text-primary h-5 w-5" />
            <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 bg-green-500 rounded-full border-2 border-card"></span>
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground">دستیار هوشمند</h3>
            <p className="text-[10px] text-muted-foreground font-medium">پاسخگوی سوالات شما</p>
          </div>
        </div>
        {isMobile ? (
          <SheetClose asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-9 px-3 rounded-xl bg-secondary/50 hover:bg-secondary text-muted-foreground hover:text-foreground border border-border/50 transition-all flex items-center gap-2"
            >
              <span className="text-xs font-medium">بستن</span>
              <X className="h-4 w-4" />
            </Button>
          </SheetClose>
        ) : (
          <Button
            onClick={onToggle}
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground"
          >
            <PanelRightClose className="h-4 w-4" />
          </Button>
        )}
      </div>
      <div 
        ref={scrollRef}
        className={cn(
          'flex-1 overflow-y-auto p-4 space-y-6 bg-background/30 no-scrollbar min-h-0', 
          !isOpen && !isMobile && 'hidden'
        )}
      >
        <ChatMessage
          sender="ai"
          time="۱۰:۳۲"
          message="سلام! 👋 من دستیار هوشمندت هستم.<br/>میتونی سوالت رو بپرسی، یا اگه توی مبحثی گیر کردی ازم راهنمایی بخوای. اگه روی کاغذ تمرین کردی، عکسش رو بفرست تا بررسی کنم."
        />
        <ChatMessage
          sender="user"
          time="۱۰:۳۴"
          message="مطمئن نیستم چطوری باید از اطلاعات داده شده برای حل این بخش استفاده کنم. میشه یه راهنمایی کلی بکنی؟"
        />
        <ChatMessage
          sender="ai"
          time="۱۰:۳۵"
          message='حتماً! برای حل این بخش، ابتدا باید متغیرهای اصلی رو شناسایی کنی. مثلاً در مورد سهمی: <br> <span class="font-mono px-1 rounded my-1 block text-center" dir="ltr">x = -b / 2a</span> <br> سعی کن مقادیر رو جایگذاری کنی تا به جواب برسی.'
        />
        {/* Spacer for keyboard on mobile */}
        <div className="h-4 flex-shrink-0" />
      </div>
      <div className={cn('p-3 border-t border-border bg-card z-10 flex-shrink-0', !isOpen && !isMobile && 'hidden')}>
        <div className="flex gap-2 mb-2 overflow-x-auto no-scrollbar pb-1">
          <Button variant="outline" className="text-xs h-8 flex-shrink-0">
            راهنماییم کن
          </Button>
          <Button variant="outline" className="text-xs h-8 flex-shrink-0">
            اشتباهم کجاست؟
          </Button>
          <Button variant="outline" className="text-xs h-8 flex-shrink-0">
            قدم اول را بگو
          </Button>
        </div>
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={message}
            onChange={handleInputChange}
            onFocus={() => {
              // Small delay to allow keyboard to open and viewport to resize
              setTimeout(() => {
                if (scrollRef.current) {
                  scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
                }
              }, 300);
            }}
            placeholder="سوالت رو بپرس... یا تصویر تمرینت رو بفرست"
            rows={1}
            className="bg-background border-border rounded-xl text-sm text-foreground focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-muted-foreground/50 py-3 pr-20 pl-12 resize-none overflow-y-hidden no-scrollbar"
          />
          <div className="absolute right-2 bottom-1.5 flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-lg text-muted-foreground hover:text-primary hover:bg-foreground/5"
              title="پیوست فایل"
            >
              <Paperclip className="h-4 w-4 -rotate-45" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-lg text-muted-foreground hover:text-primary hover:bg-foreground/5"
              title="ضبط صدا"
            >
              <Mic className="h-4 w-4" />
            </Button>
          </div>
          <div className="absolute left-2 bottom-1.5 flex items-center">
            <Button
              size="icon"
              className="h-9 w-9 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground transition-all shadow-lg shadow-primary/20 hover:scale-105 active:scale-95"
            >
              <Send className="h-4 w-4 rtl:-rotate-180" />
            </Button>
          </div>
        </div>
      </div>
    </aside>
  );
};
