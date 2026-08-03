"""Owner-scoped exception review endpoints for Exam Prep V4."""
from __future__ import annotations

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.models_v4 import ExamProject
from apps.classes.permissions import IsTeacherUser
from apps.classes.serializers_v4_review import (
    ExamPrepV4ReviewDecisionSerializer,
    ExamPrepV4ReviewFinalizeSerializer,
)
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled
from apps.classes.services.exam_prep_v4_review import (
    InvalidReviewDecision,
    ReviewNotReady,
    StaleReviewSet,
    finalize_teacher_exception_review,
    get_teacher_review_queue,
    persist_teacher_review_decision,
)


def _require_v4() -> None:
    if not exam_prep_v4_enabled():
        raise Http404


class ExamPrepV4ReviewQueueView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, project_id: int):
        _require_v4()
        try:
            payload = get_teacher_review_queue(
                teacher=request.user,
                project_id=project_id,
            )
        except ExamProject.DoesNotExist:
            raise Http404
        except ReviewNotReady:
            return Response(
                {
                    'code': 'review_not_ready',
                    'detail': 'رکوردهای استخراج و اتصال هنوز برای بازبینی آماده نیستند.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(payload, status=status.HTTP_200_OK)


class ExamPrepV4ReviewDecisionView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, project_id: int):
        _require_v4()
        serializer = ExamPrepV4ReviewDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = persist_teacher_review_decision(
                teacher=request.user,
                project_id=project_id,
                match_decision_id=serializer.validated_data['matchDecisionId'],
                action=serializer.validated_data['action'],
                question_record_id=serializer.validated_data.get('questionRecordId'),
                note=serializer.validated_data.get('note', ''),
            )
        except ExamProject.DoesNotExist:
            raise Http404
        except StaleReviewSet:
            return Response(
                {
                    'code': 'stale_review_set',
                    'detail': 'رکوردهای استخراج هنگام بازبینی تغییر کرده‌اند.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        except (InvalidReviewDecision, ReviewNotReady) as exc:
            return Response(
                {
                    'code': 'invalid_review_decision',
                    'detail': str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                'reviewId': result.review_id,
                'revision': result.revision,
                'action': result.action,
                'questionRecordId': result.question_record_id,
                'remainingCount': result.remaining_count,
                'readyToFinalize': result.ready_to_finalize,
                'reused': result.reused,
            },
            status=status.HTTP_200_OK,
        )


class ExamPrepV4ReviewFinalizeView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, project_id: int):
        _require_v4()
        serializer = ExamPrepV4ReviewFinalizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = finalize_teacher_exception_review(
                teacher=request.user,
                project_id=project_id,
                expected_question_set_fingerprint=serializer.validated_data[
                    'questionSetFingerprint'
                ],
                expected_answer_set_fingerprint=serializer.validated_data[
                    'answerSetFingerprint'
                ],
            )
        except ExamProject.DoesNotExist:
            raise Http404
        except StaleReviewSet:
            return Response(
                {
                    'code': 'stale_review_set',
                    'detail': 'نسخهٔ رکوردها تغییر کرده است؛ صفحه را بروزرسانی کنید.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        except ReviewNotReady:
            return Response(
                {
                    'code': 'review_incomplete',
                    'detail': 'ابتدا همهٔ موارد استثنا را تعیین تکلیف کنید.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(payload, status=status.HTTP_200_OK)
