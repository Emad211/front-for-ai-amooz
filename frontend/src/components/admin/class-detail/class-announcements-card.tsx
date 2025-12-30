'use client';

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

interface Announcement {
  id: string;
  title: string;
  content: string;
  date: string;
  priority: 'low' | 'medium' | 'high';
}

interface ClassAnnouncementsCardProps {
  announcements?: Announcement[];
  onAdd?: () => void;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
}

const priorityStyles: Record<string, string> = {
  high: 'bg-red-500/10 text-red-600 border-red-200',
  medium: 'bg-amber-500/10 text-amber-600 border-amber-200',
  low: 'bg-blue-500/10 text-blue-600 border-blue-200',
};

const priorityLabels: Record<string, string> = {
  high: 'فوری',
  medium: 'متوسط',
  low: 'عادی',
};

const defaultAnnouncements: Announcement[] = [
  {
    id: '1',
    title: 'آزمون میان‌ترم',
    content: 'آزمون میان‌ترم در تاریخ ۱۵ خرداد برگزار خواهد شد.',
    date: '۱۰ خرداد ۱۴۰۳',
    priority: 'high',
  },
  {
    id: '2',
    title: 'تغییر ساعت کلاس',
    content: 'جلسات کلاس از هفته آینده ساعت ۱۰ صبح برگزار می‌شود.',
    date: '۸ خرداد ۱۴۰۳',
    priority: 'medium',
  },
];

export function ClassAnnouncementsCard({ 
  announcements = defaultAnnouncements,
  onAdd,
  onEdit,
  onDelete,
}: ClassAnnouncementsCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg flex items-center gap-2">
          <Megaphone className="h-5 w-5" />
          اطلاعیه‌ها
        </CardTitle>
        <Button size="sm" variant="outline" onClick={onAdd}>
          <Plus className="h-4 w-4 ml-2" />
          اطلاعیه جدید
        </Button>
      </CardHeader>
      <CardContent>
        {announcements.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Megaphone className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>هنوز اطلاعیه‌ای ثبت نشده است</p>
          </div>
        ) : (
          <div className="space-y-3">
            {announcements.map(announcement => (
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
                    <p className="text-xs text-muted-foreground mt-2">{announcement.date}</p>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onEdit?.(announcement.id)}>
                        <Edit className="h-4 w-4 ml-2" />
                        ویرایش
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        className="text-destructive"
                        onClick={() => onDelete?.(announcement.id)}
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
    </Card>
  );
}
