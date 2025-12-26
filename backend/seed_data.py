import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.users.models import User
from apps.courses.models import Course, Module, Lesson

def seed():
    # Create superuser
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print("Superuser 'admin' created with password 'admin123'")

    # Create a sample course
    course, created = Course.objects.get_or_create(
        title='ریاضی دوازدهم - فصل اول',
        description='آموزش جامع فصل اول ریاضی دوازدهم شامل تابع، صعودی و نزولی بودن و ...'
    )
    if created:
        print(f"Course '{course.title}' created")

        # Create modules
        module1 = Module.objects.create(course=course, title='آشنایی با توابع', order=1)
        module2 = Module.objects.create(course=course, title='حد و پیوستگی', order=2)

        # Create lessons
        Lesson.objects.create(module=module1, title='توابع چندجمله‌ای', content='محتوای درس توابع چندجمله‌ای...', order=1)
        Lesson.objects.create(module=module1, title='توابع صعودی و نزولی', content='محتوای درس توابع صعودی و نزولی...', order=2)
        
        print("Sample modules and lessons created")

if __name__ == '__main__':
    seed()
