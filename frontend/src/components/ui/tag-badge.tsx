'use client';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const TAG_COLORS: Record<string, string> = {
  'هوش مصنوعی': 'bg-green-500/20 text-green-400 border-green-500/30',
  'ریاضیات': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  'فیزیک': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'برنامه‌نویسی': 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  'برنامه نویسی': 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  'زبان': 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  'ادبیات': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  'آمار': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

interface TagBadgeProps {
  tag: string;
  className?: string;
}

export const TagBadge = ({ tag, className }: TagBadgeProps) => {
  const colorClass = TAG_COLORS[tag] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  
  return (
    <Badge
      variant="secondary"
      className={cn(
        "bg-opacity-20 text-sm font-normal border mr-2",
        colorClass,
        className
      )}
    >
      {tag}
    </Badge>
  );
};
