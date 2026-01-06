import logging
import threading
from typing import Callable, Optional

from django.conf import settings


logger = logging.getLogger(__name__)


def run_in_background(target: Callable[[], None], *, name: Optional[str] = None) -> bool:
    """Runs target in a daemon thread when CLASS_PIPELINE_ASYNC is enabled.

    Returns True when a background thread was started, False when executed inline.
    """

    enabled = getattr(settings, 'CLASS_PIPELINE_ASYNC', True)
    if not enabled:
        target()
        return False

    task_name = name or getattr(target, '__name__', 'background')

    def _runner() -> None:
        try:
            target()
        except Exception:
            logger.exception('Background task failed: %s', task_name)

    thread = threading.Thread(target=_runner, name=task_name, daemon=True)
    thread.start()
    return True
