"""Unit tests for the invite-code service, focused on the BATCHED resolver.

``get_or_create_invite_codes_for_phones`` must preserve the exact contract of the
per-phone ``get_or_create_invite_code_for_phone`` (stable per phone, globally
unique, legacy ``ClassInvitation.invite_code`` reuse) while doing it in a
constant number of queries instead of O(N).
"""
from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    StudentInviteCode,
)
from apps.classes.services.invite_codes import (
    get_or_create_invite_code_for_phone,
    get_or_create_invite_codes_for_phones,
)


@pytest.mark.django_db
class TestBatchInviteCodes:
    def test_empty_input_returns_empty(self):
        assert get_or_create_invite_codes_for_phones([]) == {}
        assert get_or_create_invite_codes_for_phones(['', '   ', None]) == {}

    def test_creates_codes_for_all_new_phones(self):
        phones = ['09120000001', '09120000002', '09120000003']
        result = get_or_create_invite_codes_for_phones(phones)

        assert set(result.keys()) == set(phones)
        # All generated codes are unique and persisted.
        assert len({*result.values()}) == 3
        assert StudentInviteCode.objects.filter(phone__in=phones).count() == 3
        for phone, code in result.items():
            assert StudentInviteCode.objects.get(phone=phone).code == code

    def test_reuses_existing_student_invite_code(self):
        StudentInviteCode.objects.create(phone='09120000001', code='EXISTING-1')
        result = get_or_create_invite_codes_for_phones(['09120000001', '09120000002'])

        assert result['09120000001'] == 'EXISTING-1'  # unchanged
        assert result['09120000002'].startswith('INV-')  # freshly generated
        # No duplicate row created for the existing phone.
        assert StudentInviteCode.objects.filter(phone='09120000001').count() == 1

    def test_reuses_legacy_invitation_code(self):
        """A phone with a legacy ClassInvitation.invite_code but no
        StudentInviteCode keeps that code (backward compatibility)."""
        session = baker.make(ClassCreationSession, pipeline_type='class')
        ClassInvitation.objects.create(
            session=session, phone='09120000009', invite_code='LEGACY-CODE-9',
        )
        assert not StudentInviteCode.objects.filter(phone='09120000009').exists()

        result = get_or_create_invite_codes_for_phones(['09120000009'])

        assert result['09120000009'] == 'LEGACY-CODE-9'
        # And it is now backfilled into StudentInviteCode.
        assert StudentInviteCode.objects.get(phone='09120000009').code == 'LEGACY-CODE-9'

    def test_idempotent_across_calls(self):
        phones = ['09120000001', '09120000002']
        first = get_or_create_invite_codes_for_phones(phones)
        second = get_or_create_invite_codes_for_phones(phones)
        assert first == second
        assert StudentInviteCode.objects.filter(phone__in=phones).count() == 2

    def test_matches_single_phone_helper_for_existing_phone(self):
        """Batch and per-phone helpers agree on a phone that already has a code."""
        batch = get_or_create_invite_codes_for_phones(['09120000007'])
        single = get_or_create_invite_code_for_phone('09120000007')
        assert batch['09120000007'] == single

    def test_normalizes_and_dedupes(self):
        result = get_or_create_invite_codes_for_phones(
            ['  09120000001  ', '09120000001', '09120000002', '']
        )
        # Whitespace stripped, duplicate collapsed, empty dropped.
        assert set(result.keys()) == {'09120000001', '09120000002'}
        assert StudentInviteCode.objects.filter(phone='09120000001').count() == 1

    def test_constant_query_count(self):
        """20 fresh phones must NOT cost O(N) queries (the whole point)."""
        phones = [f'0912000{str(i).zfill(4)}' for i in range(20)]
        with CaptureQueriesContext(connection) as ctx:
            result = get_or_create_invite_codes_for_phones(phones)
        assert len(result) == 20
        # existing-fetch + legacy-fetch + bulk_create + re-fetch ≈ 4; allow slack.
        assert len(ctx.captured_queries) <= 6, (
            f'Batch resolver used {len(ctx.captured_queries)} queries for 20 phones '
            '(expected ~constant)'
        )
