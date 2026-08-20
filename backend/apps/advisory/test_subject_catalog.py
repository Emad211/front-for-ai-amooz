"""S2 — the ``Subject`` catalog: duplicate key, constraints, and admin safety.

Zero-token, no-network. The whole point of this table is that the *same* subject
typed two ways must not become two rows — so most of this file is about the ways
Persian text differs invisibly.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from model_bakery import baker

from apps.advisory.models import Subject
from apps.advisory.services.text import normalize_subject_name
from apps.organizations.models import Organization

pytestmark = pytest.mark.django_db


# ── the normalizer itself (pure) ─────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.parametrize('a, b', [
    # Arabic vs Persian letters — the single most common paste artifact.
    ('ریاضي', 'ریاضی'),
    ('كتاب', 'کتاب'),
    ('مطالعة', 'مطالعه'),
    # Persian, Arabic-Indic and ASCII digits are the same number.
    ('ریاضی ۱', 'ریاضی 1'),
    ('ریاضی ١', 'ریاضی ۱'),
    # Spacing: plain space, ZWNJ, double space and nothing at all.
    ('زیست شناسی', 'زیست‌شناسی'),
    ('زیست  شناسی', 'زیستشناسی'),
    (' فیزیک ', 'فیزیک'),
    # Invisible controls that survive a copy out of a PDF or a browser.
    ('عربی‏', 'عربی'),
    ('﻿عربی', 'عربی'),
    ('عرـبی', 'عربی'),
    ('عَرَبی', 'عربی'),
    # Latin names will eventually live here too.
    ('Math', 'math'),
])
def test_visually_equal_names_share_one_key(a, b):
    assert normalize_subject_name(a) == normalize_subject_name(b)


@pytest.mark.unit
@pytest.mark.parametrize('a, b', [
    ('ریاضی ۱', 'ریاضی ۲'),
    ('فیزیک', 'شیمی'),
    ('عربی', 'ادبیات'),
])
def test_genuinely_different_names_keep_different_keys(a, b):
    assert normalize_subject_name(a) != normalize_subject_name(b)


@pytest.mark.unit
def test_key_never_outgrows_the_column():
    """The key column shares ``name``'s max_length, so folding must not expand."""
    raw = 'ریاضی‌۱ ﻻ عَرَبی' * 6
    assert len(normalize_subject_name(raw)) <= len(raw)


@pytest.mark.unit
def test_blank_and_none_normalize_to_empty():
    assert normalize_subject_name(None) == ''
    assert normalize_subject_name('   ‌ ') == ''


# ── the derived column ───────────────────────────────────────────────────────

def test_save_derives_the_key():
    subject = Subject.objects.create(name='ریاضي ۱')
    subject.refresh_from_db()
    assert subject.normalized_name == normalize_subject_name('ریاضی 1')


def test_rename_via_update_fields_still_rewrites_the_key():
    """save(update_fields=['name']) must not leave a stale key behind."""
    subject = Subject.objects.create(name='فیزیک')
    subject.name = 'شیمی'
    subject.save(update_fields=['name'])

    subject.refresh_from_db()
    assert subject.normalized_name == normalize_subject_name('شیمی')


def test_update_fields_without_name_is_left_alone():
    subject = Subject.objects.create(name='فیزیک')
    subject.is_active = False
    subject.save(update_fields=['is_active'])

    subject.refresh_from_db()
    assert subject.is_active is False
    assert subject.normalized_name == normalize_subject_name('فیزیک')


# ── uniqueness ───────────────────────────────────────────────────────────────

def test_two_globals_with_the_same_key_are_rejected():
    """The partial constraint is the only thing stopping this: PG sees every NULL
    organization as distinct, so the composite constraint alone would allow it."""
    Subject.objects.create(name='ریاضی ۱')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Subject.objects.create(name='ریاضي 1')


def test_partial_global_constraint_actually_exists():
    names = {c.name for c in Subject._meta.constraints}
    assert 'uniq_advisory_subject_norm_global' in names
    assert 'uniq_advisory_subject_norm_org' in names


def test_same_key_in_two_organizations_is_allowed():
    org_a = baker.make(Organization, slug='org-a')
    org_b = baker.make(Organization, slug='org-b')
    Subject.objects.create(name='ریاضی ۱', organization=org_a)
    Subject.objects.create(name='ریاضی ۱', organization=org_b)
    assert Subject.objects.count() == 2


def test_org_private_subject_may_shadow_a_global_one():
    org = baker.make(Organization, slug='org-a')
    Subject.objects.create(name='ریاضی ۱')
    Subject.objects.create(name='ریاضی ۱', organization=org)
    assert Subject.objects.filter(normalized_name=normalize_subject_name('ریاضی ۱')).count() == 2


def test_duplicate_inside_one_organization_is_rejected():
    org = baker.make(Organization, slug='org-a')
    Subject.objects.create(name='ریاضی ۱', organization=org)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Subject.objects.create(name='ریاضي 1', organization=org)


# ── admin-facing validation ──────────────────────────────────────────────────

def test_clean_reports_a_duplicate_on_the_name_field():
    """``normalized_name`` is editable=False, so ModelForm validation excludes it
    and skips both constraints — without this explicit check the Django admin
    would 500 on a duplicate instead of showing a field error."""
    Subject.objects.create(name='ریاضی ۱')
    with pytest.raises(ValidationError) as exc:
        Subject(name='ریاضي 1').full_clean()
    assert 'name' in exc.value.message_dict


def test_clean_ignores_the_row_being_edited():
    subject = Subject.objects.create(name='ریاضی ۱')
    subject.name = 'ریاضي ۱'  # same subject, Arabic yeh
    subject.full_clean()  # must not raise


def test_clean_rejects_a_name_that_normalizes_to_nothing():
    with pytest.raises(ValidationError) as exc:
        Subject(name='‌ ‏').full_clean()
    assert 'name' in exc.value.message_dict


def test_clean_lets_the_same_name_through_in_a_different_scope():
    org = baker.make(Organization, slug='org-a')
    Subject.objects.create(name='ریاضی ۱')
    Subject(name='ریاضی ۱', organization=org).full_clean()  # must not raise


def test_is_global_reflects_the_organization():
    org = baker.make(Organization, slug='org-a')
    assert Subject.objects.create(name='فیزیک').is_global is True
    assert Subject.objects.create(name='فیزیک', organization=org).is_global is False
