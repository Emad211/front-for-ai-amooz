'use client';

import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { toast } from 'sonner';
import { RecipientSelector } from '@/components/admin/messages/recipient-selector';
import { MessageForm } from '@/components/admin/messages/message-form';
import { MessageStats } from '@/components/admin/messages/message-stats';
import { MessageTips } from '@/components/admin/messages/message-tips';

import { useMessageRecipients } from '@/hooks/use-message-recipients';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { AdminService } from '@/services/admin-service';

export default function BroadcastPage() {
  const { recipients, isLoading, error, reload } = useMessageRecipients();
  const [audience, setAudience] = useState<'all' | 'students' | 'teachers'>('all');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isSending, setIsSending] = useState(false);

  const filteredRecipientsCount = useMemo(() => {
    if (audience === 'students') return recipients.filter(r => r.role === 'student').length;
    if (audience === 'teachers') return recipients.filter(r => r.role === 'teacher').length;
    return recipients.length;
  }, [audience, recipients]);

  const handleSend = async () => {
    if (!subject || !message) {
      toast.error('لطفاً موضوع و متن پیام را وارد کنید');
      return;
    }

    try {
      setIsSending(true);
      await AdminService.sendBroadcastNotification({
        title: subject,
        message,
        audience,
        notification_type: 'info',
      });
      toast.success('اعلان با موفقیت ارسال شد');
      setSubject('');
      setMessage('');
      setAudience('all');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'ارسال اعلان ناموفق بود';
      toast.error(message);
    } finally {
      setIsSending(false);
    }
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="خطا در دریافت مخاطبین" description={error} onRetry={reload} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div className="text-start">
          <h1 className="text-2xl md:text-3xl font-black text-foreground">پیام همگانی</h1>
          <p className="text-muted-foreground text-sm mt-1">ارسال اعلان سراسری به کاربران</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Message Form */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="text-start">
              <CardTitle>تنظیمات پیام</CardTitle>
              <CardDescription>
                گیرندگان و محتوای پیام خود را مشخص کنید
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {isLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-40 w-full" />
                </div>
              ) : (
                <RecipientSelector 
                  audience={audience}
                  onAudienceChange={setAudience}
                  recipients={recipients}
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                />
              )}

              <MessageForm 
                subject={subject}
                onSubjectChange={setSubject}
                message={message}
                onMessageChange={setMessage}
                isSending={isSending}
                onSend={handleSend}
              />
            </CardContent>
          </Card>
        </div>

        {/* Sidebar Info */}
        <div className="space-y-6">
          <MessageStats 
            totalRecipients={recipients.length}
            selectedCount={filteredRecipientsCount}
          />
          <MessageTips />
        </div>
      </div>
    </div>
  );
}

