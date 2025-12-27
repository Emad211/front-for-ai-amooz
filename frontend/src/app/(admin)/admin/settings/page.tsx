'use client';

import { useState } from 'react';
import { Save, User, Mail, Phone, MapPin, Lock, Bell, Shield, Eye, EyeOff, Camera, Trash2, Globe, Moon, Sun, Palette } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function SettingsPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  
  // Profile State
  const [profile, setProfile] = useState({
    name: 'مدیر سیستم',
    email: 'admin@ai-amooz.ir',
    phone: '09121234567',
    bio: 'مدیر و مدرس پلتفرم AI-Amooz',
    location: 'تهران، ایران',
  });

  // Notification Settings
  const [notifications, setNotifications] = useState({
    emailNotifications: true,
    newStudentAlert: true,
    classUpdateAlert: true,
    messageAlert: true,
    weeklyReport: false,
  });

  // Security Settings
  const [security, setSecurity] = useState({
    twoFactorAuth: false,
    loginAlerts: true,
    sessionTimeout: '30',
  });

  // Appearance Settings
  const [appearance, setAppearance] = useState({
    theme: 'system',
    language: 'fa',
    fontSize: 'medium',
  });

  const handleSaveProfile = () => {
    console.log('Saving profile:', profile);
    // Add save logic here
  };

  const handleSaveNotifications = () => {
    console.log('Saving notifications:', notifications);
    // Add save logic here
  };

  const handleSaveSecurity = () => {
    console.log('Saving security:', security);
    // Add save logic here
  };

  const handleSaveAppearance = () => {
    console.log('Saving appearance:', appearance);
    // Add save logic here
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">تنظیمات</h1>
        <p className="text-muted-foreground mt-1">
          مدیریت تنظیمات حساب کاربری و ترجیحات شما
        </p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4 lg:w-[600px]">
          <TabsTrigger value="profile">پروفایل</TabsTrigger>
          <TabsTrigger value="security">امنیت</TabsTrigger>
          <TabsTrigger value="notifications">اعلان‌ها</TabsTrigger>
          <TabsTrigger value="appearance">ظاهر</TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile" className="space-y-6">
          {/* Avatar Upload */}
          <Card>
            <CardHeader>
              <CardTitle>تصویر پروفایل</CardTitle>
              <CardDescription>
                تصویر پروفایل خود را بارگذاری کنید
              </CardDescription>
            </CardHeader>
            <CardContent className="flex items-center gap-6">
              <Avatar className="h-24 w-24">
                <AvatarImage src="/api/placeholder/100/100" alt="Profile" />
                <AvatarFallback className="text-2xl">م</AvatarFallback>
              </Avatar>
              <div className="flex gap-2">
                <Button variant="outline">
                  <Camera className="w-4 h-4 ml-2" />
                  انتخاب تصویر
                </Button>
                <Button variant="outline" className="text-destructive">
                  <Trash2 className="w-4 h-4 ml-2" />
                  حذف
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Personal Information */}
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
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-6">
          {/* Change Password */}
          <Card>
            <CardHeader>
              <CardTitle>تغییر رمز عبور</CardTitle>
              <CardDescription>
                برای امنیت بیشتر، رمز عبور قوی انتخاب کنید
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="current-password">رمز عبور فعلی</Label>
                <div className="relative">
                  <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="current-password"
                    type={showPassword ? "text" : "password"}
                    className="pr-10 pl-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="new-password">رمز عبور جدید</Label>
                <div className="relative">
                  <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="new-password"
                    type={showNewPassword ? "text" : "password"}
                    className="pr-10 pl-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm-password">تکرار رمز عبور جدید</Label>
                <div className="relative">
                  <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="confirm-password"
                    type="password"
                    className="pr-10"
                  />
                </div>
              </div>

              <Button className="w-full md:w-auto">
                <Save className="w-4 h-4 ml-2" />
                تغییر رمز عبور
              </Button>
            </CardContent>
          </Card>

          {/* Security Options */}
          <Card>
            <CardHeader>
              <CardTitle>تنظیمات امنیتی</CardTitle>
              <CardDescription>
                گزینه‌های امنیتی حساب کاربری خود را مدیریت کنید
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>احراز هویت دو مرحله‌ای</Label>
                  <p className="text-sm text-muted-foreground">
                    افزودن لایه امنیتی اضافی با احراز هویت دو مرحله‌ای
                  </p>
                </div>
                <Switch
                  checked={security.twoFactorAuth}
                  onCheckedChange={(checked) => setSecurity({ ...security, twoFactorAuth: checked })}
                />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>اعلان‌های ورود</Label>
                  <p className="text-sm text-muted-foreground">
                    دریافت اعلان در صورت ورود به حساب کاربری
                  </p>
                </div>
                <Switch
                  checked={security.loginAlerts}
                  onCheckedChange={(checked) => setSecurity({ ...security, loginAlerts: checked })}
                />
              </div>

              <Separator />

              <div className="space-y-2">
                <Label htmlFor="session-timeout">زمان انقضای نشست (دقیقه)</Label>
                <Select
                  value={security.sessionTimeout}
                  onValueChange={(value) => setSecurity({ ...security, sessionTimeout: value })}
                >
                  <SelectTrigger id="session-timeout">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="15">15 دقیقه</SelectItem>
                    <SelectItem value="30">30 دقیقه</SelectItem>
                    <SelectItem value="60">1 ساعت</SelectItem>
                    <SelectItem value="120">2 ساعت</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button onClick={handleSaveSecurity} className="w-full md:w-auto">
                <Save className="w-4 h-4 ml-2" />
                ذخیره تنظیمات
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>تنظیمات اعلان‌ها</CardTitle>
              <CardDescription>
                مدیریت اعلان‌های دریافتی
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>اعلان‌های ایمیل</Label>
                  <p className="text-sm text-muted-foreground">
                    دریافت اعلان‌ها از طریق ایمیل
                  </p>
                </div>
                <Switch
                  checked={notifications.emailNotifications}
                  onCheckedChange={(checked) => setNotifications({ ...notifications, emailNotifications: checked })}
                />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>اعلان دانش‌آموز جدید</Label>
                  <p className="text-sm text-muted-foreground">
                    اطلاع از ثبت‌نام دانش‌آموز جدید
                  </p>
                </div>
                <Switch
                  checked={notifications.newStudentAlert}
                  onCheckedChange={(checked) => setNotifications({ ...notifications, newStudentAlert: checked })}
                />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>اعلان به‌روزرسانی کلاس</Label>
                  <p className="text-sm text-muted-foreground">
                    اطلاع از تغییرات در کلاس‌ها
                  </p>
                </div>
                <Switch
                  checked={notifications.classUpdateAlert}
                  onCheckedChange={(checked) => setNotifications({ ...notifications, classUpdateAlert: checked })}
                />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>اعلان پیام جدید</Label>
                  <p className="text-sm text-muted-foreground">
                    دریافت اعلان برای پیام‌های جدید
                  </p>
                </div>
                <Switch
                  checked={notifications.messageAlert}
                  onCheckedChange={(checked) => setNotifications({ ...notifications, messageAlert: checked })}
                />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>گزارش هفتگی</Label>
                  <p className="text-sm text-muted-foreground">
                    دریافت گزارش عملکرد هفتگی
                  </p>
                </div>
                <Switch
                  checked={notifications.weeklyReport}
                  onCheckedChange={(checked) => setNotifications({ ...notifications, weeklyReport: checked })}
                />
              </div>

              <Button onClick={handleSaveNotifications} className="w-full md:w-auto mt-6">
                <Save className="w-4 h-4 ml-2" />
                ذخیره تنظیمات
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Appearance Tab */}
        <TabsContent value="appearance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>تنظیمات ظاهری</CardTitle>
              <CardDescription>
                ظاهر پلتفرم را سفارشی‌سازی کنید
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="theme">تم</Label>
                <Select
                  value={appearance.theme}
                  onValueChange={(value) => setAppearance({ ...appearance, theme: value })}
                >
                  <SelectTrigger id="theme">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">روشن</SelectItem>
                    <SelectItem value="dark">تیره</SelectItem>
                    <SelectItem value="system">پیش‌فرض سیستم</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Separator />

              <div className="space-y-2">
                <Label htmlFor="language">زبان</Label>
                <Select
                  value={appearance.language}
                  onValueChange={(value) => setAppearance({ ...appearance, language: value })}
                >
                  <SelectTrigger id="language">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fa">فارسی</SelectItem>
                    <SelectItem value="en">English</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Separator />

              <div className="space-y-2">
                <Label htmlFor="font-size">اندازه فونت</Label>
                <Select
                  value={appearance.fontSize}
                  onValueChange={(value) => setAppearance({ ...appearance, fontSize: value })}
                >
                  <SelectTrigger id="font-size">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="small">کوچک</SelectItem>
                    <SelectItem value="medium">متوسط</SelectItem>
                    <SelectItem value="large">بزرگ</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button onClick={handleSaveAppearance} className="w-full md:w-auto mt-6">
                <Save className="w-4 h-4 ml-2" />
                ذخیره تنظیمات
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}