from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', _('Admin')
        # Organization manager: manages an org but does NOT teach and is NOT a
        # platform admin (no /admin access). Distinct from TEACHER on purpose.
        MANAGER = 'MANAGER', _('Manager')
        TEACHER = 'TEACHER', _('Teacher')
        STUDENT = 'STUDENT', _('Student')
        # Study advisor (مشاور): plans a student's week and reads their study
        # log. Works freelance and/or inside an organization. Grants NOTHING by
        # default — every advisory endpoint opts in explicitly via
        # apps.core.permissions.IsAdvisorUser. Has NO profile model on purpose
        # (like MANAGER) — see apps/accounts/signals.py.
        ADVISOR = 'ADVISOR', _('Advisor')
        # Parent (والد): reads one student's weekly advisory digest, nothing
        # else. Grants NOTHING by default — the only routes this role opens are
        # the advisory parent endpoints gated on
        # apps.core.permissions.IsParentUser, and even those require an ACTIVE
        # ParentLink claimed via OTP. Has NO profile model on purpose (like
        # MANAGER/ADVISOR) — see apps/accounts/signals.py.
        PARENT = 'PARENT', _('Parent')

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT
    )
    phone = models.CharField(max_length=15, blank=True, null=True)
    is_profile_completed = models.BooleanField(default=False)
    # TEACHER only: may use a personal (freelancer) workspace in addition to any
    # organizations. False = org-only (no personal space). Ignored for non-teacher
    # roles — a MANAGER never gets a personal space regardless of this flag.
    is_freelancer = models.BooleanField(default=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    class Meta(AbstractUser.Meta):
        constraints = [
            # The phone is the student identity key (invite-code login, org-code
            # redemption, class-roster matching). Enforce ONE STUDENT per phone at
            # the DB level — a partial unique index, so a phone may still belong to
            # a different-role account (e.g. the same person as TEACHER + STUDENT),
            # and NULL phones (non-students / pre-phone accounts) are unconstrained.
            models.UniqueConstraint(
                fields=['phone'],
                condition=models.Q(role='STUDENT', phone__isnull=False),
                name='uniq_student_phone',
            ),
        ]

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_effectively_completed(self) -> bool:
        """Effective profile completion — the stored flag, plus the curriculum
        keys for students.

        For STUDENTS the stored flag alone lies: anyone who onboarded before the
        advisor curriculum round carries ``is_profile_completed=True`` yet no
        grade, so their derived subject list would stay silently empty forever.
        The effective value therefore also demands grade (plus major on grades
        10–12), so the frontend gate routes those users back into onboarding
        instead of showing them a blank picker. Non-students are unaffected.
        """
        if not self.is_profile_completed:
            return False
        if self.role != self.Role.STUDENT:
            return True
        # Re-read from the DB — never trust the ``studentprofile`` reverse cache
        # on a long-lived instance (same trap MeUpdateSerializer documents).
        profile = StudentProfile.objects.filter(user_id=self.pk).first()
        return bool(profile and profile.curriculum_keys_complete)

class BaseProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='%(class)s')
    bio = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class StudentProfile(BaseProfile):
    # Deliberate value-copy of ``apps.advisory.models.SUBJECT_GRADE_CHOICES`` (not
    # an import — no cross-app dependency). A student's own grade selects their
    # derived curriculum, so both sides must accept the same codes.
    GRADE_CHOICES = [
        ('01', 'پایه اول'),
        ('02', 'پایه دوم'),
        ('03', 'پایه سوم'),
        ('04', 'پایه چهارم'),
        ('05', 'پایه پنجم'),
        ('06', 'پایه ششم'),
        ('07', 'هفتم'),
        ('08', 'هشتم'),
        ('09', 'نهم'),
        ('10', 'دهم'),
        ('11', 'یازدهم'),
        ('12', 'دوازدهم'),
    ]
    MAJOR_CHOICES = [
        ('math', 'ریاضی فیزیک'),
        ('science', 'علوم تجربی'),
        ('humanities', 'علوم انسانی'),
        ('theology', 'علوم و معارف اسلامی'),
        ('technical', 'فنی و حرفه‌ای و کاردانش'),
    ]
    
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True, null=True)
    major = models.CharField(max_length=20, choices=MAJOR_CHOICES, blank=True, null=True)
    school = models.CharField(max_length=255, blank=True, null=True)

    # Grades that REQUIRE a major (owner decision, advisor-mvp Step 9): a
    # high-schooler without a track derives no major-specific curriculum.
    # Single source of truth — ``MeUpdateSerializer`` mirrors this constant.
    HIGH_SCHOOL_GRADES = {'10', '11', '12'}

    @property
    def curriculum_keys_complete(self) -> bool:
        """True when the grade is set AND (the grade is non-HS OR a major is set).

        Mirrors ``MeUpdateSerializer.validate()``'s conditional-required rule so
        the completion signal (:meth:`User.is_effectively_completed`) can never
        disagree with what onboarding/profile writes actually accept.
        """
        if not self.grade:
            return False
        if self.grade in self.HIGH_SCHOOL_GRADES:
            return bool(self.major)
        return True

    def __str__(self):
        return f"Student: {self.user.username}"

class TeacherProfile(BaseProfile):
    expertise = models.CharField(max_length=255, blank=True, null=True)
    verification_status = models.BooleanField(default=False)
    teaching_experience = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Teacher: {self.user.username}"

class AdminProfile(BaseProfile):
    department = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Admin: {self.user.username}"
