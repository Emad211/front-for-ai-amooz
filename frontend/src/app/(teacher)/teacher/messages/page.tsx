'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { toast } from 'sonner';
import { RecipientSelector } from '@/components/admin/messages/recipient-selector';
import { MessageForm } from '@/components/admin/messages/message-form';
import { MessageStats } from '@/components/admin/messages/message-stats';
import { MessageTips } from '@/components/admin/messages/message-tips';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useTeacherMessageRecipients } from '@/hooks/use-teacher-message-recipients';

export default function TeacherMessagesPage() {
	const { recipients, isLoading, error, reload } = useTeacherMessageRecipients();
	const [recipientType, setRecipientType] = useState<'all' | 'specific'>('all');
	const [selectedStudents, setSelectedStudents] = useState<string[]>([]);
	const [subject, setSubject] = useState('');
	const [message, setMessage] = useState('');
	const [searchQuery, setSearchQuery] = useState('');
	const [isSending, setIsSending] = useState(false);

	const handleSelectStudent = (studentId: string) => {
		setSelectedStudents((prev) =>
			prev.includes(studentId)
				? prev.filter((id) => id !== studentId)
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

		setTimeout(() => {
			setIsSending(false);
			toast.success('پیام با موفقیت ارسال شد');
			setSubject('');
			setMessage('');
			setSelectedStudents([]);
			setRecipientType('all');
		}, 1500);
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
					<h1 className="text-2xl md:text-3xl font-black text-foreground">ارسال پیام</h1>
					<p className="text-muted-foreground text-sm mt-1">ارسال اطلاعیه به دانش‌آموزان</p>
				</div>
			</div>

			<div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
				<div className="lg:col-span-2 space-y-6">
					<Card>
						<CardHeader className="text-start">
							<CardTitle>تنظیمات پیام</CardTitle>
							<CardDescription>گیرندگان و محتوای پیام خود را مشخص کنید</CardDescription>
						</CardHeader>
						<CardContent className="space-y-6">
							{isLoading ? (
								<div className="space-y-4">
									<Skeleton className="h-10 w-full" />
									<Skeleton className="h-40 w-full" />
								</div>
							) : (
								<RecipientSelector
									recipientType={recipientType}
									onRecipientTypeChange={setRecipientType}
									selectedStudents={selectedStudents}
									onSelectStudent={handleSelectStudent}
									onSelectAll={setSelectedStudents}
									students={recipients}
									searchQuery={searchQuery}
									onSearchChange={setSearchQuery}
								/>
							)}

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

				<div className="space-y-6">
					<MessageTips />
					<MessageStats />
				</div>
			</div>
		</div>
	);
}
