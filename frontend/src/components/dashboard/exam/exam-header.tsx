'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowLeft, PanelRightClose } from 'lucide-react';

interface ExamHeaderProps {
  onToggle: () => void;
}

export const ExamHeader = ({ onToggle }: ExamHeaderProps) => (
  <header className="flex items-center justify-between px-4 border-b border-border w-full h-[73px]">
    <Button
      variant="outline"
      asChild
      className="bg-card hover:bg-card/80 border-border text-muted-foreground hover:text-foreground rounded-xl p-3 flex items-center justify-between transition-all group h-12"
    >
      <Link href="/exam-prep">
        <ArrowLeft className="text-muted-foreground group-hover:text-foreground group-hover:-translate-x-1 transition-all h-5 w-5 ml-2" />
        <span className="text-sm font-medium">بازگشت</span>
      </Link>
    </Button>
    <div className="text-center">
      <h1 className="text-xl font-bold text-foreground">بررسی کنکور تیر 1403 - ریاضی</h1>
    </div>
    <div className="flex items-center gap-4">
      <Button
        onClick={onToggle}
        variant="ghost"
        size="icon"
        className="h-12 w-12 rounded-lg text-muted-foreground hover:text-foreground md:hidden"
      >
        <PanelRightClose className="h-5 w-5" />
      </Button>
    </div>
  </header>
);
