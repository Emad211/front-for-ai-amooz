"""Exercise Hub — teacher API (create/extract/edit/publish/delete).

Kept in a dedicated module so the 195 KB ``views.py`` never grows for this
feature. All endpoints are owner-scoped: a teacher only ever sees/mutates
exercises of their own class sessions (``session__teacher=request.user``); a
non-owner gets 404 (fail-closed), a non-teacher 403, anonymous 401.

Design + permission matrix: docs/features/exercise-hub.md · ADR-0004.
"""
from __future__ import annotations

import os

from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    ClassCreationSession,
    ClassExercise,
    ClassExerciseAsset,
    ClassExerciseQuestion,
    ClassExerciseSection,
    StudentExerciseSubmission,
)
from .permissions import IsStudentUser, IsTeacherUser
from .serializers_exercises import (
    ExerciseCreateSerializer,
    ExerciseDetailSerializer,
    ExerciseListSerializer,
    ExerciseUpdateSerializer,
    QuestionWriteSerializer,
    SectionUpdateSerializer,
)
from .tasks import extract_exercise_content

_NOT_FOUND = {'detail': 'تمرین پیدا نشد.'}


def _owned_exercise(request, exercise_id):
    return ClassExercise.objects.filter(
        id=exercise_id, session__teacher=request.user,
    ).first()


def _asset_kind(uploaded) -> str:
    ct = (getattr(uploaded, 'content_type', '') or '').lower()
    name = (getattr(uploaded, 'name', '') or '').lower()
    if 'pdf' in ct or name.endswith('.pdf'):
        return ClassExerciseAsset.Kind.PDF
    return ClassExerciseAsset.Kind.IMAGE


