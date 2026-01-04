from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, StudentProfile, TeacherProfile, AdminProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == User.Role.STUDENT:
            StudentProfile.objects.create(user=instance)
        elif instance.role == User.Role.TEACHER:
            TeacherProfile.objects.create(user=instance)
        elif instance.role == User.Role.ADMIN:
            AdminProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if instance.role == User.Role.STUDENT and hasattr(instance, 'studentprofile'):
        instance.studentprofile.save()
    elif instance.role == User.Role.TEACHER and hasattr(instance, 'teacherprofile'):
        instance.teacherprofile.save()
    elif instance.role == User.Role.ADMIN and hasattr(instance, 'adminprofile'):
        instance.adminprofile.save()
