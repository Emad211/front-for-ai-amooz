'use client';

import { Shield, Key, Smartphone, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';

import { useTeacherSettings } from '@/hooks/use-teacher-settings';

interface SecurityTabProps {
  useSettings?: typeof useTeacherSettings;
}

export function SecurityTab({ useSettings = useTeacherSettings }: SecurityTabProps) {
  const { security, updateSecurity, isLoading } = useSettings();
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>تغییر رمز عبور</CardTitle>
          <CardDescription>
            رمز عبور خود را به صورت دوره‌ای تغییر دهید
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="current-password">رمز عبور فعلی</Label>
            <Input id="current-password" type="password" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="new-password">رمز عبور جدید</Label>
              <Input id="new-password" type="password" className="rounded-xl" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">تکرار رمز عبور جدید</Label>
              <Input id="confirm-password" type="password" className="rounded-xl" />
            </div>
          </div>
          <div className="flex justify-start">
            <Button disabled={isLoading} className="w-full sm:w-auto rounded-xl">
              {isLoading ? 'در حال به‌روزرسانی...' : 'به‌روزرسانی رمز عبور'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>امنیت حساب کاربری</CardTitle>
          <CardDescription>
            تنظیمات امنیتی پیشرفته
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-muted-foreground" />
                <Label className="text-base">تایید دو مرحله‌ای</Label>
              </div>
              <p className="text-sm text-muted-foreground">
                امنیت حساب خود را با تایید دو مرحله‌ای افزایش دهید
              </p>
            </div>
            <Switch 
              checked={security.twoFactorEnabled} 
              onCheckedChange={(checked) => updateSecurity({ twoFactorEnabled: checked })}
            />
          </div>
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-muted-foreground" />
                <Label className="text-base">ورودهای ناشناس</Label>
              </div>
              <p className="text-sm text-muted-foreground">
                در صورت ورود از دستگاه‌های جدید به من اطلاع بده
              </p>
            </div>
            <Switch defaultChecked />
          </div>
          <div className="pt-4 border-t flex justify-start">
            <Button variant="outline" className="w-full sm:w-auto text-destructive hover:text-destructive rounded-xl gap-2">
              <LogOut className="w-4 h-4" />
              خروج از تمامی دستگاه‌ها
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}