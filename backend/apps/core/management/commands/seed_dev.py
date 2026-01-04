from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Seed development data (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--admin-password', default='admin123', help='Admin password')
        parser.add_argument('--teacher-password', default='teacher123', help='Teacher password')
        parser.add_argument('--student-password', default='student123', help='Student password')

    def handle(self, *args, **options):
        self._seed_admin(password=options['admin_password'])
        self._seed_teacher(password=options['teacher_password'])
        self._seed_student(password=options['student_password'])

        self.stdout.write(self.style.SUCCESS('Seed completed.'))

    def _ensure_single_profile(self, user):
        """Ensure only the correct role profile exists (safety for repeated runs)."""
        # Related names are derived from model class names via BaseProfile related_name pattern.
        # StudentProfile -> user.studentprofile, etc.
        if user.role == User.Role.ADMIN:
            if hasattr(user, 'teacherprofile'):
                user.teacherprofile.delete()
            if hasattr(user, 'studentprofile'):
                user.studentprofile.delete()
            if not hasattr(user, 'adminprofile'):
                # signals should create on user creation; fallback for safety
                from apps.accounts.models import AdminProfile
                AdminProfile.objects.create(user=user)

        elif user.role == User.Role.TEACHER:
            if hasattr(user, 'adminprofile'):
                user.adminprofile.delete()
            if hasattr(user, 'studentprofile'):
                user.studentprofile.delete()
            if not hasattr(user, 'teacherprofile'):
                from apps.accounts.models import TeacherProfile
                TeacherProfile.objects.create(user=user)

        elif user.role == User.Role.STUDENT:
            if hasattr(user, 'adminprofile'):
                user.adminprofile.delete()
            if hasattr(user, 'teacherprofile'):
                user.teacherprofile.delete()
            if not hasattr(user, 'studentprofile'):
                from apps.accounts.models import StudentProfile
                StudentProfile.objects.create(user=user)

    def _seed_admin(self, password: str):
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            admin.set_password(password)

        # Ensure flags/role are correct even on re-run
        admin.role = User.Role.ADMIN
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        self._ensure_single_profile(admin)

        self.stdout.write(self.style.SUCCESS("Created/updated admin user: admin"))

    def _seed_teacher(self, password: str):
        teacher, created = User.objects.get_or_create(
            username='teacher',
            defaults={
                'email': 'teacher@example.com',
                'role': User.Role.TEACHER,
            },
        )
        if created:
            teacher.set_password(password)

        teacher.role = User.Role.TEACHER
        teacher.save()
        self._ensure_single_profile(teacher)

        if hasattr(teacher, 'teacherprofile'):
            teacher.teacherprofile.expertise = teacher.teacherprofile.expertise or 'Math'
            teacher.teacherprofile.teaching_experience = teacher.teacherprofile.teaching_experience or 3
            teacher.teacherprofile.save()

        self.stdout.write(self.style.SUCCESS("Created/updated teacher user: teacher"))

    def _seed_student(self, password: str):
        student, created = User.objects.get_or_create(
            username='student',
            defaults={
                'email': 'student@example.com',
                'role': User.Role.STUDENT,
            },
        )
        if created:
            student.set_password(password)

        student.role = User.Role.STUDENT
        student.save()
        self._ensure_single_profile(student)

        if hasattr(student, 'studentprofile'):
            student.studentprofile.grade = student.studentprofile.grade or '12'
            student.studentprofile.major = student.studentprofile.major or 'math'
            student.studentprofile.school = student.studentprofile.school or 'Demo School'
            student.studentprofile.save()

        self.stdout.write(self.style.SUCCESS("Created/updated student user: student"))
