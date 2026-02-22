"""Tests for token tracking system: pricing, exchange rate, and LLM usage views."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.commons.models import LLMUsageLog, estimate_cost, MODEL_PRICING
from apps.commons.exchange_rate import (
    fetch_usdt_toman_rate,
    get_usdt_toman_rate,
    usd_to_toman,
    _parse_float,
)

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════
# estimate_cost — Pricing accuracy
# ═══════════════════════════════════════════════════════════════════════════


class TestEstimateCost:
    """Validate the estimate_cost function with Gemini 2.5 Flash pricing."""

    def test_basic_text_input_output(self):
        """Text input at $0.30/1M + output at $2.50/1M."""
        cost = estimate_cost(
            'models/gemini-2.5-flash',
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        # $0.30 input + $2.50 output = $2.80
        assert abs(cost - 2.80) < 0.0001

    def test_audio_input_rate(self):
        """Audio input at $1.00/1M tokens."""
        cost = estimate_cost(
            'models/gemini-2.5-flash',
            input_tokens=1_000_000,
            output_tokens=0,
            audio_input_tokens=1_000_000,
        )
        # All 1M input tokens are audio: $1.00
        assert abs(cost - 1.00) < 0.0001

    def test_mixed_text_and_audio_input(self):
        """Mix of 500K text + 500K audio input."""
        cost = estimate_cost(
            'models/gemini-2.5-flash',
            input_tokens=1_000_000,  # Total input
            output_tokens=0,
            audio_input_tokens=500_000,
        )
        # text: 500K * $0.30/1M = $0.15
        # audio: 500K * $1.00/1M = $0.50
        expected = 0.15 + 0.50
        assert abs(cost - expected) < 0.0001

    def test_cached_text_input(self):
        """Cached text input at $0.03/1M tokens."""
        cost = estimate_cost(
            'models/gemini-2.5-flash',
            input_tokens=1_000_000,
            output_tokens=0,
            cached_input_tokens=1_000_000,
        )
        # All cached text: $0.03
        assert abs(cost - 0.03) < 0.0001

    def test_output_includes_thinking(self):
        """Output tokens (including thinking) at $2.50/1M."""
        cost = estimate_cost(
            'models/gemini-2.5-flash',
            input_tokens=0,
            output_tokens=2_000_000,
        )
        # $2.50 * 2 = $5.00
        assert abs(cost - 5.00) < 0.0001

    def test_unknown_model_uses_default(self):
        """Unknown model falls back to DEFAULT_PRICING."""
        cost = estimate_cost(
            'unknown-model-v9',
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        # Default: $0.30 input + $2.50 output = $2.80
        assert abs(cost - 2.80) < 0.0001

    def test_zero_tokens(self):
        """Zero tokens should yield zero cost."""
        cost = estimate_cost('models/gemini-2.5-flash', input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_small_call_precision(self):
        """Small calls should compute with enough decimal precision."""
        cost = estimate_cost(
            'models/gemini-2.5-flash',
            input_tokens=100,
            output_tokens=50,
        )
        # 100 * 0.30/1M + 50 * 2.50/1M = 0.00003 + 0.000125 = 0.000155
        assert cost > 0
        assert abs(cost - 0.000155) < 0.00001

    def test_gemini_2_0_flash_pricing(self):
        """Gemini 2.0 Flash has different pricing."""
        cost = estimate_cost(
            'gemini-2.0-flash',
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        # $0.10 + $0.40 = $0.50
        assert abs(cost - 0.50) < 0.0001


# ═══════════════════════════════════════════════════════════════════════════
# Exchange rate utilities
# ═══════════════════════════════════════════════════════════════════════════


class TestParseFloat:
    def test_int(self):
        assert _parse_float(42) == 42.0

    def test_float(self):
        assert _parse_float(3.14) == 3.14

    def test_string(self):
        assert _parse_float('165450') == 165450.0

    def test_string_with_commas(self):
        assert _parse_float('165,450') == 165450.0

    def test_none(self):
        assert _parse_float(None) is None

    def test_invalid(self):
        assert _parse_float('abc') is None


class TestFetchUsdtTomanRate:
    @patch('apps.commons.exchange_rate.urllib.request.urlopen')
    def test_tetherland_response_parsing(self, mock_urlopen):
        """Parse Tetherland API response correctly."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"data":{"currencies":{"USDT":{"price":"165450"}}}}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        rate, err = fetch_usdt_toman_rate()
        assert rate == 165450.0
        assert err is None

    @patch('apps.commons.exchange_rate.urllib.request.urlopen')
    def test_handles_network_error(self, mock_urlopen):
        """Return None on network failure."""
        mock_urlopen.side_effect = Exception('Connection refused')

        rate, err = fetch_usdt_toman_rate()
        assert rate is None
        assert 'Connection refused' in err


class TestUsdToToman:
    @patch('apps.commons.exchange_rate.get_usdt_toman_rate')
    def test_conversion(self, mock_rate):
        mock_rate.return_value = (165450.0, None)

        toman, err = usd_to_toman(1.0)
        assert toman == 165450.0
        assert err is None

    @patch('apps.commons.exchange_rate.get_usdt_toman_rate')
    def test_small_amount(self, mock_rate):
        mock_rate.return_value = (165450.0, None)

        toman, err = usd_to_toman(0.01)
        # 0.01 * 165450 = 1654.5 → round(1654.5, 0) = 1654.0
        assert toman == round(0.01 * 165450, 0)
        assert err is None

    @patch('apps.commons.exchange_rate.get_usdt_toman_rate')
    def test_rate_unavailable(self, mock_rate):
        mock_rate.return_value = (None, 'API error')

        toman, err = usd_to_toman(1.0)
        assert toman is None
        assert err == 'API error'


