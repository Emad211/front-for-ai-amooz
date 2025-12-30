'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ClassInfoForm } from '@/components/admin/create-class/class-info-form';
import { FileUploadSection } from '@/components/admin/create-class/file-upload-section';
import { StudentInviteSection } from '@/components/admin/create-class/student-invite-section';
import { Card } from '@/components/ui/card';

export default function CreateClassPage() {
  const [expandedSections, setExpandedSections] = useState<string[]>(['info', 'files', 'exercises', 'students']);

  const toggleSection = (section: string) => {
    setExpandedSections(prev => 
      prev.includes(section) 
        ? prev.filter(s => s !== section)
        : [...prev, section]
    );
  };

  return (
    <div className="space-y-8" dir="rtl">
      {/* هدر صفحه با گرادیان */}
      <Card className="relative overflow-hidden border-border/40 bg-gradient-to-l from-primary/10 via-background to-background rounded-3xl shadow-xl shadow-primary/5">
        <div className="absolute inset-y-0 left-0 w-40 bg-primary/10 blur-3xl" />
        <div className="relative p-6 sm:p-8 flex flex-col gap-3">
          <div className="flex items-center gap-3 text-primary">
            <span className="h-10 w-10 rounded-2xl bg-primary/10 flex items-center justify-center font-black text-lg">+</span>
            <p className="text-sm text-primary">مسیر ساخت کلاس</p>
          </div>
          <div className="flex flex-col gap-2">
            <h1 className="text-2xl md:text-3xl font-black text-foreground">ایجاد کلاس جدید</h1>
            <p className="text-muted-foreground text-sm md:text-base">اطلاعات را تکمیل کنید، فایل‌ها را بارگذاری کنید و با کد دعوت دانش‌آموزان را اضافه کنید.</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs md:text-sm text-muted-foreground">
            <span className="px-3 py-1 rounded-full bg-primary/10 text-primary">۱. اطلاعات کلاس</span>
            <span className="px-3 py-1 rounded-full bg-muted">۲. فایل‌ها و تمرین‌ها</span>
            <span className="px-3 py-1 rounded-full bg-muted">۳. دعوت دانش‌آموزان</span>
          </div>
        </div>
      </Card>

      {/* بخش اطلاعات کلاس */}
      <ClassInfoForm 
        isExpanded={expandedSections.includes('info')} 
        onToggle={() => toggleSection('info')} 
      />

      {/* بخش بارگذاری فایل */}
      <FileUploadSection 
        title="بارگذاری فایل درسی"
        icon="upload"
        type="lesson"
        isExpanded={expandedSections.includes('files')}
        onToggle={() => toggleSection('files')}
      />

      {/* بخش بارگذاری تمرین */}
      <FileUploadSection 
        title="بارگذاری تمرین"
        description="اختیاری"
        icon="exercise"
        type="exercise"
        isExpanded={expandedSections.includes('exercises')}
        onToggle={() => toggleSection('exercises')}
      />

      {/* بخش دعوت دانش‌آموزان */}
      <StudentInviteSection 
        isExpanded={expandedSections.includes('students')}
        onToggle={() => toggleSection('students')}
      />

      {/* دکمه‌های پایین */}
      <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-4">
        <Button variant="outline" className="w-full sm:w-auto rounded-xl h-11 px-6">
          انصراف
        </Button>
        <Button className="w-full sm:w-auto bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl h-11 px-8">
          ذخیره و انتشار
        </Button>
      </div>
    </div>
  );
}
