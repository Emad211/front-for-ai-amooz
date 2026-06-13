'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  UserPlus, BookOpen, MessageSquare, Award, LogIn, CheckCircle2, FileText,
  ClipboardCheck, GraduationCap, LifeBuoy, Megaphone, Activity,
} from 'lucide-react';

// Keys MUST cover every icon produced by ACTIVITY_STYLE in admin-service.ts.
// A miss falls back to `Activity` so an unknown type can never crash the list.
const ICON_MAP: Record<string, typeof Activity> = {
  'log-in': LogIn,
  'user-plus': UserPlus,
  'book': BookOpen,
  'check': CheckCircle2,
  'file-text': FileText,
  'clipboard-check': ClipboardCheck,
  'award': Award,
  'graduation': GraduationCap,
  'life-buoy': LifeBuoy,
  'message': MessageSquare,
  'megaphone': Megaphone,
};

const ROLE_LABEL: Record<string, string> = {
  STUDENT: 'دانش‌آموز',
  TEACHER: 'معلم',
  ADMIN: 'مدیر',
  MANAGER: 'مدیر سازمان',
};

interface RecentActivityProps {
  activities: any[];
}

export function RecentActivity({ activities }: RecentActivityProps) {
  return (
    <Card className="bg-card border-border/60 lg:col-span-1">
      <CardHeader>
        <CardTitle className="text-lg font-bold">فعالیت‌های کاربران</CardTitle>
      </CardHeader>
      <CardContent>
        {activities.length === 0 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">فعالیتی ثبت نشده است</p>
        ) : (
          <div className="space-y-5 max-h-[420px] overflow-y-auto pl-1">
            {activities.map((activity) => {
              const Icon = ICON_MAP[activity.icon as string] ?? Activity;
              const role = activity.userRole ? ROLE_LABEL[activity.userRole] : '';
              return (
                <div key={activity.id} className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg shrink-0 ${activity.bg ?? 'bg-muted'}`}>
                    <Icon className={`w-4 h-4 ${activity.color ?? 'text-muted-foreground'}`} />
                  </div>
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <p className="text-sm text-foreground leading-relaxed">
                      <span className="font-bold">{activity.user}</span>
                      {role ? <span className="text-muted-foreground text-xs"> ({role})</span> : null}
                      {' '}{activity.action}
                    </p>
                    <p className="text-xs text-muted-foreground">{activity.time}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
