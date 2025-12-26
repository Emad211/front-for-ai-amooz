from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
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
    phone = models.CharField(max_length=15, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return self.username
