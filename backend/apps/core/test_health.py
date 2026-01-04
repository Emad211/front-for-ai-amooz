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
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'healthy'
        assert response.data['database'] == 'connected'

    def test_health_check_no_auth_required(self):
        """Verify health check is public."""
        client = APIClient()
        url = reverse('health_check')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
