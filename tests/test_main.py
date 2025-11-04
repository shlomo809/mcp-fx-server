# tests/test_main.py
from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from app import main  # or your package entry

JSON = dict[str, Any]


class FakeResponse:
    def __init__(self, status: int = 200, payload: JSON | None = None) -> None:
        self.status = status
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise RuntimeError(f"status {self.status}")

    def json(self) -> JSON:
        return self._payload


def clear_cache() -> None:
    # however you clear your cache between tests; e.g.:
    main._cache.clear()


def test_get_rate_happy_path(monkeypatch: MonkeyPatch) -> None:
    def fake_get(self: Any, url: str, params: JSON | None = None) -> FakeResponse:
        assert "latest" in url
        assert params is not None
        base = params["base"]
        target = params["symbols"]
        return FakeResponse(
            200,
            {"base": base, "date": "2024-01-02", "rates": {target: 3.9}},
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    clear_cache()
    res = main.get_rate("usd", "ils")
    assert res.rate == 3.9
    assert res.base == "USD"
    assert res.target == "ILS"


def test_get_rate_same_currency_short_circuit(monkeypatch: MonkeyPatch) -> None:
    def fake_get(self: Any, url: str, params: JSON | None = None) -> FakeResponse:
        raise AssertionError("should not call provider when base == target")

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    res = main.get_rate("EUR", "EUR")
    assert res.rate == 1.0


def test_get_rate_uses_cache(monkeypatch: MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_get(self: Any, url: str, params: JSON | None = None) -> FakeResponse:
        calls.append("hit")
        return FakeResponse(200, {"base": "USD", "date": "2024-01-02", "rates": {"ILS": 3.8}})

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    clear_cache()
    first = main.get_rate("USD", "ILS")
    second = main.get_rate("USD", "ILS")
    assert first.rate == second.rate == 3.8
    assert calls == ["hit"]  # second call came from cache


def test_convert_happy_path(monkeypatch: MonkeyPatch) -> None:
    def fake_get(self: Any, url: str, params: JSON | None = None) -> FakeResponse:
        return FakeResponse(200, {"base": "USD", "date": "2024-01-02", "rates": {"EUR": 0.9}})

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    clear_cache()
    res = main.convert(100, "USD", "EUR")
    assert res.converted == pytest.approx(90.0)
    assert res.rate == pytest.approx(0.9)


def test_convert_same_currency() -> None:
    res = main.convert(123.45, "GBP", "GBP")
    assert res.converted == pytest.approx(123.45)
    assert res.rate == 1.0


def test_convert_uses_cached_rate(monkeypatch: MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_get(self: Any, url: str, params: JSON | None = None) -> FakeResponse:
        calls.append("hit")
        return FakeResponse(200, {"base": "USD", "date": "2024-01-02", "rates": {"JPY": 150.0}})

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    clear_cache()
    r1 = main.convert(2, "USD", "JPY")
    r2 = main.convert(3, "USD", "JPY")
    assert calls == ["hit"]
    assert r1.rate == r2.rate == pytest.approx(150.0)


def test_validation_currency_regex() -> None:
    # depending on your schema, this should raise a validation error:
    with pytest.raises(ValidationError):
        main.get_rate("us", "ILS")  # too short / lowercase without BeforeValidator hit, etc.


def test_provider_error_bubbles_as_runtime_error(monkeypatch: MonkeyPatch) -> None:
    def fake_get(self: Any, url: str, params: JSON | None = None) -> FakeResponse:
        return FakeResponse(500, {"error": "boom"})

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    clear_cache()
    with pytest.raises(RuntimeError):
        main.get_rate("USD", "ILS")
