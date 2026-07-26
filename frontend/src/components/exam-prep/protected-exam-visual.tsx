'use client';

import { useEffect, useState } from 'react';
import { ImageIcon, Loader2 } from 'lucide-react';

import { getExamPrepVisualBlob } from '@/services/classes-service';

interface ProtectedExamVisualProps {
  url: string;
  alt: string;
  className?: string;
}

export function ProtectedExamVisual({ url, alt, className }: ProtectedExamVisualProps) {
  const [objectUrl, setObjectUrl] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let nextUrl = '';
    setObjectUrl('');
    setFailed(false);
    getExamPrepVisualBlob(url, controller.signal)
      .then((blob) => {
        if (controller.signal.aborted) return;
        nextUrl = URL.createObjectURL(blob);
        setObjectUrl(nextUrl);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => {
      controller.abort();
      if (nextUrl) URL.revokeObjectURL(nextUrl);
    };
  }, [url]);

  if (!objectUrl) {
    return (
      <div className={`flex min-h-32 items-center justify-center rounded-md border bg-muted/20 ${className ?? ''}`}>
        {failed
          ? <ImageIcon className="h-6 w-6 text-muted-foreground" />
          : <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={objectUrl} alt={alt} className={className} />
  );
}
