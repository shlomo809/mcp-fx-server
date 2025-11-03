import os
import re
import time
from typing import Any, Dict, Optional, Annotated

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, StringConstraints, BeforeValidator, validate_call

# ---------- Config ----------
API_BASE = os.getenv("FX_API_BASE", "https://api.frankfurter.dev/v1")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "6.0"))
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "30"))

# ---------- MCP App ----------
mcp = FastMCP(
    "mcp-fx",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000")),
)

# ---------- Tiny in-memory TTL cache ----------
_cache: Dict[str, tuple[float, Any]] = {}


def _cache_get(k: str):
    v = _cache.get(k)
    if not v:
        return None
    ts, val = v
    if time.time() - ts <= CACHE_TTL:
        return val
    _cache.pop(k, None)
    return None


def _cache_set(k: str, v: Any):
    _cache[k] = (time.time(), v)


def _client() -> httpx.Client:
    return httpx.Client(timeout=HTTP_TIMEOUT, headers={"User-Agent": "mcp-fx/1.0"})


# ---------- Pydantic parameter types ----------
def _to_upper(v: str) -> str:
    if not isinstance(v, str):
        raise TypeError("currency must be a string")
    return v.upper()


Currency = Annotated[
    str,
    BeforeValidator(_to_upper),
    Field(pattern=r"^[A-Z]{3}$", min_length=3, max_length=3),
]

NonNegativeAmount = Annotated[float, Field(ge=0)]


# ---------- Response models ----------
class RateResponse(BaseModel):
    base: str
    target: str
    rate: float
    fetched_at: Optional[str] = None
    provider: str = "frankfurter.dev"


class ConvertResponse(BaseModel):
    from_currency: str = Field(alias="from")
    to_currency: str = Field(alias="to")
    amount: float
    converted: float
    rate: float
    fetched_at: Optional[str] = None
    provider: str = "frankfurter.dev"


# ---------- Tools ----------
@validate_call
@mcp.tool()
def get_rate(base: Currency, target: Currency) -> RateResponse:
    """
    Return the current exchange rate for base -> target using Frankfurter.
    Internally calls: GET /latest?base=BASE&symbols=TARGET
    """
    if base == target:
        return RateResponse(base=base, target=target, rate=1.0, fetched_at=None)

    ck = f"rate:{base}:{target}"
    hit = _cache_get(ck)
    if hit:
        return RateResponse(**hit)

    url = f"{API_BASE}/latest"
    params = {"base": base, "symbols": target}
    try:
        with _client() as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        rate = float(data["rates"][target])
        fetched_at = data.get("date")  # Frankfurter returns YYYY-MM-DD
    except Exception as e:
        raise RuntimeError(f"Failed to fetch rate from Frankfurter: {e}") from e

    payload = {"base": base, "target": target, "rate": rate, "fetched_at": fetched_at}
    _cache_set(ck, payload)
    return RateResponse(**payload)


@validate_call
@mcp.tool()
def convert(
    amount: NonNegativeAmount, from_: Currency, to: Currency
) -> ConvertResponse:
    """
    Convert an amount from one currency to another (Frankfurter).
    Strategy: fetch latest rate via get_rate() and multiply.
    """
    if from_ == to:
        return ConvertResponse.model_validate(
            {
                "from": from_,
                "to": to,
                "amount": float(amount),
                "converted": float(amount),
                "rate": 1.0,
                "fetched_at": None,
            }
        )

    ck = f"rate:{from_}:{to}"
    hit = _cache_get(ck)
    if hit:
        rate = float(hit["rate"])
        fetched_at = hit.get("fetched_at")
    else:
        rate_resp = get_rate(from_, to)
        rate, fetched_at = rate_resp.rate, rate_resp.fetched_at

    converted = float(amount) * rate
    return ConvertResponse.model_validate(
        {
            "from": from_,
            "to": to,
            "amount": float(amount),
            "converted": converted,
            "rate": rate,
            "fetched_at": fetched_at,
        }
    )


# ---------- Entry point ----------
if __name__ == "__main__":
    # Remote-friendly MCP over HTTP at /mcp
    mcp.run(
        transport="streamable-http",
    )
