from __future__ import annotations

# This module is retained for backward compatibility only. The canonical, robust
# LLM-JSON extractor now lives in ``apps.commons.json_utils`` (a single source of
# truth that merged the two historical, divergent copies). Importing from here
# continues to work for existing call sites.

from apps.commons.json_utils import (  # noqa: F401
    extract_json_object,
    _find_balanced_json_block,
    _normalize_llm_text,
    _remove_trailing_commas,
    _repair_broken_numbers,
    _repair_string_contents,
    _strip_code_fences,
)

__all__ = ["extract_json_object"]
