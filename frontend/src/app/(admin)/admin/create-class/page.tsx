'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ClassInfoForm } from '@/components/admin/create-class/class-info-form';
import { FileUploadSection } from '@/components/admin/create-class/file-upload-section';
import { StudentInviteSection } from '@/components/admin/create-class/student-invite-section';

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
    <div className="space-y-6" dir="rtl">
      {/* هدر صفحه */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-foreground">
            ایجاد کلاس جدید
          </h1>
          <p className="text-muted-foreground mt-1">
            یک کلاس مجازی جدید بسازید و دانش‌آموزان را دعوت کنید
          </p>
        </div>
      </div>

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
