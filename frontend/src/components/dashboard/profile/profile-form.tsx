'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Camera, User, Mail, Phone, GraduationCap, BookOpen, Save, X } from 'lucide-react';
import type { UserProfile } from '@/types';

type ProfileFormProps = {
  user: UserProfile | null;
  isLoading?: boolean;
  error?: string | null;
  onSave: (payload: {
    first_name: string;
    last_name: string;
    email: string;
    grade?: string;
    major?: string;
  }) => Promise<void> | void;
};

export function ProfileForm({ user, isLoading = false, error = null, onSave }: ProfileFormProps) {
  const initial = useMemo(() => {
    const name = (user?.name || '').trim();
    const parts = name ? name.split(' ') : [];
    const first_name = parts[0] ?? '';
    const last_name = parts.slice(1).join(' ') ?? '';

    return {
      username: user?.username ?? '',
      email: user?.email ?? '',
      phone: user?.phone ?? '',
      avatar: user?.avatar ?? '',
      grade: user?.grade ?? '',
      major: user?.major ?? '',
      first_name,
      last_name,
    };
  }, [user]);

  const [profile, setProfile] = useState(initial);

  useEffect(() => {
    setProfile(initial);
  }, [initial]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { id, value } = e.target;
    setProfile((prev) => ({ ...prev, [id]: value }));
  };

  const handleCancel = () => {
    setProfile(initial);
  };

  const handleSave = async () => {
    await onSave({
      first_name: profile.first_name,
      last_name: profile.last_name,
      email: profile.email,
      grade: profile.grade || undefined,
      major: profile.major || undefined,
    });
  };

  if (!user) {
    return (
      <Card className="border-none shadow-xl shadow-foreground/5 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden">
        <CardHeader className="pb-8 pt-10 px-8 border-b border-border/50 bg-muted/30">
          <CardTitle className="text-2xl font-bold">پروفایل</CardTitle>
          <CardDescription className="text-base">اطلاعات پروفایل در دسترس نیست.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="border-none shadow-xl shadow-foreground/5 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden">
      <CardHeader className="pb-8 pt-10 px-8 border-b border-border/50 bg-muted/30">
        <div className="flex flex-col md:flex-row items-center gap-8">
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-tr from-primary to-primary/30 rounded-full blur opacity-25 group-hover:opacity-50 transition duration-500"></div>
            <Avatar className="h-32 w-32 border-4 border-background relative">
              <AvatarImage src={profile.avatar} alt={profile.username} />
              <AvatarFallback className="text-2xl bg-primary/10 text-primary">
                {(profile.username || 'U').substring(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <Button
              size="icon"
              className="absolute bottom-1 right-1 rounded-full h-10 w-10 bg-primary hover:bg-primary/90 shadow-lg border-4 border-background transition-transform hover:scale-110"
              disabled
            >
              <Camera className="h-5 w-5" />
            </Button>
          </div>

          <div className="text-center md:text-right space-y-2">
            <CardTitle className="text-2xl font-bold">{profile.username}</CardTitle>
            <CardDescription className="text-base">
              {profile.grade || profile.major ? (
                <>
                  دانش‌آموز مقطع {profile.grade || 'ناشناخته'} • رشته {profile.major || 'ناشناخته'}
                </>
              ) : (
                <>اطلاعات تکمیلی پروفایل را ثبت کنید.</>
              )}
            </CardDescription>
            <div className="flex flex-wrap justify-center md:justify-start gap-2 mt-4">
              <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium">
                {user.isVerified ? 'حساب تایید شده' : 'حساب تایید نشده'}
              </span>
              {user.joinDate && (
                <span className="px-3 py-1 rounded-full bg-muted text-muted-foreground text-xs font-medium">
                  عضویت از {new Date(user.joinDate).toLocaleDateString('fa-IR')}
                </span>
              )}
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-8 space-y-8">
        {error && <div className="text-sm text-destructive">{error}</div>}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
          <div className="space-y-2.5">
            <Label htmlFor="first_name" className="text-sm font-semibold flex items-center gap-2 px-1">
              <User className="w-4 h-4 text-primary" />
              نام
            </Label>
            <Input
              id="first_name"
              value={profile.first_name}
              onChange={handleInputChange}
              className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all"
            />
          </div>

          <div className="space-y-2.5">
            <Label htmlFor="last_name" className="text-sm font-semibold flex items-center gap-2 px-1">
              <User className="w-4 h-4 text-primary" />
              نام خانوادگی
            </Label>
            <Input
              id="last_name"
              value={profile.last_name}
              onChange={handleInputChange}
              className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all"
            />
          </div>

          <div className="space-y-2.5">
            <Label htmlFor="email" className="text-sm font-semibold flex items-center gap-2 px-1">
              <Mail className="w-4 h-4 text-primary" />
              ایمیل
            </Label>
            <Input
              id="email"
              type="email"
              value={profile.email}
              onChange={handleInputChange}
              className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all"
            />
          </div>

          <div className="space-y-2.5">
            <Label htmlFor="phone" className="text-sm font-semibold flex items-center gap-2 px-1">
              <Phone className="w-4 h-4 text-primary" />
              شماره تماس
            </Label>
            <Input
              id="phone"
              type="tel"
              value={profile.phone}
              onChange={handleInputChange}
              className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all"
              dir="ltr"
              disabled
            />
          </div>

          <div className="space-y-2.5">
            <Label htmlFor="grade" className="text-sm font-semibold flex items-center gap-2 px-1">
              <GraduationCap className="w-4 h-4 text-primary" />
              پایه تحصیلی
            </Label>
            <Input
              id="grade"
              value={profile.grade}
              onChange={handleInputChange}
              className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all"
            />
          </div>

          <div className="space-y-2.5">
            <Label htmlFor="major" className="text-sm font-semibold flex items-center gap-2 px-1">
              <BookOpen className="w-4 h-4 text-primary" />
              رشته تحصیلی
            </Label>
            <Input
              id="major"
              value={profile.major}
              onChange={handleInputChange}
              className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all"
            />
          </div>
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
          onClick={handleSave}
          disabled={isLoading}
        >
          <Save className="w-4 h-4" />
          {isLoading ? 'ذخیره تغییرات...' : 'ذخیره تغییرات'}
        </Button>
      </CardFooter>
    </Card>
  );
}
