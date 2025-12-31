'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface ClassInfoCardProps {
  description: string;
  tags: string[];
}

export function ClassInfoCard({ description, tags }: ClassInfoCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">درباره کلاس</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground leading-relaxed">{description}</p>
        <div className="flex flex-wrap gap-2 mt-4">
          {tags.map(tag => (
            <Badge key={tag} variant="secondary" className="rounded-full">{tag}</Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
