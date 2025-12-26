
'use client';

import { useState } from 'react';
import { AdminHeader as Header } from '@/components/layout/header';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Camera } from 'lucide-react';

export default function ProfilePage() {
  const [profile, setProfile] = useState({
    username: 'alireza_student',
    grade: 'دوازدهم',
    major: 'ریاضی فیزیک',
    email: 'ali.rezaei@example.com',
    phone: '09123456789',
    avatar: 'https://picsum.photos/seed/user/100/100',
  });

  const handleInputChange = (e) => {
    const { id, value } = e.target;
    setProfile((prev) => ({ ...prev, [id]: value }));
  };

  return (
    <div className="bg-background text-foreground min-h-screen">
      <Header />
      <main className="p-4 md:p-8">
        <div className="max-w-4xl mx-auto space-y-8">
          <div>
            <h1 className="text-4xl font-bold text-foreground mb-2">پروفایل کاربری</h1>
            <p className="text-muted-foreground mb-8">اطلاعات حساب کاربری خود را مدیریت کنید.</p>
          </div>

          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle>اطلاعات شخصی</CardTitle>
              <CardDescription>این اطلاعات در حساب شما نمایش داده می‌شود.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-6">
                <div className="relative">
                  <Avatar className="h-24 w-24 border-4 border-primary/50">
                    <AvatarImage src={profile.avatar} alt={profile.username} />
                    <AvatarFallback>{profile.username.substring(0, 2).toUpperCase()}</AvatarFallback>
                  </Avatar>
                  <Button size="icon" className="absolute -bottom-2 -right-2 rounded-full h-8 w-8 bg-primary hover:bg-primary/90">
                    <Camera className="h-4 w-4" />
                  </Button>
                </div>
                <div className='flex-grow'>
                    <Label htmlFor="username" className='text-muted-foreground'>نام کاربری</Label>
                    <Input id="username" value={profile.username} onChange={handleInputChange} className="mt-2 bg-input border-border h-12" />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label htmlFor="grade">پایه تحصیلی</Label>                  <Input id="grade" value={profile.grade} onChange={handleInputChange} className="bg-input border-border h-12" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="major">رشته</Label>
                  <Input id="major" value={profile.major} onChange={handleInputChange} className="bg-input border-border h-12" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">ایمیل</Label>
                  <Input id="email" type="email" value={profile.email} onChange={handleInputChange} className="bg-input border-border h-12" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phone">شماره تماس</Label>
                  <Input id="phone" type="tel" value={profile.phone} onChange={handleInputChange} className="bg-input border-border h-12" />
                </div>
              </div>
            </CardContent>
            <CardFooter className="border-t border-border px-6 py-4 flex justify-end gap-4">
              <Button variant="outline" className='h-11'>انصراف</Button>
              <Button className="bg-primary hover:bg-primary/90 h-11">ذخیره تغییرات</Button>
            </CardFooter>
          </Card>
        </div>
      </main>
    </div>
  );
}
