from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("classes", "0034_student_exercise_answer_ocr"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentexerciseanswerasset",
            name="deactivated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
