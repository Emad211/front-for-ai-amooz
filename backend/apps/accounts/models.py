from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', _('Admin')
        TEACHER = 'TEACHER', _('Teacher')
        STUDENT = 'STUDENT', _('Student')

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT
    )
    phone = models.CharField(max_length=15, blank=True, null=True)
    is_profile_completed = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

class BaseProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='%(class)s')
    bio = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class StudentProfile(BaseProfile):
    GRADE_CHOICES = [
        ('10', 'دهم'),
        ('11', 'یازدهم'),
        ('12', 'دوازدهم'),
    ]
    MAJOR_CHOICES = [
        ('math', 'ریاضی فیزیک'),
        ('science', 'علوم تجربی'),
        ('humanities', 'علوم انسانی'),
    ]
    
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True, null=True)
    major = models.CharField(max_length=20, choices=MAJOR_CHOICES, blank=True, null=True)
    school = models.CharField(max_length=255, blank=True, null=True)

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
