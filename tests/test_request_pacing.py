import pytest
from emporio import router


def test_sequential_requests_across_agents_are_spaced(monkeypatch):
    monkeypatch.setenv('EMPORIO_MIN_REQUEST_INTERVAL_SECONDS', '7')
    monkeypatch.setattr(router, '_last_provider_started', None)
    clock, sleeps = [100.0], []
    monkeypatch.setattr(router.time, 'monotonic', lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(router.time, 'sleep', sleep)
    router.pace_provider()
    clock[0] += 2
    router.pace_provider()
    assert sleeps == [5.0]
    assert router._last_provider_started == 107.0
    clock[0] += 8
    router.pace_provider()
    assert sleeps == [5.0]


def test_disabled_pacing_does_not_sleep(monkeypatch):
    monkeypatch.setenv('EMPORIO_MIN_REQUEST_INTERVAL_SECONDS', '0')
    monkeypatch.setattr(router.time, 'sleep', lambda seconds: pytest.fail('Unexpected sleep'))
    router.pace_provider()


def test_invalid_pacing_is_rejected_before_any_provider_request(monkeypatch):
    monkeypatch.setenv('EMPORIO_MIN_REQUEST_INTERVAL_SECONDS', 'nan')
    with pytest.raises(ValueError, match='finite'):
        router.pace_provider()
