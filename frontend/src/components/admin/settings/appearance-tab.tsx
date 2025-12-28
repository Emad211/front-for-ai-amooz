'use client';

import { Moon, Sun, Monitor, Languages, Type } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export function AppearanceTab() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>تم و ظاهر</CardTitle>
          <CardDescription>
            ظاهر پنل مدیریت را شخصی‌سازی کنید
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <Label>تم سیستم</Label>
            <RadioGroup defaultValue="system" className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <RadioGroupItem value="light" id="light" className="peer sr-only" />
                <Label
                  htmlFor="light"
                  className="flex flex-col items-center justify-between rounded-xl border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary cursor-pointer transition-all"
                >
                  <Sun className="mb-3 h-6 w-6" />
                  <span className="font-medium">روشن</span>
                </Label>
              </div>
              <div>
                <RadioGroupItem value="dark" id="dark" className="peer sr-only" />
                <Label
                  htmlFor="dark"
                  className="flex flex-col items-center justify-between rounded-xl border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary cursor-pointer transition-all"
                >
                  <Moon className="mb-3 h-6 w-6" />
                  <span className="font-medium">تاریک</span>
                </Label>
              </div>
              <div>
                <RadioGroupItem value="system" id="system" className="peer sr-only" />
                <Label
                  htmlFor="system"
                  className="flex flex-col items-center justify-between rounded-xl border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary cursor-pointer transition-all"
                >
                  <Monitor className="mb-3 h-6 w-6" />
                  <span className="font-medium">سیستم</span>
                </Label>
              </div>
            </RadioGroup>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Languages className="w-4 h-4 text-muted-foreground" />
                <Label>زبان پنل</Label>
              </div>
              <Select defaultValue="fa">
                <SelectTrigger className="rounded-xl">
                  <SelectValue placeholder="انتخاب زبان" />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  <SelectItem value="fa">فارسی (RTL)</SelectItem>
                  <SelectItem value="en">English (LTR)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Type className="w-4 h-4 text-muted-foreground" />
                <Label>اندازه فونت</Label>
              </div>
              <Select defaultValue="medium">
                <SelectTrigger className="rounded-xl">
                  <SelectValue placeholder="اندازه فونت" />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  <SelectItem value="small">کوچک</SelectItem>
                  <SelectItem value="medium">متوسط</SelectItem>
                  <SelectItem value="large">بزرگ</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}