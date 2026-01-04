"""
Database and Query Tests for Authentication System
Tests direct database operations, constraints, and query performance
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.accounts.models import StudentProfile, TeacherProfile, AdminProfile

User = get_user_model()


@pytest.mark.django_db
class TestUserModelConstraints:
    def test_username_uniqueness_constraint(self):
        User.objects.create_user(username='unique_user', password='pass123')
        with pytest.raises(IntegrityError):
            User.objects.create_user(username='unique_user', password='pass456')

    def test_email_uniqueness_at_db_level(self):
        User.objects.create_user(username='user1', email='unique@test.com', password='pass123')
        # Django doesn't enforce email uniqueness at DB level by default, but our serializer does
        # This test ensures we can create users with same email at DB level (for empty emails)
        user2 = User.objects.create_user(username='user2', email='unique@test.com', password='pass456')
        assert user2.id is not None

    def test_empty_email_multiple_users(self):
        User.objects.create_user(username='empty_email_user1', email='', password='pass123')
        User.objects.create_user(username='empty_email_user2', email='', password='pass456')
        User.objects.create_user(username='empty_email_user3', password='pass789')  # No email
        
        empty_email_count = User.objects.filter(Q(email='') | Q(email__isnull=True)).count()
        # Should have at least 3 (might have more from other tests)
        assert empty_email_count >= 3

    def test_role_field_choices_constraint(self):
        # Valid roles
        student = User.objects.create_user(username='student', password='pass123', role=User.Role.STUDENT)
        teacher = User.objects.create_user(username='teacher', password='pass123', role=User.Role.TEACHER)
        admin = User.objects.create_user(username='admin', password='pass123', role=User.Role.ADMIN)
        
        assert student.role == 'STUDENT'
        assert teacher.role == 'TEACHER'
        assert admin.role == 'ADMIN'

    def test_default_role_assignment(self):
        user = User.objects.create_user(username='default_role', password='pass123')
        assert user.role == User.Role.STUDENT

    def test_user_password_hashing(self):
        user = User.objects.create_user(username='hash_test', password='plaintext123')
        assert user.password != 'plaintext123'
        assert user.check_password('plaintext123')
        assert not user.check_password('wrongpassword')

    def test_user_cascade_delete_profile(self):
        user = User.objects.create_user(username='cascade_test', password='pass123', role=User.Role.STUDENT)
        student_profile_id = user.studentprofile.id
        
        user.delete()
        
        assert not StudentProfile.objects.filter(id=student_profile_id).exists()

    def test_profile_creation_via_signals(self):
        # Student profile creation
        student = User.objects.create_user(username='student_profile', password='pass123', role=User.Role.STUDENT)
        assert StudentProfile.objects.filter(user=student).exists()
        assert not TeacherProfile.objects.filter(user=student).exists()
        assert not AdminProfile.objects.filter(user=student).exists()

        # Teacher profile creation
        teacher = User.objects.create_user(username='teacher_profile', password='pass123', role=User.Role.TEACHER)
        assert TeacherProfile.objects.filter(user=teacher).exists()
        assert not StudentProfile.objects.filter(user=teacher).exists()
        assert not AdminProfile.objects.filter(user=teacher).exists()

        # Admin profile creation
        admin = User.objects.create_user(username='admin_profile', password='pass123', role=User.Role.ADMIN)
        assert AdminProfile.objects.filter(user=admin).exists()
        assert not StudentProfile.objects.filter(user=admin).exists()
        assert not TeacherProfile.objects.filter(user=admin).exists()

    def test_profile_one_to_one_constraint(self):
        user = User.objects.create_user(username='one_to_one_test', password='pass123', role=User.Role.STUDENT)
        
        # Trying to create another StudentProfile for the same user should fail
        with pytest.raises(IntegrityError):
            StudentProfile.objects.create(user=user)

    def test_query_users_by_role(self):
        User.objects.create_user(username='role_student1', password='pass123', role=User.Role.STUDENT)
        User.objects.create_user(username='role_student2', password='pass123', role=User.Role.STUDENT)
        User.objects.create_user(username='role_teacher1', password='pass123', role=User.Role.TEACHER)
        User.objects.create_user(username='role_admin1', password='pass123', role=User.Role.ADMIN)

        students = User.objects.filter(role=User.Role.STUDENT, username__startswith='role_student')
        teachers = User.objects.filter(role=User.Role.TEACHER, username__startswith='role_teacher')
        admins = User.objects.filter(role=User.Role.ADMIN, username__startswith='role_admin')

        assert students.count() == 2
        assert teachers.count() == 1
        assert admins.count() == 1

    def test_query_users_with_profiles(self):
        student = User.objects.create_user(username='profile_query_student', password='pass123', role=User.Role.STUDENT)
        teacher = User.objects.create_user(username='profile_query_teacher', password='pass123', role=User.Role.TEACHER)

        # Query with joins
        students_with_profiles = User.objects.filter(role=User.Role.STUDENT, username='profile_query_student').select_related('studentprofile')
        teachers_with_profiles = User.objects.filter(role=User.Role.TEACHER, username='profile_query_teacher').select_related('teacherprofile')

        assert students_with_profiles.count() == 1
        assert teachers_with_profiles.count() == 1
        
        # Access profile without additional queries
        student_from_db = students_with_profiles.first()
        teacher_from_db = teachers_with_profiles.first()
        
        assert student_from_db.studentprofile is not None
        assert teacher_from_db.teacherprofile is not None

    def test_bulk_create_users(self):
        users_data = [
            User(username=f'bulk_user_{i}', role=User.Role.STUDENT, password='hashed')
            for i in range(10)
        ]
        
        created_users = User.objects.bulk_create(users_data)
        assert len(created_users) == 10
        
        # Note: bulk_create doesn't trigger signals, so profiles won't be created
        student_profiles_count = StudentProfile.objects.filter(user__username__startswith='bulk_user_').count()
        assert student_profiles_count == 0  # Signals not triggered

    def test_transaction_rollback_on_profile_creation_failure(self):
        initial_user_count = User.objects.count()
        
        try:
            with transaction.atomic():
                user = User.objects.create_user(username='tx_test', password='pass123', role=User.Role.STUDENT)
                # Manually create a conflicting profile to cause integrity error
                StudentProfile.objects.create(user=user)  # This will fail due to signal already creating one
        except IntegrityError:
            pass
        
        # Transaction should be rolled back
        final_user_count = User.objects.count()
        assert final_user_count == initial_user_count
        assert not User.objects.filter(username='tx_test').exists()


@pytest.mark.django_db 
class TestUserQueryPerformance:
    def test_efficient_user_role_filtering(self):
        # Create test data
        for i in range(100):
            User.objects.create_user(
                username=f'perf_student_{i}',
                password='pass123',
                role=User.Role.STUDENT
            )
        
        for i in range(50):
            User.objects.create_user(
                username=f'perf_teacher_{i}',
                password='pass123',
                role=User.Role.TEACHER
            )

        # Test query efficiency
        import time
        start = time.time()
        students = list(User.objects.filter(role=User.Role.STUDENT)[:10])
        end = time.time()
        
        # Should complete in under 1 second
        assert (end - start) < 1.0, f"Query took {end - start} seconds, too slow!"
        assert len(students) == 10

    def test_profile_prefetch_efficiency(self):
        # Create test users with profiles
        for i in range(20):
            User.objects.create_user(
                username=f'prefetch_student_{i}',
                password='pass123',
                role=User.Role.STUDENT
            )

        # Query with prefetch_related to avoid N+1 queries
        users_with_profiles = User.objects.filter(
            role=User.Role.STUDENT,
            username__startswith='prefetch_student_'
        ).prefetch_related('studentprofile').all()

        # Access profiles - should not generate additional queries
        profile_count = 0
        for user in users_with_profiles:
            if hasattr(user, 'studentprofile'):
                profile_count += 1

        assert profile_count == 20