"""Tests for the public waitlist intake endpoint (Phase 1)."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.waitlist.models import AccessRequest

User = get_user_model()

URL = '/api/waitlist/requests/'


@pytest.mark.django_db
def test_teacher_request_created_and_no_account():
    client = APIClient()
    before = User.objects.count()
    resp = client.post(URL, {
        'kind': 'teacher',
        'full_name': 'علی احمدی',
        'phone': '09120000000',
        'email': 'ali@example.com',
        'expertise': 'ریاضی',
    }, format='json')

    assert resp.status_code == 201, resp.content
    ar = AccessRequest.objects.get(pk=resp.json()['id'])
    assert ar.kind == AccessRequest.Kind.TEACHER
    assert ar.status == AccessRequest.Status.PENDING
    assert ar.phone == '09120000000'
    # NO account is created at request time (the chosen model).
    assert User.objects.count() == before


@pytest.mark.django_db
def test_phone_is_normalized():
    client = APIClient()
    resp = client.post(URL, {
        'kind': 'teacher',
        'full_name': 'مریم رضایی',
        'phone': '+98 912 111 2233',
    }, format='json')
    assert resp.status_code == 201, resp.content
    ar = AccessRequest.objects.get(pk=resp.json()['id'])
    assert ar.phone == '09121112233'


@pytest.mark.django_db
def test_organization_request_requires_org_name():
    client = APIClient()
    resp = client.post(URL, {
        'kind': 'organization',
        'full_name': 'مدیر مدرسه',
        'phone': '09120000001',
    }, format='json')
    assert resp.status_code == 400
    assert 'org_name' in resp.json()['errors']


@pytest.mark.django_db
def test_organization_request_ok():
    client = APIClient()
    resp = client.post(URL, {
        'kind': 'organization',
        'full_name': 'مدیر مدرسه',
        'phone': '09120000001',
        'org_name': 'دبیرستان البرز',
        'city': 'تهران',
        'expected_students': 300,
    }, format='json')
    assert resp.status_code == 201, resp.content
    ar = AccessRequest.objects.get(pk=resp.json()['id'])
    assert ar.kind == AccessRequest.Kind.ORGANIZATION
    assert ar.org_name == 'دبیرستان البرز'
    assert ar.expected_students == 300


@pytest.mark.django_db
def test_invalid_phone_rejected():
    client = APIClient()
    resp = client.post(URL, {
        'kind': 'teacher',
        'full_name': 'تست نام',
        'phone': '12345',
    }, format='json')
    assert resp.status_code == 400
    assert 'phone' in resp.json()['errors']


@pytest.mark.django_db
def test_duplicate_open_request_rejected():
    client = APIClient()
    payload = {'kind': 'teacher', 'full_name': 'علی احمدی', 'phone': '09120000000'}
    assert client.post(URL, payload, format='json').status_code == 201
    # Second open request with same phone+kind is blocked.
    resp = client.post(URL, payload, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_duplicate_allowed_after_rejection():
    client = APIClient()
    payload = {'kind': 'teacher', 'full_name': 'علی احمدی', 'phone': '09120000000'}
    first_id = client.post(URL, payload, format='json').json()['id']
    AccessRequest.objects.filter(pk=first_id).update(status=AccessRequest.Status.REJECTED)
    # After a decision, they may re-apply.
    assert client.post(URL, payload, format='json').status_code == 201
