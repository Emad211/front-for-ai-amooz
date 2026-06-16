from django.db import migrations, models


def set_managers_org_only(apps, schema_editor):
    """Existing MANAGERs never get a personal/freelancer space.

    The field default (True) is applied to every existing row by the AddField
    above; flip platform managers back to False so the flag is semantically
    correct. (Existing TEACHERs keep True — today they all have a personal space.)
    """
    User = apps.get_model('accounts', 'User')
    User.objects.filter(role='MANAGER').update(is_freelancer=False)


def noop_reverse(apps, schema_editor):
    # Reverse of the migration drops the column, so there is nothing to undo here.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_freelancer',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(set_managers_org_only, noop_reverse),
    ]
