'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CLASS_DESCRIPTION_MAX_LENGTH } from '@/constants/teacher-limits';

interface ClassInfoCardProps {
  description: string;
  tags: string[];
  objectives?: string[];
}

export function ClassInfoCard({ description, tags, objectives }: ClassInfoCardProps) {
  const normalizedDescription = (description || '').trim();
  const visibleDescription =
    normalizedDescription.length > CLASS_DESCRIPTION_MAX_LENGTH
      ? `${normalizedDescription.slice(0, CLASS_DESCRIPTION_MAX_LENGTH)}...`
      : normalizedDescription;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">درباره کلاس</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="max-w-full whitespace-pre-wrap break-words text-muted-foreground leading-relaxed [overflow-wrap:anywhere]">
          {visibleDescription || 'توضیحی برای این کلاس ثبت نشده است.'}
        </p>

        {Array.isArray(objectives) && objectives.length > 0 && (
          <div className="mt-4 space-y-2">
            <div className="text-sm font-bold">اهداف کلاس</div>
            <ul className="list-disc pr-5 text-sm text-muted-foreground space-y-1">
              {objectives.map((item, idx) => (
                <li key={`${idx}-${item}`}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap gap-2 sm:gap-3 mt-3 sm:mt-4">
          {tags.map(tag => (
            <Badge key={tag} variant="secondary" className="rounded-full">{tag}</Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
