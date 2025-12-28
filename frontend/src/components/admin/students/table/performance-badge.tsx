'use client';

import { Badge } from '@/components/ui/badge';

const performanceConfig: Record<string, { label: string; color: string }> = {
  excellent: { label: 'عالی', color: 'bg-green-500/10 text-green-700 dark:text-green-400' },
  good: { label: 'خوب', color: 'bg-blue-500/10 text-blue-700 dark:text-blue-400' },
  'needs-improvement': { label: 'نیاز به بهبود', color: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400' },
};

export function StudentPerformanceBadge({ performance }: { performance: string }) {
  const config = performanceConfig[performance] || performanceConfig.good;
  return (
    <Badge className={config.color}>
      {config.label}
    </Badge>
  );
}
