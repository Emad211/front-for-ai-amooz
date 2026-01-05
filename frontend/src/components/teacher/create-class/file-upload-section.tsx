'use client';

import { Upload, FileText, Plus, ChevronDown } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

interface FileUploadSectionProps {
  title: string;
  description?: string;
  icon: 'upload' | 'exercise';
  isExpanded: boolean;
  onToggle: () => void;
  type: 'lesson' | 'exercise';
  accept?: string;
  multiple?: boolean;
  onFilesSelected?: (files: FileList | null) => void;
  children?: ReactNode;
}

export function FileUploadSection({ 
  title, 
  description, 
  icon, 
  isExpanded, 
  onToggle,
  type,
  accept,
  multiple,
  onFilesSelected,
  children,
}: FileUploadSectionProps) {
  const Icon = icon === 'upload' ? Upload : FileText;
  const iconColor = type === 'lesson' ? 'text-primary' : 'text-muted-foreground';
  const bgColor = type === 'lesson' ? 'bg-primary/10' : 'bg-muted';

  return (
    <Card className="border-border/40 rounded-2xl overflow-hidden bg-card/70 backdrop-blur">
      <CardHeader 
        className="cursor-pointer hover:bg-primary/5 transition-colors"
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
              "flex flex-col items-center justify-center w-full border-2 border-dashed border-primary/30 rounded-2xl cursor-pointer bg-primary/5 hover:bg-primary/10 transition-colors",
              type === 'lesson' ? "h-44" : "h-36"
            )}
          >
            <div className="flex flex-col items-center gap-2 px-4 text-center">
              {type === 'lesson' ? (
                <>
                  <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                    <FileText className="h-6 w-6 text-primary" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    فایل‌ها را بکشید و رها کنید یا <span className="text-primary font-medium">کلیک کنید</span>
                  </p>
                  <p className="text-[10px] sm:text-xs text-muted-foreground">
                    Audio/Video تا ۵۰ مگابایت
                  </p>
                </>
              ) : (
                <>
                  <Plus className="h-6 w-6 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">افزودن فایل تمرین</p>
                </>
              )}
            </div>
            <input
              id={`dropzone-${type}`}
              type="file"
              className="hidden"
              accept={accept}
              multiple={multiple ?? type === 'lesson'}
              onChange={(e) => onFilesSelected?.(e.target.files)}
            />
          </label>

          {children}
        </CardContent>
      )}
    </Card>
  );
}