'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { StudentTableRow } from './table/table-row';
import { StudentTableActions } from './table/table-actions';
import { StudentPerformanceBadge } from './table/performance-badge';
import { StudentStatusBadge } from './table/status-badge';

interface Student {
  id: string;
  name: string;
  email: string;
  phone: string;
  avatar: string;
  enrolledClasses: number;
  averageScore: number;
  status: string;
  joinDate: string;
  lastActivity: string;
  performance: string;
}

interface StudentTableProps {
  students: Student[];
}

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
      <CardContent className="p-0 sm:p-6">
        {/* Desktop Table View */}
        <div className="hidden md:block rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-right">دانش‌آموز</TableHead>
                <TableHead className="text-right">اطلاعات تماس</TableHead>
                <TableHead className="text-right">کلاس‌ها</TableHead>
                <TableHead className="text-right">نمره</TableHead>
                <TableHead className="text-right">عملکرد</TableHead>
                <TableHead className="text-right">وضعیت</TableHead>
                <TableHead className="text-right">آخرین فعالیت</TableHead>
                <TableHead className="text-right"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {students.map((student) => (
                <StudentTableRow key={student.id} student={student} />
              ))}
              {students.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-10 text-muted-foreground">
                    دانش‌آموزی یافت نشد
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        {/* Mobile Card View */}
        <div className="md:hidden divide-y divide-border">
          {students.map((student) => (
            <div key={student.id} className="p-4 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center text-lg font-bold">
                    {student.name.charAt(0)}
                  </div>
                  <div>
                    <p className="font-bold text-foreground">{student.name}</p>
                    <p className="text-xs text-muted-foreground">{student.email}</p>
                  </div>
                </div>
                <StudentTableActions studentId={student.id} />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-muted/30 p-2 rounded-lg">
                  <p className="text-[10px] text-muted-foreground mb-1">کلاس‌ها</p>
                  <p className="text-sm font-bold">{student.enrolledClasses} کلاس</p>
                </div>
                <div className="bg-muted/30 p-2 rounded-lg">
                  <p className="text-[10px] text-muted-foreground mb-1">میانگین نمره</p>
                  <p className="text-sm font-bold">{student.averageScore}</p>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <div className="flex gap-2">
                  <StudentPerformanceBadge performance={student.performance} />
                  <StudentStatusBadge status={student.status} />
                </div>
                <p className="text-[10px] text-muted-foreground">
                  فعالیت: {student.lastActivity}
                </p>
              </div>
            </div>
          ))}
          {students.length === 0 && (
            <div className="py-10 text-center text-muted-foreground">
              دانش‌آموزی یافت نشد
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
