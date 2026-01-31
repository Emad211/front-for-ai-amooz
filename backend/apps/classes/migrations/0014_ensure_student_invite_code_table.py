from django.db import migrations


def ensure_student_invite_code_table(apps, schema_editor):
    StudentInviteCode = apps.get_model('classes', 'StudentInviteCode')
    table_name = StudentInviteCode._meta.db_table

    existing_tables = set(schema_editor.connection.introspection.table_names())
    if table_name in existing_tables:
        return

    schema_editor.create_model(StudentInviteCode)


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0013_student_invite_code'),
    ]

    operations = [
        migrations.RunPython(ensure_student_invite_code_table, reverse_code=migrations.RunPython.noop),
    ]
