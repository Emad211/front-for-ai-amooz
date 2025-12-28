'use client';

import { Mail, Phone, BookOpen, Award, Clock } from 'lucide-react';
import { TableCell, TableRow } from '@/components/ui/table';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { StudentStatusBadge } from './status-badge';
import { StudentPerformanceBadge } from './performance-badge';
import { StudentTableActions } from './table-actions';

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

export function StudentTableRow({ student }: { student: Student }) {
  return (
    <TableRow className="hover:bg-muted/50">
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
        <div className="flex items-center gap-2">
          <Award className="w-4 h-4 text-yellow-500" />
          <span className="font-semibold text-foreground">{student.averageScore}</span>
        </div>
      </TableCell>
      <TableCell>
        <StudentPerformanceBadge performance={student.performance} />
      </TableCell>
      <TableCell>
        <StudentStatusBadge status={student.status} />
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock className="w-3 h-3" />
          {student.lastActivity}
        </div>
      </TableCell>
      <TableCell>
        <StudentTableActions studentId={student.id} />
      </TableCell>
    </TableRow>
  );
}
