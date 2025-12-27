'use client';

import { BookOpen, ChevronDown } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

interface ClassInfoFormProps {
  isExpanded: boolean;
  onToggle: () => void;
}

export function ClassInfoForm({ isExpanded, onToggle }: ClassInfoFormProps) {
  return (
    <Card className="border-border/50 rounded-2xl overflow-hidden">
      <CardHeader 
        className="cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={onToggle}
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
            isExpanded && "rotate-180"
          )} />
        </div>
      </CardHeader>
      {isExpanded && (
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
  );
}