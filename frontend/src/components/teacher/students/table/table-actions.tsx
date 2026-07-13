'use client';

import { useEffect, useState } from 'react';
import { MoreVertical, Eye, Mail, Ban, Trash2, RotateCcw, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import type { Student, TeacherStudentProfile } from '@/types';
import { TeacherService } from '@/services/teacher-service';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Progress } from '@/components/ui/progress';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';

type Action = 'profile' | 'message' | 'access' | 'remove' | null;

export function StudentTableActions({ student, onChanged }: { student: Student; onChanged?: () => void }) {
  const [action, setAction] = useState<Action>(null);
  const [profile, setProfile] = useState<TeacherStudentProfile | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [working, setWorking] = useState(false);
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [sendSms, setSendSms] = useState(false);
  const [reason, setReason] = useState('');

  useEffect(() => {
    if (action !== 'profile' || profile) return;
    setLoadingProfile(true);
    TeacherService.getStudentProfile(student.id)
      .then(setProfile)
      .catch((error) => toast.error(error instanceof Error ? error.message : 'پروفایل دریافت نشد.'))
      .finally(() => setLoadingProfile(false));
  }, [action, profile, student.id]);

  const close = () => setAction(null);

  const sendDirectMessage = async () => {
    if (!title.trim() || !message.trim()) return toast.error('موضوع و متن پیام را کامل کنید.');
    setWorking(true);
    try {
      await TeacherService.sendTeacherBroadcast({
        title: title.trim(), message: message.trim(), recipientPhones: [student.phone], sendSms,
      });
      toast.success('پیام برای دانش‌آموز ارسال شد.');
      close();
      setTitle(''); setMessage(''); setSendSms(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'پیام ارسال نشد. دوباره تلاش کنید.');
    } finally { setWorking(false); }
  };

  const updateAccess = async () => {
    const restoring = student.status === 'suspended';
    setWorking(true);
    try {
      await TeacherService.setStudentAccess(student.id, restoring ? 'active' : 'suspended', reason);
      toast.success(restoring ? 'دسترسی دانش‌آموز بازگردانده شد.' : 'دسترسی دانش‌آموز تعلیق شد.');
      close(); setReason(''); onChanged?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'تغییر دسترسی انجام نشد.');
    } finally { setWorking(false); }
  };

  const removeStudent = async () => {
    setWorking(true);
    try {
      await TeacherService.removeStudentRelationship(student.id);
      toast.success('دانش‌آموز از کلاس‌های شخصی شما حذف شد.');
      close(); onChanged?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'حذف دانش‌آموز انجام نشد.');
    } finally { setWorking(false); }
  };

  const suspended = student.status === 'suspended';
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="باز کردن گزینه‌های دانش‌آموز">
            <MoreVertical className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-52 text-right">
          <DropdownMenuItem className="gap-2" onSelect={() => setAction('profile')}><Eye className="h-4 w-4" />مشاهده پروفایل</DropdownMenuItem>
          <DropdownMenuItem className="gap-2" onSelect={() => setAction('message')}><Mail className="h-4 w-4" />ارسال پیام مستقیم</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="gap-2" onSelect={() => setAction('access')}>
            {suspended ? <RotateCcw className="h-4 w-4" /> : <Ban className="h-4 w-4" />}
            {suspended ? 'بازگردانی دسترسی' : 'تعلیق از کلاس‌های من'}
          </DropdownMenuItem>
          <DropdownMenuItem className="gap-2 text-destructive focus:text-destructive" onSelect={() => setAction('remove')}>
            <Trash2 className="h-4 w-4" />حذف از کلاس‌های من
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Sheet open={action === 'profile'} onOpenChange={(open) => !open && close()}>
        <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
          <SheetHeader className="text-start"><SheetTitle>پروفایل دانش‌آموز</SheetTitle><SheetDescription>اطلاعات و عملکرد در کلاس‌های شما</SheetDescription></SheetHeader>
          {loadingProfile ? <div className="flex justify-center py-16"><Loader2 className="animate-spin" /></div> : profile && (
            <div className="mt-6 space-y-6 text-start">
              <div className="rounded-xl border bg-muted/30 p-4">
                <p className="text-lg font-bold">{profile.name}</p>
                <p dir="ltr" className="mt-1 text-left text-sm text-muted-foreground">{profile.phone}</p>
                <p className="text-sm text-muted-foreground">{profile.email || 'ایمیل ثبت نشده'}</p>
                <p className="mt-2 text-sm">{[profile.grade, profile.major].filter(Boolean).join(' · ') || 'اطلاعات تحصیلی تکمیل نشده'}</p>
              </div>
              <div className="space-y-3">
                <h3 className="font-bold">کلاس‌های این معلم</h3>
                {profile.classes.map((course) => <div key={course.id} className="rounded-xl border p-3">
                  <div className="flex justify-between gap-3"><span className="font-medium">{course.title}</span><span className="text-sm">{course.progress}٪</span></div>
                  <Progress value={course.progress} className="mt-2" />
                  <p className="mt-2 text-xs text-muted-foreground">میانگین نمره: {course.averageScore}</p>
                </div>)}
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Dialog open={action === 'message'} onOpenChange={(open) => !open && close()}>
        <DialogContent className="sm:max-w-lg"><DialogHeader className="text-start"><DialogTitle>پیام مستقیم به {student.name}</DialogTitle><DialogDescription>این پیام فقط برای همین دانش‌آموز ارسال می‌شود.</DialogDescription></DialogHeader>
          <div className="space-y-4 text-start"><div><label className="mb-2 block text-sm font-medium">موضوع پیام</label><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="مثلاً یادآوری تمرین فصل دوم" /></div>
          <div><label className="mb-2 block text-sm font-medium">متن پیام</label><Textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="پیام خود را روشن و کوتاه بنویسید." rows={5} /></div>
          <div className="flex items-center justify-between rounded-xl border p-3"><span className="text-sm">ارسال پیامک هم انجام شود</span><Switch checked={sendSms} onCheckedChange={setSendSms} /></div></div>
          <DialogFooter><Button variant="outline" onClick={close}>انصراف</Button><Button onClick={sendDirectMessage} disabled={working}>{working && <Loader2 className="h-4 w-4 animate-spin" />}ارسال پیام</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={action === 'access'} onOpenChange={(open) => !open && close()}>
        <AlertDialogContent><AlertDialogHeader className="text-start"><AlertDialogTitle>{suspended ? 'دسترسی دانش‌آموز بازگردانده شود؟' : 'دسترسی دانش‌آموز تعلیق شود؟'}</AlertDialogTitle><AlertDialogDescription>{suspended ? `${student.name} دوباره می‌تواند به کلاس‌های شخصی شما دسترسی داشته باشد.` : `${student.name} تا زمان بازگردانی، به کلاس‌های شخصی شما دسترسی نخواهد داشت. حساب کاربری او حذف نمی‌شود.`}</AlertDialogDescription></AlertDialogHeader>
          {!suspended && <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="دلیل تعلیق (اختیاری)" />}
          <AlertDialogFooter><AlertDialogCancel>انصراف</AlertDialogCancel><AlertDialogAction onClick={(e) => { e.preventDefault(); void updateAccess(); }} disabled={working}>{suspended ? 'بازگردانی دسترسی' : 'تعلیق دسترسی'}</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={action === 'remove'} onOpenChange={(open) => !open && close()}>
        <AlertDialogContent><AlertDialogHeader className="text-start"><AlertDialogTitle>دانش‌آموز از کلاس‌های شخصی شما حذف شود؟</AlertDialogTitle><AlertDialogDescription>{student.name} از کلاس‌های شخصی شما حذف می‌شود، اما حساب کاربری و سوابق آموزشی او پاک نخواهد شد.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>انصراف</AlertDialogCancel><AlertDialogAction onClick={(e) => { e.preventDefault(); void removeStudent(); }} disabled={working} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">حذف از کلاس‌های من</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
