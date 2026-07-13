'use client';

import { useId, useRef, useState } from 'react';
import { Eye, Keyboard, X } from 'lucide-react';

import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { MathText } from '@/components/content/math-text';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

type LatexMarkdownEditorProps = {
  label: string;
  previewLabel: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  rows?: number;
  className?: string;
};

type LatexShortcut = {
  label: string;
  accessibleLabel: string;
  template: string;
  cursorMarker?: string;
  selectedTemplate?: string;
};

const SHORTCUT_GROUPS: Array<{ title: string; shortcuts: LatexShortcut[] }> = [
  {
    title: 'پایه',
    shortcuts: [
      { label: '$+$', accessibleLabel: 'جمع', template: '$+$' },
      { label: '$-$', accessibleLabel: 'تفریق', template: '$-$' },
      { label: '$\\times$', accessibleLabel: 'ضرب', template: '$\\times$' },
      { label: '$\\div$', accessibleLabel: 'تقسیم', template: '$\\div$' },
      { label: '$=$', accessibleLabel: 'مساوی', template: '$=$' },
      { label: '$\\neq$', accessibleLabel: 'نامساوی', template: '$\\neq$' },
    ],
  },
  {
    title: 'ساختار',
    shortcuts: [
      {
        label: '$\\frac{a}{b}$',
        accessibleLabel: 'کسر',
        template: '$\\frac{◉}{}$',
        cursorMarker: '◉',
        selectedTemplate: '$\\frac{◆}{◉}$',
      },
      {
        label: '$\\sqrt{x}$',
        accessibleLabel: 'ریشه دوم',
        template: '$\\sqrt{◉}$',
        cursorMarker: '◉',
        selectedTemplate: '$\\sqrt{◆}$◉',
      },
      {
        label: '$\\sqrt[n]{x}$',
        accessibleLabel: 'ریشه با فرجه',
        template: '$\\sqrt[]{◉}$',
        cursorMarker: '◉',
        selectedTemplate: '$\\sqrt[]{◆}$◉',
      },
      {
        label: '$x^n$',
        accessibleLabel: 'توان',
        template: '$x^{◉}$',
        cursorMarker: '◉',
        selectedTemplate: '$◆^{◉}$',
      },
      {
        label: '$x_n$',
        accessibleLabel: 'اندیس',
        template: '$x_{◉}$',
        cursorMarker: '◉',
        selectedTemplate: '$◆_{◉}$',
      },
      {
        label: '$|x|$',
        accessibleLabel: 'قدر مطلق',
        template: '$|◉|$',
        cursorMarker: '◉',
        selectedTemplate: '$|◆|$◉',
      },
    ],
  },
  {
    title: 'مقایسه و مجموعه‌ها',
    shortcuts: [
      { label: '$<$', accessibleLabel: 'کوچک‌تر', template: '$<$' },
      { label: '$>$', accessibleLabel: 'بزرگ‌تر', template: '$>$' },
      { label: '$\\leq$', accessibleLabel: 'کوچک‌تر یا مساوی', template: '$\\leq$' },
      { label: '$\\geq$', accessibleLabel: 'بزرگ‌تر یا مساوی', template: '$\\geq$' },
      { label: '$\\in$', accessibleLabel: 'عضو مجموعه', template: '$\\in$' },
      { label: '$\\notin$', accessibleLabel: 'عضو مجموعه نیست', template: '$\\notin$' },
      { label: '$\\cup$', accessibleLabel: 'اجتماع', template: '$\\cup$' },
      { label: '$\\cap$', accessibleLabel: 'اشتراک', template: '$\\cap$' },
      { label: '$\\subset$', accessibleLabel: 'زیرمجموعه', template: '$\\subset$' },
      { label: '$\\emptyset$', accessibleLabel: 'مجموعه تهی', template: '$\\emptyset$' },
    ],
  },
  {
    title: 'نمادها',
    shortcuts: [
      { label: '$\\alpha$', accessibleLabel: 'آلفا', template: '$\\alpha$' },
      { label: '$\\beta$', accessibleLabel: 'بتا', template: '$\\beta$' },
      { label: '$\\theta$', accessibleLabel: 'تتا', template: '$\\theta$' },
      { label: '$\\pi$', accessibleLabel: 'پی', template: '$\\pi$' },
      {
        label: '$\\sin(x)$',
        accessibleLabel: 'سینوس',
        template: '$\\sin(◉)$',
        cursorMarker: '◉',
        selectedTemplate: '$\\sin(◆)$◉',
      },
      {
        label: '$\\cos(x)$',
        accessibleLabel: 'کسینوس',
        template: '$\\cos(◉)$',
        cursorMarker: '◉',
        selectedTemplate: '$\\cos(◆)$◉',
      },
      { label: '$\\sum$', accessibleLabel: 'مجموع', template: '$\\sum_{i=1}^{n} ◉$', cursorMarker: '◉' },
      { label: '$\\infty$', accessibleLabel: 'بی‌نهایت', template: '$\\infty$' },
    ],
  },
];

