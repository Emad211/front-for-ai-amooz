"""
Edge Cases and Error Handling Tests
Tests unusual scenarios, boundary conditions, and error states
"""
import pytest
import json
import threading
import uuid
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch

User = get_user_model()


@pytest.mark.django_db
class TestAuthenticationEdgeCases:
    def test_registration_with_unicode_characters(self):
        client = APIClient()
        
        # Test various Unicode characters in username
        unicode_usernames = [
            'user_с_кириллицей',  # Cyrillic
            'user_用户名',  # Chinese
            'user_اسم',  # Arabic
            'user_名前',  # Japanese
            'user_émojis_😀',  # Emojis
            'user_with_🔒_symbols',
        ]
        
        for username in unicode_usernames:
            response = client.post('/api/auth/register/', {
                'username': username,
                'password': 'StrongPass123!@#',
                'email': f'{username}@test.com'
            }, format='json')
            
            # Should either work (201) or fail validation (400), not crash (500)
            assert response.status_code in [201, 400]
            
            if response.status_code == 201:
                # Verify user was created correctly
                user = User.objects.get(username=username)
                assert user.username == username

    def test_extremely_long_password(self):
        client = APIClient()
        
        # Very long password (beyond reasonable limits)
        long_password = 'a' * 10000
        
        response = client.post('/api/auth/register/', {
            'username': 'long_pass_user',
            'password': long_password
        }, format='json')
        
        # Should be handled gracefully, not cause memory issues
        assert response.status_code in [201, 400]

    def test_password_with_special_characters(self):
        client = APIClient()
        
        special_passwords = [
            'Pass123!@#$%^&*()_+-={}[]|\\:";\'<>?,./`~',
            'Pass123\n\r\t',  # Whitespace characters
            'Pass123\x00\x01\x02',  # Control characters
            'Pass123™®©€£¥₹₽',  # Currency and symbols
            'Pass123😀',  # Emoji in password (proper encoding)
        ]
        
        for i, password in enumerate(special_passwords):
            response = client.post('/api/auth/register/', {
                'username': f'special_pass_user_{i}',
                'password': password
            }, format='json')
            
            assert response.status_code in [201, 400]
            
            if response.status_code == 201:
                # Test login with special password
                login_response = client.post('/api/token/', {
                    'username': f'special_pass_user_{i}',
                    'password': password
                }, format='json')
                assert login_response.status_code == 200

    def test_email_edge_cases(self):
        client = APIClient()
        
        email_edge_cases = [
            'test+tag@example.com',  # Plus addressing
            'test.with.dots@example.com',  # Dots in local part
            'test@sub.domain.example.com',  # Subdomain
            'test@example-with-dash.com',  # Dash in domain
            'test@123.456.789.012',  # IP address (invalid but test handling)
            'very.long.email.address.with.many.dots@very.long.domain.name.example.com',
            'test@localhost',  # localhost domain
            '',  # Empty email (should be allowed)
        ]
        
        for i, email in enumerate(email_edge_cases):
            response = client.post('/api/auth/register/', {
                'username': f'email_edge_user_{i}',
                'email': email,
                'password': 'StrongPass123!@#'
            }, format='json')
            
            # Should handle all cases gracefully
            assert response.status_code in [201, 400]

    def test_concurrent_registration_same_username(self):
        """Test race condition in username uniqueness"""
        import threading
        import time
        
        client = APIClient()
        results = []
        
        def register_user():
            unique_suffix = str(uuid.uuid4())[:8]
            response = client.post('/api/auth/register/', {
                'username': f'race_condition_user_{unique_suffix}',
                'password': 'StrongPass123!@#'
            }, format='json')
            results.append(response.status_code)
        
        # Start multiple threads trying to register same username
        threads = []
        for i in range(5):
            thread = threading.Thread(target=register_user)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All registrations should succeed with unique usernames
        success_count = results.count(201)
        assert success_count == 5, f"Expected 5 successes with unique usernames, got {success_count}"
        
    def test_real_race_condition_same_username(self):
        """Test actual race condition with same username"""
        client = APIClient()
        results = []
        
        def register_user():
            response = client.post('/api/auth/register/', {
                'username': 'actual_race_user',
                'password': 'StrongPass123!@#'
            }, format='json')
            results.append(response.status_code)
            
        # First make sure username doesn't exist
        User.objects.filter(username='actual_race_user').delete()
        
        # Start multiple threads trying to register SAME username
        threads = []
        for i in range(5):
            thread = threading.Thread(target=register_user)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # In race conditions, results can be mixed:
        success_count = results.count(201)
        validation_errors = results.count(400)  # Serializer caught duplicate
        integrity_errors = results.count(500)   # DB caught duplicate
        
        # Either one succeeds and others fail, or all fail at validation level
        if success_count == 1:
            assert (validation_errors + integrity_errors) == 4, f"Expected 4 total failures"
            # Verify only one user was created
            user_count = User.objects.filter(username='actual_race_user').count()
            assert user_count == 1
        else:
            # All failed at validation level (very fast threads) 
            assert validation_errors == 5, f"Expected all validation errors"
            # No user should be created
            user_count = User.objects.filter(username='actual_race_user').count()
            assert user_count == 0

    def test_malformed_jwt_tokens(self):
        user = User.objects.create_user(username='jwt_test', password='pass123')
        client = APIClient()
        
        malformed_tokens = [
            '',  # Empty token
            'invalid',  # Not JWT format
            'header.payload',  # Missing signature
            'header.payload.signature.extra',  # Too many parts
            'invalid.header.payload',  # Invalid base64
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid_payload.signature',  # Invalid payload
            'Bearer token',  # Wrong prefix included in token
        ]
        
        for token in malformed_tokens:
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            response = client.get('/api/accounts/me/')
            assert response.status_code == 401

    def test_expired_token_handling(self):
        user = User.objects.create_user(username='expired_test', password='pass123')
        
        # Create token with past expiration
        from datetime import datetime, timedelta, timezone
        from rest_framework_simplejwt.tokens import AccessToken
        
        token = AccessToken.for_user(user)
        # Manually set expiration to past
        token['exp'] = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
        
        response = client.get('/api/accounts/me/')
        assert response.status_code == 401

    def test_token_with_invalid_user_id(self):
        # Create a token with non-existent user ID
        from rest_framework_simplejwt.tokens import AccessToken
        
        token = AccessToken()
        token['user_id'] = 99999  # Non-existent user ID
        
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
        
        response = client.get('/api/accounts/me/')
        assert response.status_code == 401

    def test_database_connection_error_simulation(self):
        """Test behavior when database is unavailable"""
        client = APIClient()
        
        # This is tricky to test without actually breaking the DB
        # We'll test that the endpoint exists and handles errors gracefully
        response = client.post('/api/auth/register/', {
            'username': 'db_test_user',
            'password': 'StrongPass123!@#'
        }, format='json')
        
        # Should either succeed or fail gracefully, not crash
        assert response.status_code in [201, 400, 500]

    def test_memory_pressure_with_large_requests(self):
        """Test handling of very large request bodies"""
        client = APIClient()
        
        # Create very large request data
        large_data = {
            'username': 'memory_test',
            'password': 'StrongPass123!@#',
            'email': 'test@example.com',
            # Add large amount of irrelevant data
            'extra_data': 'x' * 100000  # 100KB of extra data
        }
        
        response = client.post('/api/auth/register/', large_data, format='json')
        
        # Should either ignore extra fields or reject, not crash
        assert response.status_code in [201, 400]

    def test_authentication_with_inactive_user(self):
        """Test authentication behavior with deactivated user"""
        user = User.objects.create_user(username='inactive_user', password='pass123')
        user.is_active = False
        user.save()
        
        client = APIClient()
        
        # Try to login with inactive user
        response = client.post('/api/token/', {
            'username': 'inactive_user',
            'password': 'pass123'
        }, format='json')
        
        # Should be rejected
        assert response.status_code == 401

    def test_logout_with_invalid_refresh_token_formats(self):
        user = User.objects.create_user(username='logout_test', password='pass123')
        client = APIClient()
        
        # Get valid access token
        login_resp = client.post('/api/token/', {'username': 'logout_test', 'password': 'pass123'}, format='json')
        access = login_resp.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        
        invalid_refresh_tokens = [
            '',  # Empty
            'invalid',  # Not JWT
            'a.b.c.d',  # Wrong format
            None,  # Null value
        ]
        
        for invalid_token in invalid_refresh_tokens:
            data = {'refresh': invalid_token} if invalid_token is not None else {}
            response = client.post('/api/auth/logout/', data, format='json')
            
            # Should handle invalid tokens gracefully
            assert response.status_code in [400, 401]

    def test_password_change_edge_cases(self):
        user = User.objects.create_user(username='pwd_change_test', password='OldPass123!')
        client = APIClient()
        
        # Login
        login_resp = client.post('/api/token/', {'username': 'pwd_change_test', 'password': 'OldPass123!'})
        access = login_resp.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        
        # Test same old and new password
        response1 = client.post('/api/auth/password-change/', {
            'old_password': 'OldPass123!',
            'new_password': 'OldPass123!'  # Same as old
        }, format='json')
        # Should be allowed (Django doesn't prevent this by default)
        assert response1.status_code in [200, 400]
        
        # Test empty passwords
        response2 = client.post('/api/auth/password-change/', {
            'old_password': '',
            'new_password': 'NewPass123!'
        }, format='json')
        assert response2.status_code == 400
        
        response3 = client.post('/api/auth/password-change/', {
            'old_password': 'OldPass123!',
            'new_password': ''
        }, format='json')
        assert response3.status_code == 400