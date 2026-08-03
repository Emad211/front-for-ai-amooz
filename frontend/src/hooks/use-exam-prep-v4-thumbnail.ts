'use client';

import { useEffect, useState } from 'react';
import { useMountedRef } from '@/hooks/use-mounted-ref';
import { normalizeApiError } from '@/services/auth-service';
import { getExamPrepV4PageThumbnail } from '@/services/exam-prep-v4-service';

export function useExamPrepV4Thumbnail({
  projectId,
  documentId,
  pageNumber,
  enabled,
}: {
  projectId: number;
  documentId: number;
  pageNumber: number;
  enabled: boolean;
}) {
  const mountedRef = useMountedRef();
  const [url, setUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setUrl(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    let objectUrl: string | null = null;
    setIsLoading(true);
    setError(null);

    getExamPrepV4PageThumbnail(
      projectId,
      documentId,
      pageNumber,
      controller.signal,
    )
      .then((blob) => {
        if (!mountedRef.current || controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch((requestError) => {
        if (!mountedRef.current || controller.signal.aborted) return;
        setError(normalizeApiError(requestError).message);
      })
      .finally(() => {
        if (mountedRef.current && !controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId, enabled, mountedRef, pageNumber, projectId]);

  return { url, isLoading, error };
}
