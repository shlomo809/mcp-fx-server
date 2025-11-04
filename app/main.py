# main.py
from __future__ import annotations

import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import validate_call

from app.cache import TTLCache
from app.logging_conf import setup_logging
from app.provider import fetch_rate
from app.schemas import (
    ConvertResponse,
    Currency,
    NonNegativeAmount,
    RateResponse,
)

# ---------- Config ----------
API_BASE = os.getenv("FX_API_BASE", "https://api.frankfurter.dev/v1")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "6.0"))
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "30"))

# ---------- Logging ----------

setup_logging()  # configures root handlers/format
log = logging.getLogger("mcp.fx")
# ---------- MCP App ----------
mcp = FastMCP(
    "mcp-fx",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000")),
)

# ---------- Cache ----------
_cache = TTLCache(CACHE_TTL)


# ---------- Tools ----------
@validate_call
@mcp.tool()
def get_rate(base: Currency, target: Currency) -> RateResponse:
    """
    Return the current exchange rate for base -> target using Frankfurter.
    Internally calls: GET /latest?base=BASE&symbols=TARGET
    """
    if base == target:
        log.debug("get_rate short-circuit: %s == %s", base, target)
        return RateResponse(base=base, target=target, rate=1.0, fetched_at=None)

    ck = f"rate:{base}:{target}"
    hit = _cache.get(ck)
    if hit:
        log.debug("cache HIT for %s", ck)
        return RateResponse(**hit)

    log.debug("cache MISS for %s; fetching from provider", ck)
    try:
        rate, fetched_at = fetch_rate(API_BASE, HTTP_TIMEOUT, base, target)
    except Exception as e:
        log.exception("provider error for %s->%s", base, target)
        raise RuntimeError(f"Failed to fetch rate from provider: {e}") from e

    payload: dict[str, Any] = {
        "base": base,
        "target": target,
        "rate": rate,
        "fetched_at": fetched_at,
    }
    _cache.set(ck, payload)
    return RateResponse(**payload)


@validate_call
@mcp.tool()
def convert(
    amount: NonNegativeAmount,
    from_currency: Currency,
    to_currency: Currency,
) -> ConvertResponse:
    """
    Convert an amount from one currency to another (Frankfurter).
    Strategy: fetch latest rate via get_rate() and multiply.
    """
    if from_currency == to_currency:
        log.debug("convert short-circuit: %s == %s", from_currency, to_currency)
        return ConvertResponse.model_validate(
            {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "amount": float(amount),
                "converted": float(amount),
                "rate": 1.0,
                "fetched_at": None,
            }
        )

    ck = f"rate:{from_currency}:{to_currency}"
    hit = _cache.get(ck)
    if hit:
        log.debug("convert using cached rate for %s", ck)
        rate = float(hit["rate"])
        fetched_at: str | None = hit.get("fetched_at")
    else:
        log.debug("convert fetching rate via get_rate for %s", ck)
        rate_resp = get_rate(from_currency, to_currency)
        rate, fetched_at = rate_resp.rate, rate_resp.fetched_at

    converted = float(amount) * rate
    return ConvertResponse.model_validate(
        {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount": float(amount),
            "converted": converted,
            "rate": rate,
            "fetched_at": fetched_at,
        }
    )


# ---------- Entry point ----------
if __name__ == "__main__":
    log.info("starting MCP server on port %s", os.getenv("PORT", "8000"))
    mcp.run(transport="streamable-http")
