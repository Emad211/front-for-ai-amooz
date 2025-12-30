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
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSave({
      ...formData,
      tags: formData.tags.split('،').map(t => t.trim()).filter(Boolean),
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
              <Label htmlFor="title">عنوان کلاس</Label>
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
              <Label htmlFor="level">سطح</Label>
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
