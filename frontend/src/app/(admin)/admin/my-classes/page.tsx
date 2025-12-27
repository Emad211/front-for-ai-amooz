'use client';

import { useState } from 'react';
import { Plus, Search, Filter, MoreVertical, Users, Clock, BookOpen, Edit, Trash2, Eye, Copy, Share2, Calendar, Star, BarChart3 } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

// Mock data for classes
const mockClasses = [
  {
    id: '1',
    title: 'ریاضی پیشرفته',
    description: 'کلاس ریاضی برای دانش‌آموزان سال سوم دبیرستان',
    studentsCount: 24,
    lessonsCount: 12,
    status: 'active',
    createdAt: '2024-01-15',
    lastActivity: '2024-01-20',
    progress: 75,
    category: 'ریاضی',
    level: 'پیشرفته',
    thumbnail: '/api/placeholder/300/200',
    price: 150000,
    rating: 4.8,
    reviews: 15,
  },
  {
    id: '2',
    title: 'فیزیک کنکور',
    description: 'آماده‌سازی برای کنکور فیزیک با تست‌های متنوع',
    studentsCount: 45,
    lessonsCount: 20,
    status: 'active',
    createdAt: '2024-01-10',
    lastActivity: '2024-01-22',
    progress: 60,
    category: 'فیزیک',
    level: 'متوسط',
    thumbnail: '/api/placeholder/300/200',
    price: 200000,
    rating: 4.9,
    reviews: 28,
  },
  {
    id: '3',
    title: 'شیمی آلی',
    description: 'اصول و مبانی شیمی آلی برای دانشجویان',
    studentsCount: 18,
    lessonsCount: 8,
    status: 'draft',
    createdAt: '2024-01-18',
    lastActivity: '2024-01-19',
    progress: 30,
    category: 'شیمی',
    level: 'مبتدی',
    thumbnail: '/api/placeholder/300/200',
    price: 120000,
    rating: 4.5,
    reviews: 8,
  },
  {
    id: '4',
    title: 'زبان انگلیسی محاورات',
    description: 'تقویت مهارت‌های مکالمه انگلیسی',
    studentsCount: 32,
    lessonsCount: 15,
    status: 'active',
    createdAt: '2024-01-05',
    lastActivity: '2024-01-21',
    progress: 90,
    category: 'زبان',
    level: 'متوسط',
    thumbnail: '/api/placeholder/300/200',
    price: 180000,
    rating: 4.7,
    reviews: 22,
  },
  {
    id: '5',
    title: 'برنامه‌نویسی پایتون',
    description: 'آموزش کامل برنامه‌نویسی پایتون از صفر',
    studentsCount: 67,
    lessonsCount: 25,
    status: 'paused',
    createdAt: '2023-12-20',
    lastActivity: '2024-01-15',
    progress: 45,
    category: 'برنامه‌نویسی',
    level: 'مبتدی',
    thumbnail: '/api/placeholder/300/200',
    price: 250000,
    rating: 4.6,
    reviews: 41,
  },
];

