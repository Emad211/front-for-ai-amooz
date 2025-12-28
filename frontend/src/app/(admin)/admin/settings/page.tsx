'use client';

import { Settings, User, Shield, Bell, Palette } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProfileTab } from '@/components/admin/settings/profile-tab';
import { SecurityTab } from '@/components/admin/settings/security-tab';
import { NotificationsTab } from '@/components/admin/settings/notifications-tab';
import { AppearanceTab } from '@/components/admin/settings/appearance-tab';

export default function AdminSettingsPage() {
  return (
    <div className="space-y-6 max-w-4xl mx-auto" dir="rtl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-black text-foreground">تنظیمات</h1>
          <p className="text-muted-foreground text-sm mt-1">
            مدیریت حساب کاربری و تنظیمات پنل مدیریت
          </p>
        </div>
        <div className="hidden sm:flex bg-primary/10 p-3 rounded-2xl">
          <Settings className="w-6 h-6 text-primary" />
        </div>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <div className="overflow-x-auto pb-1 -mx-1 px-1">
          <TabsList className="flex w-full min-w-[400px] sm:min-w-0 sm:grid sm:grid-cols-4 h-auto p-1 bg-muted/50 rounded-xl">
            <TabsTrigger value="profile" className="flex-1 py-2.5 gap-2 rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              <User className="w-4 h-4" />
              <span className="text-xs sm:text-sm">پروفایل</span>
            </TabsTrigger>
            <TabsTrigger value="security" className="flex-1 py-2.5 gap-2 rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              <Shield className="w-4 h-4" />
              <span className="text-xs sm:text-sm">امنیت</span>
            </TabsTrigger>
            <TabsTrigger value="notifications" className="flex-1 py-2.5 gap-2 rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              <Bell className="w-4 h-4" />
              <span className="text-xs sm:text-sm">اعلان‌ها</span>
            </TabsTrigger>
            <TabsTrigger value="appearance" className="flex-1 py-2.5 gap-2 rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              <Palette className="w-4 h-4" />
              <span className="text-xs sm:text-sm">ظاهر</span>
            </TabsTrigger>
          </TabsList>
        </div>

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
