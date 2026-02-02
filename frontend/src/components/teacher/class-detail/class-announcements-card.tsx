'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Megaphone, Plus, MoreHorizontal, Edit, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { formatPersianDateTime } from '@/lib/date-utils';
import {
  createClassAnnouncement,
  createExamPrepAnnouncement,
  deleteClassAnnouncement,
  deleteExamPrepAnnouncement,
  listClassAnnouncements,
  listExamPrepAnnouncements,
  updateClassAnnouncement,
  updateExamPrepAnnouncement,
  type AnnouncementPriority,
  type ClassAnnouncement,
} from '@/services/classes-service';
import { toast } from 'sonner';

interface ClassAnnouncementsCardProps {
  sessionId: number;
  sessionType: 'class' | 'exam_prep';
}

const priorityStyles: Record<string, string> = {
  high: 'bg-destructive/10 text-destructive border-destructive/20',
  medium: 'bg-muted text-muted-foreground border-border',
  low: 'bg-primary/10 text-primary border-primary/20',
};

const priorityLabels: Record<string, string> = {
  high: 'فوری',
  medium: 'متوسط',
  low: 'عادی',
};

export function ClassAnnouncementsCard({ sessionId, sessionType }: ClassAnnouncementsCardProps) {
  const [announcements, setAnnouncements] = useState<ClassAnnouncement[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editing, setEditing] = useState<ClassAnnouncement | null>(null);

  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [priority, setPriority] = useState<AnnouncementPriority>('medium');

  const loadAnnouncements = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = sessionType === 'class'
        ? await listClassAnnouncements(sessionId)
        : await listExamPrepAnnouncements(sessionId);
      setAnnouncements(data);
    } catch (err) {
      console.error(err);
      toast.error('خطا در دریافت اطلاعیه‌ها');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, sessionType]);

  useEffect(() => {
    void loadAnnouncements();
  }, [loadAnnouncements]);

  const resetForm = useCallback(() => {
    setTitle('');
    setContent('');
    setPriority('medium');
    setEditing(null);
  }, []);

  const openCreate = () => {
    resetForm();
    setIsDialogOpen(true);
  };

  const openEdit = (announcement: ClassAnnouncement) => {
    setEditing(announcement);
    setTitle(announcement.title);
    setContent(announcement.content);
    setPriority(announcement.priority);
    setIsDialogOpen(true);
  };

  const handleSave = async () => {
    if (!title.trim() || !content.trim()) {
      toast.error('عنوان و متن اطلاعیه الزامی است');
      return;
    }
    setIsSaving(true);
    try {
      if (editing) {
        const updated = sessionType === 'class'
          ? await updateClassAnnouncement(sessionId, editing.id, { title, content, priority })
          : await updateExamPrepAnnouncement(sessionId, editing.id, { title, content, priority });
        setAnnouncements((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        toast.success('اطلاعیه ویرایش شد');
      } else {
        const created = sessionType === 'class'
          ? await createClassAnnouncement(sessionId, { title, content, priority })
          : await createExamPrepAnnouncement(sessionId, { title, content, priority });
        setAnnouncements((prev) => [created, ...prev]);
        toast.success('اطلاعیه ثبت شد');
      }
      setIsDialogOpen(false);
      resetForm();
    } catch (err) {
      console.error(err);
      toast.error('خطا در ذخیره اطلاعیه');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (announcement: ClassAnnouncement) => {
    const ok = window.confirm('آیا از حذف این اطلاعیه مطمئن هستید؟');
    if (!ok) return;
    try {
      if (sessionType === 'class') {
        await deleteClassAnnouncement(sessionId, announcement.id);
      } else {
        await deleteExamPrepAnnouncement(sessionId, announcement.id);
      }
      setAnnouncements((prev) => prev.filter((item) => item.id !== announcement.id));
      toast.success('اطلاعیه حذف شد');
    } catch (err) {
      console.error(err);
      toast.error('خطا در حذف اطلاعیه');
    }
  };

  const emptyState = useMemo(() => !isLoading && announcements.length === 0, [isLoading, announcements.length]);

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <CardTitle className="text-base sm:text-lg flex items-center gap-2">
          <Megaphone className="h-5 w-5" />
          اطلاعیه‌ها
        </CardTitle>
        <Button size="sm" variant="outline" onClick={openCreate}>
          <Plus className="h-4 w-4 sm:ml-2" />
          <span className="hidden sm:inline">اطلاعیه جدید</span>
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-center py-8 text-muted-foreground">در حال بارگذاری...</div>
        ) : emptyState ? (
          <div className="text-center py-8 text-muted-foreground">
            <Megaphone className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>هنوز اطلاعیه‌ای ثبت نشده است</p>
          </div>
        ) : (
          <div className="space-y-3">
            {announcements.map((announcement) => (
              <div
                key={announcement.id}
                className="p-4 rounded-xl border hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="font-medium">{announcement.title}</h4>
                      <Badge variant="outline" className={priorityStyles[announcement.priority]}>
                        {priorityLabels[announcement.priority]}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {announcement.content}
                    </p>
                    <p className="text-xs text-muted-foreground mt-2">
                      {formatPersianDateTime(announcement.created_at)}
                    </p>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEdit(announcement)}>
                        <Edit className="h-4 w-4 ml-2" />
                        ویرایش
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => handleDelete(announcement)}
                      >
                        <Trash2 className="h-4 w-4 ml-2" />
                        حذف
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? 'ویرایش اطلاعیه' : 'اطلاعیه جدید'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">عنوان</label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="عنوان اطلاعیه" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">متن اطلاعیه</label>
              <Textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="متن اطلاعیه" rows={4} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">اولویت</label>
              <Select value={priority} onValueChange={(v) => setPriority(v as AnnouncementPriority)}>
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب اولویت" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">عادی</SelectItem>
                  <SelectItem value="medium">متوسط</SelectItem>
                  <SelectItem value="high">فوری</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? 'در حال ذخیره...' : 'ذخیره'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
