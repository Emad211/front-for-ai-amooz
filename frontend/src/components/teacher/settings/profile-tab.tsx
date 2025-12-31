'use client';

import { User, Mail, Phone, MapPin, Camera, Trash2, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Textarea } from '@/components/ui/textarea';

import { useTeacherSettings } from '@/hooks/use-teacher-settings';

interface ProfileTabProps {
  useSettings?: typeof useTeacherSettings;
}

export function ProfileTab({ useSettings = useTeacherSettings }: ProfileTabProps) {
  const { profile, updateProfile, isLoading } = useSettings();

  const handleSaveProfile = () => {
    updateProfile(profile);
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
            <AvatarImage src={profile.avatar} alt="Profile" />
            <AvatarFallback className="text-2xl bg-primary/5 text-primary">
              {profile.name[0]}
            </AvatarFallback>
          </Avatar>
          <div className="flex flex-wrap justify-center sm:justify-start gap-2">
            <Button variant="outline" size="sm" className="rounded-xl">
              <Camera className="w-4 h-4 me-2" />
              انتخاب تصویر
            </Button>
            <Button variant="outline" size="sm" className="text-destructive hover:text-destructive rounded-xl">
              <Trash2 className="w-4 h-4 me-2" />
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
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="name"
                  value={profile.name}
                  onChange={(e) => updateProfile({ name: e.target.value })}
                  className="pl-10"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">ایمیل</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  value={profile.email}
                  onChange={(e) => updateProfile({ email: e.target.value })}
                  className="pl-10"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="phone">شماره تماس</Label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="phone"
                  value={profile.phone}
                  onChange={(e) => updateProfile({ phone: e.target.value })}
                  className="pl-10"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="location">موقعیت مکانی</Label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="location"
                  value={profile.location}
                  onChange={(e) => updateProfile({ location: e.target.value })}
                  className="pl-10"
                />
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="bio">درباره من</Label>
            <Textarea
              id="bio"
              value={profile.bio}
              onChange={(e) => updateProfile({ bio: e.target.value })}
              rows={4}
              className="resize-none"
            />
          </div>

          <div className="flex justify-start">
            <Button onClick={handleSaveProfile} disabled={isLoading} className="w-full md:w-auto gap-2">
              <Save className="w-4 h-4" />
              {isLoading ? 'در حال ذخیره...' : 'ذخیره تغییرات'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}