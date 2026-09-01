"""Wave 7 (2026-08-31) — the official syllabus tree (درخت بودجه‌بندی).

Three surfaces, one deliverable:

* the ``seed_syllabus`` command — real konkur structure, idempotent by
  natural keys, and the family/grade/major matching rules (including the
  humanities «ریاضی و آمار» exclusion);
* the browse API — shaped tree for any authenticated role, 404 for a subject
  id that names no catalog row, 401 anonymous;
* ``TopicProgress`` linking — create with ``syllabusTopicId`` mirrors the
  node's title, the (engagement, node) pair is unique, patch links and
  unlinks, and the pre-tree free-text contract is unchanged.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import (
    AdvisoryEngagement,
    StudentSubject,
    Subject,
    SyllabusChapter,
    SyllabusTopic,
    TopicProgress,
)

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

TODAY = datetime.date(2026, 8, 31)

SYLLABUS_URL = '/api/advisory/subjects/{id}/syllabus/'
MY_TOPICS_URL = '/api/advisory/me/topics/'
MY_TOPIC_URL = '/api/advisory/me/topics/{id}/'

MSG_DUP_TOPIC = 'این مبحث از قبل در فهرست هست.'
MSG_BAD_TREE_TOPIC = 'مبحث انتخاب‌شده در درخت درس‌ها پیدا نشد.'
MSG_EMPTY_TOPIC = 'نام مبحث نمی‌تواند خالی باشد.'
MSG_NO_ADVISOR = 'ابتدا مشاور خود را تأیید کنید.'


def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', **kwargs):
    return baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)


def _engagement(advisor, student, *, status=Status.ACTIVE, **kwargs):
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': status,
    }
    if status == Status.ACTIVE:
        defaults['started_on'] = TODAY - datetime.timedelta(days=10)
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _subject(name, *, grade='12', major=None):
    return Subject.objects.create(name=name, grade=grade, major=major)


def _selection(engagement, subject):
    return StudentSubject.objects.create(
        engagement=engagement, subject=subject, is_active=True,
    )


def _node(subject, title='توابع', *, chapter_title='حسابان', order=1, weight=4):
    chapter = SyllabusChapter.objects.create(
        subject=subject, title=chapter_title, order=order,
    )
    return SyllabusTopic.objects.create(
        chapter=chapter, title=title, order=order, konkur_weight=weight,
    )


def _selected_row(engagement, subject):
    return StudentSubject.objects.get(engagement=engagement, subject=subject)


# ── seed command ──────────────────────────────────────────────────────────────

def test_seed_creates_real_konkur_tree():
    math = _subject('ریاضی', major='math')
    call_command('seed_syllabus')

    chapters = list(SyllabusChapter.objects.filter(subject=math).order_by('order'))
    assert [c.title for c in chapters] == [
        'حسابان', 'جبر و احتمال', 'هندسه', 'ریاضیات گسسته',
    ]
    functions = chapters[0].syllabus_topics.order_by('order').first()
    assert functions.title == 'توابع'
    assert functions.konkur_weight == 4


def _seed_counts(subject):
    return (
        SyllabusChapter.objects.filter(subject=subject).count(),
        SyllabusTopic.objects.filter(chapter__subject=subject).count(),
    )


def test_seed_is_idempotent_across_reruns():
    math_row = _subject('ریاضی ۱', grade='10', major=None)
    physics_row = _subject('فیزیک ۲', grade='11', major=None)
    chemistry_row = _subject('شیمی ۳', grade='12', major=None)
    biology_row = _subject('زیست‌شناسی ۱', grade='10', major='science')
    rows = (math_row, physics_row, chemistry_row, biology_row)

    call_command('seed_syllabus')
    first = {row.pk: _seed_counts(row) for row in rows}
    assert first == {
        math_row.pk: (4, 13),
        physics_row.pk: (8, 24),
        chemistry_row.pk: (8, 23),
        biology_row.pk: (7, 27),
    }

    call_command('seed_syllabus')
    second = {row.pk: _seed_counts(row) for row in rows}
    assert second == first


def test_seed_matching_rules_exclude_humanities_track_and_lower_grades():
    humanities_math = _subject('ریاضی و آمار ۱', grade='10', major=None)
    middle_school = _subject('فیزیک', grade='09', major=None)
    gradeless = Subject.objects.create(name='فیزیک', grade=None, major=None)

    call_command('seed_syllabus')

    for row in (humanities_math, middle_school, gradeless):
        assert not SyllabusChapter.objects.filter(subject=row).exists()


def test_seed_matches_the_math_family_by_major():
    # The merged ریاضی tree rides every math-major course row, not just a
    # subject literally named «ریاضی» — konkur coverage is per family.
    hesaban = _subject('حسابان ۱', grade='11', major='math')
    geometry = _subject('هندسه ۲', grade='11', major='math')
    humanities_econ = _subject('اقتصاد', grade='11', major='humanities')

    call_command('seed_syllabus')

    assert SyllabusChapter.objects.filter(subject=hesaban).count() == 4
    assert SyllabusChapter.objects.filter(subject=geometry).count() == 4
    assert not SyllabusChapter.objects.filter(subject=humanities_econ).exists()


# ── browse API ────────────────────────────────────────────────────────────────

def test_syllabus_browse_returns_shaped_tree():
    math = _subject('ریاضی', major='math')
    SyllabusChapter.objects.create(subject=math, title='هندسه', order=1)
    chapter = SyllabusChapter.objects.create(subject=math, title='حسابان', order=2)
    topic = SyllabusTopic.objects.create(
        chapter=chapter, title='توابع', order=1, konkur_weight=4,
    )
    SyllabusTopic.objects.create(
        chapter=chapter, title='حد و پیوستگی', order=2, konkur_weight=2,
    )

    resp = _auth(_student()).get(SYLLABUS_URL.format(id=math.id))

    assert resp.status_code == 200
    assert resp.data['subject'] == {'id': math.id, 'name': 'ریاضی'}
    # Chapters ordered by `order` (هندسه before حسابان), topics nested and ordered.
    assert [c['title'] for c in resp.data['chapters']] == ['هندسه', 'حسابان']
    assert resp.data['chapters'][1]['topics'] == [
        {'id': topic.id, 'title': 'توابع', 'order': 1, 'konkurWeight': 4},
        {'id': topic.id + 1, 'title': 'حد و پیوستگی', 'order': 2, 'konkurWeight': 2},
    ]


def test_syllabus_browse_access_matrix():
    physics = _subject('فیزیک ۱', grade='10', major=None)
    url = SYLLABUS_URL.format(id=physics.id)
    student = _student()

    assert APIClient().get(url).status_code == 401
    # Both sides of the pair browse the same reference tree.
    assert _auth(_advisor()).get(url).status_code == 200
    assert _auth(student).get(url).status_code == 200
    missing = SYLLABUS_URL.format(id=physics.id + 999)
    assert _auth(student).get(missing).status_code == 404


def test_syllabus_browse_unseeded_subject_is_empty_not_error():
    math = _subject('ریاضی', major='math')
    resp = _auth(_student()).get(SYLLABUS_URL.format(id=math.id))
    assert resp.status_code == 200
    assert resp.data == {'subject': {'id': math.id, 'name': 'ریاضی'}, 'chapters': []}


# ── TopicProgress linking ─────────────────────────────────────────────────────

def test_topic_create_with_syllabus_topic_mirrors_title():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی', major='math')
    _selection(engagement, math)
    node = _node(math)

    resp = _auth(student).post(
        MY_TOPICS_URL,
        {'subjectId': math.id, 'syllabusTopicId': node.id},
        format='json',
    )

    assert resp.status_code == 201
    assert resp.data['topic'] == 'توابع'
    assert resp.data['syllabusTopicId'] == node.id
    assert resp.data['syllabusTopicTitle'] == 'توابع'

    row = TopicProgress.objects.get(pk=resp.data['id'])
    assert row.syllabus_topic == node
    assert row.topic == 'توابع'


def test_topic_link_duplicate_rejected_across_subject_rows():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی', major='math')
    physics = _subject('فیزیک', major='science')
    _selection(engagement, math)
    _selection(engagement, physics)
    node = _node(math)

    first = _auth(student).post(
        MY_TOPICS_URL,
        {'subjectId': math.id, 'syllabusTopicId': node.id},
        format='json',
    )
    assert first.status_code == 201

    # Same student, same tree node — under a *different* subject row, so the
    # free-text uniqueness would not catch it. The (engagement, node) rule does.
    second = _auth(student).post(
        MY_TOPICS_URL,
        {'subjectId': physics.id, 'syllabusTopicId': node.id},
        format='json',
    )
    assert second.status_code == 400
    assert second.data['detail'] == MSG_DUP_TOPIC


def test_topic_link_unknown_node_rejected():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی', major='math')
    _selection(engagement, math)

    resp = _auth(student).post(
        MY_TOPICS_URL,
        {'subjectId': math.id, 'syllabusTopicId': 99999},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.data['detail'] == MSG_BAD_TREE_TOPIC


def test_topic_patch_links_and_unlinks():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی', major='math')
    _selection(engagement, math)
    node = _node(math, 'مشتق')

    row = TopicProgress.objects.create(
        engagement=engagement,
        student_subject=_selected_row(engagement, math),
        topic='یادداشت آزاد',
    )

    linked = _auth(student).patch(
        MY_TOPIC_URL.format(id=row.pk),
        {'syllabusTopicId': node.id},
        format='json',
    )
    assert linked.status_code == 200
    assert linked.data['syllabusTopicId'] == node.id
    assert linked.data['topic'] == 'مشتق'  # re-mirrored from the tree

    unlinked = _auth(student).patch(
        MY_TOPIC_URL.format(id=row.pk),
        {'syllabusTopicId': None},
        format='json',
    )
    assert unlinked.status_code == 200
    assert unlinked.data['syllabusTopicId'] is None
    assert unlinked.data['syllabusTopicTitle'] is None
    # Unlink keeps the last written title — it does not blank the row.
    assert unlinked.data['topic'] == 'مشتق'


def test_topic_patch_link_duplicate_rejected():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی', major='math')
    _selection(engagement, math)
    node = _node(math)

    TopicProgress.objects.create(
        engagement=engagement,
        student_subject=_selected_row(engagement, math),
        topic='توابع', syllabus_topic=node,
    )
    other = TopicProgress.objects.create(
        engagement=engagement,
        student_subject=_selected_row(engagement, math),
        topic='مبحث دیگر',
    )

    resp = _auth(student).patch(
        MY_TOPIC_URL.format(id=other.pk),
        {'syllabusTopicId': node.id},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.data['detail'] == MSG_DUP_TOPIC


def test_topic_free_text_contract_unchanged():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی', major='math')
    _selection(engagement, math)

    created = _auth(student).post(
        MY_TOPICS_URL, {'subjectId': math.id, 'topic': 'قانون بقای بار'}, format='json',
    )
    assert created.status_code == 201
    assert created.data['topic'] == 'قانون بقای بار'
    assert created.data['syllabusTopicId'] is None
    assert created.data['syllabusTopicTitle'] is None

    # No free text and no link is still the empty-topic 400 it always was.
    empty = _auth(student).post(
        MY_TOPICS_URL, {'subjectId': math.id}, format='json',
    )
    assert empty.status_code == 400
    assert empty.data['detail'] == MSG_EMPTY_TOPIC

    # The list carries the new nulls without touching the old keys.
    listed = _auth(student).get(MY_TOPICS_URL)
    assert listed.status_code == 200
    assert listed.data['topics'][0]['syllabusTopicId'] is None
    assert listed.data['topics'][0]['syllabusTopicTitle'] is None


def test_topic_link_writes_still_require_an_active_advisor():
    student = _student()
    math = _subject('ریاضی', major='math')

    resp = _auth(student).post(
        MY_TOPICS_URL, {'subjectId': math.id, 'topic': 'X'}, format='json',
    )
    assert resp.status_code == 409
    assert resp.data['detail'] == MSG_NO_ADVISOR
