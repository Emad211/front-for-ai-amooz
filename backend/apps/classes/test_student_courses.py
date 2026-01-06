import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, ClassSection, ClassUnit, ClassLearningObjective, ClassPrerequisite


@pytest.mark.django_db
def test_student_courses_list_requires_student_role():
    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')

    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        is_published=True,
        title='T',
        description='D',
    )
    baker.make(ClassInvitation, session=session, phone=student.phone, invite_code='INV-ABC')

    client = APIClient()
    client.force_authenticate(user=teacher)

    resp = client.get('/api/classes/student/courses/')
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_student_courses_list_returns_published_invited_sessions():
    teacher = baker.make(User, role=User.Role.TEACHER, username='t1')
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')
    other_student = baker.make(User, role=User.Role.STUDENT, phone='09921111111')

    visible = baker.make(
        ClassCreationSession,
        teacher=teacher,
        is_published=True,
        title='Visible',
        description='Desc',
    )
    hidden = baker.make(
        ClassCreationSession,
        teacher=teacher,
        is_published=True,
        title='Hidden',
        description='Desc',
    )
    draft = baker.make(
        ClassCreationSession,
        teacher=teacher,
        is_published=False,
        title='Draft',
        description='Desc',
    )

    baker.make(ClassInvitation, session=visible, phone=student.phone, invite_code='INV-V')
    baker.make(ClassInvitation, session=hidden, phone=other_student.phone, invite_code='INV-H')
    baker.make(ClassInvitation, session=draft, phone=student.phone, invite_code='INV-D')

    client = APIClient()
    client.force_authenticate(user=student)

    resp = client.get('/api/classes/student/courses/')
    assert resp.status_code == 200
    data = resp.json()

    ids = {int(item['id']) for item in data}
    assert visible.id in ids
    assert hidden.id not in ids
    assert draft.id not in ids


@pytest.mark.django_db
def test_student_course_content_returns_sections_and_units():
    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')

    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        is_published=True,
        title='Course',
        description='D',
    )
    baker.make(ClassInvitation, session=session, phone=student.phone, invite_code='INV-1')

    section = baker.make(ClassSection, session=session, external_id='sec-1', order=1, title='S1')
    unit1 = baker.make(ClassUnit, session=session, section=section, external_id='u1', order=1, title='U1', content_markdown='**Hello**')
    unit2 = baker.make(ClassUnit, session=session, section=section, external_id='u2', order=2, title='U2', content_markdown='World')

    baker.make(ClassLearningObjective, session=session, order=1, text='هدف ۱: $a^2+b^2=c^2$')
    baker.make(ClassLearningObjective, session=session, order=2, text='هدف ۲')
    baker.make(ClassPrerequisite, session=session, order=1, name='پیش‌نیاز ۱', teaching_text='متن آموزش ۱')
    baker.make(ClassPrerequisite, session=session, order=2, name='پیش‌نیاز ۲', teaching_text='')

    client = APIClient()
    client.force_authenticate(user=student)

    resp = client.get(f'/api/classes/student/courses/{session.id}/content/')
    assert resp.status_code == 200
    payload = resp.json()

    assert payload['id'] == str(session.id)
    assert payload['title'] == session.title
    assert payload['chapters'][0]['title'] == section.title
    lessons = payload['chapters'][0]['lessons']
    assert lessons[0]['title'] == unit1.title
    assert lessons[0]['content'] == unit1.content_markdown
    assert lessons[1]['title'] == unit2.title
    assert lessons[1]['content'] == unit2.content_markdown

    assert payload['learningObjectives'][0].startswith('هدف ۱')
    assert len(payload['prerequisites']) == 2
    assert payload['prerequisites'][0]['name'].startswith('پیش')


@pytest.mark.django_db
def test_student_course_content_denies_uninvited():
    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')

    session = baker.make(ClassCreationSession, teacher=teacher, is_published=True)

    client = APIClient()
    client.force_authenticate(user=student)

    resp = client.get(f'/api/classes/student/courses/{session.id}/content/')
    assert resp.status_code == 404