# ═══════════════════════════════════════════════════════════════════════════
# LLM Usage API views
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def admin_client():
    """Authenticated admin APIClient."""
    admin = User.objects.create_superuser(
        username='tokenadmin',
        email='tokenadmin@test.com',
        password='testpassword123!',
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def sample_logs():
    """Create several LLMUsageLog entries."""
    user = baker.make('accounts.User', role='STUDENT')
    logs = [
        LLMUsageLog.objects.create(
            user=user,
            feature='chat_course',
            provider='google',
            model_name='models/gemini-2.5-flash',
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            audio_input_tokens=200,
            cached_input_tokens=100,
            thinking_tokens=50,
            estimated_cost_usd=Decimal('0.001550'),
            duration_ms=350,
            success=True,
        ),
        LLMUsageLog.objects.create(
            user=user,
            feature='quiz_generation',
            provider='google',
            model_name='models/gemini-2.5-flash',
            input_tokens=5000,
            output_tokens=2000,
            total_tokens=7000,
            audio_input_tokens=0,
            cached_input_tokens=0,
            thinking_tokens=400,
            estimated_cost_usd=Decimal('0.006500'),
            duration_ms=800,
            success=True,
        ),
        LLMUsageLog.objects.create(
            user=None,
            feature='other',
            provider='google',
            model_name='models/gemini-2.0-flash',
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=Decimal('0.000030'),
            duration_ms=100,
            success=False,
            error_message='Rate limited',
        ),
    ]
    return logs


@pytest.mark.django_db
class TestLLMUsageSummaryView:
    @patch('apps.commons.views.get_usdt_toman_rate')
    @patch('apps.commons.views.usd_to_toman')
    def test_summary_includes_toman_and_token_types(
        self, mock_to_toman, mock_rate, admin_client, sample_logs
    ):
        mock_rate.return_value = (165450.0, None)
        mock_to_toman.return_value = (1323.6, None)

        resp = admin_client.get('/api/admin/llm-usage/summary/')
        assert resp.status_code == 200

        data = resp.data
        assert data['total_requests'] == 3
        assert data['successful_requests'] == 2
        assert data['failed_requests'] == 1
        assert data['total_input_tokens'] == 6100
        assert data['total_output_tokens'] == 2550

        # Toman fields
        assert 'total_cost_toman' in data
        assert 'usdt_toman_rate' in data
        assert data['usdt_toman_rate'] == 165450.0

        # Token type aggregations
        assert data['total_audio_input_tokens'] == 200
        assert data['total_cached_input_tokens'] == 100
        assert data['total_thinking_tokens'] == 450

    def test_summary_requires_admin(self):
        client = APIClient()
        resp = client.get('/api/admin/llm-usage/summary/')
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestLLMUsageRecentLogsView:
    def test_recent_logs_include_token_types(self, admin_client, sample_logs):
        resp = admin_client.get('/api/admin/llm-usage/recent/?limit=10')
        assert resp.status_code == 200
        assert len(resp.data) == 3

        # Check first log has token type fields
        log = resp.data[0]  # Most recent (last created)
        assert 'audio_input_tokens' in log
        assert 'cached_input_tokens' in log
        assert 'thinking_tokens' in log


@pytest.mark.django_db
class TestLLMUsageByFeatureView:
    def test_by_feature_returns_data(self, admin_client, sample_logs):
        resp = admin_client.get('/api/admin/llm-usage/by-feature/')
        assert resp.status_code == 200
        assert len(resp.data) >= 2

        features = {r['feature'] for r in resp.data}
        assert 'chat_course' in features
        assert 'quiz_generation' in features


@pytest.mark.django_db
class TestExchangeRateView:
    @patch('apps.commons.views.get_usdt_toman_rate')
    def test_exchange_rate_endpoint(self, mock_rate, admin_client):
        mock_rate.return_value = (165450.0, None)

        resp = admin_client.get('/api/admin/exchange-rate/')
        assert resp.status_code == 200
        assert resp.data['usdt_toman_rate'] == 165450.0
        assert resp.data['error'] is None

    @patch('apps.commons.views.get_usdt_toman_rate')
    def test_exchange_rate_error(self, mock_rate, admin_client):
        mock_rate.return_value = (None, 'API down')

        resp = admin_client.get('/api/admin/exchange-rate/')
        assert resp.status_code == 200
        assert resp.data['usdt_toman_rate'] is None
        assert resp.data['error'] == 'API down'


# ═══════════════════════════════════════════════════════════════════════════
# LLMUsageLog model
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLLMUsageLogModel:
    def test_create_with_token_types(self):
        log = LLMUsageLog.objects.create(
            feature='chat_course',
            provider='google',
            model_name='models/gemini-2.5-flash',
            input_tokens=5000,
            output_tokens=2000,
            total_tokens=7000,
            audio_input_tokens=1000,
            cached_input_tokens=500,
            thinking_tokens=300,
            estimated_cost_usd=Decimal('0.01'),
        )
        log.refresh_from_db()
        assert log.audio_input_tokens == 1000
        assert log.cached_input_tokens == 500
        assert log.thinking_tokens == 300

    def test_default_token_type_values(self):
        log = LLMUsageLog.objects.create(
            feature='other',
            provider='google',
            model_name='gemini-2.0-flash',
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )
        log.refresh_from_db()
        assert log.audio_input_tokens == 0
        assert log.cached_input_tokens == 0
        assert log.thinking_tokens == 0

    def test_str_representation(self):
        user = baker.make('accounts.User', username='testuser')
        log = LLMUsageLog.objects.create(
            user=user,
            feature='chat_course',
            total_tokens=1500,
            estimated_cost_usd=Decimal('0.0015'),
        )
        s = str(log)
        assert 'testuser' in s
        assert '1500' in s
