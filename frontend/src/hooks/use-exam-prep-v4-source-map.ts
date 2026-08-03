'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  buildSourceMapMutationPayload,
  canConfirmEditableSourceMap,
  countUnknownPages,
  createEditableSourceMapPages,
  isCompleteEditableSourceMap,
  moveEditablePageEarlier,
  moveEditablePageLater,
  rotateEditablePageClockwise,
  sourceMapPagesEqual,
  updateEditablePageRole,
  type EditableSourceMapPage,
  type ExamPrepV4SourceRole,
} from '@/features/exam-prep-v4/source-map-model';
import { useMountedRef } from '@/hooks/use-mounted-ref';
import { normalizeApiError } from '@/services/auth-service';
import {
  confirmExamPrepV4SourceMap,
  getExamPrepV4ConflictCode,
  getExamPrepV4Project,
  saveExamPrepV4SourceMap,
  type ExamPrepV4Document,
  type ExamPrepV4ProjectDetail,
} from '@/services/exam-prep-v4-service';

export type SourceMapUiConflict = {
  code: string;
  message: string;
} | null;

function documentDraft(document: ExamPrepV4Document): EditableSourceMapPage[] {
  return createEditableSourceMapPages(document.pages);
}

export function useExamPrepV4SourceMap(projectId: number) {
  const mountedRef = useMountedRef();
  const [project, setProject] = useState<ExamPrepV4ProjectDetail | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [initialPages, setInitialPages] = useState<EditableSourceMapPage[]>([]);
  const [draftPages, setDraftPages] = useState<EditableSourceMapPage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<SourceMapUiConflict>(null);
  const [announcement, setAnnouncement] = useState('');

  const selectedDocument = useMemo(() => {
    if (!project) return null;
    return (
      project.documents.find((document) => document.id === selectedDocumentId)
      ?? project.documents[0]
      ?? null
    );
  }, [project, selectedDocumentId]);

  const hydrateDocument = useCallback((document: ExamPrepV4Document | null) => {
    if (!document) {
      setSelectedDocumentId(null);
      setInitialPages([]);
      setDraftPages([]);
      return;
    }
    const pages = documentDraft(document);
    setSelectedDocumentId(document.id);
    setInitialPages(pages);
    setDraftPages(pages);
  }, []);

  const loadProject = useCallback(async (
    preferredDocumentId?: number | null,
  ) => {
    if (!Number.isInteger(projectId) || projectId < 1) {
      setError('شناسهٔ پروژه معتبر نیست.');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const result = await getExamPrepV4Project(projectId);
      if (!mountedRef.current) return;
      setProject(result);
      const document = (
        result.documents.find((item) => item.id === preferredDocumentId)
        ?? result.documents[0]
        ?? null
      );
      hydrateDocument(document);
      setConflict(null);
    } catch (requestError) {
      if (!mountedRef.current) return;
      setError(normalizeApiError(requestError).message);
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [hydrateDocument, mountedRef, projectId]);

  useEffect(() => {
    void loadProject();
  }, [loadProject]);

  const hasUnsavedChanges = useMemo(
    () => !sourceMapPagesEqual(initialPages, draftPages),
    [draftPages, initialPages],
  );

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  const selectDocument = useCallback((documentId: number) => {
    if (!project) return;
    const document = project.documents.find((item) => item.id === documentId);
    if (!document) return;
    hydrateDocument(document);
    setConflict(null);
    setAnnouncement(`سند شمارهٔ ${document.uploadOrder + 1} باز شد.`);
  }, [hydrateDocument, project]);

  const changeRole = useCallback((
    pageNumber: number,
    role: ExamPrepV4SourceRole,
  ) => {
    setDraftPages((pages) => updateEditablePageRole(pages, pageNumber, role));
    setConflict(null);
    setAnnouncement(`نقش صفحهٔ منبع ${pageNumber} تغییر کرد و هنوز ذخیره نشده است.`);
  }, []);

  const rotatePage = useCallback((pageNumber: number) => {
    setDraftPages((pages) => rotateEditablePageClockwise(pages, pageNumber));
    setConflict(null);
    setAnnouncement(`چرخش صفحهٔ منبع ${pageNumber} تغییر کرد و هنوز ذخیره نشده است.`);
  }, []);

  const movePageEarlier = useCallback((pageNumber: number) => {
    const nextPages = moveEditablePageEarlier(draftPages, pageNumber);
    const nextPosition = nextPages.find((page) => page.pageNumber === pageNumber)?.displayOrder;
    setDraftPages(nextPages);
    setConflict(null);
    if (nextPosition) {
      setAnnouncement(
        `صفحهٔ منبع ${pageNumber} به جایگاه مجازی ${nextPosition} منتقل شد و هنوز ذخیره نشده است.`,
      );
    }
  }, [draftPages]);

  const movePageLater = useCallback((pageNumber: number) => {
    const nextPages = moveEditablePageLater(draftPages, pageNumber);
    const nextPosition = nextPages.find((page) => page.pageNumber === pageNumber)?.displayOrder;
    setDraftPages(nextPages);
    setConflict(null);
    if (nextPosition) {
      setAnnouncement(
        `صفحهٔ منبع ${pageNumber} به جایگاه مجازی ${nextPosition} منتقل شد و هنوز ذخیره نشده است.`,
      );
    }
  }, [draftPages]);

  const discardChanges = useCallback(() => {
    setDraftPages(initialPages);
    setConflict(null);
    setAnnouncement('تغییرات ذخیره‌نشده کنار گذاشته شد.');
  }, [initialPages]);

  const reloadCurrentServerMap = useCallback(async () => {
    const documentId = selectedDocument?.id ?? null;
    await loadProject(documentId);
    if (mountedRef.current) {
      setAnnouncement('آخرین نسخهٔ نقشه از سرور بارگذاری شد.');
    }
  }, [loadProject, mountedRef, selectedDocument?.id]);

  const save = useCallback(async () => {
    if (!selectedDocument || isSaving || isConfirming) return false;
    if (!isCompleteEditableSourceMap(draftPages, selectedDocument.pageCount)) {
      setError('نقشه و ترتیب مجازی صفحات کامل یا معتبر نیست.');
      return false;
    }

    setIsSaving(true);
    setError(null);
    setConflict(null);
    setAnnouncement('در حال ذخیرهٔ نقشه و ترتیب مجازی صفحات.');
    try {
      const result = await saveExamPrepV4SourceMap(
        projectId,
        selectedDocument.id,
        buildSourceMapMutationPayload(
          selectedDocument.classificationRevision,
          draftPages,
        ),
      );
      if (!mountedRef.current) return false;
      await loadProject(selectedDocument.id);
      if (mountedRef.current) {
        setAnnouncement(
          result.reused
            ? 'نقشه و ترتیب مجازی صفحات از قبل با همین ساختار ذخیره شده بود.'
            : 'نقشه و ترتیب مجازی صفحات با موفقیت ذخیره شد.',
        );
      }
      return true;
    } catch (requestError) {
      if (!mountedRef.current) return false;
      const normalized = normalizeApiError(requestError);
      const conflictCode = getExamPrepV4ConflictCode(requestError);
      if (conflictCode) {
        setConflict({ code: conflictCode, message: normalized.message });
        setAnnouncement('نسخهٔ سرور تغییر کرده است؛ تغییرات محلی شما حفظ شد.');
      } else {
        setError(normalized.message);
        setAnnouncement('ذخیرهٔ نقشه و ترتیب مجازی صفحات انجام نشد.');
      }
      return false;
    } finally {
      if (mountedRef.current) setIsSaving(false);
    }
  }, [
    draftPages,
    isConfirming,
    isSaving,
    loadProject,
    mountedRef,
    projectId,
    selectedDocument,
  ]);

  const unknownPageCount = useMemo(
    () => countUnknownPages(draftPages),
    [draftPages],
  );

  const canConfirm = useMemo(() => {
    if (!selectedDocument) return false;
    return canConfirmEditableSourceMap({
      pages: draftPages,
      initialPages,
      pageCount: selectedDocument.pageCount,
      fingerprint: selectedDocument.sourceMapFingerprint ?? '',
      isSaving,
      isConfirming,
      isConfirmed: selectedDocument.isTeacherConfirmed,
    });
  }, [draftPages, initialPages, isConfirming, isSaving, selectedDocument]);

  const confirm = useCallback(async () => {
    const fingerprint = selectedDocument?.sourceMapFingerprint;
    if (!selectedDocument || !fingerprint || !canConfirm) return false;
    setIsConfirming(true);
    setError(null);
    setConflict(null);
    setAnnouncement('در حال تأیید نقشه و ترتیب مجازی صفحات.');
    try {
      const result = await confirmExamPrepV4SourceMap(
        projectId,
        selectedDocument.id,
        {
          expectedRevision: selectedDocument.classificationRevision,
          sourceMapFingerprint: fingerprint,
        },
      );
      if (!mountedRef.current) return false;
      await loadProject(selectedDocument.id);
      if (mountedRef.current) {
        setAnnouncement(
          result.reused
            ? 'این نسخه از نقشه و ترتیب مجازی قبلاً تأیید شده بود.'
            : 'نقشه و ترتیب مجازی صفحات با موفقیت تأیید شد.',
        );
      }
      return true;
    } catch (requestError) {
      if (!mountedRef.current) return false;
      const normalized = normalizeApiError(requestError);
      const conflictCode = getExamPrepV4ConflictCode(requestError);
      if (conflictCode) {
        setConflict({ code: conflictCode, message: normalized.message });
        setAnnouncement('تأیید انجام نشد؛ نسخهٔ فعلی باید دوباره بررسی شود.');
      } else {
        setError(normalized.message);
        setAnnouncement('تأیید نقشه و ترتیب مجازی صفحات انجام نشد.');
      }
      return false;
    } finally {
      if (mountedRef.current) setIsConfirming(false);
    }
  }, [canConfirm, loadProject, mountedRef, projectId, selectedDocument]);

  return {
    project,
    documents: project?.documents ?? [],
    selectedDocument,
    selectedDocumentId,
    initialPages,
    draftPages,
    isLoading,
    isSaving,
    isConfirming,
    error,
    conflict,
    announcement,
    hasUnsavedChanges,
    unknownPageCount,
    canConfirm,
    selectDocument,
    changeRole,
    rotatePage,
    movePageEarlier,
    movePageLater,
    discardChanges,
    reloadCurrentServerMap,
    save,
    confirm,
  };
}
