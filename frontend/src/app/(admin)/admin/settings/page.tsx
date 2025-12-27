'use client';

import { Settings, User, Shield, Bell, Palette } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProfileTab } from '@/components/admin/settings/profile-tab';
import { SecurityTab } from '@/components/admin/settings/security-tab';
import { NotificationsTab } from '@/components/admin/settings/notifications-tab';
import { AppearanceTab } from '@/components/admin/settings/appearance-tab';

export default function AdminSettingsPage() {
  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">تنظیمات</h1>
          <p className="text-muted-foreground mt-1">
            مدیریت حساب کاربری و تنظیمات پنل مدیریت
          </p>
        </div>
        <div className="bg-primary/10 p-3 rounded-full">
          <Settings className="w-6 h-6 text-primary" />
        </div>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4 h-auto p-1 bg-muted/50">
          <TabsTrigger value="profile" className="py-3 gap-2">
            <User className="w-4 h-4" />
            <span className="hidden md:inline">پروفایل</span>
          </TabsTrigger>
          <TabsTrigger value="security" className="py-3 gap-2">
            <Shield className="w-4 h-4" />
            <span className="hidden md:inline">امنیت</span>
          </TabsTrigger>
          <TabsTrigger value="notifications" className="py-3 gap-2">
            <Bell className="w-4 h-4" />
            <span className="hidden md:inline">اعلان‌ها</span>
          </TabsTrigger>
          <TabsTrigger value="appearance" className="py-3 gap-2">
            <Palette className="w-4 h-4" />
            <span className="hidden md:inline">ظاهر</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <ProfileTab />
        </TabsContent>

        <TabsContent value="security">
          <SecurityTab />
        </TabsContent>

        <TabsContent value="notifications">
          <NotificationsTab />
        </TabsContent>

        <TabsContent value="appearance">
          <AppearanceTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
