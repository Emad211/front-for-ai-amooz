'use client';

import React from 'react';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';

interface NoteItem {
  title?: string;
  notes_markdown?: string;
  summary_markdown?: string;
}

interface InteractiveNotesProps {
  items: NoteItem[];
}

export function InteractiveNotes({ items }: InteractiveNotesProps) {
  const notes = Array.isArray(items) ? items : [];

  if (notes.length === 0) {
    return <div className="text-sm text-muted-foreground p-4 text-center">نکته‌ای موجود نیست.</div>;
  }

  return (
    <div className="w-full py-2 space-y-3">
      <div className="text-xs font-medium text-muted-foreground px-1">📝 جزوه و نکات</div>

      {notes.map((n, idx) => {
        const title = String(n.title ?? '').trim();
        const content = String(n.notes_markdown ?? n.summary_markdown ?? '').trim();

        return (
          <div key={idx} className="rounded-xl border border-border bg-card p-3">
            {title && <div className="text-xs font-bold text-foreground mb-2">{title}</div>}
            {content && <MarkdownWithMath markdown={content} className="text-xs text-muted-foreground" />}
          </div>
        );
      })}
    </div>
  );
}
