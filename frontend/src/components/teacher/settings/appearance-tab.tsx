'use client';

import { Moon, Sun, Monitor, Languages, Type, Palette } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export function AppearanceTab() {
return (
<div className="space-y-6 text-right">
<Card className="border-none shadow-xl shadow-foreground/5 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden">
<CardHeader className="pb-8 pt-10 px-8 border-b border-border/50 bg-muted/30">
<CardTitle className="text-2xl font-bold flex items-center justify-end gap-2">
تم و ظاهر پنل
<Palette className="w-6 h-6 text-primary" />
</CardTitle>
<CardDescription className="text-base text-muted-foreground">
ظاهر پنل مدیریت خود را مطابق سلیقه و نیاز خود شخصی‌سازی کنید
</CardDescription>
</CardHeader>
<CardContent className="p-8 space-y-10">
<div className="space-y-6">
<div className="flex items-center justify-end gap-2 px-1">
<Label className="text-lg font-bold">تم سیستم</Label>
<Monitor className="w-5 h-5 text-primary" />
</div>
<RadioGroup defaultValue="system" className="grid grid-cols-1 sm:grid-cols-3 gap-6">
<div>
<RadioGroupItem value="light" id="light" className="peer sr-only" />
<Label
htmlFor="light"
className="flex flex-col items-center justify-center rounded-2xl border-2 border-muted bg-popover/50 p-6 hover:bg-accent/50 hover:text-accent-foreground peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5 [&:has([data-state=checked])]:border-primary cursor-pointer transition-all duration-300 shadow-sm"
>
<Sun className="mb-3 h-8 w-8 text-orange-400" />
<span className="font-bold text-base">روشن</span>
</Label>
</div>
<div>
<RadioGroupItem value="dark" id="dark" className="peer sr-only" />
<Label
htmlFor="dark"
className="flex flex-col items-center justify-center rounded-2xl border-2 border-muted bg-popover/50 p-6 hover:bg-accent/50 hover:text-accent-foreground peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5 [&:has([data-state=checked])]:border-primary cursor-pointer transition-all duration-300 shadow-sm"
>
<Moon className="mb-3 h-8 w-8 text-indigo-400" />
<span className="font-bold text-base">تاریک</span>
</Label>
</div>
<div>
<RadioGroupItem value="system" id="system" className="peer sr-only" />
<Label
htmlFor="system"
className="flex flex-col items-center justify-center rounded-2xl border-2 border-muted bg-popover/50 p-6 hover:bg-accent/50 hover:text-accent-foreground peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5 [&:has([data-state=checked])]:border-primary cursor-pointer transition-all duration-300 shadow-sm"
>
<Monitor className="mb-3 h-8 w-8 text-primary" />
<span className="font-bold text-base">سیستم</span>
</Label>
</div>
</RadioGroup>
</div>

<div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-10 border-t border-border/50">
<div className="space-y-3 text-right">
<div className="flex items-center gap-2 justify-end px-1">
<Label className="text-base font-bold">زبان پنل</Label>
<Languages className="w-4 h-4 text-primary" />
</div>
<Select defaultValue="fa">
<SelectTrigger className="h-12 rounded-xl bg-background/50 border-border/50 focus:ring-primary/20 transition-all font-medium">
<SelectValue placeholder="انتخاب زبان" />
</SelectTrigger>
<SelectContent className="rounded-xl">
<SelectItem value="fa" className="font-medium">فارسی (RTL)</SelectItem>
<SelectItem value="en" className="font-medium">English (LTR)</SelectItem>
</SelectContent>
</Select>
</div>
<div className="space-y-3 text-right">
<div className="flex items-center gap-2 justify-end px-1">
<Label className="text-base font-bold">اندازه فونت</Label>
<Type className="w-4 h-4 text-primary" />
</div>
<Select defaultValue="medium">
<SelectTrigger className="h-12 rounded-xl bg-background/50 border-border/50 focus:ring-primary/20 transition-all font-medium">
<SelectValue placeholder="اندازه فونت" />
</SelectTrigger>
<SelectContent className="rounded-xl">
<SelectItem value="small" className="font-medium">کوچک</SelectItem>
<SelectItem value="medium" className="font-medium">متوسط</SelectItem>
<SelectItem value="large" className="font-medium">بزرگ</SelectItem>
</SelectContent>
</Select>
</div>
</div>
</CardContent>
</Card>
</div>
);
}
