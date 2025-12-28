'use client';

import { MoreVertical, Users, BookOpen, Star, Calendar, Edit, Trash2, Eye, Copy, Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface ClassCardProps {
  cls: {
    id: string;
    title: string;
    description: string;
    studentsCount: number;
    lessonsCount: number;
    status: string;
    createdAt: string;
    lastActivity: string;
    category: string;
    level: string;
    rating: number;
  };
}

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: 'فعال', color: 'bg-primary/10 text-primary border-primary/20' },
  draft: { label: 'پیش‌نویس', color: 'bg-muted text-muted-foreground border-border' },
  paused: { label: 'متوقف', color: 'bg-muted text-muted-foreground border-border' },
};

const levelConfig: Record<string, string> = {
  'مبتدی': 'bg-muted text-muted-foreground border-border',
  'متوسط': 'bg-muted text-muted-foreground border-border',
  'پیشرفته': 'bg-muted text-muted-foreground border-border',
};

export function ClassCard({ cls }: ClassCardProps) {
  return (
    <Card className="group hover:shadow-md transition-all duration-300 border-border/60 bg-card hover:border-primary/50 overflow-hidden relative">
      <div className="absolute top-0 right-0 w-1 h-full bg-primary/0 group-hover:bg-primary transition-all duration-300" />
      
      <CardHeader className="pb-3 pt-5 px-5">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1.5 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="outline" className={`rounded-md px-2 py-0.5 text-[10px] font-normal border ${statusConfig[cls.status]?.color || ''}`}>
                {statusConfig[cls.status]?.label || cls.status}
              </Badge>
              <Badge variant="outline" className={`rounded-md px-2 py-0.5 text-[10px] font-normal border ${levelConfig[cls.level] || ''}`}>
                {cls.level}
              </Badge>
            </div>
            <CardTitle className="text-lg font-bold text-foreground group-hover:text-primary transition-colors line-clamp-1">
              {cls.title}
            </CardTitle>
            <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed h-9">
              {cls.description}
            </p>
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8 -ml-2 text-muted-foreground hover:text-foreground">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem>
                <Eye className="w-4 h-4 ml-2" />
                مشاهده جزئیات
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Edit className="w-4 h-4 ml-2" />
                ویرایش محتوا
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Users className="w-4 h-4 ml-2" />
                مدیریت دانش‌آموزان
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive focus:text-destructive">
                <Trash2 className="w-4 h-4 ml-2" />
                حذف کلاس
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      
      <CardContent className="px-5 pb-5">
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="flex items-center gap-2 bg-muted/50 p-2 rounded-lg">
            <div className="h-8 w-8 rounded-full bg-background flex items-center justify-center text-muted-foreground shrink-0">
              <Users className="h-4 w-4" />
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-[10px] text-muted-foreground leading-none mb-0.5">دانش‌آموزان</span>
              <span className="text-xs font-bold truncate">{cls.studentsCount}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 bg-muted/50 p-2 rounded-lg">
            <div className="h-8 w-8 rounded-full bg-background flex items-center justify-center text-muted-foreground shrink-0">
              <BookOpen className="h-4 w-4" />
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-[10px] text-muted-foreground leading-none mb-0.5">تعداد دروس</span>
              <span className="text-xs font-bold truncate">{cls.lessonsCount}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground border-t border-border/50 pt-3 mt-2">
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            <span>آخرین فعالیت: {cls.lastActivity}</span>
          </div>
          <div className="flex items-center gap-1">
            <Star className="h-3 w-3 text-amber-500 fill-amber-500" />
            <span>{cls.rating}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
