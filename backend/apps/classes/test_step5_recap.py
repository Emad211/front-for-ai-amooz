import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession


User = get_user_model()


@pytest.mark.django_db
class TestClassCreationStep5Recap:
    @pytest.fixture(autouse=True)
    def _disable_async_pipeline(self, settings):
        settings.CLASS_PIPELINE_ASYNC = False

    def _auth_client(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return client

    def test_step5_requires_structure(self):
        teacher = User.objects.create_user(username='t_r_1', password='pass', role=User.Role.TEACHER)
        client = self._auth_client(teacher)

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.TRANSCRIBED,
            transcript_markdown='## transcript\nhello',
            structure_json='',
        )

        res = client.post('/api/classes/creation-sessions/step-5/', {'session_id': session.id}, format='json')
        assert res.status_code == 400

    def test_step5_generates_recap_markdown(self, monkeypatch):
        teacher = User.objects.create_user(username='t_r_2', password='pass', role=User.Role.TEACHER)
        client = self._auth_client(teacher)

        structure_obj = {
            'root_object': {'title': 'درس'},
            'outline': [
                {
                    'id': 'sec-1',
                    'title': 'فصل ۱',
                    'units': [
                        {'id': 'u-1', 'title': 'درس ۱', 'content_markdown': 'متن'}
                    ],
                }
            ],
        }

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.STRUCTURED,
            transcript_markdown='## transcript\nhello',
            structure_json=json.dumps(structure_obj, ensure_ascii=False),
        )

        def _fake_generate_recap_from_structure(*, structure_json: str):
            assert structure_json.strip()
            return (
                {
                    'recap': {
                        'title': 'خلاصه',
                        'overview_markdown': 'این یک مرور کوتاه است.',
                        'key_notes_markdown': '- نکته ۱',
                        'by_unit': [
                            {
                                'section_id': 'sec-1',
                                'section_title': 'فصل ۱',
                                'unit_id': 'u-1',
                                'unit_title': 'درس ۱',
                                'unit_recap_markdown': 'مرور واحد',
                                'unit_key_points_markdown': '- نکته A',
                            }
                        ],
                        'common_mistakes_markdown': '- اشتباه',
                        'quick_self_check_markdown': '- سوال؟',
                        'formula_sheet_markdown': '',
                    }
                },
                'gemini',
                'models/gemini-2.5-flash',
            )

        monkeypatch.setattr('apps.classes.views.generate_recap_from_structure', _fake_generate_recap_from_structure)

        res = client.post('/api/classes/creation-sessions/step-5/', {'session_id': session.id}, format='json')
        assert res.status_code == 200

        session.refresh_from_db()
        assert session.status == ClassCreationSession.Status.RECAPPED
        assert session.recap_markdown.strip().startswith('#')


@pytest.mark.django_db
class TestRunFullPipelineFlag:
    def _auth_client(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return client

    def test_step1_run_full_pipeline_sets_async_status(self, settings, monkeypatch):
        """We don't assert final status here because background execution depends on threading.

        We only assert the endpoint accepts the flag and returns 202.
        """
        settings.CLASS_PIPELINE_ASYNC = True

        teacher = User.objects.create_user(username='t_r_3', password='pass', role=User.Role.TEACHER)
        client = self._auth_client(teacher)

        called = {'ok': False}

        def _fake_run_in_background(fn, name: str):
            called['ok'] = True

        monkeypatch.setattr('apps.classes.views.run_in_background', _fake_run_in_background)

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        res = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 't', 'description': '', 'file': upload, 'run_full_pipeline': True},
            format='multipart',
        )
        assert res.status_code == 202
        assert called['ok'] is True
