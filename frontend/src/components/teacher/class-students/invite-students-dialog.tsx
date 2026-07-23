'use client';

import { useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { isValidIranPhone, normalizeIranPhone } from '@/lib/iran-phone';

interface InviteStudentsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  destinationTitle: string;
  onSubmit: (phones: string[]) => Promise<void>;
  successMessage: string;
}

export function InviteStudentsDialog({
  open,
  onOpenChange,
  destinationTitle,
  onSubmit,
  successMessage,
}: InviteStudentsDialogProps) {
  const [phonesText, setPhonesText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const phoneEntries = useMemo(
    () =>
      phonesText
        .split(/[\n,،\s]+/)
        .map((raw) => raw.trim())
        .filter(Boolean)
        .map((raw) => ({ raw, normalized: normalizeIranPhone(raw) })),
    [phonesText],
  );
  const phones = useMemo(
    () => Array.from(new Set(phoneEntries.map(({ normalized }) => normalized))),
    [phoneEntries],
  );
  const invalidPhones = phoneEntries.filter(({ normalized }) => !isValidIranPhone(normalized));

  const submit = async () => {
    if (!phones.length) {
      toast.error('حداقل یک شماره موبایل وارد کنید.');
      return;
    }
    if (invalidPhones.length) {
      toast.error('شماره‌های موبایل باید با قالب 09XXXXXXXXX وارد شوند.');
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit(phones);
      setPhonesText('');
      onOpenChange(false);
      toast.success(successMessage);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'ثبت دعوت‌ها انجام نشد.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="text-start">
          <DialogTitle>افزودن دانش‌آموز</DialogTitle>
          <DialogDescription>
            شماره موبایل دانش‌آموزان را برای دعوت به «{destinationTitle}» وارد کنید.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2 text-start">
          <label htmlFor="student-phones" className="block text-sm font-medium">
            شماره موبایل دانش‌آموزان
          </label>
          <Textarea
            id="student-phones"
            dir="ltr"
            className="min-h-32 text-left"
            maxLength={1200}
            value={phonesText}
            onChange={(event) => setPhonesText(event.target.value)}
            placeholder={'09123456789\n09351234567'}
          />
          <p className="text-xs text-muted-foreground">هر شماره را در یک خط جدا وارد کنید.</p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            انصراف
          </Button>
          <Button onClick={submit} disabled={submitting}>
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            ثبت {phones.length || ''} دعوت
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
