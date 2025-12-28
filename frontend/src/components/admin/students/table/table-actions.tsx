'use client';

import { MoreVertical, Eye, Mail, Ban, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export function StudentTableActions({ studentId }: { studentId: string }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <MoreVertical className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48" dir="rtl">
        <DropdownMenuItem className="gap-2">
          <Eye className="h-4 w-4" />
          مشاهده پروفایل
        </DropdownMenuItem>
        <DropdownMenuItem className="gap-2">
          <Mail className="h-4 w-4" />
          ارسال پیام مستقیم
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="gap-2 text-amber-600 focus:text-amber-600">
          <Ban className="h-4 w-4" />
          تعلیق حساب
        </DropdownMenuItem>
        <DropdownMenuItem className="gap-2 text-destructive focus:text-destructive">
          <Trash2 className="h-4 w-4" />
          حذف دانش‌آموز
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
