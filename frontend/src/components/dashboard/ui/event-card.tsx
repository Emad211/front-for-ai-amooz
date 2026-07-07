'use client';

import { ArrowLeft } from 'lucide-react';
import { Event } from '@/types';
import { MathText } from '@/components/content/math-text';
import Link from 'next/link';
import { cn } from '@/lib/utils';

interface EventCardProps extends Event {
  href?: string;
}

export const EventCard = ({ title, status, icon, date, month, href }: EventCardProps) => {
  const content = (
    <>
      <div className="flex items-center gap-4">
        <div className="flex flex-col items-center justify-center bg-primary/10 text-primary rounded-xl w-12 h-12 md:w-14 md:h-14 flex-shrink-0 border border-primary/20 group-hover:bg-primary group-hover:text-primary-foreground transition-all duration-300">
          <span className="text-lg font-black leading-none">{date}</span>
          <span className="text-[10px] font-bold uppercase mt-1">{month}</span>
        </div>
        <div>
          <h4 className="font-bold text-foreground group-hover:text-primary transition-colors">
            <MathText text={title} />
          </h4>
          <p className="text-xs text-muted-foreground flex items-center gap-1.5 mt-1.5">
            <span className="p-1 bg-background rounded-md border border-border group-hover:border-primary/30 transition-colors">
              {icon}
            </span>
            <span className="font-medium">{status}</span>
          </p>
        </div>
      </div>
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-background border border-border group-hover:border-primary/50 group-hover:text-primary transition-all duration-300 opacity-50 group-hover:opacity-100 md:opacity-0 md:group-hover:opacity-100 translate-x-0 md:-translate-x-2 md:group-hover:translate-x-0">
        <ArrowLeft className="h-4 w-4" />
      </div>
    </>
  );

  const className = cn(
    'group flex min-h-20 items-center justify-between bg-muted/30 p-4 rounded-2xl border border-transparent transition-all duration-300',
    href
      ? 'cursor-pointer hover:bg-muted/50 hover:border-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'
      : 'cursor-default'
  );

  if (href) {
    return (
      <Link href={href} className={className}>
        {content}
      </Link>
    );
  }

  return <div className={className}>{content}</div>;
};
