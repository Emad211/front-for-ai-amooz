'use client';

import React, { useState, useCallback } from 'react';
import { ChevronRight, ChevronLeft, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { cn } from '@/lib/utils';

interface Flashcard {
  front: string;
  back: string;
}

interface InteractiveFlashcardProps {
  flashcards: Flashcard[];
}

export function InteractiveFlashcard({ flashcards }: InteractiveFlashcardProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  const cards = Array.isArray(flashcards) ? flashcards : [];
  const total = cards.length;
  const current = cards[currentIndex] ?? { front: '', back: '' };

  const flip = useCallback(() => setIsFlipped((f) => !f), []);
  const next = useCallback(() => {
    if (currentIndex < total - 1) {
      setCurrentIndex((i) => i + 1);
      setIsFlipped(false);
    }
  }, [currentIndex, total]);
  const prev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex((i) => i - 1);
      setIsFlipped(false);
    }
  }, [currentIndex]);
  const reset = useCallback(() => {
    setCurrentIndex(0);
    setIsFlipped(false);
  }, []);

  if (total === 0) {
    return <div className="text-sm text-muted-foreground p-4 text-center">فلش‌کارتی موجود نیست.</div>;
  }

  return (
    <div className="w-full py-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 px-1">
        <span className="text-xs font-medium text-muted-foreground">📚 فلش‌کارت</span>
        <span className="text-xs text-muted-foreground">
          {currentIndex + 1} / {total}
        </span>
      </div>

      {/* Card Container */}
      <div className="perspective-[1000px] w-full h-40 sm:h-48 md:h-56 cursor-pointer" onClick={flip}>
        <div
          className={cn(
            'relative w-full h-full transition-transform duration-500 [transform-style:preserve-3d]',
            isFlipped && '[transform:rotateY(180deg)]'
          )}
        >
          {/* Front */}
          <div className="absolute inset-0 [backface-visibility:hidden] rounded-xl border border-border bg-card flex items-center justify-center p-2 sm:p-4 overflow-auto">
            <MarkdownWithMath markdown={String(current.front ?? '')} className="text-sm text-center" renderKey={`front-${currentIndex}-${isFlipped}`} />
          </div>
          {/* Back */}
          <div className="absolute inset-0 [backface-visibility:hidden] [transform:rotateY(180deg)] rounded-xl border border-primary/30 bg-primary/5 flex items-center justify-center p-2 sm:p-4 overflow-auto">
            <MarkdownWithMath markdown={String(current.back ?? '')} className="text-sm text-center text-foreground" renderKey={`back-${currentIndex}-${isFlipped}`} />
          </div>
        </div>
      </div>

      {/* Hint */}
      <p className="text-[10px] text-muted-foreground text-center mt-2">برای دیدن پاسخ روی کارت کلیک کن</p>

      {/* Controls */}
      <div className="flex items-center justify-center gap-2 mt-3">
        <Button
          variant="outline"
          size="sm"
          className="h-10 sm:h-8 px-2 sm:px-3 text-xs rounded-lg"
          disabled={currentIndex === 0}
          onClick={(e) => {
            e.stopPropagation();
            prev();
          }}
        >
          <ChevronRight className="h-4 w-4 ml-1" />
          قبلی
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded-lg"
          onClick={(e) => {
            e.stopPropagation();
            reset();
          }}
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-10 sm:h-8 px-2 sm:px-3 text-xs rounded-lg"
          disabled={currentIndex === total - 1}
          onClick={(e) => {
            e.stopPropagation();
            next();
          }}
        >
          بعدی
          <ChevronLeft className="h-4 w-4 mr-1" />
        </Button>
      </div>
    </div>
  );
}
