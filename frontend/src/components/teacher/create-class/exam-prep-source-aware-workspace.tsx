'use client';

/**
 * Legacy compatibility shim.
 *
 * New Exam Prep creation uses the normal simple session flow and the OCR4
 * document engine behind it. The old V4 source-map/page-confirmation workspace
 * must never render in the create-class UI again.
 */
export function ExamPrepSourceAwareWorkspace(_props: { sessionId: number }) {
  return null;
}
