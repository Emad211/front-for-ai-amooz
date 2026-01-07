import json

import pytest


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.ping_called = 0

    def ping(self):
        self.ping_called += 1
        return True

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value: str):
        self.store[key] = value
        return True


@pytest.mark.unit
def test_memory_service_falls_back_to_in_memory_when_redis_unavailable(monkeypatch):
    from apps.chatbot.services import memory_service as ms

    def _raise(*_args, **_kwargs):
        raise RuntimeError('no redis')

    monkeypatch.setattr(ms.redis.Redis, 'from_url', staticmethod(_raise))

    mem = ms.MemoryService(thread_id='t1')
    mem.add(role='user', content='hi')
    mem.add(role='assistant', content='hello')

    summary, history = mem.get_history_for_llm()
    assert summary == ''
    assert 'Student: hi' in history
    assert 'Amooz: hello' in history


@pytest.mark.unit
def test_memory_service_uses_redis_when_available(monkeypatch):
    from apps.chatbot.services import memory_service as ms

    monkeypatch.delenv('CHAT_MEMORY_MAX_BUFFER', raising=False)
    monkeypatch.delenv('CHAT_MEMORY_SUMMARIZE_AFTER', raising=False)

    fake = FakeRedis()
    monkeypatch.setattr(ms.redis.Redis, 'from_url', staticmethod(lambda *_a, **_k: fake))

    mem = ms.MemoryService(thread_id='t2', max_buffer_messages=6, summarize_after_messages=8)
    mem.add(role='user', content='hello')

    # Ensure state was written to redis.
    raw = fake.get('chat_memory:t2')
    assert raw
    obj = json.loads(raw)
    assert obj['buffer'][0]['role'] == 'user'
    assert obj['buffer'][0]['content'] == 'hello'


@pytest.mark.unit
def test_memory_service_trims_buffer(monkeypatch):
    from apps.chatbot.services import memory_service as ms

    monkeypatch.delenv('CHAT_MEMORY_MAX_BUFFER', raising=False)
    monkeypatch.delenv('CHAT_MEMORY_SUMMARIZE_AFTER', raising=False)

    fake = FakeRedis()
    monkeypatch.setattr(ms.redis.Redis, 'from_url', staticmethod(lambda *_a, **_k: fake))

    # Avoid real LLM calls if summarization is triggered.
    monkeypatch.setattr(ms, 'generate_text', lambda *, contents, model=None: type('R', (), {'text': 'SUMMARY'})())

    mem = ms.MemoryService(thread_id='t3', max_buffer_messages=6, summarize_after_messages=7)
    mem.add(role='user', content='m1')
    mem.add(role='assistant', content='m2')
    mem.add(role='user', content='m3')
    mem.add(role='assistant', content='m4')
    mem.add(role='user', content='m5')
    mem.add(role='assistant', content='m6')
    mem.add(role='user', content='m7')
    mem.add(role='assistant', content='m8')

    _summary, history = mem.get_history_for_llm()
    # Only last 6 messages kept.
    assert 'm1' not in history
    assert 'm2' not in history
    assert 'm3' in history
    assert 'm4' in history
    assert 'm5' in history
    assert 'm6' in history
    assert 'm7' in history
    assert 'm8' in history


@pytest.mark.unit
def test_memory_service_summarizes_overflow(monkeypatch):
    from apps.chatbot.services import memory_service as ms

    monkeypatch.delenv('CHAT_MEMORY_MAX_BUFFER', raising=False)
    monkeypatch.delenv('CHAT_MEMORY_SUMMARIZE_AFTER', raising=False)

    fake = FakeRedis()
    monkeypatch.setattr(ms.redis.Redis, 'from_url', staticmethod(lambda *_a, **_k: fake))

    # Make summarizer deterministic.
    monkeypatch.setattr(ms, 'generate_text', lambda *, contents, model=None: type('R', (), {'text': 'SUMMARY'})())

    mem = ms.MemoryService(thread_id='t4', max_buffer_messages=6, summarize_after_messages=7)
    mem.add(role='user', content='u1')
    mem.add(role='assistant', content='a1')
    mem.add(role='user', content='u2')
    mem.add(role='assistant', content='a2')
    mem.add(role='user', content='u3')
    mem.add(role='assistant', content='a3')
    mem.add(role='user', content='u4')
    mem.add(role='assistant', content='a4')
    mem.add(role='user', content='u5')
    mem.add(role='assistant', content='a5')

    summary, history = mem.get_history_for_llm()
    assert summary == 'SUMMARY'
    # Tail remains and includes newest.
    assert 'a5' in history


@pytest.mark.unit
def test_activation_step_roundtrip(monkeypatch):
    from apps.chatbot.services import memory_service as ms

    fake = FakeRedis()
    monkeypatch.setattr(ms.redis.Redis, 'from_url', staticmethod(lambda *_a, **_k: fake))

    mem = ms.MemoryService(thread_id='t5')
    assert mem.get_activation_step() == 0
    mem.set_activation_step(2)
    assert mem.get_activation_step() == 2
