'use client';

import Link from 'next/link';
import { Users, UserPlus, MoreHorizontal, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { ClassStudent } from '@/types';

interface ClassStudentsPreviewProps {
  classId: string;
  students: ClassStudent[];
  maxDisplay?: number;
}

const statusColors: Record<string, string> = {
  active: 'bg-emerald-500/10 text-emerald-600',
  inactive: 'bg-gray-500/10 text-gray-600',
  completed: 'bg-blue-500/10 text-blue-600',
};

const statusLabels: Record<string, string> = {
  active: 'فعال',
  inactive: 'غیرفعال',
  completed: 'تکمیل شده',
};

export function ClassStudentsPreview({ classId, students, maxDisplay = 5 }: ClassStudentsPreviewProps) {
  const displayedStudents = students.slice(0, maxDisplay);
  const remainingCount = students.length - maxDisplay;

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <CardTitle className="text-lg flex items-center gap-2">
            <Users className="h-5 w-5 text-primary" />
            دانش‌آموزان
          </CardTitle>
          <CardDescription>{students.length} دانش‌آموز ثبت‌نام شده</CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/admin/my-classes/${classId}/students`}>
              مشاهده همه
            </Link>
          </Button>
          <Button size="sm">
            <UserPlus className="h-4 w-4 ml-2" />
            افزودن
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {displayedStudents.map(student => (
            <div key={student.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors gap-3">
              <div className="flex items-center gap-3">
                <Avatar className="h-10 w-10 shrink-0">
                  <AvatarFallback className="bg-primary/10 text-primary">{student.name.charAt(0)}</AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <p className="font-medium text-sm truncate">{student.name}</p>
                  <p className="text-xs text-muted-foreground truncate">{student.email}</p>
                </div>
              </div>
              <div className="flex items-center justify-between sm:justify-end gap-3 mr-[52px] sm:mr-0">
                <div className="text-left">
                  <p className="text-sm font-medium text-primary">{student.progress}%</p>
                  <p className="text-xs text-muted-foreground">پیشرفت</p>
                </div>
                <Badge variant="outline" className={statusColors[student.status]}>
                  {statusLabels[student.status]}
                </Badge>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem>مشاهده پروفایل</DropdownMenuItem>
                    <DropdownMenuItem>ارسال پیام</DropdownMenuItem>
                    <DropdownMenuItem className="text-destructive">
                      <Trash2 className="h-4 w-4 ml-2" />
                      حذف از کلاس
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          ))}
          {remainingCount > 0 && (
            <Link 
              href={`/admin/my-classes/${classId}/students`}
              className="block text-center text-sm text-primary hover:underline py-2"
            >
              و {remainingCount} دانش‌آموز دیگر...
            </Link>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
