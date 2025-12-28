'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { toast } from 'sonner';
import { RecipientSelector } from '@/components/admin/messages/recipient-selector';
import { MessageForm } from '@/components/admin/messages/message-form';
import { MessageStats } from '@/components/admin/messages/message-stats';
import { MessageTips } from '@/components/admin/messages/message-tips';

// Mock students data
const mockStudents = [
  { id: '1', name: 'علی محمدی', email: 'ali@example.com', avatar: '/avatars/01.png' },
  { id: '2', name: 'سارا احمدی', email: 'sara@example.com', avatar: '/avatars/02.png' },
  { id: '3', name: 'رضا کریمی', email: 'reza@example.com', avatar: '/avatars/03.png' },
  { id: '4', name: 'مریم حسینی', email: 'maryam@example.com', avatar: '/avatars/04.png' },
  { id: '5', name: 'امیر رضایی', email: 'amir@example.com', avatar: '/avatars/05.png' },
  { id: '6', name: 'زهرا نوری', email: 'zahra@example.com', avatar: '/avatars/06.png' },
  { id: '7', name: 'محمد کاظمی', email: 'mohammad@example.com', avatar: '/avatars/07.png' },
  { id: '8', name: 'فاطمه موسوی', email: 'fatemeh@example.com', avatar: '/avatars/08.png' },
];

export default function MessagesPage() {
  const [recipientType, setRecipientType] = useState<'all' | 'specific'>('all');
  const [selectedStudents, setSelectedStudents] = useState<string[]>([]);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isSending, setIsSending] = useState(false);

  const handleSelectStudent = (studentId: string) => {
    setSelectedStudents(prev => 
      prev.includes(studentId) 
        ? prev.filter(id => id !== studentId)
        : [...prev, studentId]
    );
  };

  const handleSend = () => {
    if (!subject || !message) {
      toast.error('لطفاً موضوع و متن پیام را وارد کنید');
      return;
    }

    if (recipientType === 'specific' && selectedStudents.length === 0) {
      toast.error('لطفاً حداقل یک گیرنده انتخاب کنید');
      return;
    }

    setIsSending(true);
    
    // Simulate API call
    setTimeout(() => {
      setIsSending(false);
      toast.success('پیام با موفقیت ارسال شد');
      setSubject('');
      setMessage('');
      setSelectedStudents([]);
      setRecipientType('all');
    }, 1500);
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div className="text-start">
          <h1 className="text-2xl md:text-3xl font-black text-foreground">ارسال پیام</h1>
          <p className="text-muted-foreground text-sm mt-1">
            ارسال اطلاعیه و پیام به دانش‌آموزان
          </p>
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
              <RecipientSelector 
                recipientType={recipientType}
                onRecipientTypeChange={setRecipientType}
                selectedStudents={selectedStudents}
                onSelectStudent={handleSelectStudent}
                onSelectAll={setSelectedStudents}
                students={mockStudents}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
              />

              <MessageForm 
                subject={subject}
                onSubjectChange={setSubject}
                message={message}
                onMessageChange={setMessage}
                onSend={handleSend}
                isSending={isSending}
              />
            </CardContent>
          </Card>
        </div>

        {/* Preview / Info Side */}
        <div className="space-y-6">
          <MessageTips />
          <MessageStats />
        </div>
      </div>
    </div>
  );
}

