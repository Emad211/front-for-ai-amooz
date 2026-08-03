"""Owner-scoped source-map mutation and confirmation endpoints for V4."""
from __future__ import annotations

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.permissions import IsTeacherUser
from apps.classes.serializers_v4 import (
    ExamPrepV4SourceMapConfirmationSerializer,
    ExamPrepV4SourceMapMutationSerializer,
)
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled
from apps.classes.services.exam_prep_v4_source_map_mutation import (
    SourceMapFingerprintConflict,
    SourceMapMutationError,
    SourceMapMutationResult,
    SourceMapNotConfirmable,
    SourceMapNotReady,
    StaleSourceMapRevision,
    confirm_teacher_source_map,
    mutate_teacher_source_map,
)
from apps.classes.tasks_v4 import (
    ExtractionDispatchResult,
    dispatch_exam_prep_v4_extraction,
)


def _require_v4() -> None:
    if not exam_prep_v4_enabled():
        raise Http404


def _result_payload(
    result: SourceMapMutationResult,
    *,
    dispatch: ExtractionDispatchResult | None = None,
) -> dict:
    payload = {
        'documentId': result.document_id,
        'classificationRevision': result.revision,
        'sourceMapFingerprint': result.fingerprint,
        'status': result.status,
        'reused': result.reused,
        'isTeacherConfirmed': result.confirmed,
    }
    if dispatch is not None:
        payload['extraction'] = {
            'runId': dispatch.run_id,
            'taskId': dispatch.task_id,
            'queued': dispatch.queued,
            'reused': dispatch.reused,
        }
    return payload


def _conflict_response(code: str, detail: str) -> Response:
    return Response(
        {'code': code, 'detail': detail},
        status=status.HTTP_409_CONFLICT,
    )


class ExamPrepV4SourceMapMutationView(APIView):
    """Replace the complete effective page map for one owned source document."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def put(self, request, project_id: int, document_id: int):
        _require_v4()
        serializer = ExamPrepV4SourceMapMutationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = mutate_teacher_source_map(
                teacher=request.user,
                project_id=project_id,
                document_id=document_id,
                expected_revision=serializer.validated_data['expectedRevision'],
                pages=serializer.validated_data['pages'],
            )
        except (ExamProject.DoesNotExist, ExamSourceDocument.DoesNotExist):
            raise Http404
        except SourceMapMutationError:
            return Response(
                {
                    'code': 'invalid_source_map',
                    'detail': 'نقشهٔ صفحات باید کامل، یکتا و معتبر باشد.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except StaleSourceMapRevision:
            return _conflict_response(
                'stale_source_map_revision',
                'نقشهٔ صفحات پس از بارگذاری شما تغییر کرده است.',
            )
        except SourceMapNotReady:
            return _conflict_response(
                'source_map_not_ready',
                'نقشهٔ صفحات هنوز برای ویرایش آماده نیست.',
            )

        return Response(_result_payload(result), status=status.HTTP_200_OK)


class ExamPrepV4SourceMapConfirmationView(APIView):
    """Confirm the current Source Map and queue its semantic extraction."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, project_id: int, document_id: int):
        _require_v4()
        serializer = ExamPrepV4SourceMapConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = confirm_teacher_source_map(
                teacher=request.user,
                project_id=project_id,
                document_id=document_id,
                expected_revision=serializer.validated_data['expectedRevision'],
                expected_fingerprint=serializer.validated_data[
                    'sourceMapFingerprint'
                ],
            )
        except (ExamProject.DoesNotExist, ExamSourceDocument.DoesNotExist):
            raise Http404
        except StaleSourceMapRevision:
            return _conflict_response(
                'stale_source_map_revision',
                'نقشهٔ صفحات پس از بارگذاری شما تغییر کرده است.',
            )
        except SourceMapFingerprintConflict:
            return _conflict_response(
                'source_map_fingerprint_conflict',
                'نسخهٔ تأییدشده با نقشهٔ فعلی یکسان نیست.',
            )
        except SourceMapNotReady:
            return _conflict_response(
                'source_map_not_ready',
                'نقشهٔ صفحات هنوز برای تأیید آماده نیست.',
            )
        except SourceMapNotConfirmable:
            return _conflict_response(
                'source_map_not_confirmable',
                'همهٔ صفحات باید نقش قطعی و پوشش segment معتبر داشته باشند.',
            )

        try:
            dispatch = dispatch_exam_prep_v4_extraction(result.document_id)
        except (ExamSourceDocument.DoesNotExist, ValueError):
            return Response(
                {
                    **_result_payload(result),
                    'code': 'extraction_not_dispatchable',
                    'detail': 'نقشه تأیید شد اما نسخهٔ فعلی برای استخراج آماده نیست.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            return Response(
                {
                    **_result_payload(result),
                    'code': 'extraction_dispatch_failed',
                    'detail': (
                        'نقشه تأیید شد اما ارسال استخراج به صف انجام نشد. '
                        'از عملیات تلاش مجدد استفاده کنید.'
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response_status = status.HTTP_202_ACCEPTED if dispatch.queued else status.HTTP_200_OK
        return Response(
            _result_payload(result, dispatch=dispatch),
            status=response_status,
        )
