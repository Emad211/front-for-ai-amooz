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
import type { ClassDetail } from '@/types';

interface ClassEditFormProps {
  classDetail: ClassDetail;
  onSave: (data: Partial<ClassDetail>) => Promise<void>;
  isSaving?: boolean;
}

const levelOptions = [
  { value: 'مبتدی', label: 'مبتدی' },
  { value: 'متوسط', label: 'متوسط' },
  { value: 'پیشرفته', label: 'پیشرفته' },
];

const statusOptions = [
  { value: 'draft', label: 'پیش‌نویس' },
  { value: 'active', label: 'فعال' },
  { value: 'paused', label: 'متوقف' },
  { value: 'archived', label: 'آرشیو شده' },
];

export function ClassEditForm({ classDetail, onSave, isSaving }: ClassEditFormProps) {
  const [formData, setFormData] = useState({
    title: classDetail.title,
    description: classDetail.description,
    category: classDetail.category || '',
    level: classDetail.level || 'مبتدی' as const,
    status: (classDetail.status || 'draft') as 'draft' | 'active' | 'paused' | 'archived',
    tags: classDetail.tags.join('، '),
    scheduleDay: classDetail.schedule?.[0]?.day || '',
    scheduleTime: classDetail.schedule?.[0]?.time || '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSave({
      title: formData.title,
      description: formData.description,
      category: formData.category,
      level: formData.level,
      status: formData.status,
      tags: formData.tags.split('،').map(t => t.trim()).filter(Boolean),
      schedule: formData.scheduleDay && formData.scheduleTime
        ? [{ day: formData.scheduleDay, time: formData.scheduleTime }]
        : classDetail.schedule,
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
              <Label htmlFor="title">عنوان کلاس (الزامی)</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={e => setFormData(prev => ({ ...prev, title: e.target.value }))}
                placeholder="عنوان کلاس را وارد کنید"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="category">دسته‌بندی</Label>
              <Input
                id="category"
                value={formData.category}
                onChange={e => setFormData(prev => ({ ...prev, category: e.target.value }))}
                placeholder="دسته‌بندی"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="level">سطح (الزامی)</Label>
              <Select
                value={formData.level}
                onValueChange={(value: 'مبتدی' | 'متوسط' | 'پیشرفته') => setFormData(prev => ({ ...prev, level: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب سطح" />
                </SelectTrigger>
                <SelectContent>
                  {levelOptions.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="status">وضعیت</Label>
              <Select
                value={formData.status}
                onValueChange={(value: 'draft' | 'active' | 'paused' | 'archived') => setFormData(prev => ({ ...prev, status: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب وضعیت" />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="schedule">زمان‌بندی کلاس (الزامی)</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  id="schedule-day"
                  value={formData.scheduleDay}
                  onChange={e => setFormData(prev => ({ ...prev, scheduleDay: e.target.value }))}
                  placeholder="مثلاً دوشنبه"
                />
                <Input
                  id="schedule-time"
                  value={formData.scheduleTime}
                  onChange={e => setFormData(prev => ({ ...prev, scheduleTime: e.target.value }))}
                  placeholder="مثلاً 10:00 تا 12:00"
                />
              </div>
              <p className="text-xs text-muted-foreground">استاد باید زمان برگزاری را مشخص کند.</p>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">توضیحات</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={e => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="توضیحات کلاس را وارد کنید"
              rows={4}
            />
          </div>

          {Array.isArray(classDetail.objectives) && classDetail.objectives.length > 0 && (
            <div className="space-y-2">
              <Label>اهداف کلاس (از خروجی ساختاردهی)</Label>
              <div className="rounded-lg border bg-muted/30 p-4">
                <ul className="list-disc pr-5 text-sm text-muted-foreground space-y-1">
                  {classDetail.objectives.map((item, idx) => (
                    <li key={`${idx}-${item}`}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="tags">برچسب‌ها (با ویرگول جدا کنید)</Label>
            <Input
              id="tags"
              value={formData.tags}
              onChange={e => setFormData(prev => ({ ...prev, tags: e.target.value }))}
              placeholder="برچسب ۱، برچسب ۲، ..."
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
