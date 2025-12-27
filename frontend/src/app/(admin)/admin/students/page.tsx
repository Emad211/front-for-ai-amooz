'use client';

import { useState } from 'react';
import { Search, Filter, MoreVertical, Mail, Phone, Calendar, Award, TrendingUp, UserPlus, Download, Eye, Ban, CheckCircle, XCircle, BookOpen, Clock } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

// Mock data for students
const mockStudents = [
  {
    id: '1',
    name: 'علی احمدی',
    email: 'ali.ahmadi@example.com',
    phone: '09121234567',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 3,
    completedLessons: 24,
    totalLessons: 45,
    averageScore: 85,
    status: 'active',
    joinDate: '2024-01-10',
    lastActivity: '2024-01-22',
    performance: 'excellent',
  },
  {
    id: '2',
    name: 'زهرا محمدی',
    email: 'zahra.mohammadi@example.com',
    phone: '09129876543',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 5,
    completedLessons: 67,
    totalLessons: 90,
    averageScore: 92,
    status: 'active',
    joinDate: '2023-12-15',
    lastActivity: '2024-01-23',
    performance: 'excellent',
  },
  {
    id: '3',
    name: 'محمد رضایی',
    email: 'mohammad.rezaei@example.com',
    phone: '09135551234',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 2,
    completedLessons: 15,
    totalLessons: 30,
    averageScore: 72,
    status: 'active',
    joinDate: '2024-01-18',
    lastActivity: '2024-01-21',
    performance: 'good',
  },
  {
    id: '4',
    name: 'فاطمه کریمی',
    email: 'fatemeh.karimi@example.com',
    phone: '09141239876',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 4,
    completedLessons: 38,
    totalLessons: 60,
    averageScore: 78,
    status: 'active',
    joinDate: '2024-01-05',
    lastActivity: '2024-01-20',
    performance: 'good',
  },
  {
    id: '5',
    name: 'حسین نوری',
    email: 'hossein.noori@example.com',
    phone: '09151234567',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 2,
    completedLessons: 8,
    totalLessons: 30,
    averageScore: 58,
    status: 'inactive',
    joinDate: '2023-12-20',
    lastActivity: '2024-01-10',
    performance: 'needs-improvement',
  },
  {
    id: '6',
    name: 'مریم صادقی',
    email: 'maryam.sadeghi@example.com',
    phone: '09161234567',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 6,
    completedLessons: 89,
    totalLessons: 100,
    averageScore: 95,
    status: 'active',
    joinDate: '2023-11-10',
    lastActivity: '2024-01-23',
    performance: 'excellent',
  },
];

const statusConfig = {
  active: { label: 'فعال', color: 'bg-green-500/10 text-green-700 dark:text-green-400', icon: CheckCircle },
  inactive: { label: 'غیرفعال', color: 'bg-gray-500/10 text-gray-700 dark:text-gray-400', icon: XCircle },
};

