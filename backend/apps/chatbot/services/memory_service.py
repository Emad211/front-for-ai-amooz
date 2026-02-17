from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Literal, Optional

import redis

from apps.commons.llm_prompts import PROMPTS
from .llm_client import generate_text

Role = Literal['user', 'assistant', 'system']


def _get_env(name: str) -> str:
    return (os.getenv(name) or '').strip()


def _default_redis_url() -> str:
    # Works for local dev (host network) and docker-compose (service name).
    return _get_env('CHAT_REDIS_URL') or 'redis://localhost:6379/0'


@dataclass
class ConversationState:
    summary: str
    buffer: list[dict[str, str]]  # {role, content}
    activation_step: int
    updated_at: float


_in_memory_fallback: dict[str, ConversationState] = {}


class MemoryService:
    def __init__(
        self,
        *,
        thread_id: str,
        max_buffer_messages: int = 30,
        summarize_after_messages: int = 40,
    ) -> None:
        self.thread_id = thread_id

        env_max = _get_env('CHAT_MEMORY_MAX_BUFFER')
        env_sum_after = _get_env('CHAT_MEMORY_SUMMARIZE_AFTER')
        try:
            max_buffer_messages = int(env_max) if env_max else max_buffer_messages
        except Exception:
            pass
        try:
            summarize_after_messages = int(env_sum_after) if env_sum_after else summarize_after_messages
        except Exception:
            pass

        self.max_buffer_messages = max(6, int(max_buffer_messages))
        # Keep a slightly larger rolling window than `max_buffer_messages`, so we can
        # periodically summarize older turns into `summary`.
        self.summarize_after_messages = max(self.max_buffer_messages + 1, int(summarize_after_messages))

        self._redis: Optional[redis.Redis] = None
        try:
            self._redis = redis.Redis.from_url(_default_redis_url(), decode_responses=True, socket_timeout=1)
            # Ping to validate connection early.
            self._redis.ping()
        except Exception:
            self._redis = None

    def _key(self) -> str:
        return f'chat_memory:{self.thread_id}'

    def _load(self) -> ConversationState:
        now = time.time()
        if self._redis is None:
            state = _in_memory_fallback.get(self.thread_id)
            if state is None:
                state = ConversationState(summary='', buffer=[], activation_step=0, updated_at=now)
                _in_memory_fallback[self.thread_id] = state
            return state

        raw = self._redis.get(self._key())
        if not raw:
            return ConversationState(summary='', buffer=[], activation_step=0, updated_at=now)

        try:
            obj = json.loads(raw)
        except Exception:
            return ConversationState(summary='', buffer=[], activation_step=0, updated_at=now)

        summary = str(obj.get('summary') or '')
        activation_step = int(obj.get('activation_step') or 0)
        buffer = obj.get('buffer')
        if not isinstance(buffer, list):
            buffer = []

        cleaned: list[dict[str, str]] = []
        for item in buffer:
            if not isinstance(item, dict):
                continue
            role = str(item.get('role') or '').strip()
            content = str(item.get('content') or '').strip()
            if role not in {'user', 'assistant', 'system'}:
                continue
            if not content:
                continue
            cleaned.append({'role': role, 'content': content})

        return ConversationState(summary=summary, buffer=cleaned, activation_step=activation_step, updated_at=now)

    def _save(self, state: ConversationState) -> None:
        state.updated_at = time.time()

        if self._redis is None:
            _in_memory_fallback[self.thread_id] = state
            return

        payload = {
            'summary': state.summary,
            'buffer': state.buffer,
            'activation_step': state.activation_step,
            'updated_at': state.updated_at,
        }
        self._redis.set(self._key(), json.dumps(payload, ensure_ascii=False))

    def add(self, *, role: Role, content: str) -> None:
        text = (content or '').strip()
        if not text:
            return

        state = self._load()
        state.buffer.append({'role': role, 'content': text})

        # Allow the buffer to grow up to `summarize_after_messages`, then summarize the
        # oldest turns and keep a bounded recent tail.
        if len(state.buffer) > self.summarize_after_messages:
            self._summarize_and_archive(state)

        # Safety bound (in case summarization couldn't run for some reason).
        if len(state.buffer) > self.summarize_after_messages:
            state.buffer = state.buffer[-self.summarize_after_messages :]

        self._save(state)

    def set_activation_step(self, step: int) -> None:
        state = self._load()
        state.activation_step = max(0, int(step))
        self._save(state)

    def get_activation_step(self) -> int:
        return int(self._load().activation_step)

    def get_history_for_llm(self) -> tuple[str, str]:
        """Return (summary, history_str)"""
        state = self._load()
        # Format as a compact chat transcript.
        lines: list[str] = []
        for m in state.buffer:
            role = m.get('role')
            content = m.get('content')
            if role == 'user':
                lines.append(f'Student: {content}')
            elif role == 'assistant':
                lines.append(f'Amooz: {content}')
            else:
                lines.append(f'SYSTEM: {content}')

        return state.summary, '\n'.join(lines).strip()

    def _summarize_and_archive(self, state: ConversationState) -> None:
        # Summarize the oldest turns, keep a recent tail.
        overflow_count = max(0, len(state.buffer) - self.max_buffer_messages)
        if overflow_count <= 0:
            return

        to_summarize = state.buffer[:overflow_count]
        tail = state.buffer[overflow_count:]

        new_turns = '\n'.join([f"{m['role']}: {m['content']}" for m in to_summarize])
        prompt = PROMPTS['memory_summary']['default'].format(old_summary=state.summary, new_turns=new_turns)
        updated_summary = generate_text(contents=prompt, feature='memory_summary').text.strip()

        state.summary = updated_summary
        state.buffer = tail
