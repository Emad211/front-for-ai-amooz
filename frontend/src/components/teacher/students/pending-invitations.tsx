'use client';

import { useEffect, useState } from 'react';
import { Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import type { PendingStudentInvitation } from '@/types';
import { TeacherService } from '@/services/teacher-service';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatPersianDate } from '@/lib/date-utils';

export function PendingInvitations({ refreshKey = 0 }: { refreshKey?: number }) {
  const [items, setItems] = useState<PendingStudentInvitation[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () => {
    setLoading(true);
    TeacherService.getPendingStudentInvitations().then(setItems).catch(() => toast.error('دعوت‌ها دریافت نشدند.')).finally(() => setLoading(false));
  };
  useEffect(load, [refreshKey]);

  const cancel = async (id: number) => {
    try { await TeacherService.cancelStudentInvitation(id); setItems((current) => current.filter((item) => item.id !== id)); toast.success('دعوت لغو شد.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'لغو دعوت انجام نشد.'); }
  };

  return <Card><CardHeader className="text-start"><CardTitle className="text-base">دعوت‌های در انتظار</CardTitle></CardHeader><CardContent>
    {loading ? <div className="flex justify-center py-8"><Loader2 className="animate-spin" /></div> : !items.length ? <p className="py-4 text-center text-sm text-muted-foreground">دعوت در انتظاری وجود ندارد.</p> : <div className="divide-y rounded-xl border">
      {items.map((item) => <div key={item.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <div className="flex-1 text-start"><p dir="ltr" className="text-left font-medium">{item.phone}</p><p className="text-sm text-muted-foreground">{item.classTitle} · {formatPersianDate(item.createdAt)}</p></div>
        <Button variant="ghost" size="sm" className="gap-2 text-destructive" onClick={() => void cancel(item.id)}><Trash2 className="h-4 w-4" />لغو دعوت</Button>
      </div>)}
    </div>}
  </CardContent></Card>;
}
