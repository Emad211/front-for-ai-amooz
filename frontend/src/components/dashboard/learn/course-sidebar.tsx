'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
  List,
  Flag,
  Hourglass,
  Folder,
  FolderOpen,
  FileText,
  PlayCircle,
  CheckCircle,
  Book,
  Lock,
  BookOpen,
  Settings,
  RotateCcw,
} from 'lucide-react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { SidebarItem, SubmenuItem } from './sidebar-items';

export const CourseSidebar = () => (
  <aside className="w-80 flex-shrink-0 flex-col gap-3 hidden lg:flex h-full">
    <Button
      variant="outline"
      asChild
      className="bg-card hover:bg-card/80 border-border text-muted-foreground hover:text-foreground rounded-xl p-3 flex items-center justify-between transition-all group h-12"
    >
      <Link href="/classes">
        <span className="text-base font-medium pr-1">بازگشت به لیست دوره‌ها</span>
        <ArrowLeft className="text-muted-foreground group-hover:text-foreground group-hover:-translate-x-1 transition-all h-5 w-5" />
      </Link>
    </Button>
    <div className="flex-1 bg-card border border-border rounded-2xl flex flex-col overflow-hidden shadow-lg">
      <div className="p-4 border-b border-border/50 flex items-center justify-between">
        <h3 className="font-bold text-foreground text-sm flex items-center gap-2">
          <List className="text-primary h-5 w-5" />
          فهرست مطالب
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1 no-scrollbar">
        <SidebarItem icon={<Flag className="h-5 w-5" />} title="اهداف یادگیری" />
        <SidebarItem icon={<Hourglass className="h-5 w-5" />} title="پیش نیازها" />

        <Accordion type="single" collapsible defaultValue="item-1" className="w-full">
          <AccordionItem value="item-1" className="border-none">
            <AccordionTrigger className="p-3 rounded-xl hover:no-underline hover:bg-secondary/30 text-foreground data-[state=open]:font-bold data-[state=open]:border data-[state=open]:border-border group">
              <div className="flex items-center gap-3">
                <Folder className="h-5 w-5 group-data-[state=open]:hidden" />
                <FolderOpen className="h-5 w-5 hidden group-data-[state=open]:block" />
                <span className="text-base">آشنایی با سهمی</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="p-1 space-y-1">
              <SubmenuItem icon={<FileText className="h-4 w-4" />} title="شکل کلی و جهت سهمی" />
              <SubmenuItem icon={<PlayCircle className="h-4 w-4" />} title="رأس سهمی: مهمترین نقطه" active />
              <SubmenuItem icon={<FileText className="h-4 w-4" />} title="ارتباط رأس با نقاط متقارن" />
              <SubmenuItem icon={<FileText className="h-4 w-4" />} title="عرض از مبدأ و ریشه‌ها" />
              <SubmenuItem icon={<CheckCircle className="h-4 w-4" />} title="آزمون فصل" special />
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="item-2" className="border-none">
            <AccordionTrigger className="p-3 rounded-xl hover:no-underline hover:bg-secondary/30 text-muted-foreground hover:text-foreground group data-[state=open]:font-bold data-[state=open]:border data-[state=open]:border-border">
              <div className="flex items-center gap-3">
                <Folder className="h-5 w-5 group-data-[state=open]:hidden" />
                <FolderOpen className="h-5 w-5 hidden group-data-[state=open]:block" />
                <span className="text-base font-medium">گام به گام رسم نمودار</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="p-1 space-y-1">
              <SubmenuItem icon={<FileText className="h-4 w-4" />} title="مثال عملی رسم سهمی با a>0" />
              <SubmenuItem icon={<FileText className="h-4 w-4" />} title="مثال عملی رسم سهمی با a<0" />
              <SubmenuItem icon={<CheckCircle className="h-4 w-4" />} title="آزمون فصل" special />
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="item-3" className="border-none">
            <AccordionTrigger className="p-3 rounded-xl hover:no-underline hover:bg-secondary/30 text-muted-foreground hover:text-foreground group data-[state=open]:font-bold data-[state=open]:border data-[state=open]:border-border">
              <div className="flex items-center gap-3">
                <Folder className="h-5 w-5 group-data-[state=open]:hidden" />
                <FolderOpen className="h-5 w-5 hidden group-data-[state=open]:block" />
                <span className="text-base font-medium">حل مسائل مربوطه</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="p-1 space-y-1">
              <SubmenuItem icon={<FileText className="h-4 w-4" />} title="یافتن ضرایب با استفاده از رأس سهمی" />
              <SubmenuItem icon={<FileText className="h-4 w-4" />} title="یافتن ضریب با استفاده از مقدار مینیمم" />
              <SubmenuItem icon={<Book className="h-4 w-4" />} title="آزمون فصل" />
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        <SidebarItem icon={<Lock className="h-5 w-5" />} title="آزمون نهایی دوره" disabled />
        <SidebarItem icon={<BookOpen className="h-5 w-5" />} title="خلاصه و نکات" />
      </div>
      <div className="p-3 border-t border-border/50 space-y-2 bg-background/20">
        <Button
          variant="outline"
          className="w-full justify-between p-2.5 h-auto bg-secondary/50 border-border text-primary hover:bg-primary/10 hover:border-primary/30 transition-all"
        >
          <span className="text-sm font-bold">دانلود جزوه</span>
          <BookOpen className="h-4 w-4" />
        </Button>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1 justify-center gap-2 p-2.5 h-auto bg-secondary/50 border-border text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <span className="text-sm font-medium">تنظیمات</span>
            <Settings className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            className="flex-1 justify-center gap-2 p-2.5 h-auto bg-secondary/50 border-border text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <span className="text-sm font-medium">شروع مجدد</span>
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  </aside>
);
