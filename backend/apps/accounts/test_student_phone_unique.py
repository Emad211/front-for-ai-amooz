"""Phase B — the conditional unique constraint + clean-slate wipe."""

from importlib import import_module

import pytest
from django.apps import apps as global_apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from model_bakery import baker

User = get_user_model()


@pytest.mark.django_db
def test_constraint_rejects_duplicate_student_phone():
    baker.make('accounts.User', role='STUDENT', phone='09120000000', username='s1')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            baker.make('accounts.User', role='STUDENT', phone='09120000000', username='s2')


@pytest.mark.django_db
def test_constraint_allows_same_phone_for_different_role():
    baker.make('accounts.User', role='STUDENT', phone='09120000000', username='s1')
    # A TEACHER may share the phone with a STUDENT — partial index is STUDENT-only.
    teacher = baker.make('accounts.User', role='TEACHER', phone='09120000000', username='t1')
    assert teacher.pk is not None


@pytest.mark.django_db
def test_constraint_allows_multiple_null_phone_students():
    baker.make('accounts.User', role='STUDENT', phone=None, username='s1')
    s2 = baker.make('accounts.User', role='STUDENT', phone=None, username='s2')
    assert s2.pk is not None


@pytest.mark.django_db
def test_wipe_keeps_admins_deletes_everyone_else():
    mod = import_module('apps.accounts.migrations.0006_student_phone_unique')

    baker.make('accounts.User', role='ADMIN', is_superuser=True, username='boss')
    baker.make('accounts.User', role='STUDENT', phone='09120000000', username='s1')
    baker.make('accounts.User', role='TEACHER', phone=None, username='t1')
    baker.make('accounts.User', role='MANAGER', phone=None, username='m1')

    mod.wipe_non_admin_users(global_apps, None)

    assert sorted(User.objects.values_list('username', flat=True)) == ['boss']
