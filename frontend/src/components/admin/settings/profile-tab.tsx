'use client';

import { useState } from 'react';
import { User, Mail, Phone, MapPin, Camera, Trash2, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Textarea } from '@/components/ui/textarea';

export function ProfileTab() {
  const [profile, setProfile] = useState({
    name: 'مدیر سیستم',
    email: 'admin@ai-amooz.ir',
    phone: '09121234567',
    bio: 'مدیر و مدرس پلتفرم AI-Amooz',
    location: 'تهران، ایران',
  });

  const handleSaveProfile = () => {
    console.log('Saving profile:', profile);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>تصویر پروفایل</CardTitle>
          <CardDescription>
            تصویر پروفایل خود را بارگذاری کنید
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col sm:flex-row items-center gap-6">
          <Avatar className="h-24 w-24 border-2 border-muted">
            <AvatarImage src="" alt="Profile" />
            <AvatarFallback className="text-2xl bg-primary/5 text-primary">م</AvatarFallback>
          </Avatar>
          <div className="flex flex-wrap justify-center sm:justify-start gap-2">
            <Button variant="outline" size="sm" className="rounded-xl">
              <Camera className="w-4 h-4 ml-2" />
              انتخاب تصویر
            </Button>
            <Button variant="outline" size="sm" className="text-destructive hover:text-destructive rounded-xl">
              <Trash2 className="w-4 h-4 ml-2" />
              حذف
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>اطلاعات شخصی</CardTitle>
          <CardDescription>
            اطلاعات شخصی خود را ویرایش کنید
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">نام و نام خانوادگی</Label>
              <div className="relative">
                <User className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="name"
                  value={profile.name}
                  onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                  className="pr-10"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">ایمیل</Label>
              <div className="relative">
                <Mail className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  value={profile.email}
                  onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                  className="pr-10"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="phone">شماره تماس</Label>
              <div className="relative">
                <Phone className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="phone"
                  value={profile.phone}
                  onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                  className="pr-10"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="location">موقعیت مکانی</Label>
              <div className="relative">
                <MapPin className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="location"
                  value={profile.location}
                  onChange={(e) => setProfile({ ...profile, location: e.target.value })}
                  className="pr-10"
                />
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="bio">درباره من</Label>
            <Textarea
              id="bio"
              value={profile.bio}
              onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
              rows={4}
              className="resize-none"
            />
          </div>

          <Button onClick={handleSaveProfile} className="w-full md:w-auto">
            <Save className="w-4 h-4 ml-2" />
            ذخیره تغییرات
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}