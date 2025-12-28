'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { 
  PieChart, 
  Pie, 
  Cell, 
  ResponsiveContainer, 
  Legend, 
  Tooltip 
} from 'recharts';

const data = [
  { name: 'ریاضی', value: 35 },
  { name: 'فیزیک', value: 25 },
  { name: 'شیمی', value: 20 },
  { name: 'زیست', value: 20 },
];

const COLORS = [
  'hsl(var(--primary))',
  '#6366f1',
  '#8b5cf6',
  '#ec4899',
];

export function ClassDistribution() {
  return (
    <Card className="bg-card border-border/60 lg:col-span-1">
      <CardHeader>
        <CardTitle className="text-lg font-bold">توزیع موضوعی کلاس‌ها</CardTitle>
        <CardDescription>درصد کلاس‌ها بر اساس دسته‌بندی</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={80}
                paddingAngle={5}
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'hsl(var(--card))', 
                  borderColor: 'hsl(var(--border))',
                  borderRadius: '12px',
                  fontSize: '12px'
                }}
              />
              <Legend 
                verticalAlign="bottom" 
                height={36}
                formatter={(value) => <span className="text-xs font-medium text-muted-foreground">{value}</span>}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
