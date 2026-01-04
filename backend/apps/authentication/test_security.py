"""
Security and Penetration Tests for Authentication System
Tests for security vulnerabilities, attack vectors, and abuse prevention
"""
import pytest
import json
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()


@pytest.mark.django_db
class TestAuthenticationSecurityVulnerabilities:
    def test_sql_injection_in_username(self):
        client = APIClient()
        # Attempt SQL injection via username
        malicious_data = {
            'username': "admin'; DROP TABLE auth_user; --",
            'password': 'StrongPass123!@#'
        }
        
        response = client.post('/api/auth/register/', malicious_data, format='json')
        
        # Should not cause SQL injection, just create user with that username
        if response.status_code == 201:
            # Verify user was created with the literal string, not executed as SQL
            user = User.objects.get(username=malicious_data['username'])
            assert user.username == malicious_data['username']
        
        # Verify our users table still exists
        assert User.objects.all().count() >= 0

    def test_xss_attempt_in_registration(self):
        client = APIClient()
        xss_payload = "<script>alert('xss')</script>"
        
        response = client.post('/api/auth/register/', {
            'username': xss_payload,
            'email': f'test{xss_payload}@example.com',
            'password': 'StrongPass123!@#'
        }, format='json')
        
        if response.status_code == 201:
            # Data should be stored as-is, not executed
            user = User.objects.get(username=xss_payload)
            assert user.username == xss_payload
            assert xss_payload in user.email

    def test_extremely_long_input_dos_attempt(self):
        client = APIClient()
        
        # Attempt DoS with extremely long strings
        long_string = 'a' * 10000
        response = client.post('/api/auth/register/', {
            'username': long_string,
            'email': f'{long_string}@example.com',
            'password': long_string
        }, format='json')
        
        # Should be rejected due to validation, not cause server crash
        assert response.status_code == 400

    def test_null_byte_injection(self):
        client = APIClient()
        
        response = client.post('/api/auth/register/', {
            'username': 'user\x00admin',
            'password': 'StrongPass123!@#'
        }, format='json')
        
        # System should handle null bytes gracefully
        assert response.status_code in [201, 400]  # Either created or validation error

    def test_unicode_normalization_attack(self):
        client = APIClient()
        
        # Unicode characters that might normalize to different strings
        username1 = "admin\u0300"  # admin with combining grave accent
        username2 = "àdmin"        # admin with precomposed à
        
        client.post('/api/auth/register/', {
            'username': username1,
            'password': 'StrongPass123!@#'
        }, format='json')
        
        response2 = client.post('/api/auth/register/', {
            'username': username2,
            'password': 'StrongPass123!@#'
        }, format='json')
        
        # Should handle Unicode properly - both users should be creatable
        assert response2.status_code == 201

    def test_password_brute_force_protection(self):
        user = User.objects.create_user(username='brute_target', password='CorrectPass123!')
        client = APIClient()
        
        # Attempt multiple failed logins
        failed_attempts = 0
        for i in range(10):
            response = client.post('/api/token/', {
                'username': 'brute_target',
                'password': f'WrongPass{i}'
            }, format='json')
            
            if response.status_code == 401:
                failed_attempts += 1
        
        assert failed_attempts == 10
        
        # Valid login should still work (no account lockout implemented yet)
        valid_response = client.post('/api/token/', {
            'username': 'brute_target',
            'password': 'CorrectPass123!'
        }, format='json')
        assert valid_response.status_code == 200

    def test_jwt_token_tampering(self):
        user = User.objects.create_user(username='jwt_test', password='pass123')
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Tamper with the token
        tampered_token = access_token[:-10] + 'tampered123'
        
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tampered_token}')
        
        response = client.get('/api/accounts/me/')
        assert response.status_code == 401

    def test_jwt_token_replay_attack(self):
        user = User.objects.create_user(username='replay_test', password='pass123')
        client = APIClient()
        
        # Get tokens
        token_response = client.post('/api/token/', {
            'username': 'replay_test',
            'password': 'pass123'
        }, format='json')
        
        access = token_response.data['access']
        refresh = token_response.data['refresh']
        
        # Use access token
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response1 = client.get('/api/accounts/me/')
        assert response1.status_code == 200
        
        # Logout (blacklist refresh token)
        client.post('/api/auth/logout/', {'refresh': refresh}, format='json')
        
        # Try to refresh with blacklisted token
        client.credentials()
        refresh_response = client.post('/api/token/refresh/', {'refresh': refresh}, format='json')
        assert refresh_response.status_code in [401, 400]

    def test_authorization_bypass_attempt(self):
        user_a = User.objects.create_user(username='user_a', password='pass123', role=User.Role.STUDENT)
        user_b = User.objects.create_user(username='user_b', password='pass123', role=User.Role.TEACHER)
        
        client = APIClient()
        
        # Get token for user_a
        token_resp = client.post('/api/token/', {'username': 'user_a', 'password': 'pass123'}, format='json')
        token_a = token_resp.data['access']
        
        # Try to access with user_a's token
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_a}')
        response = client.get('/api/accounts/me/')
        
        assert response.status_code == 200
        assert response.data['username'] == 'user_a'
        assert response.data['role'] == 'STUDENT'
        
        # Should not be able to get user_b's data with user_a's token
        assert response.data['username'] != 'user_b'

    def test_role_elevation_attempt(self):
        # Create a student user
        student = User.objects.create_user(username='student_hacker', password='pass123', role=User.Role.STUDENT)
        client = APIClient()
        
        # Login as student
        token_resp = client.post('/api/token/', {'username': 'student_hacker', 'password': 'pass123'}, format='json')
        access = token_resp.data['access']
        
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        
        # Attempt to change role via API (if such endpoint existed)
        # Since we don't have a profile update endpoint, this test verifies the user can't change their role
        me_response = client.get('/api/accounts/me/')
        assert me_response.data['role'] == 'STUDENT'
        
        # Verify the role wasn't changed in database
        student.refresh_from_db()
        assert student.role == User.Role.STUDENT

    def test_csrf_protection(self):
        # Our API uses JWT tokens, so CSRF should not be relevant
        # But we test that the authentication system works without CSRF tokens
        client = APIClient()
        client.credentials(HTTP_X_CSRFTOKEN='')  # Empty CSRF token
        
        response = client.post('/api/auth/register/', {
            'username': 'csrf_test',
            'password': 'StrongPass123!@#'
        }, format='json')
        
        # Should work fine without CSRF token (JWT-based API)
        assert response.status_code == 201

    def test_information_disclosure_on_error(self):
        client = APIClient()
        
        # Test that error messages don't reveal sensitive information
        response = client.post('/api/token/', {
            'username': 'nonexistent_user',
            'password': 'some_password'
        }, format='json')
        
        assert response.status_code == 401
        # Should not reveal whether username exists or not
        assert 'nonexistent_user' not in str(response.data)

    def test_timing_attack_resistance(self):
        # Create a user
        User.objects.create_user(username='timing_test', password='CorrectPass123!')
        client = APIClient()

        # Timing tests are inherently noisy (OS scheduling, CI load, DB cache warmup).
        # Use multiple samples and compare medians to reduce flakiness.
        import time
        import statistics

        def timed_call(payload):
            start = time.perf_counter()
            resp = client.post('/api/token/', payload, format='json')
            end = time.perf_counter()
            return resp, (end - start)

        valid_user_wrong_pass = {'username': 'timing_test', 'password': 'WrongPassword'}
        invalid_user = {'username': 'nonexistent_user', 'password': 'SomePassword'}

        # Warmup calls
        warm1, _ = timed_call(valid_user_wrong_pass)
        warm2, _ = timed_call(invalid_user)
        assert warm1.status_code == 401
        assert warm2.status_code == 401

        samples = 7
        times_valid = []
        times_invalid = []

        for _ in range(samples):
            r1, t1 = timed_call(valid_user_wrong_pass)
            r2, t2 = timed_call(invalid_user)
            assert r1.status_code == 401
            assert r2.status_code == 401
            times_valid.append(t1)
            times_invalid.append(t2)

        median_diff = abs(statistics.median(times_valid) - statistics.median(times_invalid))

        # Keep this as a coarse regression guard.
        # If this becomes flaky on certain machines, prefer increasing samples before tightening threshold.
        assert median_diff < 0.25, f"Median timing difference: {median_diff}s - potential timing attack vector"