'use client';

import { useId, useRef, useState } from 'react';
import { Eye, Keyboard, X } from 'lucide-react';

import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { MathText } from '@/components/content/math-text';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
      { label: '$-x$', accessibleLabel: 'عدد منفی', template: '$-◉$', cursorMarker: '◉' },
      { label: '$\\times$', accessibleLabel: 'ضرب', template: '$\\times$' },
      { label: '$\\div$', accessibleLabel: 'تقسیم', template: '$\\div$' },
      { label: '$=$', accessibleLabel: 'مساوی', template: '$=$' },
      { label: '$\\neq$', accessibleLabel: 'نامساوی', template: '$\\neq$' },
      { label: '$(x)$', accessibleLabel: 'پرانتز', template: '$(◉)$', cursorMarker: '◉' },
      { label: '$[x]$', accessibleLabel: 'کروشه', template: '$[◉]$', cursorMarker: '◉' },
    ],
  },
  {
    title: 'ساختار',
    shortcuts: [
      {
        label: '$x+1$',
        accessibleLabel: 'فرمول داخل جمله',
        template: '$◉$',
        cursorMarker: '◉',
      },
      {
        label: '$$x+1=2$$',
        accessibleLabel: 'فرمول در سطر جدا',
        template: '$$\n◉\n$$',
        cursorMarker: '◉',
      },
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
      {
        label: '$x\\%$',
        accessibleLabel: 'درصد',
        template: '$◉\\%$',
        cursorMarker: '◉',
      },
      {
        label: '$n!$',
        accessibleLabel: 'فاکتوریل',
        template: '$◉!$',
        cursorMarker: '◉',
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
      { label: '$\\Rightarrow$', accessibleLabel: 'نتیجه می‌دهد', template: '$\\Rightarrow$' },
      { label: '$\\Leftrightarrow$', accessibleLabel: 'اگر و تنها اگر', template: '$\\Leftrightarrow$' },
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
  {
    title: 'پیشرفته',
    shortcuts: [
      {
        label: '$\\lim_{x \\to a} f(x)$',
        accessibleLabel: 'حد',
        template: '$\\lim_{x \\to ◉} f(x)$',
        cursorMarker: '◉',
      },
      {
        label: '$\\int_a^b f(x)dx$',
        accessibleLabel: 'انتگرال',
        template: '$\\int_{◉}^{ } f(x)\\,dx$',
        cursorMarker: '◉',
      },
      {
        label: '$\\frac{d}{dx}f(x)$',
        accessibleLabel: 'مشتق',
        template: '$\\frac{d}{dx}\\left(◉\\right)$',
        cursorMarker: '◉',
      },
      {
        label: '$\\vec{v}$',
        accessibleLabel: 'بردار',
        template: '$\\vec{◉}$',
        cursorMarker: '◉',
        selectedTemplate: '$\\vec{◆}$◉',
      },
      { label: '$\\angle ABC$', accessibleLabel: 'زاویه', template: '$\\angle ABC$' },
      { label: '$90^\\circ$', accessibleLabel: 'درجه', template: '$◉^\\circ$', cursorMarker: '◉' },
      { label: '$\\parallel$', accessibleLabel: 'موازی', template: '$\\parallel$' },
      { label: '$\\perp$', accessibleLabel: 'عمود', template: '$\\perp$' },
      {
        label: '$\\begin{bmatrix}a&b\\\\c&d\\end{bmatrix}$',
        accessibleLabel: 'ماتریس دو در دو',
        template: '$$\\begin{bmatrix}◉ & 0 \\\\ 0 & 0\\end{bmatrix}$$',
        cursorMarker: '◉',
      },
      {
        label: '$\\begin{cases}x=1\\\\y=2\\end{cases}$',
        accessibleLabel: 'دستگاه معادلات',
        template: '$$\\begin{cases}◉ \\\\ {}\\end{cases}$$',
        cursorMarker: '◉',
      },
    ],
  },
];

function mathModeAt(text: string, cursor: number): '$' | '$$' | '\\(' | '\\[' | null {
  const tokenPattern = /(?<!\\)(\$\$|\$)|\\\(|\\\)|\\\[|\\\]/g;
  let mode: '$' | '$$' | '\\(' | '\\[' | null = null;
  let openingIndex = -1;
  for (const match of text.matchAll(tokenPattern)) {
    const token = match[0];
    const tokenIndex = match.index;
    if (!mode && (token === '$' || token === '$$' || token === '\\(' || token === '\\[')) {
      mode = token;
      openingIndex = tokenIndex;
    } else if (
      (mode === '$' && token === '$') ||
      (mode === '$$' && token === '$$') ||
      (mode === '\\(' && token === '\\)') ||
      (mode === '\\[' && token === '\\]')
    ) {
      if (openingIndex < cursor && cursor <= tokenIndex) return mode;
      mode = null;
      openingIndex = -1;
    }
  }
  return null;
}

function removeOuterMathDelimiters(template: string): string {
  const cursorSuffix = template.endsWith('◉') ? '◉' : '';
  const core = cursorSuffix ? template.slice(0, -1) : template;
  if (core.startsWith('$$') && core.endsWith('$$')) return core.slice(2, -2) + cursorSuffix;
  if (core.startsWith('$') && core.endsWith('$')) return core.slice(1, -1) + cursorSuffix;
  if (core.startsWith('\\(') && core.endsWith('\\)')) return core.slice(2, -2) + cursorSuffix;
  if (core.startsWith('\\[') && core.endsWith('\\]')) return core.slice(2, -2) + cursorSuffix;
  return template;
}

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
    if (mathModeAt(value, selectionStart)) {
      template = removeOuterMathDelimiters(template);
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
            <div className="flex flex-col gap-1 rounded-md bg-primary/5 px-3 py-2 text-xs leading-5 text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <span>برای ساخت معادله کامل، از «فرمول داخل جمله» یا «فرمول در سطر جدا» شروع کنید.</span>
              <span className="font-medium text-primary">متن انتخاب‌شده داخل قالب قرار می‌گیرد.</span>
            </div>
            <Tabs defaultValue="0" dir="rtl" className="space-y-3">
              <TabsList className="grid h-auto w-full grid-cols-3 gap-1 bg-background/70 p-1 sm:grid-cols-5">
                {SHORTCUT_GROUPS.map((group, index) => (
                  <TabsTrigger key={group.title} value={String(index)} className="min-h-9 text-xs">
                    {group.title}
                  </TabsTrigger>
                ))}
              </TabsList>
              {SHORTCUT_GROUPS.map((group, index) => (
                <TabsContent key={group.title} value={String(index)} className="mt-0">
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-5" dir="ltr">
                    {group.shortcuts.map((shortcut) => (
                      <Button
                        key={shortcut.accessibleLabel}
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-14 min-w-0 flex-col gap-0.5 bg-background px-1.5 py-1"
                        aria-label={`افزودن ${shortcut.accessibleLabel}`}
                        title={shortcut.accessibleLabel}
                        onClick={() => insertShortcut(shortcut)}
                      >
                        <MathText text={shortcut.label} className="max-w-full overflow-hidden text-sm" />
                        <span className="max-w-full truncate text-[10px] text-muted-foreground" dir="rtl">
                          {shortcut.accessibleLabel}
                        </span>
                      </Button>
                    ))}
                  </div>
                </TabsContent>
              ))}
            </Tabs>
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
