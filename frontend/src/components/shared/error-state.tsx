'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { AlertTriangle, Home, RotateCcw } from 'lucide-react';

export type ErrorStateVariant = 'error' | 'not-found';

export interface ErrorStateProps {
  title: string;
  description?: string;
  variant?: ErrorStateVariant;
  className?: string;

  /**
   * Optional technical details. Keep it short; this should not leak sensitive info.
   * Shown in a collapsible UI.
   */
  details?: string;

  /** Called by Next.js error boundary pages. */
  onRetry?: () => void;

  /** Defaults to '/home' (dashboard home). */
  homeHref?: string;

  /** Overrides the default primary/secondary CTAs. */
  primaryAction?: { label: string; onClick?: () => void; href?: string };
  secondaryAction?: { label: string; onClick?: () => void; href?: string };
}

function ActionButton({
  action,
  variant,
}: {
  action: { label: string; onClick?: () => void; href?: string };
  variant: 'default' | 'outline';
}) {
  if (action.href) {
    return (
      <Button asChild variant={variant} className="rounded-xl">
        <Link href={action.href}>{action.label}</Link>
      </Button>
    );
  }

  return (
    <Button variant={variant} onClick={action.onClick} className="rounded-xl">
      {action.label}
    </Button>
  );
}

export function ErrorState({
  title,
  description,
  variant = 'error',
  className,
  details,
  onRetry,
  homeHref = '/home',
  primaryAction,
  secondaryAction,
}: ErrorStateProps) {
  const defaultPrimary: ErrorStateProps['primaryAction'] =
    variant === 'not-found'
      ? { label: 'بازگشت به خانه', href: homeHref }
      : onRetry
        ? { label: 'تلاش مجدد', onClick: onRetry }
        : { label: 'بازگشت به خانه', href: homeHref };

  const defaultSecondary: ErrorStateProps['secondaryAction'] =
    variant === 'not-found'
      ? { label: 'صفحه اصلی سایت', href: '/' }
      : { label: 'صفحه اصلی سایت', href: '/' };

  const p = primaryAction ?? defaultPrimary;
  const s = secondaryAction ?? defaultSecondary;

  return (
    <div className={cn('w-full', className)}>
      <Card className="border-border/50 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden shadow-xl shadow-foreground/5">
        <CardHeader className="pb-4">
          <div className="flex items-start gap-3">
            <div className="h-10 w-10 rounded-2xl bg-muted flex items-center justify-center shrink-0">
              <AlertTriangle className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="space-y-1">
              <CardTitle className="text-xl md:text-2xl">{title}</CardTitle>
              {description ? (
                <CardDescription className="text-sm md:text-base leading-6">
                  {description}
                </CardDescription>
              ) : null}
            </div>
          </div>
        </CardHeader>

        {details ? (
          <CardContent className="pt-0">
            <details className="rounded-2xl border border-border/50 bg-background/40 p-4">
              <summary className="cursor-pointer text-sm font-medium text-muted-foreground select-none">
                نمایش جزئیات
              </summary>
              <pre className="mt-3 whitespace-pre-wrap break-words text-xs text-muted-foreground leading-5">
                {details}
              </pre>
            </details>
          </CardContent>
        ) : null}

        <CardFooter className="flex flex-col sm:flex-row gap-2 sm:justify-between">
          <div className="flex gap-2">
            <ActionButton action={p} variant="default" />
            <ActionButton action={s} variant="outline" />
          </div>

          {onRetry ? (
            <Button
              variant="ghost"
              onClick={onRetry}
              className="rounded-xl text-muted-foreground"
            >
              <RotateCcw className="h-4 w-4 ms-2" />
              ریست و تلاش مجدد
            </Button>
          ) : (
            <Button asChild variant="ghost" className="rounded-xl text-muted-foreground">
              <Link href={homeHref}>
                <Home className="h-4 w-4 ms-2" />
                خانه
              </Link>
            </Button>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}
