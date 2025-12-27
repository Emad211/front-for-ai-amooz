'use client';

import { MoreVertical, Mail, Phone, BookOpen, Award, Clock, Eye, Ban, CheckCircle, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

interface Student {
  id: string;
  name: string;
  email: string;
  phone: string;
  avatar: string;
  enrolledClasses: number;
  completedLessons: number;
  totalLessons: number;
  averageScore: number;
  status: string;
  joinDate: string;
  lastActivity: string;
  performance: string;
}

interface StudentTableProps {
  students: Student[];
}

const statusConfig: Record<string, { label: string; color: string; icon: any }> = {
  active: { label: 'فعال', color: 'bg-green-500/10 text-green-700 dark:text-green-400', icon: CheckCircle },
  inactive: { label: 'غیرفعال', color: 'bg-gray-500/10 text-gray-700 dark:text-gray-400', icon: XCircle },
};

const performanceConfig: Record<string, { label: string; color: string }> = {
  excellent: { label: 'عالی', color: 'bg-green-500/10 text-green-700 dark:text-green-400' },
  good: { label: 'خوب', color: 'bg-blue-500/10 text-blue-700 dark:text-blue-400' },
  'needs-improvement': { label: 'نیاز به بهبود', color: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400' },
};

export function StudentTable({ students }: StudentTableProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>لیست دانش‌آموزان</CardTitle>
          <p className="text-sm text-muted-foreground">
            {students.length} دانش‌آموز یافت شد
          </p>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-right">دانش‌آموز</TableHead>
                <TableHead className="text-right">اطلاعات تماس</TableHead>
                <TableHead className="text-right">کلاس‌ها</TableHead>
                <TableHead className="text-right">پیشرفت</TableHead>
                <TableHead className="text-right">نمره</TableHead>
                <TableHead className="text-right">عملکرد</TableHead>
                <TableHead className="text-right">وضعیت</TableHead>
                <TableHead className="text-right">آخرین فعالیت</TableHead>
                <TableHead className="text-right"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {students.map((student) => {
                const progress = Math.round((student.completedLessons / student.totalLessons) * 100);
                const StatusIcon = statusConfig[student.status]?.icon || CheckCircle;
                
                return (
                  <TableRow key={student.id} className="hover:bg-muted/50">
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="h-10 w-10">
                          <AvatarImage src={student.avatar} alt={student.name} />
                          <AvatarFallback>{student.name.charAt(0)}</AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium text-foreground">{student.name}</p>
                          <p className="text-xs text-muted-foreground">
                            عضو از {new Date(student.joinDate).toLocaleDateString('fa-IR')}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Mail className="w-3 h-3" />
                          {student.email}
                        </div>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Phone className="w-3 h-3" />
                          {student.phone}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <BookOpen className="w-4 h-4 text-primary" />
                        <span className="font-medium">{student.enrolledClasses}</span>
                        <span className="text-xs text-muted-foreground">کلاس</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">{progress}%</span>
                          <span className="text-muted-foreground">
                            {student.completedLessons}/{student.totalLessons}
                          </span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-1.5">
                          <div 
                            className="bg-primary rounded-full h-1.5 transition-all"
                            style={{ width: `${progress}%` }}
                          ></div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Award className="w-4 h-4 text-yellow-500" />
                        <span className="font-semibold text-foreground">{student.averageScore}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={performanceConfig[student.performance]?.color || ''}>
                        {performanceConfig[student.performance]?.label || student.performance}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={statusConfig[student.status]?.color || ''}>
                        <StatusIcon className="w-3 h-3 ml-1" />
                        {statusConfig[student.status]?.label || student.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-sm text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        {new Date(student.lastActivity).toLocaleDateString('fa-IR')}
                      </div>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-56">
                          <DropdownMenuItem>
                            <Eye className="w-4 h-4 ml-2" />
                            مشاهده پروفایل
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Mail className="w-4 h-4 ml-2" />
                            ارسال پیام
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem className="text-destructive">
                            <Ban className="w-4 h-4 ml-2" />
                            مسدود کردن
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}