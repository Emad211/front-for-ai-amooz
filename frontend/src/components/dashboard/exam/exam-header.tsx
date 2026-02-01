'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowLeft, PanelRightClose } from 'lucide-react';

interface ExamHeaderProps {
  onToggle: () => void;
  title: string;
}

export const ExamHeader = ({ onToggle, title }: ExamHeaderProps) => (
  <header className="hidden lg:flex items-center justify-between px-4 border-b border-border w-full h-[73px]">
    <Button
      variant="outline"
      asChild
      className="hidden md:flex bg-card hover:bg-card/80 border-border text-muted-foreground hover:text-foreground rounded-xl p-3 items-center justify-between transition-all group h-12"
    >
      <Link href="/exam-prep">
        <ArrowLeft className="text-muted-foreground group-hover:text-foreground group-hover:-translate-x-1 transition-all h-5 w-5 ml-2" />
        <span className="text-sm font-medium">بازگشت</span>
      </Link>
    </Button>
    <div className="text-center">
      <h1 className="text-xl font-bold text-foreground">{title}</h1>
    </div>
    <div className="flex items-center gap-4 w-[100px] justify-end">
      {/* Toggle button removed to avoid redundancy with ChatAssistant's own close button */}
    </div>
  </header>
);
