'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader2, UserPlus } from 'lucide-react';
import { toast } from 'sonner';
import type { Course } from '@/types';
import { TeacherService } from '@/services/teacher-service';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';

export function AddStudentsDialog({ onCompleted }: { onCompleted?: () => void }) {
  const [open, setOpen] = useState(false);
  const [courses, setCourses] = useState<Course[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [phonesText, setPhonesText] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open || courses.length) return;
    setLoading(true);
    TeacherService.getCourses(null).then(setCourses).catch(() => toast.error('کلاس‌ها دریافت نشدند.')).finally(() => setLoading(false));
  }, [open, courses.length]);

  const phones = useMemo(() => Array.from(new Set(
    phonesText.split(/[\n,،\s]+/).map((value) => value.trim()).filter(Boolean),
  )), [phonesText]);

  const submit = async () => {
    if (!phones.length) return toast.error('حداقل یک شماره موبایل وارد کنید.');
    if (!selected.length) return toast.error('حداقل یک کلاس را انتخاب کنید.');
    setSubmitting(true);
    try {
      const result = await TeacherService.inviteStudentsToClasses(phones, selected);
      toast.success(result.createdCount ? 'دعوت‌ها ثبت شدند؛ دانش‌آموز پس از ورود به کلاس در فهرست اصلی دیده می‌شود.' : 'این دعوت‌ها قبلاً ثبت شده‌اند.');
      setOpen(false); setPhonesText(''); setSelected([]); onCompleted?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'دعوت ارسال نشد.');
    } finally { setSubmitting(false); }
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button size="sm" className="h-10 gap-2 rounded-xl"><UserPlus className="h-4 w-4" />افزودن به کلاس‌ها</Button></DialogTrigger>
    <DialogContent className="max-h-[85dvh] overflow-hidden sm:max-w-xl">
      <DialogHeader className="text-start"><DialogTitle>افزودن دانش‌آموز به کلاس‌ها</DialogTitle><DialogDescription>شماره موبایل دانش‌آموزان را وارد کنید و کلاس‌های مقصد را انتخاب کنید.</DialogDescription></DialogHeader>
      <div className="space-y-5 overflow-y-auto text-start">
        <div><label className="mb-2 block text-sm font-medium">شماره موبایل دانش‌آموزان</label><Textarea dir="ltr" className="min-h-28 text-left" value={phonesText} onChange={(e) => setPhonesText(e.target.value)} placeholder={'09123456789\n09351234567'} /><p className="mt-2 text-xs text-muted-foreground">هر شماره را در یک خط جدا وارد کنید.</p></div>
        <div><p className="mb-2 text-sm font-medium">انتخاب کلاس‌ها</p>
          <ScrollArea className="h-56 rounded-xl border"><div className="divide-y">
            {loading && <div className="flex justify-center p-8"><Loader2 className="animate-spin" /></div>}
            {!loading && !courses.length && <p className="p-6 text-center text-sm text-muted-foreground">کلاس شخصی قابل دعوت ندارید.</p>}
            {courses.map((course) => <label key={course.id} className="flex cursor-pointer items-center gap-3 p-4">
              <Checkbox checked={selected.includes(Number(course.id))} onCheckedChange={(checked) => setSelected((current) => checked ? [...current, Number(course.id)] : current.filter((id) => id !== Number(course.id)))} />
              <span className="flex-1"><span className="block font-medium">{course.title}</span><span className="text-xs text-muted-foreground">{course.status === 'active' ? 'منتشرشده' : 'پیش‌نویس'}</span></span>
            </label>)}
          </div></ScrollArea>
        </div>
      </div>
      <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>انصراف</Button><Button onClick={submit} disabled={submitting}>{submitting && <Loader2 className="h-4 w-4 animate-spin" />}ثبت {phones.length || ''} دعوت</Button></DialogFooter>
    </DialogContent>
  </Dialog>;
}
