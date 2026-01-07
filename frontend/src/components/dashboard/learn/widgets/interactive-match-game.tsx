'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { cn } from '@/lib/utils';
import { RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Pair {
  term: string;
  definition: string;
}

interface InteractiveMatchGameProps {
  pairs: Pair[];
}

type ItemState = 'idle' | 'selected' | 'matched' | 'wrong';

export function InteractiveMatchGame({ pairs }: InteractiveMatchGameProps) {
  const rawPairs = Array.isArray(pairs) ? pairs : [];
  const total = rawPairs.length;

  // Shuffle definitions once on mount
  const shuffledDefinitions = useMemo(() => {
    const defs = rawPairs.map((p, i) => ({ id: i, text: String(p.definition ?? '') }));
    for (let i = defs.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [defs[i], defs[j]] = [defs[j], defs[i]];
    }
    return defs;
  }, [rawPairs]);

  // State: which term is selected, matches, wrong pairs, score
  const [selectedTermId, setSelectedTermId] = useState<number | null>(null);
  const [matchedIds, setMatchedIds] = useState<Set<number>>(new Set());
  const [wrongPair, setWrongPair] = useState<{ termId: number; defId: number } | null>(null);
  const [score, setScore] = useState(0);
  const [feedback, setFeedback] = useState<{ text: string; type: 'success' | 'error' | 'complete' | 'info' } | null>(null);

  const selectTerm = useCallback(
    (id: number) => {
      if (matchedIds.has(id)) return;
      setSelectedTermId(id);
      setWrongPair(null);
    },
    [matchedIds]
  );

  const selectDefinition = useCallback(
    (defId: number) => {
      if (selectedTermId === null) {
        setFeedback({ text: 'اول از ستون راست یک مفهوم انتخاب کن!', type: 'info' });
        return;
      }
      if (matchedIds.has(defId)) return;

      const isCorrect = defId === selectedTermId;
      if (isCorrect) {
        const newMatched = new Set(matchedIds);
        newMatched.add(defId);
        setMatchedIds(newMatched);
        setScore((s) => s + 1);
        setFeedback({ text: 'آفرین! درست بود 🎉', type: 'success' });

        if (newMatched.size === total) {
          setTimeout(() => {
            setFeedback({ text: 'تبریک! همه موارد را درست تطبیق دادی 🏆', type: 'complete' });
          }, 400);
        }
      } else {
        setWrongPair({ termId: selectedTermId, defId });
        setFeedback({ text: 'اشتباه بود! دوباره امتحان کن', type: 'error' });
        setTimeout(() => {
          setWrongPair(null);
        }, 600);
      }
      setSelectedTermId(null);
    },
    [matchedIds, selectedTermId, total]
  );

  const reset = useCallback(() => {
    setMatchedIds(new Set());
    setScore(0);
    setSelectedTermId(null);
    setWrongPair(null);
    setFeedback(null);
  }, []);

  if (total === 0) {
    return <div className="text-sm text-muted-foreground p-4 text-center">بازی تطبیق موجود نیست.</div>;
  }

  const getTermState = (id: number): ItemState => {
    if (matchedIds.has(id)) return 'matched';
    if (wrongPair?.termId === id) return 'wrong';
    if (selectedTermId === id) return 'selected';
    return 'idle';
  };

  const getDefState = (id: number): ItemState => {
    if (matchedIds.has(id)) return 'matched';
    if (wrongPair?.defId === id) return 'wrong';
    return 'idle';
  };

  return (
    <div className="w-full py-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 px-1">
        <span className="text-xs font-medium text-muted-foreground">🎮 بازی تطبیق</span>
        <span className="text-xs text-muted-foreground">
          {score} / {total}
        </span>
      </div>

      {/* Columns */}
      <div className="grid grid-cols-2 gap-3">
        {/* Terms */}
        <div className="space-y-2">
          <div className="text-[10px] text-muted-foreground text-center mb-1">مفاهیم</div>
          {rawPairs.map((p, i) => {
            const state = getTermState(i);
            return (
              <div
                key={`term-${i}`}
                onClick={() => selectTerm(i)}
                className={cn(
                  'rounded-lg border p-2 cursor-pointer transition-all text-xs',
                  state === 'idle' && 'border-border bg-card hover:border-primary/40',
                  state === 'selected' && 'border-primary bg-primary/10',
                  state === 'matched' && 'border-green-500/50 bg-green-500/10 opacity-60 cursor-default',
                  state === 'wrong' && 'border-destructive bg-destructive/10 animate-shake'
                )}
              >
                <MarkdownWithMath markdown={String(p.term ?? '')} className="text-xs" renderKey={`term-${i}-${state}`} />
              </div>
            );
          })}
        </div>

        {/* Definitions */}
        <div className="space-y-2">
          <div className="text-[10px] text-muted-foreground text-center mb-1">تعاریف</div>
          {shuffledDefinitions.map((d) => {
            const state = getDefState(d.id);
            return (
              <div
                key={`def-${d.id}`}
                onClick={() => selectDefinition(d.id)}
                className={cn(
                  'rounded-lg border p-2 cursor-pointer transition-all text-xs',
                  state === 'idle' && 'border-border bg-card hover:border-primary/40',
                  state === 'matched' && 'border-green-500/50 bg-green-500/10 opacity-60 cursor-default',
                  state === 'wrong' && 'border-destructive bg-destructive/10 animate-shake'
                )}
              >
                <MarkdownWithMath markdown={d.text} className="text-xs" renderKey={`def-${d.id}-${state}`} />
              </div>
            );
          })}
        </div>
      </div>

      {/* Feedback */}
      {feedback && (
        <div
          className={cn(
            'mt-3 text-center text-xs py-2 px-3 rounded-lg border',
            feedback.type === 'success' && 'border-green-500/30 bg-green-500/10 text-green-600',
            feedback.type === 'error' && 'border-destructive/30 bg-destructive/10 text-destructive',
            feedback.type === 'complete' && 'border-primary/30 bg-primary/10 text-primary font-medium',
            feedback.type === 'info' && 'border-border bg-muted/50 text-muted-foreground'
          )}
        >
          {feedback.text}
        </div>
      )}

      {/* Reset */}
      <div className="flex justify-center mt-3">
        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={reset}>
          <RotateCcw className="h-3 w-3 ml-1" />
          شروع مجدد
        </Button>
      </div>
    </div>
  );
}
