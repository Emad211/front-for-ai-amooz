import {
  ApiRequestError,
  getStoredTokens,
  refreshAccessToken,
} from '@/services/auth-service';
import type {
  EditableSourceMapPage,
  ExamPrepV4Orientation,
  ExamPrepV4Page,
  ExamPrepV4SourceRole,
} from '@/features/exam-prep-v4/source-map-model';

const API_ROOT = '/api/classes/exam-prep-v4';

export type ExamPrepV4ProjectProgress = {
  stage: string;
  progressPercent: number;
  warningCount: number;
};

export type ExamPrepV4ProjectSummary = {
  id: number;
  title: string;
  description: string;
  engineVersion: 4;
  revision: number;
  status: string;
  progress: ExamPrepV4ProjectProgress;
  errorCode: string | null;
  documentCount: number;
  isPublished: boolean;
  publishedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ExamPrepV4Issue = {
  code: string;
  pageNumber: number | null;
};

export type ExamPrepV4Segment = {
  id: number;
  revision: number;
  order: number;
  startPage: number;
  endPage: number;
  displayOrderStart: number | null;
  displayOrderEnd: number | null;
  pageNumbers: number[];
  role: ExamPrepV4SourceRole;
  predictedRole: ExamPrepV4SourceRole;
  predictedConfidence: number;
  teacherConfirmed: boolean;
  expectedNumberStart: number | null;
  expectedNumberEnd: number | null;
  status: string;
};

export type ExamPrepV4Document = {
  id: number;
  uploadOrder: number;
  status: string;
  pageCount: number;
  classificationRevision: number;
  sourceMapFingerprint: string | null;
  hasClassification: boolean;
  hasSourceMap: boolean;
  issueCount: number;
  issues: ExamPrepV4Issue[];
  teacherConfirmedAt: string | null;
  teacherConfirmedRevision: number | null;
  isTeacherConfirmed: boolean;
  errorCode: string | null;
  createdAt: string;
  updatedAt: string;
  pages: ExamPrepV4Page[];
  segments: ExamPrepV4Segment[];
};

export type ExamPrepV4ProjectDetail = ExamPrepV4ProjectSummary & {
  documents: ExamPrepV4Document[];
};

export type ExamPrepV4PaginatedProjects = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ExamPrepV4ProjectSummary[];
};

export type ExamPrepV4SourceMapMutationPayload = {
  expectedRevision: number;
  pages: EditableSourceMapPage[];
};

export type ExamPrepV4SourceMapConfirmationPayload = {
  expectedRevision: number;
  sourceMapFingerprint: string;
};

export type ExamPrepV4SourceMapMutationResult = {
  documentId: number;
  classificationRevision: number;
  sourceMapFingerprint: string;
  status: string;
  reused: boolean;
  isTeacherConfirmed: boolean;
};

export type ExamPrepV4ConflictCode =
  | 'stale_source_map_revision'
  | 'source_map_fingerprint_conflict'
  | 'source_map_not_ready'
  | 'source_map_not_confirmable';

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

async function parsePayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function safeMessage(payload: unknown, fallback: string): string {
  if (isRecord(payload) && typeof payload.detail === 'string') {
    return payload.detail;
  }
  return fallback;
}

async function authenticatedRequest(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(options.headers);
  const access = getStoredTokens()?.access;
  if (access && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${access}`);
  }
  if (
    options.body
    && !(typeof FormData !== 'undefined' && options.body instanceof FormData)
    && !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...options,
      headers,
      credentials: 'include',
    });
  } catch {
    throw new Error('ارتباط با سرور برقرار نشد');
  }

  if (response.status === 401 && retry) {
    const newAccess = await refreshAccessToken();
    headers.set('Authorization', `Bearer ${newAccess}`);
    return authenticatedRequest(path, { ...options, headers }, false);
  }
  return response;
}

async function requestJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await authenticatedRequest(path, options);
  const payload = await parsePayload(response);
  if (!response.ok) {
    throw new ApiRequestError(
      safeMessage(payload, 'درخواست انجام نشد'),
      response.status,
      payload,
    );
  }
  return payload as T;
}

export async function listExamPrepV4Projects(
  page = 1,
  signal?: AbortSignal,
): Promise<ExamPrepV4PaginatedProjects> {
  const safePage = Math.max(1, Math.trunc(page));
  return requestJson<ExamPrepV4PaginatedProjects>(
    `/projects/?page=${safePage}`,
    { method: 'GET', signal },
  );
}

export async function getExamPrepV4Project(
  projectId: number,
  signal?: AbortSignal,
): Promise<ExamPrepV4ProjectDetail> {
  return requestJson<ExamPrepV4ProjectDetail>(
    `/projects/${projectId}/`,
    { method: 'GET', signal },
  );
}

export async function saveExamPrepV4SourceMap(
  projectId: number,
  documentId: number,
  payload: ExamPrepV4SourceMapMutationPayload,
): Promise<ExamPrepV4SourceMapMutationResult> {
  return requestJson<ExamPrepV4SourceMapMutationResult>(
    `/projects/${projectId}/documents/${documentId}/source-map/`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  );
}

export async function confirmExamPrepV4SourceMap(
  projectId: number,
  documentId: number,
  payload: ExamPrepV4SourceMapConfirmationPayload,
): Promise<ExamPrepV4SourceMapMutationResult> {
  return requestJson<ExamPrepV4SourceMapMutationResult>(
    `/projects/${projectId}/documents/${documentId}/source-map/confirm/`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export async function getExamPrepV4PageThumbnail(
  projectId: number,
  documentId: number,
  pageNumber: number,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await authenticatedRequest(
    `/projects/${projectId}/documents/${documentId}/pages/${pageNumber}/thumbnail/`,
    { method: 'GET', signal },
  );
  if (!response.ok) {
    const payload = await parsePayload(response);
    throw new ApiRequestError(
      safeMessage(payload, 'تصویر این صفحه در دسترس نیست'),
      response.status,
      payload,
    );
  }
  return response.blob();
}

export function getExamPrepV4ConflictCode(error: unknown): ExamPrepV4ConflictCode | null {
  if (!(error instanceof ApiRequestError) || !isRecord(error.payload)) {
    return null;
  }
  const code = error.payload.code;
  if (
    code === 'stale_source_map_revision'
    || code === 'source_map_fingerprint_conflict'
    || code === 'source_map_not_ready'
    || code === 'source_map_not_confirmable'
  ) {
    return code;
  }
  return null;
}

export function isValidExamPrepV4Orientation(
  value: number,
): value is ExamPrepV4Orientation {
  return value === 0 || value === 90 || value === 180 || value === 270;
}
