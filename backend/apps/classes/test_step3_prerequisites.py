import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import (
    ClassCreationSession,
    ClassPrerequisite,
    ClassLearningObjective,
    ClassSection,
    ClassUnit,
)


User = get_user_model()


@pytest.mark.django_db
class TestClassCreationStep3AndStep4Prerequisites:
    @pytest.fixture(autouse=True)
    def _disable_async_pipeline(self, settings):
        settings.CLASS_PIPELINE_ASYNC = False

    def _auth_client(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return client

    def test_step3_requires_transcript(self):
        teacher = User.objects.create_user(username='t_pr_1', password='pass', role=User.Role.TEACHER)
        client = self._auth_client(teacher)

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.STRUCTURED,
            transcript_markdown='',
            structure_json='{}',
        )

        res = client.post('/api/classes/creation-sessions/step-3/', {'session_id': session.id}, format='json')
        assert res.status_code == 400

    def test_step4_requires_prerequisites_first(self):
        teacher = User.objects.create_user(username='t_pr_2', password='pass', role=User.Role.TEACHER)
        client = self._auth_client(teacher)

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.PREREQ_EXTRACTED,
            transcript_markdown='## transcript\nhello',
            structure_json='{}',
        )

        res = client.post('/api/classes/creation-sessions/step-4/', {'session_id': session.id}, format='json')
        assert res.status_code == 400

    def test_step3_creates_prerequisites_in_db(self, monkeypatch):
        teacher = User.objects.create_user(username='t_pr_3', password='pass', role=User.Role.TEACHER)
        client = self._auth_client(teacher)

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.STRUCTURED,
            transcript_markdown='## transcript\nhello',
            structure_json='{}',
        )

        prereqs = [f'P{i}' for i in range(1, 11)]

        def _fake_extract_prerequisites(*, transcript_markdown: str):
            assert transcript_markdown.strip()
            return ({'prerequisites': prereqs}, 'gemini', 'models/gemini-2.5-flash')

        monkeypatch.setattr('apps.classes.views.extract_prerequisites', _fake_extract_prerequisites)

        res = client.post('/api/classes/creation-sessions/step-3/', {'session_id': session.id}, format='json')
        assert res.status_code == 200

        session.refresh_from_db()
        assert session.status == ClassCreationSession.Status.PREREQ_EXTRACTED
        assert ClassPrerequisite.objects.filter(session=session).count() == 10
        assert list(ClassPrerequisite.objects.filter(session=session).order_by('order').values_list('name', flat=True)) == prereqs

    def test_step4_generates_teaching_for_each_prerequisite(self, monkeypatch):
        teacher = User.objects.create_user(username='t_pr_4', password='pass', role=User.Role.TEACHER)
        client = self._auth_client(teacher)

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.PREREQ_EXTRACTED,
            transcript_markdown='## transcript\nhello',
        )

        ClassPrerequisite.objects.create(session=session, order=1, name='P1')
        ClassPrerequisite.objects.create(session=session, order=2, name='P2')

        def _fake_generate_prerequisite_teaching(*, prerequisite_name: str):
            return (f'# {prerequisite_name}\ntext', 'gemini', 'models/gemini-2.5-flash')

        monkeypatch.setattr('apps.classes.views.generate_prerequisite_teaching', _fake_generate_prerequisite_teaching)

        res = client.post('/api/classes/creation-sessions/step-4/', {'session_id': session.id}, format='json')
        assert res.status_code == 200

        session.refresh_from_db()
        assert session.status == ClassCreationSession.Status.PREREQ_TAUGHT

        rows = list(ClassPrerequisite.objects.filter(session=session).order_by('order'))
        assert rows[0].teaching_text.startswith('# P1')
        assert rows[1].teaching_text.startswith('# P2')


@pytest.mark.django_db
class TestNormalizedStructureSync:
    def test_patch_structure_json_syncs_to_tables(self):
        teacher = User.objects.create_user(username='t_sync_1', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(teacher).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.STRUCTURED,
            transcript_markdown='## transcript\nhello',
        )

        payload = {
            'root_object': {
                'what_you_will_learn': ['o1', 'o2'],
            },
            'outline': [
                {
                    'id': 'sec-1',
                    'title': 'S1',
                    'units': [
                        {
                            'id': 'u1',
                            'title': 'U1',
                            'merrill_type': 'activation',
                            'content_markdown': 'c1',
                            'teaching_markdown': 't1',
                        }
                    ],
                }
            ],
        }

        res = client.patch(
            f'/api/classes/creation-sessions/{session.id}/',
            {'structure_json': payload},
            format='json',
        )
        assert res.status_code == 200

        assert ClassLearningObjective.objects.filter(session=session).count() == 2
        assert ClassSection.objects.filter(session=session).count() == 1
        assert ClassUnit.objects.filter(session=session).count() == 1

        unit = ClassUnit.objects.get(session=session)
        assert unit.title == 'U1'
        assert unit.content_markdown == 'c1'
        # teaching_markdown is ignored/removed; only content_markdown is persisted
        assert unit.content_markdown == 'c1'
