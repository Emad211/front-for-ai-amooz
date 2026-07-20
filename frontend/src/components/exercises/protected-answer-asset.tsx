'use client';

import { useEffect, useRef, useState } from 'react';
import { FileText, Loader2 } from 'lucide-react';

import { getAnswerOcrAssetBlob, type AnswerOcrAsset } from '@/services/exercises-service';

export function ProtectedAnswerAsset({ asset, label }: { asset: AnswerOcrAsset; label: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [objectUrl, setObjectUrl] = useState('');
  const [failed, setFailed] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '120px' },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [asset.id]);

  useEffect(() => {
    if (!visible) return;
    const controller = new AbortController();
    let nextUrl = '';
    setFailed(false);
    getAnswerOcrAssetBlob(asset.url, controller.signal)
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
  }, [asset.url, visible]);

  if (!objectUrl) {
    return (
      <div ref={containerRef} className="flex h-28 w-28 items-center justify-center rounded-md border border-border bg-muted/20">
        {failed
          ? <FileText className="h-5 w-5 text-muted-foreground" />
          : visible
            ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            : <FileText className="h-5 w-5 text-muted-foreground" />}
      </div>
    );
  }
  if (asset.contentType === 'application/pdf') {
    return (
      <a
        href={objectUrl}
        target="_blank"
        rel="noreferrer"
        className="flex h-28 w-28 flex-col items-center justify-center gap-2 rounded-md border border-border text-xs"
      >
        <FileText className="h-6 w-6 text-primary" />
        {label}
      </a>
    );
  }
  return (
    <a href={objectUrl} target="_blank" rel="noreferrer" title="نمایش در اندازه کامل">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={objectUrl}
        alt={label}
        className="h-28 w-28 rounded-md border border-border object-cover"
        loading="lazy"
      />
    </a>
  );
}
