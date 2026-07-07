"""E4 — Exercise Hub teacher API: happy CRUD + publish gate + the owner/role
negative matrix (anonymous→401, student→403, cross-teacher→404).

Design + permission matrix: docs/features/exercise-hub.md.
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import (
    ClassCreationSession,
    ClassExercise,
    ClassExerciseAsset,
    ClassExerciseQuestion,
    ClassExerciseSection,
)

pytestmark = [pytest.mark.django_db, pytest.mark.api]

Status = ClassExercise.Status


def _auth(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _teacher():
    return baker.make(User, role=User.Role.TEACHER)


def _session(owner):
    return baker.make(ClassCreationSession, teacher=owner, pipeline_type='class')


def _exercise(owner, **kw):
    return baker.make(ClassExercise, session=_session(owner), **kw)


LIST = '/api/classes/creation-sessions/{}/exercises/'
DETAIL = '/api/classes/exercises/{}/'
EXTRACT = '/api/classes/exercises/{}/extract/'
PUBLISH = '/api/classes/exercises/{}/publish/'
REF_PREVIEW = '/api/classes/exercises/{}/reference-ingest/preview/'
REF_APPLY = '/api/classes/exercises/{}/reference-ingest/apply/'


class TestCreateAndList:
    def test_teacher_creates_and_lists_exercise(self):
        owner = _teacher()
        session = _session(owner)
        res = _auth(owner).post(LIST.format(session.id), {'title': 'تمرین ۱'}, format='multipart')
        assert res.status_code == 201, res.content
        assert res.data['title'] == 'تمرین ۱'
        assert res.data['status'] == Status.DRAFT
        lst = _auth(owner).get(LIST.format(session.id))
        assert lst.status_code == 200 and len(lst.data) == 1

    def test_create_on_other_teacher_session_is_404(self):
        owner, other = _teacher(), _teacher()
        session = _session(owner)
        res = _auth(other).post(LIST.format(session.id), {'title': 'x'}, format='multipart')
        assert res.status_code == 404

    def test_anonymous_denied(self):
        session = _session(_teacher())
        assert APIClient().get(LIST.format(session.id)).status_code in (401, 403)

    def test_student_forbidden(self):
        session = _session(_teacher())
        student = baker.make(User, role=User.Role.STUDENT)
        assert _auth(student).get(LIST.format(session.id)).status_code == 403

    def test_create_rejects_fake_image_asset_without_creating_exercise(self):
        owner = _teacher()
        session = _session(owner)
        bad = SimpleUploadedFile('bad.png', b'not-an-image', content_type='image/png')
        res = _auth(owner).post(
            LIST.format(session.id),
            {'title': 'تمرین خراب', 'files': [bad]},
            format='multipart',
        )
        assert res.status_code == 400
        assert not ClassExercise.objects.filter(title='تمرین خراب').exists()

    def test_create_rejects_fake_pdf_asset_without_creating_exercise(self):
        owner = _teacher()
        session = _session(owner)
        bad = SimpleUploadedFile('bad.pdf', b'not-a-pdf', content_type='application/pdf')
        res = _auth(owner).post(
            LIST.format(session.id),
            {'title': 'تمرین PDF خراب', 'files': [bad]},
            format='multipart',
        )
        assert res.status_code == 400
        assert not ClassExercise.objects.filter(title='تمرین PDF خراب').exists()
        assert ClassExerciseAsset.objects.count() == 0

    def test_create_rejects_too_many_assets_before_creating_exercise(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        session = _session(owner)
        monkeypatch.setattr(vx, '_MAX_SOURCE_FILES', 1)
        files = [
            SimpleUploadedFile('a.pdf', b'not-even-validated', content_type='application/pdf'),
            SimpleUploadedFile('b.pdf', b'not-even-validated', content_type='application/pdf'),
        ]
        res = _auth(owner).post(
            LIST.format(session.id),
            {'title': 'تمرین فایل زیاد', 'files': files},
            format='multipart',
        )
        assert res.status_code == 400
        assert not ClassExercise.objects.filter(title='تمرین فایل زیاد').exists()


class TestDetailUpdateDelete:
    def test_owner_patches_toggle_and_deadline(self):
        owner = _teacher()
        ex = _exercise(owner)
        res = _auth(owner).patch(
            DETAIL.format(ex.id), {'assistant_enabled': False, 'allow_late': True}, format='json',
        )
        assert res.status_code == 200
        ex.refresh_from_db()
        assert ex.assistant_enabled is False and ex.allow_late is True

    def test_non_owner_cannot_view_or_patch_or_delete(self):
        owner, other = _teacher(), _teacher()
        ex = _exercise(owner)
        assert _auth(other).get(DETAIL.format(ex.id)).status_code == 404
        assert _auth(other).patch(DETAIL.format(ex.id), {'title': 'hijack'}, format='json').status_code == 404
        assert _auth(other).delete(DETAIL.format(ex.id)).status_code == 404
        ex.refresh_from_db()
        assert ex.title != 'hijack'

    def test_owner_deletes(self):
        owner = _teacher()
        ex = _exercise(owner)
        assert _auth(owner).delete(DETAIL.format(ex.id)).status_code == 204
        assert not ClassExercise.objects.filter(id=ex.id).exists()


class TestExtract:
    def test_extract_dispatches(self, monkeypatch):
        from apps.classes import views_exercises as vx
        called = {}
        monkeypatch.setattr(vx.extract_exercise_content, 'delay', lambda eid: called.setdefault('id', eid))
        owner = _teacher()
        ex = _exercise(owner, status=Status.DRAFT)
        res = _auth(owner).post(EXTRACT.format(ex.id))
        assert res.status_code == 202

    def test_extract_conflicts_while_extracting(self):
        owner = _teacher()
        ex = _exercise(owner, status=Status.EXTRACTING)
        assert _auth(owner).post(EXTRACT.format(ex.id)).status_code == 409

    def test_extract_cross_teacher_404(self):
        owner, other = _teacher(), _teacher()
        ex = _exercise(owner)
        assert _auth(other).post(EXTRACT.format(ex.id)).status_code == 404


class TestPublishGate:
    def _exercise_with_question(self, owner, **qkw):
        ex = _exercise(owner, status=Status.EXTRACTED)
        sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
        baker.make(ClassExerciseQuestion, section=sec, order=0, **qkw)
        return ex

    def test_publish_blocked_without_reference_answer(self):
        owner = _teacher()
        ex = self._exercise_with_question(
            owner, reference_answer_markdown='', max_points=Decimal('2'))
        res = _auth(owner).post(PUBLISH.format(ex.id))
        assert res.status_code == 400
        assert 'incompleteQuestionIds' in res.data
        ex.refresh_from_db()
        assert ex.status == Status.EXTRACTED  # not published

    def test_publish_blocked_wrong_status(self):
        owner = _teacher()
        ex = _exercise(owner, status=Status.DRAFT)
        assert _auth(owner).post(PUBLISH.format(ex.id)).status_code == 409

    def test_publish_blocked_when_no_questions(self):
        owner = _teacher()
        ex = _exercise(owner, status=Status.EXTRACTED)
        assert _auth(owner).post(PUBLISH.format(ex.id)).status_code == 400

    def test_publish_succeeds_when_complete(self):
        owner = _teacher()
        ex = self._exercise_with_question(
            owner, reference_answer_markdown='پاسخ', max_points=Decimal('2'))
        res = _auth(owner).post(PUBLISH.format(ex.id))
        assert res.status_code == 200
        ex.refresh_from_db()
        assert ex.status == Status.PUBLISHED

    def test_publish_cross_teacher_404(self):
        owner, other = _teacher(), _teacher()
        ex = self._exercise_with_question(
            owner, reference_answer_markdown='پاسخ', max_points=Decimal('2'))
        assert _auth(other).post(PUBLISH.format(ex.id)).status_code == 404


class TestSectionAndQuestionOwnership:
    def test_section_toggle_owner_only(self):
        owner, other = _teacher(), _teacher()
        ex = _exercise(owner)
        sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
        url = f'/api/classes/exercises/sections/{sec.id}/'
        assert _auth(other).patch(url, {'assistant_enabled': False}, format='json').status_code == 404
        ok = _auth(owner).patch(url, {'assistant_enabled': False}, format='json')
        assert ok.status_code == 200 and ok.data['assistantEnabled'] is False

    def test_question_edit_owner_only(self):
        owner, other = _teacher(), _teacher()
        ex = _exercise(owner)
        sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
        q = baker.make(ClassExerciseQuestion, section=sec, order=0)
        url = f'/api/classes/exercises/questions/{q.id}/'
        assert _auth(other).patch(url, {'reference_answer_markdown': 'x'}, format='json').status_code == 404
        ok = _auth(owner).patch(url, {'reference_answer_markdown': 'پاسخ'}, format='json')
        assert ok.status_code == 200
        q.refresh_from_db()
        assert q.reference_answer_markdown == 'پاسخ'


class TestReferenceIngest:
    def _exercise_with_questions(self, owner):
        ex = _exercise(owner, status=Status.EXTRACTED)
        sec = baker.make(ClassExerciseSection, exercise=ex, order=0, title='بخش اول')
        q1 = baker.make(
            ClassExerciseQuestion,
            section=sec,
            order=0,
            question_markdown='سوال اول',
            reference_answer_markdown='',
            max_points=Decimal('1'),
        )
        q2 = baker.make(
            ClassExerciseQuestion,
            section=sec,
            order=1,
            question_markdown='سوال دوم',
            reference_answer_markdown='پاسخ موجود',
            max_points=Decimal('1'),
        )
        return ex, q1, q2

    def test_preview_returns_candidates_without_writing(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, q1, _q2 = self._exercise_with_questions(owner)
        monkeypatch.setattr(
            vx,
            'ingest_reference_answers_markdown',
            lambda **_kw: ({
                'mode_detected': 'numbered_answers',
                'items': [{
                    'item_id': 'i1',
                    'question_number': 1,
                    'reference_answer_markdown': 'پاسخ مرجع',
                    'points': 2,
                    'confidence': 0.95,
                    'notes': '',
                }],
                'warnings': [],
            }, 'test', 'model'),
        )

        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id),
            {'source_text': '۱) پاسخ مرجع', 'mode_hint': 'numbered_answers'},
            format='multipart',
        )
        assert res.status_code == 200, res.content
        assert res.data['items'][0]['matchStatus'] == 'matched'
        assert res.data['items'][0]['targetQuestionId'] == q1.id
        q1.refresh_from_db()
        assert q1.reference_answer_markdown == ''

    def test_preview_cross_teacher_404_and_student_403(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner, other = _teacher(), _teacher()
        student = baker.make(User, role=User.Role.STUDENT)
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        called = {'n': 0}

        def fake(**_kw):
            called['n'] += 1
            return ({'items': []}, 'p', 'm')

        monkeypatch.setattr(vx, 'ingest_reference_answers_markdown', fake)
        assert _auth(other).post(
            REF_PREVIEW.format(ex.id), {'source_text': 'x'}, format='multipart',
        ).status_code == 404
        assert _auth(student).post(
            REF_PREVIEW.format(ex.id), {'source_text': 'x'}, format='multipart',
        ).status_code == 403
        assert called['n'] == 0

    def test_preview_rejects_invalid_image_bytes(self, monkeypatch):
        owner = _teacher()
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        bad = SimpleUploadedFile('bad.png', b'not-an-image', content_type='image/png')
        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id),
            {'files': [bad]},
            format='multipart',
        )
        assert res.status_code == 400

    def test_preview_blocks_published_exercise_before_llm(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        ex.status = Status.PUBLISHED
        ex.save(update_fields=['status'])
        called = {'n': 0}

        def fake(**_kw):
            called['n'] += 1
            return ({'items': []}, 'p', 'm')

        monkeypatch.setattr(vx, 'ingest_reference_answers_markdown', fake)
        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id), {'source_text': 'x'}, format='multipart',
        )
        assert res.status_code == 409
        assert called['n'] == 0

    def test_preview_rejects_too_many_files_before_llm(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        called = {'n': 0}

        def fake(**_kw):
            called['n'] += 1
            return ({'items': []}, 'p', 'm')

        monkeypatch.setattr(vx, '_MAX_REFERENCE_FILES', 1)
        monkeypatch.setattr(vx, 'ingest_reference_answers_markdown', fake)
        files = [
            SimpleUploadedFile('a.pdf', b'not-validated', content_type='application/pdf'),
            SimpleUploadedFile('b.pdf', b'not-validated', content_type='application/pdf'),
        ]
        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id), {'files': files}, format='multipart',
        )
        assert res.status_code == 400
        assert called['n'] == 0

    def test_preview_rejects_fake_pdf_before_llm(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        called = {'n': 0}

        def fake(**_kw):
            called['n'] += 1
            return ({'items': []}, 'p', 'm')

        monkeypatch.setattr(vx, 'ingest_reference_answers_markdown', fake)
        bad = SimpleUploadedFile('bad.pdf', b'not-a-pdf', content_type='application/pdf')
        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id), {'files': [bad]}, format='multipart',
        )
        assert res.status_code == 400
        assert called['n'] == 0

    def test_preview_rejects_file_size_limit_before_llm(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        called = {'n': 0}

        def fake(**_kw):
            called['n'] += 1
            return ({'items': []}, 'p', 'm')

        monkeypatch.setattr(vx, '_MAX_REFERENCE_FILE_BYTES', 3)
        monkeypatch.setattr(vx, 'ingest_reference_answers_markdown', fake)
        too_large = SimpleUploadedFile('big.pdf', b'%PDF-1.7', content_type='application/pdf')
        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id), {'files': [too_large]}, format='multipart',
        )
        assert res.status_code == 413
        assert called['n'] == 0

    def test_preview_rejects_invalid_mode_hint_before_llm(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        called = {'n': 0}

        def fake(**_kw):
            called['n'] += 1
            return ({'items': []}, 'p', 'm')

        monkeypatch.setattr(vx, 'ingest_reference_answers_markdown', fake)
        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id),
            {'source_text': 'x', 'mode_hint': 'x' * 100},
            format='multipart',
        )
        assert res.status_code == 400
        assert called['n'] == 0

    def test_preview_rejects_pdf_page_budget_before_ocr_and_llm(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        called = {'ocr': 0, 'llm': 0}

        def fake_ocr(_files):
            called['ocr'] += 1
            return 'ocr'

        def fake_llm(**_kw):
            called['llm'] += 1
            return ({'items': []}, 'p', 'm')

        monkeypatch.setattr(vx, '_MAX_REFERENCE_PDF_PAGES', 2)
        monkeypatch.setattr(vx, '_reference_ocr_unit_count', lambda _uploaded, _kind: 3)
        monkeypatch.setattr(vx, 'ocr_uploaded_files_to_markdown', fake_ocr)
        monkeypatch.setattr(vx, 'ingest_reference_answers_markdown', fake_llm)
        pdf = SimpleUploadedFile('answers.pdf', b'%PDF-1.7', content_type='application/pdf')
        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id),
            {'files': [pdf]},
            format='multipart',
        )
        assert res.status_code == 413
        assert called == {'ocr': 0, 'llm': 0}

    def test_preview_rejects_oversized_source_text_before_llm(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        called = {'n': 0}

        def fake(**_kw):
            called['n'] += 1
            return ({'items': []}, 'p', 'm')

        monkeypatch.setattr(vx, '_MAX_REFERENCE_SOURCE_CHARS', 10)
        monkeypatch.setattr(vx, 'ingest_reference_answers_markdown', fake)
        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id),
            {'source_text': 'x' * 11},
            format='multipart',
        )
        assert res.status_code == 413
        assert called['n'] == 0

    def test_preview_rejects_oversized_ocr_text_before_llm(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, _q1, _q2 = self._exercise_with_questions(owner)
        called = {'n': 0}

        def fake(**_kw):
            called['n'] += 1
            return ({'items': []}, 'p', 'm')

        monkeypatch.setattr(vx, '_MAX_REFERENCE_SOURCE_CHARS', 10)
        monkeypatch.setattr(vx, '_reference_ocr_unit_count', lambda _uploaded, _kind: 1)
        monkeypatch.setattr(vx, 'ocr_uploaded_files_to_markdown', lambda _files: 'x' * 11)
        monkeypatch.setattr(vx, 'ingest_reference_answers_markdown', fake)
        pdf = SimpleUploadedFile('answers.pdf', b'%PDF-1.7', content_type='application/pdf')
        res = _auth(owner).post(
            REF_PREVIEW.format(ex.id),
            {'files': [pdf]},
            format='multipart',
        )
        assert res.status_code == 413
        assert called['n'] == 0

    def test_apply_updates_only_explicit_target_question(self):
        owner = _teacher()
        ex, q1, q2 = self._exercise_with_questions(owner)
        res = _auth(owner).post(
            REF_APPLY.format(ex.id),
            {'items': [{
                'targetQuestionId': q1.id,
                'referenceAnswerMarkdown': 'پاسخ تازه',
                'maxPoints': 2,
            }]},
            format='json',
        )
        assert res.status_code == 200, res.content
        q1.refresh_from_db()
        q2.refresh_from_db()
        assert q1.reference_answer_markdown == 'پاسخ تازه'
        assert q1.max_points == Decimal('2')
        assert q2.reference_answer_markdown == 'پاسخ موجود'

    def test_apply_permission_matrix_does_not_write(self):
        owner, other = _teacher(), _teacher()
        student = baker.make(User, role=User.Role.STUDENT)
        ex, q1, _q2 = self._exercise_with_questions(owner)
        payload = {'items': [{
            'targetQuestionId': q1.id,
            'referenceAnswerMarkdown': 'نباید ذخیره شود',
        }]}

        assert APIClient().post(
            REF_APPLY.format(ex.id), payload, format='json',
        ).status_code in (401, 403)
        assert _auth(student).post(
            REF_APPLY.format(ex.id), payload, format='json',
        ).status_code == 403
        assert _auth(other).post(
            REF_APPLY.format(ex.id), payload, format='json',
        ).status_code == 404
        q1.refresh_from_db()
        assert q1.reference_answer_markdown == ''

    def test_apply_does_not_overwrite_existing_reference_without_flag(self):
        owner = _teacher()
        ex, _q1, q2 = self._exercise_with_questions(owner)
        res = _auth(owner).post(
            REF_APPLY.format(ex.id),
            {'items': [{
                'targetQuestionId': q2.id,
                'referenceAnswerMarkdown': 'پاسخ جایگزین',
                'maxPoints': 5,
            }]},
            format='json',
        )
        assert res.status_code == 200, res.content
        q2.refresh_from_db()
        assert q2.reference_answer_markdown == 'پاسخ موجود'
        assert q2.max_points == Decimal('1')
        assert res.data['skipped'][0]['reason'] == 'existing_reference'

    def test_apply_replaces_existing_reference_only_with_flag(self):
        owner = _teacher()
        ex, _q1, q2 = self._exercise_with_questions(owner)
        res = _auth(owner).post(
            REF_APPLY.format(ex.id),
            {'items': [{
                'targetQuestionId': q2.id,
                'referenceAnswerMarkdown': 'پاسخ جایگزین',
                'replaceExisting': True,
            }]},
            format='json',
        )
        assert res.status_code == 200, res.content
        q2.refresh_from_db()
        assert q2.reference_answer_markdown == 'پاسخ جایگزین'

    def test_apply_rolls_back_mixed_valid_and_invalid_items(self):
        owner = _teacher()
        ex, q1, q2 = self._exercise_with_questions(owner)
        q3 = baker.make(
            ClassExerciseQuestion,
            section=q1.section,
            order=2,
            question_markdown='سوال سوم',
            reference_answer_markdown='',
            max_points=Decimal('1'),
        )
        res = _auth(owner).post(
            REF_APPLY.format(ex.id),
            {'items': [
                {'targetQuestionId': q1.id, 'referenceAnswerMarkdown': 'پاسخ معتبر'},
                {'targetQuestionId': q3.id, 'maxPoints': -1},
            ]},
            format='json',
        )
        assert res.status_code == 400
        q1.refresh_from_db()
        q2.refresh_from_db()
        q3.refresh_from_db()
        assert q1.reference_answer_markdown == ''
        assert q2.max_points == Decimal('1')
        assert q3.max_points == Decimal('1')

    def test_apply_rejects_too_many_items_before_writing(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, q1, _q2 = self._exercise_with_questions(owner)
        monkeypatch.setattr(vx, '_MAX_REFERENCE_APPLY_ITEMS', 1)
        res = _auth(owner).post(
            REF_APPLY.format(ex.id),
            {'items': [
                {'targetQuestionId': q1.id, 'referenceAnswerMarkdown': 'a'},
                {'targetQuestionId': q1.id, 'referenceAnswerMarkdown': 'b'},
            ]},
            format='json',
        )
        assert res.status_code == 400
        q1.refresh_from_db()
        assert q1.reference_answer_markdown == ''

    def test_apply_rejects_huge_points_without_writing(self, monkeypatch):
        from apps.classes import views_exercises as vx

        owner = _teacher()
        ex, q1, _q2 = self._exercise_with_questions(owner)
        monkeypatch.setattr(vx, '_MAX_REFERENCE_POINTS', Decimal('10'))
        res = _auth(owner).post(
            REF_APPLY.format(ex.id),
            {'items': [{
                'targetQuestionId': q1.id,
                'referenceAnswerMarkdown': 'پاسخ',
                'maxPoints': 1000000,
            }]},
            format='json',
        )
        assert res.status_code == 400
        q1.refresh_from_db()
        assert q1.reference_answer_markdown == ''
        assert q1.max_points == Decimal('1')

    def test_apply_blocks_published_exercise_until_regrade_story_exists(self):
        owner = _teacher()
        ex, q1, _q2 = self._exercise_with_questions(owner)
        ex.status = Status.PUBLISHED
        ex.save(update_fields=['status'])
        res = _auth(owner).post(
            REF_APPLY.format(ex.id),
            {'items': [{'targetQuestionId': q1.id, 'referenceAnswerMarkdown': 'x'}]},
            format='json',
        )
        assert res.status_code == 409
