'use client';

import React, { useState, useCallback } from 'react';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface Scenario {
  title?: string;
  context?: string;
  scenario?: string;
  challenge_question?: string;
  solution_hint?: string;
}

interface InteractiveScenarioProps {
  scenarios: Scenario[];
}

export function InteractiveScenario({ scenarios }: InteractiveScenarioProps) {
  const items = Array.isArray(scenarios) ? scenarios : [];

  const [expandedHints, setExpandedHints] = useState<Set<number>>(new Set());

  const toggleHint = useCallback((idx: number) => {
    setExpandedHints((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  }, []);

  if (items.length === 0) {
    return <div className="text-sm text-muted-foreground p-4 text-center">سناریویی موجود نیست.</div>;
  }

  return (
    <div className="w-full py-2 space-y-4">
      <div className="text-xs font-medium text-muted-foreground px-1">🎭 سناریو</div>

      {items.map((s, idx) => {
        const title = String(s.title ?? 'سناریو').trim();
        const context = String(s.context ?? s.scenario ?? '').trim();
        const question = String(s.challenge_question ?? '').trim();
        const hint = String(s.solution_hint ?? '').trim();
        const isExpanded = expandedHints.has(idx);

        return (
          <div key={idx} className="rounded-xl border border-border bg-card p-3">
            {/* Title */}
            <div className="text-sm font-bold text-foreground mb-2">{title}</div>

            {/* Context */}
            {context && (
              <div className="text-xs text-muted-foreground mb-2">
                <MarkdownWithMath markdown={context} className="text-xs" />
              </div>
            )}

            {/* Challenge Question */}
            {question && (
              <div className="text-xs font-medium text-foreground mt-2 p-2 rounded-lg bg-muted/50 border border-border/50">
                ❓ <MarkdownWithMath markdown={question} className="text-xs inline" />
              </div>
            )}

            {/* Hint Toggle */}
            {hint && (
              <div className="mt-3">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs text-muted-foreground"
                  onClick={() => toggleHint(idx)}
                >
                  💡 {isExpanded ? 'مخفی کردن راهنمایی' : 'نمایش راهنمایی'}
                  {isExpanded ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
                </Button>
                {isExpanded && (
                  <div className="mt-2 p-2 rounded-lg bg-primary/5 border border-primary/20 text-xs">
                    <MarkdownWithMath markdown={hint} className="text-xs" />
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
