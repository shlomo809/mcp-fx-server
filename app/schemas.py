from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


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


class RateResponse(BaseModel):
    base: str
    target: str
    rate: float
    fetched_at: str | None = None
    provider: str = "frankfurter.dev"


class ConvertResponse(BaseModel):
    from_currency: str
    to_currency: str
    amount: float
    converted: float
    rate: float
    fetched_at: str | None = None
    provider: str = "frankfurter.dev"
