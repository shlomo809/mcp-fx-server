# tests/test_main.py
import sys
from pathlib import Path

# Add the parent directory (folder that contains main.py) to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import types
import httpx
import pytest
from pydantic import ValidationError
import main
# your server module


# --- helpers / fixtures ---


class DummyResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message="bad",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def clear_cache():
    # wipe the module-level TTL cache between tests
    main._cache.clear()
    yield
    main._cache.clear()


# --- tests ---


def test_get_rate_happy_path(monkeypatch):
    """USD->EUR returns a numeric rate and includes fetched_at."""

    def fake_get(self, url, params=None):
        assert url.endswith("/latest")
        assert params == {"base": "USD", "symbols": "EUR"}
        payload = {"base": "USD", "date": "2025-11-02", "rates": {"EUR": 0.92}}
        return DummyResp(payload=payload)

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    out = main.get_rate("usd", "eur")  # lower-case on purpose; validator upper-cases
    assert out.base == "USD" and out.target == "EUR"
    assert out.rate == 0.92
    assert out.fetched_at == "2025-11-02"
    assert out.provider == "frankfurter.dev"


def test_get_rate_same_currency_short_circuit(monkeypatch):
    """Same base/target should return rate=1.0 and not call HTTP."""
    calls = {"n": 0}

    def fake_get(self, url, params=None):
        calls["n"] += 1
        return DummyResp(payload={})

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    out = main.get_rate("JPY", "JPY")
    assert out.rate == 1.0
    assert calls["n"] == 0  # no HTTP call


def test_get_rate_uses_cache(monkeypatch):
    """Second call should hit cache (only 1 provider request)."""
    calls = {"n": 0}

    def fake_get(self, url, params=None):
        calls["n"] += 1
        return DummyResp(
            payload={"base": "USD", "date": "2025-11-02", "rates": {"EUR": 0.9}}
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    a = main.get_rate("USD", "EUR")
    b = main.get_rate("USD", "EUR")
    assert a.rate == b.rate == 0.9
    assert calls["n"] == 1  # cache hit on second call


def test_convert_happy_path(monkeypatch):
    """convert() should fetch rate (via /latest) and multiply amount."""

    def fake_get(self, url, params=None):
        assert params == {"base": "USD", "symbols": "JPY"}
        return DummyResp(
            payload={"base": "USD", "date": "2025-11-02", "rates": {"JPY": 150.0}}
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    out = main.convert(2, "USD", "JPY")
    assert out.rate == 150.0
    assert out.converted == 300.0
    assert out.from_currency == "USD" and out.to_currency == "JPY"
    assert out.provider == "frankfurter.dev"


def test_convert_same_currency():
    """No HTTP call; amount unchanged; rate=1.0."""
    out = main.convert(123.45, "EUR", "EUR")
    assert out.converted == 123.45
    assert out.rate == 1.0


def test_convert_uses_cached_rate(monkeypatch):
    """If get_rate ran before, convert should reuse cached rate (no extra HTTP)."""
    calls = {"n": 0}

    def fake_get(self, url, params=None):
        calls["n"] += 1
        return DummyResp(
            payload={"base": "USD", "date": "2025-11-02", "rates": {"ILS": 3.6}}
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    # prime cache
    r = main.get_rate("USD", "ILS")
    assert r.rate == 3.6 and calls["n"] == 1

    # convert should not trigger another HTTP call
    c = main.convert(10, "USD", "ILS")
    assert c.rate == 3.6 and c.converted == 36.0
    assert calls["n"] == 1


def test_validation_currency_regex():
    """Invalid currency code should raise pydantic ValidationError (validate_call)."""
    with pytest.raises(ValidationError):
        main.get_rate("US", "EUR")  # not 3 letters

    with pytest.raises(ValidationError):
        main.convert(10, "US$", "EUR")


def test_provider_error_bubbles_as_runtime_error(monkeypatch):
    """If provider returns non-JSON/shape, we raise RuntimeError with context."""

    def fake_get(self, url, params=None):
        return DummyResp(payload={"oops": "no rates here"})

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(RuntimeError) as e:
        main.get_rate("USD", "EUR")
    assert "Frankfurter" in str(e.value)
