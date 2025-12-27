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
    progress: number;
    category: string;
    level: string;
    price: number;
    rating: number;
  };
}

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: 'فعال', color: 'bg-green-500/10 text-green-700 dark:text-green-400' },
  draft: { label: 'پیش‌نویس', color: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400' },
  paused: { label: 'متوقف', color: 'bg-gray-500/10 text-gray-700 dark:text-gray-400' },
};

const levelConfig: Record<string, string> = {
  'مبتدی': 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
  'متوسط': 'bg-purple-500/10 text-purple-700 dark:text-purple-400',
  'پیشرفته': 'bg-red-500/10 text-red-700 dark:text-red-400',
};

export function ClassCard({ cls }: ClassCardProps) {
  return (
    <Card className="group hover:shadow-lg transition-all duration-300 hover:border-primary/20 bg-card/50 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1 flex-1">
            <CardTitle className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors line-clamp-1">
              {cls.title}
            </CardTitle>
            <p className="text-sm text-muted-foreground line-clamp-2 leading-relaxed">
              {cls.description}
            </p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuItem>
                <Eye className="w-4 h-4 ml-2" />
                مشاهده کلاس
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Edit className="w-4 h-4 ml-2" />
                ویرایش
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Copy className="w-4 h-4 ml-2" />
                کپی
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Share2 className="w-4 h-4 ml-2" />
                اشتراک‌گذاری
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive">
                <Trash2 className="w-4 h-4 ml-2" />
                حذف
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        
        <div className="flex items-center gap-2 pt-2">
          <Badge className={statusConfig[cls.status]?.color || ''}>
            {statusConfig[cls.status]?.label || cls.status}
          </Badge>
          <Badge variant="outline" className={levelConfig[cls.level] || ''}>
            {cls.level}
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">پیشرفت</span>
            <span className="font-medium text-foreground">{cls.progress}%</span>
          </div>
          <div className="w-full bg-muted rounded-full h-2">
            <div 
              className="bg-primary rounded-full h-2 transition-all duration-500"
              style={{ width: `${cls.progress}%` }}
            ></div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 pt-2">
          <div className="text-center">
            <div className="flex items-center justify-center w-8 h-8 mx-auto mb-1 bg-primary/10 rounded-lg">
              <Users className="w-4 h-4 text-primary" />
            </div>
            <div className="text-lg font-semibold text-foreground">{cls.studentsCount}</div>
            <div className="text-xs text-muted-foreground">دانش‌آموز</div>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center w-8 h-8 mx-auto mb-1 bg-blue-500/10 rounded-lg">
              <BookOpen className="w-4 h-4 text-blue-500" />
            </div>
            <div className="text-lg font-semibold text-foreground">{cls.lessonsCount}</div>
            <div className="text-xs text-muted-foreground">درس</div>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center w-8 h-8 mx-auto mb-1 bg-yellow-500/10 rounded-lg">
              <Star className="w-4 h-4 text-yellow-500" />
            </div>
            <div className="text-lg font-semibold text-foreground">{cls.rating}</div>
            <div className="text-xs text-muted-foreground">امتیاز</div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-border/50">
          <div className="flex items-center gap-1 text-sm text-muted-foreground">
            <Calendar className="w-3 h-3" />
            {new Date(cls.lastActivity).toLocaleDateString('fa-IR')}
          </div>
          <div className="text-sm font-medium text-primary">
            {cls.price.toLocaleString()} تومان
          </div>
        </div>
      </CardContent>
    </Card>
  );
}