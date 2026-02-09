"""Mediana SMS service resilience tests.

Verifies retry logic, error handling, and edge cases in the SMS service.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from unittest.mock import patch

import pytest

from apps.classes.services.mediana_sms import _post_json, send_publish_sms_for_session


class TestPostJsonRetry:
    """Test _post_json retry logic on transient errors."""

    def test_success_on_first_try(self):
        fake_response = json.dumps({'data': {'TotalSent': 1}}).encode()

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = mock_urlopen.return_value.__enter__.return_value
            mock_resp.read.return_value = fake_response

            result = _post_json(
                url='https://api.mediana.ir/sms/v1/send/array',
                api_key='test-key',
                payload={'Requests': []},
            )

        assert result['data']['TotalSent'] == 1
        assert mock_urlopen.call_count == 1

    def test_retry_on_500_then_success(self):
        """Should retry once on 5xx and succeed on second attempt."""
        fake_response = json.dumps({'data': {'TotalSent': 1}}).encode()

        call_count = {'n': 0}

        def side_effect(req, timeout=None):
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise urllib.error.HTTPError(
                    url='http://test', code=500, msg='Internal Server Error',
                    hdrs=None, fp=None,
                )
            mock = type('resp', (), {
                'read': lambda self: fake_response,
                '__enter__': lambda self: self,
                '__exit__': lambda self, *a: None,
            })()
            return mock

        with patch('urllib.request.urlopen', side_effect=side_effect):
            result = _post_json(
                url='https://api.mediana.ir/sms/v1/send/array',
                api_key='test-key',
                payload={'Requests': []},
                max_retries=2,
            )

        assert result['data']['TotalSent'] == 1
        assert call_count['n'] == 2

    def test_no_retry_on_4xx(self):
        """Should NOT retry on client errors (4xx)."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url='http://test', code=400, msg='Bad Request',
                hdrs=None, fp=None,
            )

            with pytest.raises(RuntimeError, match='HTTP 400'):
                _post_json(
                    url='https://api.mediana.ir/sms/v1/send/array',
                    api_key='test-key',
                    payload={},
                    max_retries=2,
                )

        # Only 1 attempt — no retry on 4xx.
        assert mock_urlopen.call_count == 1

    def test_raises_after_all_retries_exhausted(self):
        """Should raise RuntimeError after max_retries + 1 attempts."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url='http://test', code=503, msg='Service Unavailable',
                hdrs=None, fp=None,
            )

            with pytest.raises(RuntimeError, match='HTTP 503'):
                _post_json(
                    url='https://api.mediana.ir/sms/v1/send/array',
                    api_key='test-key',
                    payload={},
                    max_retries=2,
                )

        # 1 initial + 2 retries = 3 attempts.
        assert mock_urlopen.call_count == 3

    def test_retry_on_timeout(self):
        """Should retry on TimeoutError."""
        fake_response = json.dumps({'ok': True}).encode()
        call_count = {'n': 0}

        def side_effect(req, timeout=None):
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise TimeoutError('Connection timed out')
            mock = type('resp', (), {
                'read': lambda self: fake_response,
                '__enter__': lambda self: self,
                '__exit__': lambda self, *a: None,
            })()
            return mock

        with patch('urllib.request.urlopen', side_effect=side_effect):
            result = _post_json(
                url='https://api.mediana.ir/sms/v1/send/array',
                api_key='test-key',
                payload={},
                max_retries=1,
            )

        assert result == {'ok': True}
        assert call_count['n'] == 2


@pytest.mark.django_db
class TestSendPublishSmsForSession:
    """Integration test for send_publish_sms_for_session."""

    def test_skips_when_no_api_key(self, monkeypatch):
        from model_bakery import baker

        monkeypatch.delenv('MEDIANA_API_KEY', raising=False)
        session = baker.make('classes.ClassCreationSession')

        # Should not raise.
        send_publish_sms_for_session(session.id)

    def test_skips_when_session_not_found(self, monkeypatch):
        monkeypatch.setenv('MEDIANA_API_KEY', 'test-key')

        # Non-existent session.
        send_publish_sms_for_session(99999)

    def test_skips_when_no_invites(self, monkeypatch):
        from model_bakery import baker

        monkeypatch.setenv('MEDIANA_API_KEY', 'test-key')
        session = baker.make('classes.ClassCreationSession')

        # No invites — should not raise.
        send_publish_sms_for_session(session.id)

    def test_sends_sms_for_invites(self, monkeypatch):
        from model_bakery import baker

        monkeypatch.setenv('MEDIANA_API_KEY', 'test-key')
        session = baker.make('classes.ClassCreationSession', title='Test Class')
        baker.make(
            'classes.ClassInvitation',
            session=session,
            phone='09121111111',
            invite_code='ABC',
        )

        fake_result = {
            'meta': {'errorMessage': None},
            'data': {'TotalSent': 1, 'TotalRequested': 1},
        }
        monkeypatch.setattr(
            'apps.classes.services.mediana_sms.send_peer_to_peer_sms',
            lambda **kw: fake_result,
        )

        send_publish_sms_for_session(session.id)
