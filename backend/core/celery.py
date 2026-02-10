"""Celery application for AI_AMOOZ.

This module bootstraps Celery so that Django settings (prefixed with ``CELERY_``)
are picked up automatically and tasks inside installed apps are auto-discovered.
"""
from __future__ import annotations

import logging
import os
import time

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun, task_retry, task_success

# Make sure Django settings are available before Celery starts.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('ai_amooz')

# Read config keys from Django settings that start with ``CELERY_``.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover ``tasks.py`` in every installed app.
app.autodiscover_tasks()


_celery_logger = logging.getLogger('core.celery')


def _safe_repr(value, limit: int = 500) -> str:
	try:
		text = repr(value)
	except Exception:
		return '<unrepr-able>'
	if len(text) > limit:
		return f'{text[:limit]}…'
	return text


@task_prerun.connect
def _log_task_start(sender=None, task_id=None, task=None, args=None, kwargs=None, **_):
	try:
		if task is not None and getattr(task, 'request', None) is not None:
			task.request._start_time = time.monotonic()
	except Exception:
		pass

	name = getattr(sender, 'name', None) or '<unknown>'
	_celery_logger.info(
		'Celery start name=%s id=%s args=%s kwargs=%s',
		name,
		task_id,
		_safe_repr(args),
		_safe_repr(kwargs),
	)


@task_success.connect
def _log_task_success(sender=None, result=None, **_):
	name = getattr(sender, 'name', None) or '<unknown>'
	_celery_logger.info('Celery success name=%s result=%s', name, _safe_repr(result))


@task_retry.connect
def _log_task_retry(sender=None, request=None, reason=None, **_):
	name = getattr(sender, 'name', None) or '<unknown>'
	task_id = getattr(request, 'id', None)
	_celery_logger.warning(
		'Celery retry name=%s id=%s reason=%s',
		name,
		task_id,
		_safe_repr(reason),
	)


@task_failure.connect
def _log_task_failure(sender=None, task_id=None, exception=None, traceback=None, **_):
	name = getattr(sender, 'name', None) or '<unknown>'
	_celery_logger.error(
		'Celery failure name=%s id=%s exc=%s',
		name,
		task_id,
		_safe_repr(exception),
		exc_info=True,
	)


@task_postrun.connect
def _log_task_postrun(sender=None, task_id=None, task=None, state=None, **_):
	name = getattr(sender, 'name', None) or '<unknown>'
	duration_ms = None
	try:
		if task is not None and getattr(task, 'request', None) is not None:
			start = getattr(task.request, '_start_time', None)
			if start is not None:
				duration_ms = int((time.monotonic() - start) * 1000)
	except Exception:
		duration_ms = None

	if duration_ms is None:
		_celery_logger.info('Celery done name=%s id=%s state=%s', name, task_id, state)
	else:
		_celery_logger.info(
			'Celery done name=%s id=%s state=%s duration_ms=%s',
			name,
			task_id,
			state,
			duration_ms,
		)
