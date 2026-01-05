import threading
from typing import Callable, Optional

from django.conf import settings


def run_in_background(target: Callable[[], None], *, name: Optional[str] = None) -> bool:
    """Runs target in a daemon thread when CLASS_PIPELINE_ASYNC is enabled.

    Returns True when a background thread was started, False when executed inline.
    """

    enabled = getattr(settings, 'CLASS_PIPELINE_ASYNC', True)
    if not enabled:
        target()
        return False

    thread = threading.Thread(target=target, name=name or getattr(target, '__name__', 'background'), daemon=True)
    thread.start()
    return True