const performanceConfig = {
  excellent: { label: 'عالی', color: 'bg-green-500/10 text-green-700 dark:text-green-400' },
  good: { label: 'خوب', color: 'bg-blue-500/10 text-blue-700 dark:text-blue-400' },
  'needs-improvement': { label: 'نیاز به بهبود', color: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400' },
};

export default function StudentsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [performanceFilter, setPerformanceFilter] = useState('all');
  const [sortBy, setSortBy] = useState('recent');

  // Filter and sort students
  const filteredStudents = mockStudents
    .filter(student => {
      const matchesSearch = student.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           student.email.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || student.status === statusFilter;
      const matchesPerformance = performanceFilter === 'all' || student.performance === performanceFilter;
      return matchesSearch && matchesStatus && matchesPerformance;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'recent':
          return new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime();
        case 'name':
          return a.name.localeCompare(b.name, 'fa');
        case 'score':
          return b.averageScore - a.averageScore;
        case 'progress':
          return (b.completedLessons / b.totalLessons) - (a.completedLessons / a.totalLessons);
        default:
          return 0;
      }
    });

  // Statistics
  const stats = {
    totalStudents: mockStudents.length,
    activeStudents: mockStudents.filter(s => s.status === 'active').length,
    averageScore: Math.round(mockStudents.reduce((sum, s) => sum + s.averageScore, 0) / mockStudents.length),
    totalEnrollments: mockStudents.reduce((sum, s) => sum + s.enrolledClasses, 0),
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">دانش‌آموزان</h1>
          <p className="text-muted-foreground mt-1">
            مدیریت و پیگیری دانش‌آموزان
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Download className="w-4 h-4 ml-2" />
            خروجی Excel
          </Button>
          <Button>
            <UserPlus className="w-4 h-4 ml-2" />
            افزودن دانش‌آموز
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
          <CardContent className="flex items-center p-6">
            <div className="flex-shrink-0">
              <div className="flex items-center justify-center w-12 h-12 bg-primary/20 rounded-xl">
                <Award className="w-6 h-6 text-primary" />
              </div>
            </div>
            <div className="mr-4">
              <p className="text-sm font-medium text-muted-foreground">کل دانش‌آموزان</p>
              <p className="text-2xl font-bold text-foreground">{stats.totalStudents}</p>
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-green-500/5 to-green-500/10 border-green-500/20">
          <CardContent className="flex items-center p-6">
            <div className="flex-shrink-0">
              <div className="flex items-center justify-center w-12 h-12 bg-green-500/20 rounded-xl">
                <CheckCircle className="w-6 h-6 text-green-500" />
              </div>
            </div>
            <div className="mr-4">
              <p className="text-sm font-medium text-muted-foreground">دانش‌آموزان فعال</p>
              <p className="text-2xl font-bold text-foreground">{stats.activeStudents}</p>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-blue-500/5 to-blue-500/10 border-blue-500/20">
          <CardContent className="flex items-center p-6">
            <div className="flex-shrink-0">
              <div className="flex items-center justify-center w-12 h-12 bg-blue-500/20 rounded-xl">
                <TrendingUp className="w-6 h-6 text-blue-500" />
              </div>
            </div>
            <div className="mr-4">
              <p className="text-sm font-medium text-muted-foreground">میانگین نمره</p>
              <p className="text-2xl font-bold text-foreground">{stats.averageScore}</p>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-500/5 to-purple-500/10 border-purple-500/20">
          <CardContent className="flex items-center p-6">
            <div className="flex-shrink-0">
              <div className="flex items-center justify-center w-12 h-12 bg-purple-500/20 rounded-xl">
                <BookOpen className="w-6 h-6 text-purple-500" />
              </div>
            </div>
            <div className="mr-4">
              <p className="text-sm font-medium text-muted-foreground">کل ثبت‌نام‌ها</p>
              <p className="text-2xl font-bold text-foreground">{stats.totalEnrollments}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card className="bg-card/50 backdrop-blur-sm">
        <CardContent className="p-6">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
              <Input
                placeholder="جستجو بر اساس نام یا ایمیل..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pr-10 bg-background/50"
              />
            </div>

            {/* Filters */}
            <div className="flex gap-3">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[140px] bg-background/50">
                  <SelectValue placeholder="وضعیت" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">همه وضعیت‌ها</SelectItem>
                  <SelectItem value="active">فعال</SelectItem>
                  <SelectItem value="inactive">غیرفعال</SelectItem>
                </SelectContent>
              </Select>

              <Select value={performanceFilter} onValueChange={setPerformanceFilter}>
                <SelectTrigger className="w-[140px] bg-background/50">
                  <SelectValue placeholder="عملکرد" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">همه عملکردها</SelectItem>
                  <SelectItem value="excellent">عالی</SelectItem>
                  <SelectItem value="good">خوب</SelectItem>
                  <SelectItem value="needs-improvement">نیاز به بهبود</SelectItem>
                </SelectContent>
              </Select>

              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-[140px] bg-background/50">
                  <SelectValue placeholder="مرتب‌سازی" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recent">آخرین فعالیت</SelectItem>
                  <SelectItem value="name">نام</SelectItem>
                  <SelectItem value="score">نمره</SelectItem>
                  <SelectItem value="progress">پیشرفت</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Students Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>لیست دانش‌آموزان</CardTitle>
            <p className="text-sm text-muted-foreground">
              {filteredStudents.length} دانش‌آموز یافت شد
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
                {filteredStudents.map((student) => {
                  const progress = Math.round((student.completedLessons / student.totalLessons) * 100);
                  const StatusIcon = statusConfig[student.status].icon;
                  
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
                        <Badge className={performanceConfig[student.performance].color}>
                          {performanceConfig[student.performance].label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusConfig[student.status].color}>
                          <StatusIcon className="w-3 h-3 ml-1" />
                          {statusConfig[student.status].label}
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
    </div>
  );
}