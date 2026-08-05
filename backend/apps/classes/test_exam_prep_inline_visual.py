import base64
import io
import json

import pytest
from model_bakery import baker
from PIL import Image
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession, ClassInvitation


pytestmark = pytest.mark.django_db


def _image_data_url():
    image = Image.new('RGB', (24, 24), 'white')
    output = io.BytesIO()
    image.save(output, format='JPEG')
    image.close()
    return 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def _session(*, published=True, role='question'):
    teacher = baker.make('accounts.User', role='TEACHER')
    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='آزمون',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        is_published=published,
        exam_prep_json=json.dumps(
            {
                'exam_prep': {
                    'title': 'آزمون',
                    'questions': [
                        {
                            'question_id': 'default-q-1',
                            'question_text_markdown': 'سؤال',
                            'options': [],
                            'visuals': [
                                {
                                    'id': 'inline-default-q-1',
                                    'role': role,
                                    'dataUrl': _image_data_url(),
                                }
                            ],
                        }
                    ],
                }
            },
            ensure_ascii=False,
        ),
    )
    return session, teacher


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _url(session):
    return (
        f'/api/classes/exam-prep-sessions/{session.id}/visuals/'
        'inline-default-q-1/content/'
    )


def test_teacher_can_read_inline_verified_crop():
    session, teacher = _session(published=False)

    response = _client(teacher).get(_url(session))

    assert response.status_code == 200
    assert response['Content-Type'] == 'image/jpeg'
    assert response['Cache-Control'] == 'private, max-age=3600'
    assert response.content


def test_invited_student_can_read_published_question_crop():
    session, _teacher = _session(published=True)
    student = baker.make('accounts.User', role='STUDENT', phone='09120000001')
    ClassInvitation.objects.create(
        session=session,
        phone=student.phone,
        invite_code='inline-visual-student',
    )

    response = _client(student).get(_url(session))

    assert response.status_code == 200
    assert response['Content-Type'] == 'image/jpeg'


def test_unrelated_student_cannot_read_crop():
    session, _teacher = _session(published=True)
    student = baker.make('accounts.User', role='STUDENT', phone='09120000002')

    response = _client(student).get(_url(session))

    assert response.status_code == 404


def test_solution_crop_is_hidden_from_student():
    session, _teacher = _session(published=True, role='solution')
    student = baker.make('accounts.User', role='STUDENT', phone='09120000003')
    ClassInvitation.objects.create(
        session=session,
        phone=student.phone,
        invite_code='inline-solution-student',
    )

    response = _client(student).get(_url(session))

    assert response.status_code == 404
