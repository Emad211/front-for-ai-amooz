'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface ClassInfoCardProps {
  description: string;
  tags: string[];
  objectives?: string[];
}

export function ClassInfoCard({ description, tags, objectives }: ClassInfoCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">درباره کلاس</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground leading-relaxed">{description}</p>

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

        <div className="flex flex-wrap gap-2 mt-4">
          {tags.map(tag => (
            <Badge key={tag} variant="secondary" className="rounded-full">{tag}</Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