const statusConfig = {
  active: { label: 'فعال', color: 'bg-green-500/10 text-green-700 dark:text-green-400' },
  draft: { label: 'پیش‌نویس', color: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400' },
  paused: { label: 'متوقف', color: 'bg-gray-500/10 text-gray-700 dark:text-gray-400' },
};

const levelConfig = {
  'مبتدی': 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
  'متوسط': 'bg-purple-500/10 text-purple-700 dark:text-purple-400',
  'پیشرفته': 'bg-red-500/10 text-red-700 dark:text-red-400',
};

export default function MyClassesPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [sortBy, setSortBy] = useState('recent');
  const [viewMode, setViewMode] = useState('grid'); // grid or list

  // Get unique categories
  const categories = [...new Set(mockClasses.map(cls => cls.category))];

  // Filter and sort classes
  const filteredClasses = mockClasses
    .filter(cls => {
      const matchesSearch = cls.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           cls.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || cls.status === statusFilter;
      const matchesCategory = categoryFilter === 'all' || cls.category === categoryFilter;
      return matchesSearch && matchesStatus && matchesCategory;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'recent':
          return new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime();
        case 'oldest':
          return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
        case 'students':
          return b.studentsCount - a.studentsCount;
        case 'progress':
          return b.progress - a.progress;
        case 'rating':
          return b.rating - a.rating;
        default:
          return 0;
      }
    });

  // Statistics
  const stats = {
    totalClasses: mockClasses.length,
    activeClasses: mockClasses.filter(cls => cls.status === 'active').length,
    totalStudents: mockClasses.reduce((sum, cls) => sum + cls.studentsCount, 0),
    averageRating: (mockClasses.reduce((sum, cls) => sum + cls.rating, 0) / mockClasses.length).toFixed(1),
  };

  const ClassCard = ({ cls }) => (
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
          <Badge className={statusConfig[cls.status].color}>
            {statusConfig[cls.status].label}
          </Badge>
          <Badge variant="outline" className={levelConfig[cls.level]}>
            {cls.level}
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Progress Bar */}
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

        {/* Stats */}
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

        {/* Footer */}
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

  return (
    <div className="space-y-8">
      {/* Header Section */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">کلاس‌های من</h1>
          <p className="text-muted-foreground mt-1">
            مدیریت و پیگیری کلاس‌های آموزشی شما
          </p>
        </div>
        <Button asChild className="w-fit">
          <Link href="/admin/create-class">
            <Plus className="w-4 h-4 ml-2" />
            ایجاد کلاس جدید
          </Link>
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
          <CardContent className="flex items-center p-6">
            <div className="flex-shrink-0">
              <div className="flex items-center justify-center w-12 h-12 bg-primary/20 rounded-xl">
                <BookOpen className="w-6 h-6 text-primary" />
              </div>
            </div>
            <div className="mr-4">
              <p className="text-sm font-medium text-muted-foreground">کل کلاس‌ها</p>
              <p className="text-2xl font-bold text-foreground">{stats.totalClasses}</p>
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-green-500/5 to-green-500/10 border-green-500/20">
          <CardContent className="flex items-center p-6">
            <div className="flex-shrink-0">
              <div className="flex items-center justify-center w-12 h-12 bg-green-500/20 rounded-xl">
                <BarChart3 className="w-6 h-6 text-green-500" />
              </div>
            </div>
            <div className="mr-4">
              <p className="text-sm font-medium text-muted-foreground">کلاس‌های فعال</p>
              <p className="text-2xl font-bold text-foreground">{stats.activeClasses}</p>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-blue-500/5 to-blue-500/10 border-blue-500/20">
          <CardContent className="flex items-center p-6">
            <div className="flex-shrink-0">
              <div className="flex items-center justify-center w-12 h-12 bg-blue-500/20 rounded-xl">
                <Users className="w-6 h-6 text-blue-500" />
              </div>
            </div>
            <div className="mr-4">
              <p className="text-sm font-medium text-muted-foreground">کل دانش‌آموزان</p>
              <p className="text-2xl font-bold text-foreground">{stats.totalStudents}</p>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-yellow-500/5 to-yellow-500/10 border-yellow-500/20">
          <CardContent className="flex items-center p-6">
            <div className="flex-shrink-0">
              <div className="flex items-center justify-center w-12 h-12 bg-yellow-500/20 rounded-xl">
                <Star className="w-6 h-6 text-yellow-500" />
              </div>
            </div>
            <div className="mr-4">
              <p className="text-sm font-medium text-muted-foreground">میانگین امتیاز</p>
              <p className="text-2xl font-bold text-foreground">{stats.averageRating}</p>
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
                placeholder="جستجو در کلاس‌ها..."
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
                  <SelectItem value="draft">پیش‌نویس</SelectItem>
                  <SelectItem value="paused">متوقف</SelectItem>
                </SelectContent>
              </Select>

              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-[140px] bg-background/50">
                  <SelectValue placeholder="دسته‌بندی" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">همه دسته‌ها</SelectItem>
                  {categories.map(category => (
                    <SelectItem key={category} value={category}>{category}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-[140px] bg-background/50">
                  <SelectValue placeholder="مرتب‌سازی" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recent">جدیدترین</SelectItem>
                  <SelectItem value="oldest">قدیمی‌ترین</SelectItem>
                  <SelectItem value="students">تعداد دانش‌آموز</SelectItem>
                  <SelectItem value="progress">درصد پیشرفت</SelectItem>
                  <SelectItem value="rating">امتیاز</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {filteredClasses.length} کلاس یافت شد
          </p>
        </div>

        {/* Classes Grid */}
        {filteredClasses.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredClasses.map((cls) => (
              <ClassCard key={cls.id} cls={cls} />
            ))}
          </div>
        ) : (
          <Card className="border-dashed border-2 border-muted-foreground/25">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <BookOpen className="w-12 h-12 text-muted-foreground/50 mb-4" />
              <h3 className="text-lg font-semibold text-muted-foreground mb-2">
                هیچ کلاسی یافت نشد
              </h3>
              <p className="text-muted-foreground text-center max-w-sm">
                بر اساس فیلترهای اعمال شده، کلاسی پیدا نشد. فیلترها را تغییر دهید یا کلاس جدید ایجاد کنید.
              </p>
              <Button asChild className="mt-4">
                <Link href="/admin/create-class">
                  <Plus className="w-4 h-4 ml-2" />
                  ایجاد کلاس جدید
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}