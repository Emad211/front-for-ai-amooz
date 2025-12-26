'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { User, Trash2 } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Card } from '@/components/ui/card';

export default function CreateClassPage() {
  const [invitedStudents, setInvitedStudents] = useState([
    { email: 'student1@example.com', avatar: 'https://picsum.photos/seed/s1/40/40' },
  ]);
  const [newStudent, setNewStudent] = useState('');

  const handleAddStudent = () => {
    if (newStudent && !invitedStudents.find(s => s.email === newStudent)) {
      setInvitedStudents([...invitedStudents, { email: newStudent, avatar: `https://picsum.photos/seed/${newStudent}/40/40` }]);
      setNewStudent('');
    }
  };

  const handleRemoveStudent = (email) => {
    setInvitedStudents(invitedStudents.filter(s => s.email !== email));
  };

  return (
    <div className="flex-1 space-y-8">
       <h1 className="text-3xl font-bold text-foreground">ایجاد کلاس مجازی جدید</h1>

      <Accordion type="multiple" defaultValue={['item-1', 'item-4']} className="space-y-6">
        <AccordionItem value="item-1" asChild>
          <Card className="bg-card border-border rounded-2xl overflow-hidden">
            <AccordionTrigger className="p-6 text-lg font-bold hover:no-underline">
              اطلاعات کلاس
            </AccordionTrigger>
            <AccordionContent className="p-6 pt-0">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label htmlFor="class-title" className="text-sm font-medium text-muted-foreground">عنوان کلاس</label>
                  <Input id="class-title" placeholder="مثال: آموزش برنامه نویسی پایتون" className="h-12 bg-background"/>
                </div>
                <div className="space-y-2">
                  <label htmlFor="class-description" className="text-sm font-medium text-muted-foreground">توضیحات</label>
                  <Textarea id="class-description" placeholder="توضیحات مختصری در مورد کلاس بنویسید..." className="min-h-[120px] bg-background" />
                </div>
              </div>
            </AccordionContent>
          </Card>
        </AccordionItem>

        <AccordionItem value="item-2" asChild>
           <Card className="bg-card border-border rounded-2xl overflow-hidden">
            <AccordionTrigger className="p-6 text-lg font-bold hover:no-underline">
              بارگذاری فایل
            </AccordionTrigger>
            <AccordionContent className="p-6 pt-0">
               <div className="flex items-center justify-center w-full">
                    <label htmlFor="dropzone-file" className="flex flex-col items-center justify-center w-full h-32 border-2 border-border border-dashed rounded-lg cursor-pointer bg-background hover:bg-secondary/50">
                        <div className="flex flex-col items-center justify-center pt-5 pb-6">
                            <p className="mb-2 text-sm text-muted-foreground">برای بارگذاری، فایل را بکشید و رها کنید یا کلیک کنید</p>
                        </div>
                        <input id="dropzone-file" type="file" className="hidden" />
                    </label>
                </div> 
            </AccordionContent>
           </Card>
        </AccordionItem>

        <AccordionItem value="item-3" asChild>
          <Card className="bg-card border-border rounded-2xl overflow-hidden">
            <AccordionTrigger className="p-6 text-lg font-bold hover:no-underline">
              بارگذاری تمرین (اختیاری)
            </AccordionTrigger>
             <AccordionContent className="p-6 pt-0">
               <div className="flex items-center justify-center w-full">
                    <label htmlFor="dropzone-exercise" className="flex flex-col items-center justify-center w-full h-32 border-2 border-border border-dashed rounded-lg cursor-pointer bg-background hover:bg-secondary/50">
                        <div className="flex flex-col items-center justify-center pt-5 pb-6">
                            <p className="mb-2 text-sm text-muted-foreground">برای بارگذاری، فایل را بکشید و رها کنید یا کلیک کنید</p>
                        </div>
                        <input id="dropzone-exercise" type="file" className="hidden" />
                    </label>
                </div> 
            </AccordionContent>
          </Card>
        </AccordionItem>

        <AccordionItem value="item-4" asChild>
          <Card className="bg-card border-border rounded-2xl overflow-hidden">
            <AccordionTrigger className="p-6 text-lg font-bold hover:no-underline">
              دعوت دانش‌آموزان
            </AccordionTrigger>
            <AccordionContent className="p-6 pt-0 space-y-4">
              <p className="text-sm text-muted-foreground">می‌توانید دانش‌آموزان را بر اساس شماره یا ایمیل به کلاس اضافه کنید.</p>
              <div className="flex gap-4">
                <Input 
                  value={newStudent}
                  onChange={(e) => setNewStudent(e.target.value)}
                  placeholder="ایمیل یا شماره تلفن دانش آموز را وارد کنید" 
                  className="h-12 bg-background flex-grow" 
                />
                <Button onClick={handleAddStudent} className="h-12 bg-primary text-primary-foreground hover:bg-primary/90">افزودن</Button>
              </div>
              <div className="space-y-3 pt-4">
                {invitedStudents.map((student) => (
                  <div key={student.email} className="flex items-center justify-between p-3 bg-background rounded-lg">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8">
                        <AvatarImage src={student.avatar} />
                        <AvatarFallback><User className="h-4 w-4" /></AvatarFallback>
                      </Avatar>
                      <span className="text-sm font-medium text-foreground">{student.email}</span>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => handleRemoveStudent(student.email)} className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </AccordionContent>
          </Card>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
