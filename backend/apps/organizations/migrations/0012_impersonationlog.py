"""Risman step 4: ``ImpersonationLog`` — the append-only audit of direct logins.

Written by hand to mirror the model exactly (and pinned by
``makemigrations --check``): one row per impersonation session, ``ended_at``
closing it. No data migration, no backfill — sessions before this table simply
never happened, same doctrine as ``AdvisoryAccessLog``.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('organizations', '0011_alter_orgmembership_org_role_advisor'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImpersonationLog',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID',
                    ),
                ),
                ('started_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                (
                    'manager',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='impersonations_started',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='مدیر',
                    ),
                ),
                (
                    'target_user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='impersonated_sessions',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='کاربر هدف',
                    ),
                ),
                (
                    'organization',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='impersonation_logs',
                        to='organizations.organization',
                        verbose_name='سازمان',
                    ),
                ),
            ],
            options={
                'verbose_name': 'ورود مستقیم',
                'verbose_name_plural': 'ورودهای مستقیم',
                'ordering': ['-started_at'],
                'indexes': [
                    models.Index(
                        fields=['manager', '-started_at'],
                        name='idx_implog_mgr_time',
                    ),
                    models.Index(
                        fields=['target_user', '-started_at'],
                        name='idx_implog_target_time',
                    ),
                ],
            },
        ),
    ]
