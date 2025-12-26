// app/admin/create-class/page.tsx
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { 
  User, 
  Trash2, 
  Upload, 
  FileText, 
  Users, 
  BookOpen,
  ChevronDown,
  Plus,
  Copy,
  Check
} from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface Student {
  email: string;
  avatar: string;
}

export default function CreateClassPage() {
  const [invitedStudents, setInvitedStudents] = useState<Student[]>([
    { email: 'student1@example.com', avatar: 'https://picsum.photos/seed/s1/40/40' },
  ]);
  const [newStudent, setNewStudent] = useState('');
  const [expandedSections, setExpandedSections] = useState<string[]>(['info', 'students']);
  const [copied, setCopied] = useState(false);

  const inviteCode = 'AI-AMOOZ-2024';

  const toggleSection = (section: string) => {
    setExpandedSections(prev => 
      prev.includes(section) 
        ? prev.filter(s => s !== section)
        : [...prev, section]
    );
  };

  const handleAddStudent = () => {
    if (newStudent && !invitedStudents.find(s => s.email === newStudent)) {
      setInvitedStudents([...invitedStudents, { 
        email: newStudent, 
        avatar: `https://picsum.photos/seed/${newStudent}/40/40` 
      }]);
      setNewStudent('');
    }
  };

  const handleRemoveStudent = (email: string) => {
    setInvitedStudents(invitedStudents.filter(s => s.email !== email));
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(inviteCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-4xl space-y-6">
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
        <Button className="bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl h-11 px-6">
          ذخیره و انتشار
        </Button>
      </div>

      {/* بخش اطلاعات کلاس */}
      <Card className="border-border/50 rounded-2xl overflow-hidden">
        <CardHeader 
          className="cursor-pointer hover:bg-muted/30 transition-colors"
          onClick={() => toggleSection('info')}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <BookOpen className="h-5 w-5 text-primary" />
              </div>
              <CardTitle className="text-lg">اطلاعات کلاس</CardTitle>
            </div>
            <ChevronDown className={cn(
              "h-5 w-5 text-muted-foreground transition-transform duration-200",
              expandedSections.includes('info') && "rotate-180"
            )} />
          </div>
        </CardHeader>
        {expandedSections.includes('info') && (
          <CardContent className="pt-0 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="class-title">عنوان کلاس</Label>
              <Input 
                id="class-title" 
                placeholder="مثال: آموزش برنامه‌نویسی پایتون" 
                className="h-12 bg-background rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="class-description">توضیحات</Label>
              <Textarea 
                id="class-description" 
                placeholder="توضیحات مختصری درباره کلاس بنویسید..." 
                className="min-h-[100px] bg-background rounded-xl resize-none" 
              />
            </div>
          </CardContent>
        )}
      </Card>

      {/* بخش بارگذاری فایل */}
      <Card className="border-border/50 rounded-2xl overflow-hidden">
        <CardHeader 
          className="cursor-pointer hover:bg-muted/30 transition-colors"
          onClick={() => toggleSection('files')}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <Upload className="h-5 w-5 text-blue-500" />
              </div>
              <CardTitle className="text-lg">بارگذاری فایل درسی</CardTitle>
            </div>
            <ChevronDown className={cn(
              "h-5 w-5 text-muted-foreground transition-transform duration-200",
              expandedSections.includes('files') && "rotate-180"
            )} />
          </div>
        </CardHeader>
        {expandedSections.includes('files') && (
          <CardContent className="pt-0">
            <label 
              htmlFor="dropzone-file" 
              className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-border/50 rounded-xl cursor-pointer bg-muted/20 hover:bg-muted/40 transition-colors"
            >
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
                  <FileText className="h-6 w-6 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">
                  فایل‌ها را بکشید و رها کنید یا <span className="text-primary font-medium">کلیک کنید</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  PDF, DOCX, PPTX تا ۵۰ مگابایت
                </p>
              </div>
              <input id="dropzone-file" type="file" className="hidden" multiple />
            </label>
          </CardContent>
        )}
      </Card>

      {/* بخش بارگذاری تمرین */}
      <Card className="border-border/50 rounded-2xl overflow-hidden">
        <CardHeader 
          className="cursor-pointer hover:bg-muted/30 transition-colors"
          onClick={() => toggleSection('exercises')}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                <FileText className="h-5 w-5 text-amber-500" />
              </div>
              <div>
                <CardTitle className="text-lg">بارگذاری تمرین</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">اختیاری</p>
              </div>
            </div>
            <ChevronDown className={cn(
              "h-5 w-5 text-muted-foreground transition-transform duration-200",
              expandedSections.includes('exercises') && "rotate-180"
            )} />
          </div>
        </CardHeader>
        {expandedSections.includes('exercises') && (
          <CardContent className="pt-0">
            <label 
              htmlFor="dropzone-exercise" 
              className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-border/50 rounded-xl cursor-pointer bg-muted/20 hover:bg-muted/40 transition-colors"
            >
              <div className="flex flex-col items-center gap-2">
                <Plus className="h-6 w-6 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">افزودن فایل تمرین</p>
              </div>
              <input id="dropzone-exercise" type="file" className="hidden" />
            </label>
          </CardContent>
        )}
      </Card>

      {/* بخش دعوت دانش‌آموزان */}
      <Card className="border-border/50 rounded-2xl overflow-hidden">
        <CardHeader 
          className="cursor-pointer hover:bg-muted/30 transition-colors"
          onClick={() => toggleSection('students')}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
                <Users className="h-5 w-5 text-green-500" />
              </div>
              <div>
                <CardTitle className="text-lg">دعوت دانش‌آموزان</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {invitedStudents.length} نفر اضافه شده
                </p>
              </div>
            </div>
            <ChevronDown className={cn(
              "h-5 w-5 text-muted-foreground transition-transform duration-200",
              expandedSections.includes('students') && "rotate-180"
            )} />
          </div>
        </CardHeader>
        {expandedSections.includes('students') && (
          <CardContent className="pt-0 space-y-5">
            {/* کد دعوت */}
            <div className="p-4 bg-muted/30 rounded-xl">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground">کد دعوت کلاس</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    این کد را با دانش‌آموزان به اشتراک بگذارید
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <code className="px-3 py-2 bg-background rounded-lg text-sm font-mono font-bold tracking-wider">
                    {inviteCode}
                  </code>
                  <Button 
                    variant="outline" 
                    size="icon" 
                    className="rounded-lg h-9 w-9"
                    onClick={handleCopyCode}
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>

            {/* افزودن دستی */}
            <div className="space-y-2">
              <Label>افزودن دستی</Label>
              <div className="flex gap-3">
                <Input 
                  value={newStudent}
                  onChange={(e) => setNewStudent(e.target.value)}
                  placeholder="ایمیل یا شماره تلفن" 
                  className="h-11 bg-background rounded-xl flex-1" 
                  onKeyDown={(e) => e.key === 'Enter' && handleAddStudent()}
                />
                <Button 
                  onClick={handleAddStudent} 
                  className="h-11 px-5 bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl"
                >
                  <Plus className="h-4 w-4 ml-2" />
                  افزودن
                </Button>
              </div>
            </div>

            {/* لیست دانش‌آموزان */}
            {invitedStudents.length > 0 && (
              <div className="space-y-2">
                <Label>دانش‌آموزان دعوت شده</Label>
                <div className="space-y-2">
                  {invitedStudents.map((student, index) => (
                    <div 
                      key={student.email} 
                      className="flex items-center justify-between p-3 bg-muted/30 rounded-xl group hover:bg-muted/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-6 h-6 rounded-full bg-muted text-xs flex items-center justify-center text-muted-foreground">
                          {index + 1}
                        </span>
                        <Avatar className="h-9 w-9">
                          <AvatarImage src={student.avatar} />
                          <AvatarFallback>
                            <User className="h-4 w-4" />
                          </AvatarFallback>
                        </Avatar>
                        <span className="text-sm font-medium text-foreground">
                          {student.email}
                        </span>
                      </div>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        onClick={() => handleRemoveStudent(student.email)} 
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {/* دکمه‌های پایین */}
      <div className="flex items-center justify-end gap-3 pt-4">
        <Button variant="outline" className="rounded-xl h-11 px-6">
          انصراف
        </Button>
        <Button className="bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl h-11 px-8">
          ذخیره و انتشار
        </Button>
      </div>
    </div>
  );
}