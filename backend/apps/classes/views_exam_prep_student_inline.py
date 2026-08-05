"""Student exam-prep detail with support for inline verified source crops."""
from __future__ import annotations

import json

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClassCreationSession
from .permissions import IsStudentUser
from .serializers import StudentExamPrepDetailSerializer
from .services.exam_prep_utils import normalize_exam_prep_questions
from .views import _infer_exam_prep_question_type
from rest_framework.views import APIView


class StudentExamPrepInlineDetailView(APIView):
    """Return published questions without answers, including safe data-URL crops."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='Get exam prep detail with questions',
        operation_id='student_exam_prep_detail_inline_visuals',
        responses={200: StudentExamPrepDetailSerializer, 404: OpenApiTypes.OBJECT},
    )
    def get(self, request, session_id: int):
        phone = (getattr(request.user, 'phone', None) or '').strip()
        if not phone:
            return Response(
                {'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        session = ClassCreationSession.objects.filter(
            id=session_id,
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            invites__phone=phone,
        ).first()
        if session is None:
            return Response(
                {'detail': 'آزمون آمادگی پیدا نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        questions_list: list[dict] = []
        subject = ''
        try:
            parsed = json.loads(session.exam_prep_json or '{}')
            if isinstance(parsed, dict):
                normalized, changed = normalize_exam_prep_questions(parsed)
                if changed:
                    session.exam_prep_json = json.dumps(normalized, ensure_ascii=False)
                    session.save(update_fields=['exam_prep_json', 'updated_at'])
                exam = normalized.get('exam_prep') or {}
                subject = str(exam.get('title') or '')
                raw = exam.get('questions') or []
                if isinstance(raw, list):
                    questions_list = [item for item in raw if isinstance(item, dict)]
        except (json.JSONDecodeError, TypeError, ValueError):
            questions_list = []

        safe_questions: list[dict] = []
        for question in questions_list:
            qid = str(question.get('question_id') or '').strip()
            if not qid:
                continue
            options = []
            for option in question.get('options') or []:
                if not isinstance(option, dict):
                    continue
                label = str(option.get('label') or '').strip()
                if label:
                    options.append(
                        {
                            'label': label,
                            'text_markdown': str(option.get('text_markdown') or '').strip(),
                        }
                    )
            visuals = []
            for visual in question.get('visuals') or []:
                if not isinstance(visual, dict) or visual.get('role') == 'solution':
                    continue
                visual_id = visual.get('id')
                data_url = str(visual.get('dataUrl') or '')
                if data_url.startswith('data:image/'):
                    url = data_url
                elif visual_id:
                    url = (
                        f'/api/classes/exam-prep-sessions/{session.id}/visuals/'
                        f'{visual_id}/content/'
                    )
                else:
                    continue
                visuals.append(
                    {
                        'id': visual_id,
                        'role': visual.get('role') or 'question',
                        'optionLabel': visual.get('optionLabel'),
                        'altText': visual.get('altText') or '',
                        'url': url,
                    }
                )
            safe_questions.append(
                {
                    'question_id': qid,
                    'question_text_markdown': str(
                        question.get('question_text_markdown') or ''
                    ).strip(),
                    'type': _infer_exam_prep_question_type(question),
                    'options': options,
                    'visuals': visuals,
                }
            )

        payload = {
            'id': session.id,
            'title': session.title,
            'description': session.description or '',
            'questions': safe_questions,
            'totalQuestions': len(safe_questions),
            'subject': subject,
        }
        return Response(StudentExamPrepDetailSerializer(payload).data)
