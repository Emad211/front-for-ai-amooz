"""
End-to-End Authentication Flow Tests
Tests complete authentication workflows from registration to logout
"""
import pytest
import json
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import StudentProfile, TeacherProfile

User = get_user_model()


@pytest.mark.django_db
class TestCompleteAuthenticationFlows:
    def test_complete_student_registration_to_logout_flow(self):
        """Test complete flow: register -> login -> access protected resource -> logout"""
        client = APIClient()
        
        # Step 1: Register as student
        register_data = {
            'username': 'e2e_student',
            'email': 'student@e2e.com',
            'password': 'StrongPass123!@#',
            'role': 'STUDENT'
        }
        
        register_response = client.post('/api/auth/register/', register_data, format='json')
        assert register_response.status_code == 201
        
        # Verify tokens received
        assert 'tokens' in register_response.data
        assert 'access' in register_response.data['tokens']
        assert 'refresh' in register_response.data['tokens']
        
        # Verify user data
        user_data = register_response.data['user']
        assert user_data['username'] == 'e2e_student'
        assert user_data['email'] == 'student@e2e.com'
        assert user_data['role'] == 'STUDENT'
        
        # Verify profile created
        user = User.objects.get(username='e2e_student')
        assert StudentProfile.objects.filter(user=user).exists()
        
        # Step 2: Use access token to access protected resource
        access_token = register_response.data['tokens']['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        me_response = client.get('/api/accounts/me/')
        assert me_response.status_code == 200
        assert me_response.data['username'] == 'e2e_student'
        assert me_response.data['role'] == 'STUDENT'
        
        # Step 3: Refresh token
        refresh_token = register_response.data['tokens']['refresh']
        client.credentials()  # Remove access token
        
        refresh_response = client.post('/api/token/refresh/', {'refresh': refresh_token}, format='json')
        assert refresh_response.status_code == 200
        assert 'access' in refresh_response.data
        
        # Step 4: Use new access token
        new_access_token = refresh_response.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access_token}')
        
        me_response2 = client.get('/api/accounts/me/')
        assert me_response2.status_code == 200
        
        # Step 5: Logout (blacklist refresh token)
        final_refresh = refresh_response.data.get('refresh', refresh_token)
        logout_response = client.post('/api/auth/logout/', {'refresh': final_refresh}, format='json')
        assert logout_response.status_code == 205
        
        # Step 6: Verify tokens are invalid after logout
        client.credentials()
        post_logout_refresh = client.post('/api/token/refresh/', {'refresh': final_refresh}, format='json')
        assert post_logout_refresh.status_code in [401, 400]

    def test_complete_teacher_registration_to_password_change_flow(self):
        """Test teacher registration and password change flow"""
        client = APIClient()
        
        # Step 1: Register as teacher
        register_data = {
            'username': 'e2e_teacher',
            'email': 'teacher@e2e.com',
            'password': 'OriginalPass123!@#',
            'role': 'TEACHER'
        }
        
        register_response = client.post('/api/auth/register/', register_data, format='json')
        assert register_response.status_code == 201
        assert register_response.data['user']['role'] == 'TEACHER'
        
        # Verify teacher profile created
        user = User.objects.get(username='e2e_teacher')
        assert TeacherProfile.objects.filter(user=user).exists()
        
        # Step 2: Login with original password (to get fresh tokens)
        login_response = client.post('/api/token/', {
            'username': 'e2e_teacher',
            'password': 'OriginalPass123!@#'
        }, format='json')
        assert login_response.status_code == 200
        
        access_token = login_response.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Step 3: Change password
        password_change_response = client.post('/api/auth/password-change/', {
            'old_password': 'OriginalPass123!@#',
            'new_password': 'NewPassword123!@#'
        }, format='json')
        assert password_change_response.status_code == 200
        
        # Step 4: Verify old password no longer works
        client.credentials()
        old_password_login = client.post('/api/token/', {
            'username': 'e2e_teacher',
            'password': 'OriginalPass123!@#'
        }, format='json')
        assert old_password_login.status_code == 401
        
        # Step 5: Verify new password works
        new_password_login = client.post('/api/token/', {
            'username': 'e2e_teacher',
            'password': 'NewPassword123!@#'
        }, format='json')
        assert new_password_login.status_code == 200

    def test_login_flow_with_username_and_email(self):
        """Test that login works with both username and email"""
        # Create user via Django ORM (not through registration API)
        user = User.objects.create_user(
            username='login_test',
            email='login@test.com',
            password='TestPass123!@#'
        )
        
        client = APIClient()
        
        # Test login with username
        username_login = client.post('/api/token/', {
            'username': 'login_test',
            'password': 'TestPass123!@#'
        }, format='json')
        assert username_login.status_code == 200
        
        # Test login with email (Django's default auth doesn't support this without custom backend)
        # We support this via a custom SimpleJWT serializer that maps email -> username.
        email_login = client.post('/api/token/', {
            'username': 'login@test.com',
            'password': 'TestPass123!@#'
        }, format='json')
        assert email_login.status_code == 200

    def test_email_login_with_multiple_accounts_uses_matching_password(self):
        """Email can be shared by multiple accounts and login resolves by password."""
        shared_email = 'shared@test.com'
        admin_user = User.objects.create_user(
            username='shared_admin',
            email=shared_email,
            password='AdminPass123!@#',
            role=User.Role.ADMIN,
        )
        teacher_user = User.objects.create_user(
            username='shared_teacher',
            email=shared_email,
            password='TeacherPass123!@#',
            role=User.Role.TEACHER,
        )

        client = APIClient()

        admin_login = client.post('/api/token/', {
            'username': shared_email,
            'password': 'AdminPass123!@#',
        }, format='json')
        assert admin_login.status_code == 200
        admin_access = admin_login.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_access}')
        admin_me = client.get('/api/accounts/me/')
        assert admin_me.status_code == 200
        assert admin_me.data['username'] == admin_user.username
        assert admin_me.data['role'] == User.Role.ADMIN

        client.credentials()
        teacher_login = client.post('/api/token/', {
            'username': shared_email,
            'password': 'TeacherPass123!@#',
        }, format='json')
        assert teacher_login.status_code == 200
        teacher_access = teacher_login.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {teacher_access}')
        teacher_me = client.get('/api/accounts/me/')
        assert teacher_me.status_code == 200
        assert teacher_me.data['username'] == teacher_user.username
        assert teacher_me.data['role'] == User.Role.TEACHER

    def test_email_login_prefers_admin_when_same_password_matches_multiple_accounts(self):
        """When same email+password matches multiple accounts, admin-capable account is selected."""
        shared_email = 'ambiguous@test.com'
        shared_password = 'SamePass123!@#'

        teacher_user = User.objects.create_user(
            username='ambiguous_teacher',
            email=shared_email,
            password=shared_password,
            role=User.Role.TEACHER,
        )
        admin_user = User.objects.create_user(
            username='ambiguous_admin',
            email=shared_email,
            password=shared_password,
            role=User.Role.STUDENT,
            is_staff=True,
            is_superuser=True,
        )

        assert teacher_user.id < admin_user.id

        client = APIClient()
        login_response = client.post('/api/token/', {
            'username': shared_email,
            'password': shared_password,
        }, format='json')
        assert login_response.status_code == 200

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        me = client.get('/api/accounts/me/')
        assert me.status_code == 200
        assert me.data['username'] == admin_user.username
        assert me.data['is_superuser'] is True

    def test_token_lifecycle_and_blacklisting(self):
        """Test complete token lifecycle with blacklisting"""
        user = User.objects.create_user(username='token_lifecycle', password='pass123')
        client = APIClient()
        
        # Step 1: Get initial tokens
        login_response = client.post('/api/token/', {
            'username': 'token_lifecycle',
            'password': 'pass123'
        }, format='json')
        
        initial_access = login_response.data['access']
        initial_refresh = login_response.data['refresh']
        
        # Step 2: Use access token
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {initial_access}')
        me_response = client.get('/api/accounts/me/')
        assert me_response.status_code == 200
        
        # Step 3: Refresh token (should get new tokens due to rotation)
        client.credentials()
        refresh_response = client.post('/api/token/refresh/', {'refresh': initial_refresh}, format='json')
        assert refresh_response.status_code == 200
        
        new_access = refresh_response.data['access']
        new_refresh = refresh_response.data['refresh']
        
        # Verify we got new tokens
        assert new_access != initial_access
        assert new_refresh != initial_refresh
        
        # Step 4: Old refresh token should be blacklisted due to rotation
        old_refresh_attempt = client.post('/api/token/refresh/', {'refresh': initial_refresh}, format='json')
        assert old_refresh_attempt.status_code in [401, 400]
        
        # Step 5: New refresh token should work
        final_refresh_response = client.post('/api/token/refresh/', {'refresh': new_refresh}, format='json')
        assert final_refresh_response.status_code == 200

    def test_concurrent_login_sessions(self):
        """Test multiple concurrent login sessions for same user"""
        user = User.objects.create_user(username='concurrent_user', password='pass123')
        client1 = APIClient()
        client2 = APIClient()
        
        # Login from two different "devices" (clients)
        login1 = client1.post('/api/token/', {'username': 'concurrent_user', 'password': 'pass123'}, format='json')
        login2 = client2.post('/api/token/', {'username': 'concurrent_user', 'password': 'pass123'}, format='json')
        
        assert login1.status_code == 200
        assert login2.status_code == 200
        
        # Both sessions should work independently
        client1.credentials(HTTP_AUTHORIZATION=f'Bearer {login1.data["access"]}')
        client2.credentials(HTTP_AUTHORIZATION=f'Bearer {login2.data["access"]}')
        
        me1 = client1.get('/api/accounts/me/')
        me2 = client2.get('/api/accounts/me/')
        
        assert me1.status_code == 200
        assert me2.status_code == 200
        
        # Logout from one session shouldn't affect the other
        client1.post('/api/auth/logout/', {'refresh': login1.data['refresh']}, format='json')
        
        # Client2 should still work
        me2_after_client1_logout = client2.get('/api/accounts/me/')
        assert me2_after_client1_logout.status_code == 200

    def test_registration_with_existing_data_edge_cases(self):
        """Test registration edge cases with existing data"""
        # Create existing user
        User.objects.create_user(
            username='existing',
            email='existing@test.com',
            password='pass123',
            role=User.Role.STUDENT,
        )
        
        client = APIClient()
        
        # Test duplicate username
        response1 = client.post('/api/auth/register/', {
            'username': 'existing',
            'email': 'new@test.com',
            'password': 'StrongPass123!@#'
        }, format='json')
        assert response1.status_code == 400
        assert response1.data['detail'] == 'Validation error.'
        assert 'username' in response1.data['errors']
        
        # Test duplicate email in same role is rejected
        response2 = client.post('/api/auth/register/', {
            'username': 'newuser',
            'email': 'existing@test.com',
            'password': 'StrongPass123!@#',
            'role': 'STUDENT',
        }, format='json')
        assert response2.status_code == 400
        assert response2.data['detail'] == 'Validation error.'
        assert 'email' in response2.data['errors']

        # Test duplicate email in different role is allowed
        response4 = client.post('/api/auth/register/', {
            'username': 'newteacher',
            'email': 'existing@test.com',
            'password': 'StrongPass123!@#',
            'role': 'TEACHER',
        }, format='json')
        assert response4.status_code == 201
        
        # Test case sensitivity (username)
        response3 = client.post('/api/auth/register/', {
            'username': 'EXISTING',
            'email': 'EXISTING@TEST.COM',
            'password': 'StrongPass123!@#'
        }, format='json')
        # Should fail because email is compared case-insensitively for same role (default STUDENT)
        assert response3.status_code == 400

    def test_authentication_error_handling(self):
        """Test various authentication error scenarios"""
        client = APIClient()
        
        # Test empty request
        response1 = client.post('/api/token/', {}, format='json')
        assert response1.status_code == 400
        
        # Test missing password
        response2 = client.post('/api/token/', {'username': 'test'}, format='json')
        assert response2.status_code == 400
        
        # Test missing username
        response3 = client.post('/api/token/', {'password': 'test'}, format='json')
        assert response3.status_code == 400
        
        # Test malformed JSON
        response4 = client.post('/api/token/', 'invalid json', content_type='application/json')
        assert response4.status_code == 400
        
        # Test wrong content type
        response5 = client.post('/api/token/', 'username=test&password=pass', content_type='text/plain')
        assert response5.status_code in [400, 415]