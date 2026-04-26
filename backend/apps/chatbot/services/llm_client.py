from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from apps.commons.llm_prompts import PROMPTS
from apps.commons.json_utils import extract_json_object
from apps.commons.token_tracker import (
    track_llm_usage,
    track_llm_error,
    LLMTimer,
)
from apps.commons.models import LLMUsageLog


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _default_model() -> str:
    return _get_env("CHAT_MODEL") or "gemini-2.5-flash"


# ----------------------------------------
# GapGPT Client (using AVALAI env names)
# ----------------------------------------
def _get_client() -> OpenAI:

    api_key = _get_env("AVALAI_API_KEY")
    base_url = _get_env("AVALAI_BASE_URL") or "https://api.gapgpt.app/v1"

    if not api_key:
        raise RuntimeError("AVALAI_API_KEY is not configured")

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
    )


@dataclass
class LlmResult:
    text: str
    provider: str
    model: str


def _extract_text(resp: Any) -> str:

    try:
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def generate_text(*, contents: Any, model: Optional[str] = None, feature: Optional[str] = None) -> LlmResult:

    client = _get_client()
    used_model = model or _default_model()

    timer = LLMTimer().start()

    try:

        response = client.chat.completions.create(
            model=used_model,
            messages=[
                {"role": "user", "content": contents}
            ],
        )

        text = _extract_text(response)

        if not text:
            raise ValueError("Empty LLM response")

        track_llm_usage(
            resp=response,
            feature=feature or LLMUsageLog.Feature.OTHER,
            provider="gapgpt",
            model_name=used_model,
            duration_ms=timer.elapsed_ms,
        )

        return LlmResult(
            text=text,
            provider="gapgpt",
            model=used_model,
        )

    except Exception as exc:

        track_llm_error(
            feature=feature or LLMUsageLog.Feature.OTHER,
            provider="gapgpt",
            model_name=used_model,
            error_message=str(exc),
        )

        raise


# ----------------------------------------
# JSON generation helper
# ----------------------------------------
def _repair_json_with_llm(*, feature: str, model_output: str) -> dict[str, Any]:

    template = PROMPTS["json_repair"]["default"]

    prompt = template.replace("{raw_text}", model_output)

    repaired = generate_text(
        contents=prompt,
        feature=LLMUsageLog.Feature.JSON_REPAIR,
    ).text

    try:
        obj = extract_json_object(repaired)
        return obj if isinstance(obj, dict) else {"result": obj}
    except Exception:
        return {}


def generate_json(*, feature: str, contents: Any) -> dict[str, Any]:

    out = generate_text(
        contents=contents,
        feature=feature,
    ).text

    if not out.strip():
        return _repair_json_with_llm(feature=feature, model_output=out)

    try:
        obj = extract_json_object(out)
        return obj if isinstance(obj, dict) else {"result": obj}

    except Exception:
        return _repair_json_with_llm(feature=feature, model_output=out)