class ExerciseListCreateView(APIView):
    """List a session's exercises / create a new one (with optional assets)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id, teacher=request.user,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        qs = ClassExercise.objects.filter(session=session).order_by('-created_at')
        return Response(ExerciseListSerializer(qs, many=True).data)

    def post(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id, teacher=request.user,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ExerciseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exercise = ClassExercise.objects.create(
            session=session,
            title=serializer.validated_data['title'],
            description=serializer.validated_data.get('description', ''),
        )
        for idx, uploaded in enumerate(request.FILES.getlist('files')):
            ClassExerciseAsset.objects.create(
                exercise=exercise, kind=_asset_kind(uploaded), file=uploaded, order=idx,
            )
        return Response(
            ExerciseDetailSerializer(exercise).data, status=status.HTTP_201_CREATED,
        )


class ExerciseDetailView(APIView):
    """Get / update (title, deadline, allow_late, assistant_enabled) / delete."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        return Response(ExerciseDetailSerializer(exercise).data)

    def patch(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        serializer = ExerciseUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields: list[str] = []
        for key in ('title', 'deadline', 'allow_late', 'assistant_enabled'):
            if key in serializer.validated_data:
                setattr(exercise, key, serializer.validated_data[key])
                fields.append(key)
        if fields:
            fields.append('updated_at')
            exercise.save(update_fields=fields)
        return Response(ExerciseDetailSerializer(exercise).data)

    def delete(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        # GC storage objects (CASCADE drops rows, not S3/MinIO blobs — E1 db-gate).
        for asset in exercise.assets.all():
            try:
                asset.file.delete(save=False)
            except Exception:
                pass
        exercise.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExerciseExtractView(APIView):
    """Kick off async structure extraction (E3 task on the pipeline queue)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if exercise.status == ClassExercise.Status.EXTRACTING:
            return Response(
                {'detail': 'استخراج این تمرین در حال انجام است.'},
                status=status.HTTP_409_CONFLICT,
            )
        transaction.on_commit(lambda: extract_exercise_content.delay(exercise.id))
        return Response(
            {'detail': 'استخراج تمرین آغاز شد.', 'status': ClassExercise.Status.EXTRACTING},
            status=status.HTTP_202_ACCEPTED,
        )


class ExercisePublishView(APIView):
    """Publish an extracted exercise after validating reference answers + points."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if exercise.status not in (
            ClassExercise.Status.EXTRACTED, ClassExercise.Status.PUBLISHED,
        ):
            return Response(
                {'detail': 'ابتدا باید سوال‌های تمرین استخراج شوند.'},
                status=status.HTTP_409_CONFLICT,
            )
        questions = ClassExerciseQuestion.objects.filter(section__exercise=exercise)
        if not questions.exists():
            return Response(
                {'detail': 'این تمرین هیچ سوالی ندارد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        incomplete = [
            q.id for q in questions
            if not (q.reference_answer_markdown or '').strip()
            or q.max_points is None or q.max_points <= 0
        ]
        if incomplete:
            return Response(
                {
                    'detail': 'برای انتشار، هر سوال باید پاسخ مرجع و بارم داشته باشد.',
                    'incompleteQuestionIds': incomplete,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        exercise.status = ClassExercise.Status.PUBLISHED
        exercise.save(update_fields=['status', 'updated_at'])
        return Response(ExerciseDetailSerializer(exercise).data)


class ExerciseSectionDetailView(APIView):
    """Toggle a section's assistant (and edit its title)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def patch(self, request, section_id: int):
        section = ClassExerciseSection.objects.filter(
            id=section_id, exercise__session__teacher=request.user,
        ).first()
        if section is None:
            return Response({'detail': 'بخش پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SectionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields: list[str] = []
        for key in ('assistant_enabled', 'title'):
            if key in serializer.validated_data:
                setattr(section, key, serializer.validated_data[key])
                fields.append(key)
        if fields:
            section.save(update_fields=fields)
        return Response({'id': section.id, 'assistantEnabled': section.assistant_enabled,
                         'title': section.title})


class ExerciseQuestionListCreateView(APIView):
    """Add a question to a section of an owned exercise."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = ClassExerciseSection.objects.filter(
            id=serializer.validated_data.get('section_id'), exercise=exercise,
        ).first()
        if section is None:
            return Response(
                {'detail': 'بخش این تمرین پیدا نشد.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        next_order = section.questions.count()
        q = ClassExerciseQuestion.objects.create(
            section=section, order=next_order,
            question_markdown=serializer.validated_data.get('question_markdown', ''),
            question_type=serializer.validated_data.get(
                'question_type', ClassExerciseQuestion.QuestionType.DESCRIPTIVE),
            options=serializer.validated_data.get('options', []),
            reference_answer_markdown=serializer.validated_data.get('reference_answer_markdown', ''),
            max_points=serializer.validated_data.get('max_points', 1),
            grading_notes=serializer.validated_data.get('grading_notes', ''),
        )
        return Response({'id': q.id}, status=status.HTTP_201_CREATED)


class ExerciseQuestionDetailView(APIView):
    """Edit / delete a question (reference answer, points, text, type, options)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def _owned_question(self, request, question_id):
        return ClassExerciseQuestion.objects.filter(
            id=question_id, section__exercise__session__teacher=request.user,
        ).first()

    def patch(self, request, question_id: int):
        q = self._owned_question(request, question_id)
        if q is None:
            return Response({'detail': 'سوال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields: list[str] = []
        mapping = {
            'question_markdown': 'question_markdown',
            'question_type': 'question_type',
            'options': 'options',
            'reference_answer_markdown': 'reference_answer_markdown',
            'max_points': 'max_points',
            'grading_notes': 'grading_notes',
        }
        for key, attr in mapping.items():
            if key in serializer.validated_data:
                setattr(q, attr, serializer.validated_data[key])
                fields.append(attr)
        if fields:
            q.save(update_fields=fields)
        return Response({'id': q.id})

    def delete(self, request, question_id: int):
        q = self._owned_question(request, question_id)
        if q is None:
            return Response({'detail': 'سوال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        q.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════════════
# Student API — phone-scoped. A student only ever reaches a PUBLISHED exercise
# of a published class they were invited to (via phone). No phone -> 400.
# Reference answers are withheld until the reveal condition holds (deadline
# passed, or no-deadline + own GRADED) — a single helper decides that.
# ═══════════════════════════════════════════════════════════════════════════

_NO_PHONE = {'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}
_EX_NOT_FOUND = {'detail': 'تمرین پیدا نشد.'}

_MAX_IMAGE_BYTES = int(os.getenv('EXERCISE_MAX_IMAGE_BYTES', str(8 * 1024 * 1024)))


def _student_phone(request):
    return (getattr(request.user, 'phone', None) or '').strip()


def _published_exercise_for_student(phone, session_id, exercise_id):
    return (
        ClassExercise.objects.filter(
            id=exercise_id,
            session_id=session_id,
            status=ClassExercise.Status.PUBLISHED,
            session__is_published=True,
            session__invites__phone=phone,
        )
        .prefetch_related('sections__questions')
        .first()
    )


def _reveal_open(exercise, submission) -> bool:
    """THE single reveal rule: reference answers may be shown only when the
    deadline has passed, or (no deadline) when the student's own submission is
    graded. Never before — an early submitter must not see the answers while
    classmates are still within the deadline (owner decision 2026-07-05)."""
    if exercise.deadline_passed():
        return True
    if exercise.deadline is None and submission is not None:
        return submission.status == StudentExerciseSubmission.Status.GRADED
    return False


# Keys that must never reach a student before reveal, even if a future grader
# (E6) accidentally persists them into result['per_question']. Defense-in-depth
# so the reveal gate holds regardless of what the grading payload contains
# (security-auditor E5 Low-1).
_REVEAL_ONLY_RESULT_KEYS = {
    'reference_answer', 'reference_answer_markdown', 'grading_notes',
}


def _result_for_student(result, *, reveal: bool):
    """Return ``result`` with any reference-answer-ish keys stripped from each
    ``per_question`` entry when the reveal condition is not yet open."""
    if reveal or not isinstance(result, dict):
        return result
    per_q = result.get('per_question')
    if not isinstance(per_q, list):
        return result
    cleaned = [
        {k: v for k, v in pq.items() if k not in _REVEAL_ONLY_RESULT_KEYS}
        if isinstance(pq, dict) else pq
        for pq in per_q
    ]
    return {**result, 'per_question': cleaned}


def _q_for_solving(q) -> dict:
    """Solving-view question shape — NEVER contains the reference answer."""
    return {
        'id': q.id, 'order': q.order,
        'questionMarkdown': q.question_markdown,
        'questionType': q.question_type,
        'options': q.options,
        'maxPoints': str(q.max_points),
    }


def _q_with_answer(q) -> dict:
    """Reveal-view question shape — adds the reference answer. Only ever used
    once ``_reveal_open`` returned True."""
    d = _q_for_solving(q)
    d['referenceAnswerMarkdown'] = q.reference_answer_markdown
    return d


def _serialize_exercise(exercise, *, reveal: bool) -> dict:
    q_fn = _q_with_answer if reveal else _q_for_solving
    return {
        'id': exercise.id,
        'title': exercise.title,
        'description': exercise.description,
        'status': exercise.status,
        'deadline': exercise.deadline.isoformat() if exercise.deadline else None,
        'assistantEnabled': exercise.assistant_enabled,
        'sections': [
            {
                'id': s.id, 'order': s.order, 'title': s.title,
                'assistantEnabled': s.assistant_enabled,
                'questions': [q_fn(q) for q in s.questions.all()],
            }
            for s in exercise.sections.all()
        ],
    }


class StudentExerciseListView(APIView):
    """List the PUBLISHED exercises of an enrolled class (+ own submission state)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request, session_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        session = ClassCreationSession.objects.filter(
            id=session_id, is_published=True, invites__phone=phone,
        ).first()
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        exercises = ClassExercise.objects.filter(
            session=session, status=ClassExercise.Status.PUBLISHED,
        ).order_by('-created_at')
        subs = {
            s.exercise_id: s.status
            for s in StudentExerciseSubmission.objects.filter(
                exercise__in=exercises, student=request.user,
            )
        }
        now = timezone.now()
        return Response([
            {
                'id': ex.id, 'title': ex.title, 'status': ex.status,
                'deadline': ex.deadline.isoformat() if ex.deadline else None,
                'deadlinePassed': ex.deadline is not None and ex.deadline < now,
                'allowLate': ex.allow_late,
                'submissionStatus': subs.get(ex.id),
            }
            for ex in exercises
        ])


class StudentExerciseDetailView(APIView):
    """The solving view — sections/questions WITHOUT reference answers, plus the
    student's own draft/submission answers to resume."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        submission = StudentExerciseSubmission.objects.filter(
            exercise=exercise, student=request.user,
        ).first()
        data = _serialize_exercise(exercise, reveal=False)  # solving = never reveal
        data['myAnswers'] = submission.answers if submission else {}
        data['submissionStatus'] = submission.status if submission else None
        return Response(data)


class StudentExerciseDraftView(APIView):
    """Autosave the student's in-progress answers (upsert a DRAFT submission)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def put(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        submission = StudentExerciseSubmission.objects.filter(
            exercise=exercise, student=request.user,
        ).first()
        if submission and submission.status != StudentExerciseSubmission.Status.DRAFT:
            return Response(
                {'detail': 'این تمرین قبلاً ارسال شده است.'}, status=status.HTTP_409_CONFLICT,
            )
        answers = request.data.get('answers') if isinstance(request.data, dict) else None
        if not isinstance(answers, dict):
            answers = {}
        if submission is None:
            submission = StudentExerciseSubmission.objects.create(
                exercise=exercise, student=request.user,
                status=StudentExerciseSubmission.Status.DRAFT, answers=answers,
            )
        else:
            submission.answers = answers
            submission.save(update_fields=['answers', 'updated_at'])
        return Response({'status': submission.status, 'saved': True})


class StudentExerciseImageView(APIView):
    """Upload one handwriting/photo answer image for a question (server-side
    type + size validation), recorded on the DRAFT submission."""

    permission_classes = [IsAuthenticated, IsStudentUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, session_id: int, exercise_id: int, question_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        question = ClassExerciseQuestion.objects.filter(
            id=question_id, section__exercise=exercise,
        ).first()
        if question is None:
            return Response({'detail': 'سوال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        up = request.FILES.get('file')
        if up is None:
            return Response({'detail': 'فایل ارسال نشده است.'}, status=status.HTTP_400_BAD_REQUEST)
        content_type = (getattr(up, 'content_type', '') or '').lower()
        if not content_type.startswith('image/'):
            return Response(
                {'detail': 'فقط تصویر مجاز است.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        if up.size and up.size > _MAX_IMAGE_BYTES:
            return Response(
                {'detail': 'حجم تصویر بیش از حد مجاز است.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        path = default_storage.save(
            f'exercises/answers/{exercise.id}/{request.user.id}/{question_id}_{up.name}',
            up,
        )
        submission, _created = StudentExerciseSubmission.objects.get_or_create(
            exercise=exercise, student=request.user,
            defaults={'status': StudentExerciseSubmission.Status.DRAFT},
        )
        if submission.status != StudentExerciseSubmission.Status.DRAFT:
            return Response(
                {'detail': 'این تمرین قبلاً ارسال شده است.'}, status=status.HTTP_409_CONFLICT,
            )
        answers = submission.answers if isinstance(submission.answers, dict) else {}
        qkey = str(question_id)
        entry = answers.get(qkey) if isinstance(answers.get(qkey), dict) else {}
        images = entry.get('images') if isinstance(entry.get('images'), list) else []
        images.append(path)
        entry['images'] = images
        answers[qkey] = entry
        submission.answers = answers
        submission.save(update_fields=['answers', 'updated_at'])
        return Response({'path': path}, status=status.HTTP_201_CREATED)


class StudentExerciseSubmitView(APIView):
    """Finalize the submission. 409 after the deadline (unless allow_late) and on
    a duplicate final submission. (Grading dispatch is wired at E6.)"""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def post(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        past_deadline = exercise.deadline is not None and exercise.deadline < timezone.now()
        if past_deadline and not exercise.allow_late:
            return Response(
                {'detail': 'مهلت ارسال این تمرین گذشته است.'}, status=status.HTTP_409_CONFLICT,
            )

        answers = request.data.get('answers') if isinstance(request.data, dict) else None
        submission = StudentExerciseSubmission.objects.filter(
            exercise=exercise, student=request.user,
        ).first()
        if submission and submission.status != StudentExerciseSubmission.Status.DRAFT:
            return Response(
                {'detail': 'شما قبلاً پاسخ این تمرین را ارسال کرده‌اید.'},
                status=status.HTTP_409_CONFLICT,
            )
        if submission is None:
            try:
                submission = StudentExerciseSubmission.objects.create(
                    exercise=exercise, student=request.user,
                    status=StudentExerciseSubmission.Status.SUBMITTED,
                    answers=answers if isinstance(answers, dict) else {},
                    is_late=bool(past_deadline),
                )
            except IntegrityError:
                return Response(
                    {'detail': 'شما قبلاً پاسخ این تمرین را ارسال کرده‌اید.'},
                    status=status.HTTP_409_CONFLICT,
                )
        else:
            if isinstance(answers, dict):
                submission.answers = answers
            submission.status = StudentExerciseSubmission.Status.SUBMITTED
            submission.is_late = bool(past_deadline)
            submission.save(update_fields=['answers', 'status', 'is_late', 'updated_at'])
        # Dispatch async grading (the task no-ops if the kill-switch is off).
        from .tasks import grade_exercise_submission
        sid = submission.id
        transaction.on_commit(lambda: grade_exercise_submission.delay(sid))
        return Response(
            {'status': submission.status, 'isLate': submission.is_late},
            status=status.HTTP_201_CREATED,
        )


class StudentExerciseResultView(APIView):
    """The student's own graded result. Reference answers appear ONLY when the
    reveal condition holds (deadline passed, or no-deadline + own GRADED)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        submission = StudentExerciseSubmission.objects.filter(
            exercise=exercise, student=request.user,
        ).first()
        if submission is None or submission.status == StudentExerciseSubmission.Status.DRAFT:
            return Response({'detail': 'هنوز پاسخی ارسال نکرده‌اید.'}, status=status.HTTP_404_NOT_FOUND)
        if submission.status != StudentExerciseSubmission.Status.GRADED:
            # Failure-specific copy — a generic "wait for grading" would contradict
            # the «خطا در نمره‌دهی» badge the hub shows for GRADING_FAILED.
            if submission.status == StudentExerciseSubmission.Status.GRADING_FAILED:
                detail = 'نمره‌دهی خودکار با خطا مواجه شد. پاسخ شما محفوظ است و پس از بررسی، نتیجه ثبت می‌شود.'
            else:
                detail = 'پاسخ شما ارسال شد. نتیجه پس از نمره‌دهی نمایش داده می‌شود.'
            return Response({'status': submission.status, 'detail': detail})
        reveal = _reveal_open(exercise, submission)
        return Response({
            'status': submission.status,
            'scorePoints': str(submission.score_points) if submission.score_points is not None else None,
            'maxPoints': str(submission.max_points) if submission.max_points is not None else None,
            'result': _result_for_student(submission.result, reveal=reveal),
            'answersRevealed': reveal,
            'exercise': _serialize_exercise(exercise, reveal=reveal),
        })


class StudentFinishedAnswersView(APIView):
    """«پاسخ تمرین‌های تمام‌شده» — browse the reference answers of past
    (deadline-passed) exercises of the student's enrolled classes."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        exercises = (
            ClassExercise.objects.filter(
                status=ClassExercise.Status.PUBLISHED,
                session__is_published=True,
                session__invites__phone=phone,
                deadline__isnull=False,
                deadline__lt=now,  # reveal is open
            )
            .prefetch_related('sections__questions')
            .select_related('session')
            .order_by('-deadline')
            .distinct()
        )
        return Response([
            {
                'sessionId': ex.session_id,
                'courseTitle': ex.session.title,
                **_serialize_exercise(ex, reveal=True),  # deadline passed -> reveal
            }
            for ex in exercises
        ])


# ═══════════════════════════════════════════════════════════════════════════
# E7 — Report cards + teacher override + allow-redo.
# Override writes teacher_score/teacher_feedback beside an IMMUTABLE llm_score
# (audit); the effective score_points is recomputed = teacher_score if set else
# llm_score. Report cards = simple average of the student's GRADED exercises'
# percentages (past-deadline no-submission exercises are excluded, not zeroed).
# ═══════════════════════════════════════════════════════════════════════════

from decimal import Decimal as _Decimal  # noqa: E402


def _owned_submission(request, submission_id):
    return StudentExerciseSubmission.objects.filter(
        id=submission_id, exercise__session__teacher=request.user,
    ).select_related('exercise', 'student').first()


def _effective(pq: dict):
    ts = pq.get('teacher_score')
    if ts is not None:
        return float(ts)
    llm = pq.get('llm_score')
    if llm is not None:
        return float(llm)
    return float(pq.get('score_points') or 0)


def _recompute_submission_score(submission) -> None:
    result = submission.result if isinstance(submission.result, dict) else {}
    per_q = result.get('per_question') if isinstance(result.get('per_question'), list) else []
    for pq in per_q:
        if isinstance(pq, dict):
            pq['score_points'] = round(_effective(pq), 2)
    total = sum(_effective(pq) for pq in per_q if isinstance(pq, dict))
    submission.result = {'per_question': per_q}
    submission.score_points = _Decimal(str(round(total, 2)))


class TeacherSubmissionListView(APIView):
    """List every student submission for one owned exercise (gradebook column)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        subs = StudentExerciseSubmission.objects.filter(
            exercise=exercise,
        ).exclude(status=StudentExerciseSubmission.Status.DRAFT).select_related('student')
        return Response([
            {
                'id': s.id,
                'studentId': s.student_id,
                'studentName': (s.student.get_full_name() or s.student.username),
                'status': s.status,
                'isLate': s.is_late,
                'scorePoints': str(s.score_points) if s.score_points is not None else None,
                'maxPoints': str(s.max_points) if s.max_points is not None else None,
                'overridden': s.overridden_at is not None,
            }
            for s in subs
        ])


class TeacherSubmissionDetailView(APIView):
    """Full detail of one owned submission (teacher sees answers + result)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, submission_id: int):
        submission = _owned_submission(request, submission_id)
        if submission is None:
            return Response({'detail': 'ارسال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'id': submission.id,
            'studentId': submission.student_id,
            'studentName': (submission.student.get_full_name() or submission.student.username),
            'status': submission.status,
            'isLate': submission.is_late,
            'answers': submission.answers,
            'result': submission.result,
            'scorePoints': str(submission.score_points) if submission.score_points is not None else None,
            'maxPoints': str(submission.max_points) if submission.max_points is not None else None,
            'overriddenAt': submission.overridden_at.isoformat() if submission.overridden_at else None,
        })


class TeacherSubmissionOverrideView(APIView):
    """Override per-question scores/feedback. llm_score is NEVER overwritten."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def patch(self, request, submission_id: int):
        submission = _owned_submission(request, submission_id)
        if submission is None:
            return Response({'detail': 'ارسال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        raw = request.data.get('overrides') if isinstance(request.data, dict) else None
        overrides = {}
        if isinstance(raw, list):
            for o in raw:
                if isinstance(o, dict) and o.get('question_id') is not None:
                    overrides[str(o['question_id'])] = o
        result = submission.result if isinstance(submission.result, dict) else {}
        per_q = result.get('per_question') if isinstance(result.get('per_question'), list) else []
        for pq in per_q:
            if not isinstance(pq, dict):
                continue
            o = overrides.get(str(pq.get('question_id')))
            if not o:
                continue
            if 'teacher_score' in o and o['teacher_score'] is not None:
                pq['teacher_score'] = float(o['teacher_score'])  # llm_score untouched
            if 'teacher_feedback' in o:
                pq['teacher_feedback'] = str(o['teacher_feedback'] or '')
        submission.result = {'per_question': per_q}
        _recompute_submission_score(submission)
        submission.overridden_at = timezone.now()
        submission.save(update_fields=['result', 'score_points', 'overridden_at', 'updated_at'])
        return Response({
            'id': submission.id,
            'scorePoints': str(submission.score_points),
            'result': submission.result,
        })


class TeacherSubmissionAllowRedoView(APIView):
    """Grant a re-submission: reset the submission to DRAFT (keeps answers,
    clears the grade so the student must retake — the exam-prep reset pattern)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, submission_id: int):
        submission = _owned_submission(request, submission_id)
        if submission is None:
            return Response({'detail': 'ارسال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        submission.status = StudentExerciseSubmission.Status.DRAFT
        submission.result = {}
        submission.score_points = None
        submission.max_points = None
        submission.graded_at = None
        submission.overridden_at = None
        submission.save(update_fields=[
            'status', 'result', 'score_points', 'max_points',
            'graded_at', 'overridden_at', 'updated_at',
        ])
        return Response({'status': submission.status})


def _course_report(student, session_id=None):
    """Build the student's graded-exercise percentages (optionally one course)."""
    qs = StudentExerciseSubmission.objects.filter(
        student=student, status=StudentExerciseSubmission.Status.GRADED,
    ).select_related('exercise')
    if session_id is not None:
        qs = qs.filter(exercise__session_id=session_id)
    rows = []
    for s in qs:
        mx = float(s.max_points or 0)
        pct = round(float(s.score_points or 0) / mx * 100, 1) if mx > 0 else 0.0
        rows.append({
            'exerciseId': s.exercise_id,
            'exerciseTitle': s.exercise.title,
            'scorePoints': str(s.score_points) if s.score_points is not None else None,
            'maxPoints': str(s.max_points) if s.max_points is not None else None,
            'percent': pct,
        })
    avg = round(sum(r['percent'] for r in rows) / len(rows), 1) if rows else None
    return rows, avg


class StudentCourseReportCardView(APIView):
    """The student's report card for one enrolled course (per-exercise + average)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request, session_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        session = ClassCreationSession.objects.filter(
            id=session_id, is_published=True, invites__phone=phone,
        ).first()
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        rows, avg = _course_report(request.user, session_id=session_id)
        return Response({'average': avg, 'exercises': rows})


class StudentOverallReportCardView(APIView):
    """The student's overall report card across all enrolled courses."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        rows, avg = _course_report(request.user)
        return Response({'average': avg, 'exercises': rows})


class StudentCalendarView(APIView):
    """Aggregate calendar for a student: published exercise deadlines of enrolled
    classes + scheduled (timed) exam-prep sessions they were invited to. Returns
    Tehran-tz ISO datetimes; the frontend does the Jalali conversion."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from django.utils.dateparse import parse_datetime
        from .models import StudentExamPrepAttempt

        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)

        tehran = ZoneInfo('Asia/Tehran')

        def _parse(raw):
            if not raw:
                return None
            dt = parse_datetime(raw)
            if dt is None:
                try:
                    dt = datetime.fromisoformat(raw)
                except (ValueError, TypeError):
                    return None
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, tehran)
            return dt

        dt_from = _parse(request.query_params.get('from'))
        dt_to = _parse(request.query_params.get('to'))

        def _iso(dt):
            return timezone.localtime(dt, tehran).isoformat() if dt else None

        # Exercise deadlines of enrolled (invited + published) classes.
        exercises = ClassExercise.objects.filter(
            status=ClassExercise.Status.PUBLISHED,
            session__is_published=True,
            session__invites__phone=phone,
            deadline__isnull=False,
        ).select_related('session').distinct()
        if dt_from:
            exercises = exercises.filter(deadline__gte=dt_from)
        if dt_to:
            exercises = exercises.filter(deadline__lte=dt_to)

        submitted_ex = set(
            StudentExerciseSubmission.objects.filter(
                student=request.user, exercise__in=exercises,
            ).exclude(status=StudentExerciseSubmission.Status.DRAFT)
            .values_list('exercise_id', flat=True)
        )

        # Scheduled (timed) exam-prep sessions the student was invited to.
        exam_preps = ClassCreationSession.objects.filter(
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            is_published=True,
            invites__phone=phone,
            scheduled_at__isnull=False,
        ).distinct()
        if dt_from:
            exam_preps = exam_preps.filter(scheduled_at__gte=dt_from)
        if dt_to:
            exam_preps = exam_preps.filter(scheduled_at__lte=dt_to)

        finalized_sessions = set(
            StudentExamPrepAttempt.objects.filter(
                student=request.user, session__in=exam_preps, finalized=True,
            ).values_list('session_id', flat=True)
        )

        events = []
        for ex in exercises:
            events.append({
                'id': f'exercise-{ex.id}',
                'kind': 'exercise_deadline',
                'title': ex.title,
                'courseTitle': ex.session.title,
                'datetime': _iso(ex.deadline),
                'sessionId': ex.session_id,
                'exerciseId': ex.id,
                'isCompleted': ex.id in submitted_ex,
            })
        for s in exam_preps:
            events.append({
                'id': f'exam_prep-{s.id}',
                'kind': 'exam_prep',
                'title': s.title,
                'courseTitle': s.title,
                'datetime': _iso(s.scheduled_at),
                'sessionId': s.id,
                'isCompleted': s.id in finalized_sessions,
            })
        events.sort(key=lambda e: e['datetime'] or '')
        return Response(events)


class StudentExerciseAssistantView(APIView):
    """In-exercise assistant chat. Two-level server-side toggle guard (exercise
    AND section) -> 403 `assistant_disabled`. Reference answers enter the model
    context only after reveal (structural leak guard in the service)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def post(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        question_id = request.data.get('question_id') if isinstance(request.data, dict) else None
        question = ClassExerciseQuestion.objects.filter(
            id=question_id, section__exercise=exercise,
        ).select_related('section').first()
        if question is None:
            return Response({'detail': 'سوال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        # Two-level assistant toggle — server-side, deny-by-default.
        if not (exercise.assistant_enabled and question.section.assistant_enabled):
            return Response(
                {'detail': 'دستیار برای این بخش غیرفعال است.', 'code': 'assistant_disabled'},
                status=status.HTTP_403_FORBIDDEN,
            )

        submission = StudentExerciseSubmission.objects.filter(
            exercise=exercise, student=request.user,
        ).first()
        reveal = _reveal_open(exercise, submission)  # gates reference-answer teaching
        student_work = ''
        if submission and isinstance(submission.answers, dict):
            entry = submission.answers.get(str(question.id))
            if isinstance(entry, dict):
                student_work = str(entry.get('text') or '')

        from .services.exercise_assistant import handle_assistant_message
        reply = handle_assistant_message(
            exercise_id=exercise.id, question=question,
            student_id=request.user.id,
            user_message=str(request.data.get('message') or ''),
            student_work=student_work, reveal=reveal,
        )
        return Response(reply)