export function LatexMarkdownEditor({
  label,
  previewLabel,
  value,
  onChange,
  placeholder,
  rows = 3,
  className,
}: LatexMarkdownEditorProps) {
  const id = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [keyboardOpen, setKeyboardOpen] = useState(false);

  const insertShortcut = (shortcut: LatexShortcut) => {
    const textarea = textareaRef.current;
    const selectionStart = textarea?.selectionStart ?? value.length;
    const selectionEnd = textarea?.selectionEnd ?? selectionStart;
    const selectedText = value.slice(selectionStart, selectionEnd);
    const marker = shortcut.cursorMarker;
    let template = shortcut.template;
    if (selectedText && shortcut.selectedTemplate) {
      template = shortcut.selectedTemplate.replace('◆', selectedText);
    } else if (marker && selectedText) {
      template = shortcut.template.replace(marker, `${selectedText}${marker}`);
    }
    const cleanTemplate = marker ? template.replace(marker, '') : template;
    const markerIndex = marker ? template.indexOf(marker) : -1;
    const nextValue = value.slice(0, selectionStart) + cleanTemplate + value.slice(selectionEnd);
    const nextCursor = selectionStart + (markerIndex >= 0 ? markerIndex : cleanTemplate.length);

    onChange(nextValue);
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(nextCursor, nextCursor);
    });
  };

  return (
    <div className={cn('overflow-hidden rounded-lg border border-border/70 bg-background', className)}>
      <div className="border-b border-border/60 bg-muted/20 px-4 py-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Eye className="h-4 w-4" />
          <span>{previewLabel}</span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary">زنده</span>
        </div>
        {value.trim() ? (
          <div className="min-h-12 overflow-x-auto rounded-md border border-border/50 bg-background/80 px-3 py-2">
            <MarkdownWithMath markdown={value} allowImages={false} className="[&_.md-p]:text-sm" />
          </div>
        ) : (
          <div className="flex min-h-12 items-center rounded-md border border-dashed border-border/60 px-3 py-2 text-xs text-muted-foreground">
            پیش‌نمایش پس از نوشتن متن یا افزودن فرمول نمایش داده می‌شود.
          </div>
        )}
      </div>

      <div className="space-y-2 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label htmlFor={id} className="text-sm font-medium">{label}</Label>
          <Button
            type="button"
            size="sm"
            variant={keyboardOpen ? 'secondary' : 'outline'}
            aria-expanded={keyboardOpen}
            aria-controls={`${id}-keyboard`}
            onClick={() => setKeyboardOpen((current) => !current)}
          >
            {keyboardOpen ? <X className="ms-2 h-4 w-4" /> : <Keyboard className="ms-2 h-4 w-4" />}
            {keyboardOpen ? 'بستن کیبورد ریاضی' : 'کیبورد ریاضی'}
          </Button>
        </div>

        {keyboardOpen && (
          <div id={`${id}-keyboard`} className="space-y-3 rounded-md border border-border/60 bg-muted/20 p-3">
            <p className="text-xs leading-5 text-muted-foreground">
              نشانگر را در محل دلخواه بگذارید و نماد را انتخاب کنید. برای کسر، ریشه و توان، نشانگر داخل فرمول قرار می‌گیرد.
            </p>
            <div className="grid gap-3 lg:grid-cols-2">
              {SHORTCUT_GROUPS.map((group) => (
                <div key={group.title} className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">{group.title}</p>
                  <div className="flex flex-wrap justify-end gap-1.5" dir="ltr">
                    {group.shortcuts.map((shortcut) => (
                      <Button
                        key={shortcut.accessibleLabel}
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-9 min-w-10 bg-background px-2"
                        aria-label={`افزودن ${shortcut.accessibleLabel}`}
                        title={shortcut.accessibleLabel}
                        onClick={() => insertShortcut(shortcut)}
                      >
                        <MathText text={shortcut.label} />
                      </Button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <Textarea
          ref={textareaRef}
          id={id}
          dir="rtl"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          rows={rows}
          placeholder={placeholder}
          className="font-medium leading-7"
        />
      </div>
    </div>
  );
}
