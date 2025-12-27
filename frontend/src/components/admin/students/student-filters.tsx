'use client';

import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface StudentFiltersProps {
  searchTerm: string;
  setSearchTerm: (value: string) => void;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
  performanceFilter: string;
  setPerformanceFilter: (value: string) => void;
  sortBy: string;
  setSortBy: (value: string) => void;
}

export function StudentFilters({
  searchTerm,
  setSearchTerm,
  statusFilter,
  setStatusFilter,
  performanceFilter,
  setPerformanceFilter,
  sortBy,
  setSortBy,
}: StudentFiltersProps) {
  return (
    <Card className="bg-card/50 backdrop-blur-sm">
      <CardContent className="p-6">
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
            <Input
              placeholder="جستجو بر اساس نام یا ایمیل..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pr-10 bg-background/50"
            />
          </div>

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
  );
}