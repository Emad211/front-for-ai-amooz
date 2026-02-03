'use client';

import React, { useState } from 'react';
import { Shield, Key, Smartphone, LogOut, CheckCircle2, Lock, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

import { useTeacherSettings } from '@/hooks/use-teacher-settings';

interface SecurityTabProps {
useSettings?: typeof useTeacherSettings;
}

export function SecurityTab({ useSettings = useTeacherSettings }: SecurityTabProps) {
const { security, updateSecurity, isLoading } = useSettings();
const [showSuccessDialog, setShowSuccessDialog] = useState(false);
const [passwordState, setPasswordState] = useState({
current: '',
new: '',
confirm: ''
});

const handleUpdatePassword = async () => {
// Mock logic for password update
if (!passwordState.current || !passwordState.new || !passwordState.confirm) return;

try {
// Simulate API call
await new Promise(resolve => setTimeout(resolve, 800));
setShowSuccessDialog(true);
setPasswordState({ current: '', new: '', confirm: '' });
} catch (error) {
console.error('Failed to update password:', error);
}
};

return (
<div className="space-y-6 text-right">
<Card className="border-none shadow-xl shadow-foreground/5 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden">
<CardHeader className="pb-8 pt-10 px-8 border-b border-border/50 bg-muted/30">
<CardTitle className="text-2xl font-bold flex items-center justify-end gap-2">
تغییر رمز عبور
<Key className="w-6 h-6 text-primary" />
</CardTitle>
<CardDescription className="text-base text-muted-foreground">
رمز عبور خود را به صورت دوره‌ای تغییر دهید تا امنیت حسابتان حفظ شود
</CardDescription>
</CardHeader>
<CardContent className="p-8 space-y-6">
<div className="space-y-2.5">
<Label htmlFor="current-password" className="pb-1 text-sm font-semibold flex items-center gap-2 px-1 justify-end">
رمز عبور فعلی
<Lock className="w-4 h-4 text-primary" />
</Label>
<Input 
id="current-password" 
type="password" 
value={passwordState.current}
onChange={(e) => setPasswordState(prev => ({ ...prev, current: e.target.value }))}
className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all text-left"
dir="ltr"
/>
</div>
<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
<div className="space-y-2.5">
<Label htmlFor="new-password" className="pb-1 text-sm font-semibold flex items-center gap-2 px-1 justify-end">
رمز عبور جدید
<Key className="w-4 h-4 text-primary" />
</Label>
<Input 
id="new-password" 
type="password" 
value={passwordState.new}
onChange={(e) => setPasswordState(prev => ({ ...prev, new: e.target.value }))}
className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all text-left"
dir="ltr"
/>
</div>
<div className="space-y-2.5">
<Label htmlFor="confirm-password" className="pb-1 text-sm font-semibold flex items-center gap-2 px-1 justify-end">
تکرار رمز عبور جدید
<Key className="w-4 h-4 text-primary" />
</Label>
<Input 
id="confirm-password" 
type="password" 
value={passwordState.confirm}
onChange={(e) => setPasswordState(prev => ({ ...prev, confirm: e.target.value }))}
className="bg-background/50 border-border/50 h-12 rounded-xl focus:ring-primary/20 focus:border-primary transition-all text-left"
dir="ltr"
/>
</div>
</div>
</CardContent>
<CardFooter className="p-8 pt-0 flex justify-end">
<Button 
onClick={handleUpdatePassword} 
disabled={isLoading || !passwordState.new} 
className="h-12 px-10 rounded-xl font-semibold gap-2 bg-primary hover:bg-primary/90 shadow-lg shadow-primary/20"
>
<Save className="w-4 h-4" />
{isLoading ? 'در حال به‌روزرسانی...' : 'به‌روزرسانی رمز عبور'}
</Button>
</CardFooter>
</Card>

<Card className="border-none shadow-xl shadow-foreground/5 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden">
<CardHeader className="pb-8 pt-10 px-8 border-b border-border/50 bg-muted/30">
<CardTitle className="text-2xl font-bold flex items-center justify-end gap-2">
امنیت حساب کاربری
<Shield className="w-6 h-6 text-primary" />
</CardTitle>
<CardDescription className="text-base text-muted-foreground">
تنظیمات امنیتی پیشرفته برای محافظت بیشتر از حساب شما
</CardDescription>
</CardHeader>
<CardContent className="p-8 space-y-8">
<div className="flex items-center justify-between gap-4">
<Switch 
checked={security.twoFactorEnabled} 
onCheckedChange={(checked) => updateSecurity({ twoFactorEnabled: checked })}
/>
<div className="space-y-1 text-right">
<div className="flex items-center gap-2 justify-end">
<Label className="text-base font-bold">تایید دو مرحله‌ای</Label>
<Smartphone className="w-4 h-4 text-primary" />
</div>
<p className="text-sm text-muted-foreground">
امنیت حساب خود را با تایید دو مرحله‌ای پیامکی افزایش دهید
</p>
</div>
</div>

<div className="flex items-center justify-between gap-4">
<Switch defaultChecked />
<div className="space-y-1 text-right">
<div className="flex items-center gap-2 justify-end">
<Label className="text-base font-bold">هشدار ورود</Label>
<Shield className="w-4 h-4 text-primary" />
</div>
<p className="text-sm text-muted-foreground">
در صورت ورود از دستگاه‌های جدید، از طریق ایمیل به من اطلاع بده
</p>
</div>
</div>

<div className="pt-6 border-t border-border/50 flex justify-end">
<Button variant="outline" className="h-12 px-6 text-destructive hover:text-destructive hover:bg-destructive/10 rounded-xl gap-2 border-destructive/20 transition-all font-semibold">
<LogOut className="w-4 h-4" />
خروج از تمامی دستگاه‌ها
</Button>
</div>
</CardContent>
</Card>

{/* Success Dialog */}
<Dialog open={showSuccessDialog} onOpenChange={setShowSuccessDialog}>
<DialogContent className="sm:max-w-md">
<DialogHeader>
<div className="mx-auto w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center mb-4">
<CheckCircle2 className="w-6 h-6 text-green-600 dark:text-green-400" />
</div>
<DialogTitle className="text-center font-bold text-xl">رمز عبور با موفقیت تغییر کرد</DialogTitle>
<DialogDescription className="text-center text-base">
از این پس می‌توانید با رمز عبور جدید وارد شوید.
</DialogDescription>
</DialogHeader>
<DialogFooter className="sm:justify-center">
<Button onClick={() => setShowSuccessDialog(false)} className="rounded-xl px-8">
متوجه شدم
</Button>
</DialogFooter>
</DialogContent>
</Dialog>
</div>
);
}
