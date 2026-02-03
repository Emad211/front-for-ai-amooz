'use client';

import React, { useState, useRef, useEffect } from 'react';
import { User, Mail, Phone, MapPin, Camera, Trash2, Save, X, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

import { useTeacherSettings } from '@/hooks/use-teacher-settings';

interface ProfileTabProps {
	useSettings?: typeof useTeacherSettings;
}

export function ProfileTab({ useSettings = useTeacherSettings }: ProfileTabProps) {
	const { profile, updateProfile, isLoading } = useSettings();
	const [localProfile, setLocalProfile] = useState(profile);
	const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
	const [showSuccessDialog, setShowSuccessDialog] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);

	// Update local state when remote profile changes
	useEffect(() => {
		setLocalProfile(profile);
	}, [profile]);

	const handleSaveProfile = async () => {
		try {
			const payload = { ...localProfile };
			if (avatarPreview) {
				payload.avatar = avatarPreview;
			}
			await updateProfile(payload);
			
			// Dispatch event to sync global header
			window.dispatchEvent(new Event('user-profile-updated'));
			
			setShowSuccessDialog(true);
		} catch (error) {
			console.error('Failed to update teacher profile:', error);
		}
	};

	const handleAvatarClick = () => {
		fileInputRef.current?.click();
	};

	const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (file) {
			const reader = new FileReader();
			reader.onloadend = () => {
				const result = reader.result as string;
				setAvatarPreview(result);
			};
			reader.readAsDataURL(file);
		}
	};

	const handleRemoveAvatar = () => {
		setAvatarPreview(null);
		setLocalProfile(prev => ({ ...prev, avatar: '' }));
	};

	const handleCancel = () => {
		setLocalProfile(profile);
		setAvatarPreview(null);
	};

	return (
		<div className="space-y-6">
			<Card className="border-none shadow-xl shadow-foreground/5 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden text-right">
				<CardHeader className="pb-8 pt-10 px-8 border-b border-border/50 bg-muted/30">
					<CardTitle className="text-2xl font-bold">تصویر پروفایل</CardTitle>
					<CardDescription className="text-base">
						تصویر پروفایل خود را بارگذاری یا تغییر دهید
					</CardDescription>
				</CardHeader>
				<CardContent className="p-8 flex flex-col sm:flex-row items-center gap-8">
					<div className="relative group">
						<div className="absolute -inset-1 bg-gradient-to-tr from-primary to-primary/30 rounded-full blur opacity-25 group-hover:opacity-50 transition duration-500"></div>
						<Avatar className="h-32 w-32 border-4 border-background relative">
							<AvatarImage src={avatarPreview || localProfile.avatar || ''} alt="Profile" />
							<AvatarFallback className="text-2xl bg-primary/10 text-primary">
								{localProfile.name ? localProfile.name.substring(0, 2).toUpperCase() : 'U'}
							</AvatarFallback>
						</Avatar>
						<input
							ref={fileInputRef}
							type="file"
							accept="image/*"
							className="hidden"
							onChange={handleAvatarChange}
						/>
						<Button
							size="icon"
							type="button"
							onClick={handleAvatarClick}
							className="absolute bottom-1 right-1 rounded-full h-10 w-10 bg-primary hover:bg-primary/90 shadow-lg border-4 border-background transition-transform hover:scale-110"
						>
							<Camera className="h-5 w-5" />
						</Button>
					</div>

					<div className="flex flex-wrap justify-center sm:justify-start gap-3">
						<Button 
							variant="outline" 
							className="rounded-xl font-medium"
							onClick={handleAvatarClick}
						>
							<Camera className="w-4 h-4 me-2" />
							تغییر تصویر
						</Button>
						{(avatarPreview || localProfile.avatar) && (
							<Button 
								variant="outline" 
								className="text-destructive hover:text-destructive hover:bg-destructive/10 rounded-xl font-medium border-destructive/20"
								onClick={handleRemoveAvatar}
							>
								<Trash2 className="w-4 h-4 me-2" />
								حذف تصویر
							</Button>
						)}
					</div>
				</CardContent>
			</Card>

			<Card className="border-none shadow-xl shadow-foreground/5 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden text-right">
				<CardHeader className="pb-8 pt-10 px-8 border-b border-border/50 bg-muted/30">
					<CardTitle className="text-2xl font-bold">اطلاعات شخصی</CardTitle>
					<CardDescription className="text-base">
						برای بهتر شناخته شدن توسط دانش‌آموزان، اطلاعات خود را بروزرسانی کنید
					</CardDescription>
				</CardHeader>
				<CardContent className="p-8 space-y-6">
					<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
						<div className="space-y-2.5">
							<Label htmlFor="name" className="pb-2 text-sm font-semibold flex items-center gap-2 px-1 justify-end">
								نام و نام خانوادگی
								<User className="w-4 h-4 text-primary" />
							</Label>
							<Input
								id="name"
								value={localProfile.name}
								onChange={(e) => setLocalProfile(prev => ({ ...prev, name: e.target.value }))}
								className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all text-right"
								placeholder="مثلاً: محمد کریمی"
							/>
						</div>
						<div className="space-y-2.5">
							<Label htmlFor="email" className="pb-2 text-sm font-semibold flex items-center gap-2 px-1 justify-end">
								آدرس ایمیل
								<Mail className="w-4 h-4 text-primary" />
							</Label>
							<Input
								id="email"
								type="email"
								value={localProfile.email}
								onChange={(e) => setLocalProfile(prev => ({ ...prev, email: e.target.value }))}
								className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all text-left"
								dir="ltr"
							/>
						</div>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
						<div className="space-y-2.5">
							<Label htmlFor="phone" className="pb-2 text-sm font-semibold flex items-center gap-2 px-1 justify-end">
								شماره تماس
								<Phone className="w-4 h-4 text-primary" />
							</Label>
							<Input
								id="phone"
								value={localProfile.phone}
								onChange={(e) => setLocalProfile(prev => ({ ...prev, phone: e.target.value }))}
								className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all text-left"
								dir="ltr"
								disabled
							/>
						</div>
						<div className="space-y-2.5">
							<Label htmlFor="location" className="pb-2 text-sm font-semibold flex items-center gap-2 px-1 justify-end">
								محل اقامت / شهر
								<MapPin className="w-4 h-4 text-primary" />
							</Label>
							<Input
								id="location"
								value={localProfile.location}
								onChange={(e) => setLocalProfile(prev => ({ ...prev, location: e.target.value }))}
								className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all text-right"
								placeholder="مثلاً: تهران"
							/>
						</div>
					</div>

					<div className="space-y-2.5">
						<Label htmlFor="bio" className="pb-2 text-sm font-semibold flex items-center gap-2 px-1 justify-end">
							درباره من / تخصص‌ها
							<CheckCircle2 className="w-4 h-4 text-primary" />
						</Label>
						<Textarea
							id="bio"
							value={localProfile.bio}
							onChange={(e) => setLocalProfile(prev => ({ ...prev, bio: e.target.value }))}
							className="bg-background/50 border-border/50 min-h-[120px] rounded-xl focus:ring-primary/20 focus:border-primary transition-all text-right resize-none"
							placeholder="توضیحات کوتاهی درباره خود و سوابق آموزشی‌تان بنویسید..."
						/>
					</div>
				</CardContent>
				<CardFooter className="p-8 pt-0 flex flex-col sm:flex-row justify-end gap-3">
					<Button
						variant="ghost"
						className="h-12 px-8 rounded-xl font-semibold gap-2 order-2 sm:order-1"
						onClick={handleCancel}
						disabled={isLoading}
					>
						<X className="w-4 h-4" />
						انصراف
					</Button>
					<Button
						className="h-12 px-10 rounded-xl font-semibold gap-2 bg-primary hover:bg-primary/90 shadow-lg shadow-primary/20 order-1 sm:order-2"
						onClick={handleSaveProfile}
						disabled={isLoading}
					>
						<Save className="w-4 h-4" />
						{isLoading ? 'در حال ذخیره...' : 'ذخیره تغییرات'}
					</Button>
				</CardFooter>
			</Card>

			{/* Success Dialog */}
			<Dialog open={showSuccessDialog} onOpenChange={setShowSuccessDialog}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<div className="mx-auto w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center mb-4">
							<CheckCircle2 className="w-6 h-6 text-green-600 dark:text-green-400" />
						</div>
						<DialogTitle className="text-center font-bold text-xl">تغییرات با موفقیت ذخیره شد</DialogTitle>
						<DialogDescription className="text-center text-base">
							اطلاعات پروفایل شما در سیستم بروزرسانی شد.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="sm:justify-center">
						<Button onClick={() => setShowSuccessDialog(false)} className="rounded-xl px-8">
							متوجه شدم
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
