'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Camera, User, Mail, Phone, GraduationCap, BookOpen, Save, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export function ProfileForm() {
  const [profile, setProfile] = useState({
    username: 'alireza_student',
    grade: 'دوازدهم',
    major: 'ریاضی فیزیک',
    email: 'ali.rezaei@example.com',
    phone: '09123456789',
    avatar: 'https://picsum.photos/seed/user/100/100',
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { id, value } = e.target;
    setProfile((prev) => ({ ...prev, [id]: value }));
  };

  return (
    <Card className="border-none shadow-xl shadow-foreground/5 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden">
      <CardHeader className="pb-8 pt-10 px-8 border-b border-border/50 bg-muted/30">
        <div className="flex flex-col md:flex-row items-center gap-8">
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-tr from-primary to-primary/30 rounded-full blur opacity-25 group-hover:opacity-50 transition duration-500"></div>
            <Avatar className="h-32 w-32 border-4 border-background relative">
              <AvatarImage src={profile.avatar} alt={profile.username} />
              <AvatarFallback className="text-2xl bg-primary/10 text-primary">
                {profile.username.substring(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <Button 
              size="icon" 
              className="absolute bottom-1 right-1 rounded-full h-10 w-10 bg-primary hover:bg-primary/90 shadow-lg border-4 border-background transition-transform hover:scale-110"
            >
              <Camera className="h-5 w-5" />
            </Button>
          </div>
          
          <div className="text-center md:text-right space-y-2">
            <CardTitle className="text-2xl font-bold">{profile.username}</CardTitle>
            <CardDescription className="text-base">
              دانش‌آموز مقطع {profile.grade} • رشته {profile.major}
            </CardDescription>
            <div className="flex flex-wrap justify-center md:justify-start gap-2 mt-4">
              <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium">حساب تایید شده</span>
              <span className="px-3 py-1 rounded-full bg-muted text-muted-foreground text-xs font-medium">عضویت از دی ۱۴۰۲</span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-8 space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
          {/* Username */}
          <div className="space-y-2.5">
            <Label htmlFor="username" className="text-sm font-semibold flex items-center gap-2 px-1">
              <User className="w-4 h-4 text-primary" />
              نام کاربری
            </Label>
            <Input 
              id="username" 
              value={profile.username} 
              onChange={handleInputChange} 
              className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all" 
            />
          </div>

          {/* Email */}
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

          {/* Phone */}
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
            />
          </div>

          {/* Grade */}
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

          {/* Major */}
          <div className="space-y-2.5 md:col-span-2">
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
        <Button variant="ghost" className="h-12 px-8 rounded-xl font-semibold gap-2 order-2 sm:order-1">
          <X className="w-4 h-4" />
          انصراف
        </Button>
        <Button className="h-12 px-10 rounded-xl font-semibold gap-2 bg-primary hover:bg-primary/90 shadow-lg shadow-primary/20 order-1 sm:order-2">
          <Save className="w-4 h-4" />
          ذخیره تغییرات
        </Button>
      </CardFooter>
    </Card>
  );
}
