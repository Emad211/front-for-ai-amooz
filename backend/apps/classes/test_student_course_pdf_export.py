import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, ClassSection, ClassUnit


@pytest.mark.django_db
def test_student_course_pdf_export_requires_student_role(monkeypatch):
    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')

    session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='T')
    baker.make(ClassInvitation, session=session, phone=student.phone, invite_code='INV-1')

    client = APIClient()
    client.force_authenticate(user=teacher)

    resp = client.get(f'/api/classes/student/courses/{session.id}/export-pdf/')
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_student_course_pdf_export_returns_pdf(monkeypatch):
    # Avoid requiring WeasyPrint in unit tests by stubbing the generator.
    monkeypatch.setattr('apps.classes.views.generate_course_pdf', lambda **_kwargs: b'%PDF-FAKE')

    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')

    session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='Course', description='D')
    baker.make(ClassInvitation, session=session, phone=student.phone, invite_code='INV-1')

    section = baker.make(ClassSection, session=session, external_id='sec-1', order=1, title='S1')
    baker.make(ClassUnit, session=session, section=section, external_id='u1', order=1, title='U1', content_markdown='**Hello** $a^2$')

    client = APIClient()
    client.force_authenticate(user=student)

    resp = client.get(f'/api/classes/student/courses/{session.id}/export-pdf/')
    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/pdf'
    assert resp.content.startswith(b'%PDF')
