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
    <div className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="subject">موضوع پیام</Label>
        <Input 
          id="subject" 
          placeholder="مثلاً: تغییر زمان کلاس ریاضی" 
          value={subject}
          onChange={(e) => onSubjectChange(e.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="message">متن پیام</Label>
        <Textarea 
          id="message" 
          placeholder="متن پیام خود را اینجا بنویسید..." 
          className="min-h-[200px] resize-none"
          value={message}
          onChange={(e) => onMessageChange(e.target.value)}
        />
      </div>

      <div className="flex justify-end pt-4">
        <Button 
          size="lg" 
          className="w-full sm:w-auto gap-2"
          onClick={onSend}
          disabled={isSending}
        >
          {isSending ? (
            <>در حال ارسال...</>
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
