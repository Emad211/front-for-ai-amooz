import uuid

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings
from model_bakery import baker

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)
from apps.classes.services.exam_prep_v4_projects import (
    ExamPrepV4Disabled,
    ExamPrepV4IdempotencyConflict,
    NewExamPdf,
    create_independent_exam_projects,
    teacher_exam_projects,
)


pytestmark = pytest.mark.django_db


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _project(teacher=None, **kwargs):
    return ExamProject.objects.create(
        teacher=teacher or _teacher(),
        title=kwargs.pop('title', 'آزمون'),
        **kwargs,
    )


def _document(project, **kwargs):
    return ExamSourceDocument.objects.create(
        project=project,
        original_name=kwargs.pop('original_name', 'exam.pdf'),
        **kwargs,
    )


def test_v4_models_are_registered_under_classes_app():
    assert apps.get_model('classes', 'ExamProject') is ExamProject
    assert apps.get_model('classes', 'ExamSourceDocument') is ExamSourceDocument
    assert apps.get_model('classes', 'ExamSourcePage') is ExamSourcePage
    assert apps.get_model('classes', 'ExamSourceSegment') is ExamSourceSegment


@override_settings(EXAM_PREP_V4_ENABLED=False)
def test_project_creation_is_disabled_without_feature_flag():
    with pytest.raises(ExamPrepV4Disabled):
        create_independent_exam_projects(
            teacher=_teacher(),
            sources=[NewExamPdf(original_name='one.pdf')],
        )


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_three_uploaded_pdfs_create_three_independent_projects():
    teacher = _teacher()
    shared_hash = 'a' * 64

    projects = create_independent_exam_projects(
        teacher=teacher,
        sources=[
            NewExamPdf(
                original_name='first.pdf',
                page_count=16,
                source_sha256=shared_hash,
            ),
            NewExamPdf(
                original_name='second.pdf',
                page_count=27,
                source_sha256=shared_hash,
            ),
            NewExamPdf(
                original_name='third.pdf',
                page_count=15,
                source_sha256=shared_hash,
            ),
        ],
    )

    assert len(projects) == 3
    assert len({project.id for project in projects}) == 3
    assert ExamProject.objects.filter(teacher=teacher).count() == 3
    assert ExamSourceDocument.objects.filter(project__teacher=teacher).count() == 3
    assert all(project.source_documents.count() == 1 for project in projects)
    assert [project.source_documents.get().page_count for project in projects] == [
        16,
        27,
        15,
    ]


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_identical_hashes_do_not_merge_independent_exams():
    teacher = _teacher()
    digest = 'b' * 64

    projects = create_independent_exam_projects(
        teacher=teacher,
        sources=[
            NewExamPdf(original_name='a.pdf', source_sha256=digest),
            NewExamPdf(original_name='b.pdf', source_sha256=digest),
        ],
    )

    assert projects[0].id != projects[1].id
    assert projects[0].source_documents.get().source_sha256 == digest
    assert projects[1].source_documents.get().source_sha256 == digest


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_same_request_retry_reuses_project_without_second_document():
    teacher = _teacher()
    request_id = uuid.uuid4()
    document_id = uuid.uuid4()
    source = NewExamPdf(
        original_name='retry.pdf',
        client_request_id=request_id,
        client_document_id=document_id,
        source_sha256='c' * 64,
    )

    first = create_independent_exam_projects(teacher=teacher, sources=[source])[0]
    second = create_independent_exam_projects(teacher=teacher, sources=[source])[0]

    assert second.id == first.id
    assert ExamProject.objects.filter(teacher=teacher).count() == 1
    assert first.source_documents.count() == 1


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_request_retry_with_different_document_is_rejected():
    teacher = _teacher()
    request_id = uuid.uuid4()
    create_independent_exam_projects(
        teacher=teacher,
        sources=[
            NewExamPdf(
                original_name='original.pdf',
                client_request_id=request_id,
            )
        ],
    )

    with pytest.raises(ExamPrepV4IdempotencyConflict):
        create_independent_exam_projects(
            teacher=teacher,
            sources=[
                NewExamPdf(
                    original_name='replacement.pdf',
                    client_request_id=request_id,
                )
            ],
        )


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_owner_scoped_queryset_never_returns_another_teachers_project():
    owner = _teacher()
    other = _teacher()
    own_project = create_independent_exam_projects(
        teacher=owner,
        sources=[NewExamPdf(original_name='owner.pdf')],
    )[0]
    create_independent_exam_projects(
        teacher=other,
        sources=[NewExamPdf(original_name='other.pdf')],
    )

    assert list(teacher_exam_projects(owner)) == [own_project]


def test_page_duplicate_reference_cannot_cross_exam_project():
    first_project = _project(title='اول')
    second_project = _project(title='دوم')
    first_document = _document(first_project, original_name='first.pdf')
    second_document = _document(second_project, original_name='second.pdf')
    original = ExamSourcePage.objects.create(
        document=first_document,
        page_number=1,
    )
    duplicate = ExamSourcePage(
        document=second_document,
        page_number=1,
        duplicate_of=original,
    )

    with pytest.raises(ValidationError, match='same exam project'):
        duplicate.full_clean()


def test_page_teacher_role_overrides_classifier_role():
    project = _project()
    document = _document(project)
    page = ExamSourcePage.objects.create(
        document=document,
        page_number=1,
        predicted_role=ExamSourceRole.COVER,
        teacher_role=ExamSourceRole.QUESTIONS,
    )

    assert page.effective_role == ExamSourceRole.QUESTIONS


def test_segment_cannot_extend_beyond_known_document_page_count():
    project = _project()
    document = _document(project, page_count=5)
    segment = ExamSourceSegment(
        document=document,
        start_page=2,
        end_page=6,
        role=ExamSourceRole.QUESTIONS,
    )

    with pytest.raises(ValidationError, match='beyond the source document'):
        segment.full_clean()


def test_database_rejects_reversed_segment_page_range():
    project = _project()
    document = _document(project, page_count=10)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExamSourceSegment.objects.create(
                document=document,
                start_page=8,
                end_page=3,
                role=ExamSourceRole.QUESTIONS,
            )


def test_database_rejects_confidence_outside_zero_to_one():
    project = _project()
    document = _document(project)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExamSourcePage.objects.create(
                document=document,
                page_number=1,
                predicted_confidence='1.1000',
            )
