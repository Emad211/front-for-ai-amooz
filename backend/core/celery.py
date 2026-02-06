"""Celery application for AI_AMOOZ.

This module bootstraps Celery so that Django settings (prefixed with ``CELERY_``)
are picked up automatically and tasks inside installed apps are auto-discovered.
"""
from __future__ import annotations

import os

from celery import Celery

# Make sure Django settings are available before Celery starts.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('ai_amooz')

# Read config keys from Django settings that start with ``CELERY_``.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover ``tasks.py`` in every installed app.
app.autodiscover_tasks()
