'use client';

import { useState } from 'react';
import { Save, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { ExamPrepSessionDetail } from '@/services/classes-service';

interface ExamEditFormProps {
  examDetail: ExamPrepSessionDetail;
  onSave: (data: Partial<ExamPrepSessionDetail>) => Promise<void>;
  isSaving?: boolean;
}

const levelOptions = [
  { value: 'مبتدی', label: 'مبتدی' },
  { value: 'متوسط', label: 'متوسط' },
  { value: 'پیشرفته', label: 'پیشرفته' },
];

export function ExamEditForm({ examDetail, onSave, isSaving }: ExamEditFormProps) {
  const [formData, setFormData] = useState({
    title: examDetail.title,
    description: examDetail.description,
    level: examDetail.level || 'مبتدی' as const,
    duration: examDetail.duration || '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSave({
      title: formData.title,
      description: formData.description,
      level: formData.level,
      duration: formData.duration,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">اطلاعات کلی</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="title">عنوان آزمون (الزامی)</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
                placeholder="عنوان آزمون را وارد کنید"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="level">سطح (الزامی)</Label>
              <Select
                value={formData.level}
                onValueChange={(value: 'مبتدی' | 'متوسط' | 'پیشرفته') =>
                  setFormData((prev) => ({ ...prev, level: value }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب سطح" />
                </SelectTrigger>
                <SelectContent>
                  {levelOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="duration">زمان تقریبی</Label>
              <Input
                id="duration"
                value={formData.duration}
                onChange={(e) => setFormData((prev) => ({ ...prev, duration: e.target.value }))}
                placeholder="مثلاً ۱ ساعت یا ۳۰ دقیقه"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">توضیحات</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="توضیحات آزمون را وارد کنید"
              rows={4}
            />
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={isSaving}>
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin ml-2" />
              ) : (
                <Save className="h-4 w-4 ml-2" />
              )}
              ذخیره تغییرات
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
