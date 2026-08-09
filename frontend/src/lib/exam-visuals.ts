/**
 * Small, shared helpers for protected exam images.
 *
 * The source-first projection returns a ready-to-fetch `url`.  Older exam
 * records only have a numeric visual id, so keep the legacy URL as a fallback
 * while the data migrates.  No image is made public by this helper: all URLs
 * are still fetched through ProtectedExamVisual and the authenticated blob
 * service.
 */

export type ExamVisualRole = 'question' | 'option' | 'solution';

export interface ExamVisualRefLike {
  id: string | number;
  role?: ExamVisualRole | string;
  optionLabel?: string | null;
  altText?: string | null;
  url?: string | null;
  sourceUrl?: string | null;
  generatedUrl?: string | null;
  dataUrl?: string | null;
  selectedVariant?: 'source' | 'generated' | string | null;
}

/** Resolve both source-first refs and legacy ExamPrepVisualAsset refs. */
export function resolveExamVisualUrl(
  visual: ExamVisualRefLike,
  sessionId?: string | number,
): string | null {
  const direct = visual.url?.trim();
  if (direct) return direct;
  const inline = visual.dataUrl?.trim();
  if (inline && /^data:image\/(?:png|jpe?g|webp);base64,/.test(inline)) return inline;

  const variantUrl = visual.selectedVariant === 'generated'
    ? visual.generatedUrl?.trim()
    : visual.sourceUrl?.trim();
  if (variantUrl) return variantUrl;

  // Legacy records use the asset-content endpoint.  Do not manufacture a URL
  // for opaque source-first ids; those must be supplied by the API itself.
  const id = String(visual.id ?? '').trim();
  const session = String(sessionId ?? '').trim();
  // Numeric stored assets and the older verified `inline-*` source crops are
  // both served by the authenticated legacy endpoint.  Opaque V4 ids are not
  // accepted here: a V4 projection must provide its project-bound URL.
  if (
    session
    && /^\d+$/.test(session)
    && (/^\d+$/.test(id) || /^inline-[A-Za-z0-9._-]+$/.test(id))
  ) {
    return `/api/classes/exam-prep-sessions/${session}/visuals/${id}/content/`;
  }
  return null;
}

function normalizeOptionLabel(value: string | null | undefined): string {
  return String(value ?? '')
    .trim()
    .toLocaleLowerCase()
    .replace(/[يى]/g, 'ی')
    .replace(/[ك]/g, 'ک')
    .replace(/[۰-۹]/g, (digit) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(digit)));
}

/** Match labels even when OCR alternates Persian/Arabic glyphs or digits. */
export function visualMatchesOption(
  visual: ExamVisualRefLike,
  optionLabel: string | null | undefined,
): boolean {
  const left = normalizeOptionLabel(visual.optionLabel);
  const right = normalizeOptionLabel(optionLabel);
  return Boolean(left && right && left === right);
}

export function visualsForRole(
  visuals: readonly ExamVisualRefLike[] | null | undefined,
  role: ExamVisualRole,
): ExamVisualRefLike[] {
  return (visuals ?? []).filter((visual) => visual.role === role);
}
