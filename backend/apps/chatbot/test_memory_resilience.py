"""Chat MemoryService resilience — a corrupt or hostile cache entry must never
crash a student's chat turn.

The happy paths (redis vs in-memory fallback, trim, overflow-summarize, activation
round-trip, `_safe_template_replace` brace-survival) are already covered in
`test_memory_service_unit.py` / `test_vision_and_json_mode.py`. This file adds the
degrade-gracefully branches of `_load` + the empty-`add` guard + the non-str-key
skip in `_safe_template_replace` — all previously untested, all LLM-free.
"""
import json

import pytest

pytestmark = pytest.mark.unit


class FakeRedis:
    def __init__(self):
        self.store = {}

    def ping(self):
        return True

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value
        return True


def _mem(monkeypatch, thread_id, seed=None):
    from apps.chatbot.services import memory_service as ms

    fake = FakeRedis()
    if seed is not None:
        fake.store[f'chat_memory:{thread_id}'] = seed
    monkeypatch.setattr(ms.redis.Redis, 'from_url', staticmethod(lambda *_a, **_k: fake))
    # Never hit a real LLM even if summarization triggers.
    monkeypatch.setattr(
        ms, 'generate_text',
        lambda *, contents, feature=None, model=None, **_: type('R', (), {'text': 'S'})(),
    )
    return ms.MemoryService(thread_id=thread_id, max_buffer_messages=6, summarize_after_messages=7)


def test_add_ignores_empty_and_whitespace(monkeypatch):
    mem = _mem(monkeypatch, 't-empty')
    mem.add(role='user', content='')
    mem.add(role='user', content='   ')
    _summary, history = mem.get_history_for_llm()
    assert history == ''  # no phantom turns
    mem.add(role='user', content='real')
    _s, history2 = mem.get_history_for_llm()
    assert 'real' in history2


def test_fresh_thread_returns_empty_baseline(monkeypatch):
    mem = _mem(monkeypatch, 't-fresh')
    assert mem.get_history_for_llm() == ('', '')


def test_load_degrades_gracefully_on_corrupt_json(monkeypatch):
    mem = _mem(monkeypatch, 't-corrupt', seed='}{ not json at all')
    # A garbage cache entry must not raise — it resets to an empty state.
    assert mem.get_history_for_llm() == ('', '')


def test_load_ignores_non_list_buffer(monkeypatch):
    seed = json.dumps({'summary': 'KEEP', 'buffer': 'not-a-list', 'activation_step': 0})
    mem = _mem(monkeypatch, 't-badbuf', seed=seed)
    summary, history = mem.get_history_for_llm()
    assert summary == 'KEEP'   # scalar summary still honored
    assert history == ''       # non-list buffer coerced to empty, no crash


def test_load_skips_malformed_buffer_items(monkeypatch):
    seed = json.dumps({
        'summary': '',
        'buffer': [
            'i-am-a-string-not-a-dict',                    # not a dict → skip
            {'role': 'user', 'content': ''},               # empty content → skip
            {'role': 'martian', 'content': 'hi'},          # bad role → skip
            {'role': 'user', 'content': 'valid-turn'},     # keeper
        ],
        'activation_step': 0,
    })
    mem = _mem(monkeypatch, 't-malformed', seed=seed)
    _summary, history = mem.get_history_for_llm()
    assert 'valid-turn' in history
    assert 'martian' not in history
    assert 'i-am-a-string' not in history


def test_safe_template_replace_skips_non_str_keys(monkeypatch):
    from apps.chatbot.services.memory_service import _safe_template_replace
    # A non-str key must be skipped (not crash); str keys still substitute.
    out = _safe_template_replace('{a} and {b}', {1: 'X', 'a': 'AA', 'b': 'BB'})
    assert out == 'AA and BB'


def test_activation_step_survives_corrupt_reload(monkeypatch):
    """A corrupt entry resets activation_step to 0 rather than propagating junk."""
    mem = _mem(monkeypatch, 't-act', seed='not-json')
    assert mem.get_activation_step() == 0
