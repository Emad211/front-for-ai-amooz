'use client';

import { Upload, FileText, Plus, ChevronDown } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface FileUploadSectionProps {
  title: string;
  description?: string;
  icon: 'upload' | 'exercise';
  isExpanded: boolean;
  onToggle: () => void;
  type: 'lesson' | 'exercise';
}

export function FileUploadSection({ 
  title, 
  description, 
  icon, 
  isExpanded, 
  onToggle,
  type 
}: FileUploadSectionProps) {
  const Icon = icon === 'upload' ? Upload : FileText;
  const iconColor = type === 'lesson' ? 'text-blue-500' : 'text-amber-500';
  const bgColor = type === 'lesson' ? 'bg-blue-500/10' : 'bg-amber-500/10';

  return (
    <Card className="border-border/50 rounded-2xl overflow-hidden">
      <CardHeader 
        className="cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", bgColor)}>
              <Icon className={cn("h-5 w-5", iconColor)} />
            </div>
            <div>
              <CardTitle className="text-lg">{title}</CardTitle>
              {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
            </div>
          </div>
          <ChevronDown className={cn(
            "h-5 w-5 text-muted-foreground transition-transform duration-200",
            isExpanded && "rotate-180"
          )} />
        </div>
      </CardHeader>
      {isExpanded && (
        <CardContent className="pt-0">
          <label 
            htmlFor={`dropzone-${type}`} 
            className={cn(
              "flex flex-col items-center justify-center w-full border-2 border-dashed border-border/50 rounded-xl cursor-pointer bg-muted/20 hover:bg-muted/40 transition-colors",
              type === 'lesson' ? "h-40" : "h-32"
            )}
          >
            <div className="flex flex-col items-center gap-2 px-4 text-center">
              {type === 'lesson' ? (
                <>
                  <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
                    <FileText className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    فایل‌ها را بکشید و رها کنید یا <span className="text-primary font-medium">کلیک کنید</span>
                  </p>
                  <p className="text-[10px] sm:text-xs text-muted-foreground">
                    PDF, DOCX, PPTX تا ۵۰ مگابایت
                  </p>
                </>
              ) : (
                <>
                  <Plus className="h-6 w-6 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">افزودن فایل تمرین</p>
                </>
              )}
            </div>
            <input id={`dropzone-${type}`} type="file" className="hidden" multiple={type === 'lesson'} />
          </label>
        </CardContent>
      )}
    </Card>
  );
}