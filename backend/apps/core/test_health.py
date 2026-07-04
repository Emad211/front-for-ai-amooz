import json

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

@pytest.mark.django_db
class TestHealthCheck:
    def test_health_check_success(self):
        client = APIClient()
        url = reverse('health_check')
        response = client.get(url)

        # /api/health/ is served by HealthCheckMiddleware (before ALLOWED_HOSTS),
        # which returns a plain JSON HttpResponse — NOT a DRF Response — so read
        # the body via response.content, not response.data.
        assert response.status_code == status.HTTP_200_OK
        payload = json.loads(response.content)
        assert payload['status'] == 'healthy'
        assert payload['database'] == 'connected'

    def test_health_check_no_auth_required(self):
        """Verify health check is public."""
        client = APIClient()
        url = reverse('health_check')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
