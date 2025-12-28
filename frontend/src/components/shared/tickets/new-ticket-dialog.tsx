'use client';

import { useState } from 'react';
import { Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { TICKET_DEPARTMENTS } from '@/constants/mock';

interface NewTicketDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: { subject: string; department: string; message: string }) => void;
}

export function NewTicketDialog({ open, onOpenChange, onSubmit }: NewTicketDialogProps) {
  const [subject, setSubject] = useState('');
  const [department, setDepartment] = useState('');
  const [message, setMessage] = useState('');

  const handleSubmit = () => {
    if (subject && department && message) {
      onSubmit({ subject, department, message });
      setSubject('');
      setDepartment('');
      setMessage('');
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>ارسال تیکت جدید</DialogTitle>
          <DialogDescription>
            سوال یا مشکل خود را با ما در میان بگذارید
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          <div className="space-y-2">
            <Label htmlFor="subject">موضوع</Label>
            <Input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="موضوع تیکت را وارد کنید"
              className="rounded-xl"
            />
          </div>

          <div className="space-y-2">
            <Label>دپارتمان</Label>
            <Select value={department} onValueChange={setDepartment}>
              <SelectTrigger className="rounded-xl">
                <SelectValue placeholder="انتخاب دپارتمان" />
              </SelectTrigger>
              <SelectContent>
                {TICKET_DEPARTMENTS.map((dept) => (
                  <SelectItem key={dept} value={dept}>
                    {dept}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="message">پیام</Label>
            <Textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="توضیحات کامل مشکل یا سوال خود را بنویسید..."
              rows={5}
              className="rounded-xl resize-none"
            />
          </div>

          <Button
            onClick={handleSubmit}
            disabled={!subject || !department || !message}
            className="w-full rounded-xl gap-2"
          >
            <Send className="w-4 h-4" />
            ارسال تیکت
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
