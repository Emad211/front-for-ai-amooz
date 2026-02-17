"""
Unit Tests for Authentication App - Individual Components
Tests serializers, validators, and isolated logic without API calls
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

from apps.authentication.serializers import RegisterSerializer, LogoutSerializer, PasswordChangeSerializer

User = get_user_model()


@pytest.mark.django_db
class TestRegisterSerializer:
    def test_valid_student_registration_data(self):
        data = {
            'username': 'test_student',
            'email': 'student@test.com',
            'password': 'StrongPass123!@#',
            'role': 'STUDENT'
        }
        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data['role'] == 'STUDENT'

    def test_valid_teacher_registration_data(self):
        data = {
            'username': 'test_teacher',
            'email': 'teacher@test.com',
            'password': 'StrongPass123!@#',
            'role': 'TEACHER'
        }
        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data['role'] == 'TEACHER'

    def test_invalid_admin_role_registration(self):
        data = {
            'username': 'fake_admin',
            'email': 'admin@test.com',
            'password': 'StrongPass123!@#',
            'role': 'ADMIN'
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert 'role' in serializer.errors

    def test_duplicate_username_validation(self):
        User.objects.create_user(username='existing_user', password='pass123')
        data = {
            'username': 'existing_user',
            'password': 'StrongPass123!@#'
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert 'username' in serializer.errors
        assert 'already exists' in str(serializer.errors['username'][0])

    def test_duplicate_email_validation(self):
        User.objects.create_user(username='user1', email='taken@test.com', password='pass123')
        data = {
            'username': 'user2',
            'email': 'taken@test.com',
            'password': 'StrongPass123!@#'
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        # Error may be on 'email' key or 'non_field_errors' depending on validate() location
        errors_str = str(serializer.errors)
        assert 'email' in serializer.errors or 'non_field_errors' in serializer.errors, errors_str

    def test_empty_email_is_allowed(self):
        data = {
            'username': 'no_email_user',
            'password': 'StrongPass123!@#'
        }
        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid()

    def test_blank_email_is_allowed(self):
        data = {
            'username': 'blank_email_user',
            'email': '',
            'password': 'StrongPass123!@#'
        }
        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid()

    def test_password_too_short_validation(self):
        data = {
            'username': 'user',
            'password': '1234567'  # 7 chars, minimum is 8
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert 'password' in serializer.errors

    def test_weak_password_validation(self):
        data = {
            'username': 'user',
            'password': '12345678'  # Too simple
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert 'password' in serializer.errors

    def test_create_user_with_default_student_role(self):
        data = {
            'username': 'default_role_user',
            'password': 'StrongPass123!@#'
        }
        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid()
        user = serializer.save()
        assert user.role == User.Role.STUDENT

    def test_create_user_with_specified_role(self):
        data = {
            'username': 'teacher_user',
            'password': 'StrongPass123!@#',
            'role': 'TEACHER'
        }
        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid()
        user = serializer.save()
        assert user.role == User.Role.TEACHER

    def test_username_max_length_validation(self):
        data = {
            'username': 'a' * 151,  # Exceeds 150 char limit
            'password': 'StrongPass123!@#'
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert 'username' in serializer.errors


@pytest.mark.django_db
class TestLogoutSerializer:
    def test_valid_refresh_token_format(self):
        data = {'refresh': 'valid.jwt.token'}
        serializer = LogoutSerializer(data=data)
        assert serializer.is_valid()

    def test_missing_refresh_token(self):
        data = {}
        serializer = LogoutSerializer(data=data)
        assert not serializer.is_valid()
        assert 'refresh' in serializer.errors

    def test_empty_refresh_token(self):
        data = {'refresh': ''}
        serializer = LogoutSerializer(data=data)
        assert not serializer.is_valid()
        assert 'refresh' in serializer.errors


@pytest.mark.django_db
class TestPasswordChangeSerializer:
    def test_valid_password_change_data(self):
        data = {
            'old_password': 'OldPass123!',
            'new_password': 'NewPass123!@#'
        }
        serializer = PasswordChangeSerializer(data=data)
        assert serializer.is_valid()

    def test_missing_old_password(self):
        data = {'new_password': 'NewPass123!@#'}
        serializer = PasswordChangeSerializer(data=data)
        assert not serializer.is_valid()
        assert 'old_password' in serializer.errors

    def test_missing_new_password(self):
        data = {'old_password': 'OldPass123!'}
        serializer = PasswordChangeSerializer(data=data)
        assert not serializer.is_valid()
        assert 'new_password' in serializer.errors

    def test_new_password_too_short(self):
        data = {
            'old_password': 'OldPass123!',
            'new_password': '1234567'  # 7 chars
        }
        serializer = PasswordChangeSerializer(data=data)
        assert not serializer.is_valid()
        assert 'new_password' in serializer.errors

    def test_weak_new_password(self):
        data = {
            'old_password': 'OldPass123!',
            'new_password': '12345678'  # Too simple
        }
        serializer = PasswordChangeSerializer(data=data)
        assert not serializer.is_valid()
        assert 'new_password' in serializer.errors