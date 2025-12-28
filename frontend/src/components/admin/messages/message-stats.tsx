'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export function MessageStats() {
  return (
    <Card>
      <CardHeader className="text-start">
        <CardTitle className="text-lg">آمار پیام‌ها</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">پیام‌های ارسال شده امروز</span>
          <Badge variant="secondary">۱۲</Badge>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">کل پیام‌های ماه</span>
          <Badge variant="secondary">۱۴۵</Badge>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">میانگین نرخ بازدید</span>
          <Badge variant="outline" className="text-green-600 bg-green-50 border-green-200">۸۵٪</Badge>
        </div>
      </CardContent>
    </Card>
  );
}
