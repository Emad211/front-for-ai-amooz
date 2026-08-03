from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from model_bakery import baker

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)


pytestmark = pytest.mark.django_db


def _document(page_count=3):
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(teacher=teacher, title='Order constraints')
    return ExamSourceDocument.objects.create(
        project=project,
        original_name='private.pdf',
        page_count=page_count,
    )


def test_display_order_defaults_to_physical_page_number():
    document = _document(page_count=1)

    page = ExamSourcePage.objects.create(
        document=document,
        page_number=1,
    )

    assert page.display_order == 1


def test_display_order_must_be_unique_inside_document():
    document = _document(page_count=2)
    ExamSourcePage.objects.create(
        document=document,
        page_number=1,
        display_order=1,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExamSourcePage.objects.create(
                document=document,
                page_number=2,
                display_order=1,
            )


def test_display_order_must_be_positive():
    document = _document(page_count=1)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExamSourcePage.objects.create(
                document=document,
                page_number=1,
                display_order=0,
            )


def test_same_display_order_is_allowed_in_separate_documents():
    first = _document(page_count=1)
    second = _document(page_count=1)

    ExamSourcePage.objects.create(
        document=first,
        page_number=1,
        display_order=1,
    )
    ExamSourcePage.objects.create(
        document=second,
        page_number=1,
        display_order=1,
    )

    assert ExamSourcePage.objects.filter(display_order=1).count() == 2


def test_virtual_segment_can_have_descending_physical_boundary_pages():
    document = _document(page_count=3)

    segment = ExamSourceSegment.objects.create(
        document=document,
        revision=1,
        order=0,
        start_page=3,
        end_page=2,
        role=ExamSourceRole.QUESTIONS,
        predicted_role=ExamSourceRole.QUESTIONS,
        predicted_confidence=Decimal('0.9000'),
        metadata={
            'pageNumbers': [3, 2],
            'displayOrderStart': 1,
            'displayOrderEnd': 2,
        },
    )

    assert segment.start_page == 3
    assert segment.end_page == 2
