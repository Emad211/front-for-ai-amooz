'use client';

import { Send } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';

interface MessageFormProps {
  subject: string;
  onSubjectChange: (value: string) => void;
  message: string;
  onMessageChange: (value: string) => void;
  onSend: () => void;
  isSending: boolean;
}

export function MessageForm({
  subject,
  onSubjectChange,
  message,
  onMessageChange,
  onSend,
  isSending,
}: MessageFormProps) {
  return (
    <div className="space-y-6 text-start">
      <div className="space-y-2">
        <Label htmlFor="subject" className="text-sm font-bold px-1">موضوع پیام</Label>
        <Input 
          id="subject" 
          placeholder="مثلاً: تغییر زمان کلاس ریاضی" 
          value={subject}
          onChange={(e) => onSubjectChange(e.target.value)}
          className="h-12 rounded-xl bg-muted/30 border-none focus-visible:ring-primary/20 text-start"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="message" className="text-sm font-bold px-1">متن پیام</Label>
        <Textarea 
          id="message" 
          placeholder="متن پیام خود را اینجا بنویسید..." 
          className="min-h-[200px] resize-none rounded-xl bg-muted/30 border-none focus-visible:ring-primary/20 p-4 text-start"
          value={message}
          onChange={(e) => onMessageChange(e.target.value)}
        />
      </div>

      <div className="flex justify-end pt-4">
        <Button 
          size="lg" 
          className="w-full sm:w-auto gap-2 h-12 px-8 rounded-xl shadow-lg shadow-primary/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
          onClick={onSend}
          disabled={isSending}
        >
          {isSending ? (
            <>
              <div className="h-4 w-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              در حال ارسال...
            </>
          ) : (
            <>
              <Send className="h-4 w-4 rtl:-rotate-180" />
              ارسال پیام
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
