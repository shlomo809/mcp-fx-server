from __future__ import annotations

import httpx


def make_client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": "mcp-fx/1.0"})


def fetch_rate(api_base: str, timeout: float, base: str, target: str) -> tuple[float, str | None]:
    url = f"{api_base}/latest"
    params: dict[str, str] = {"base": base, "symbols": target}
    with make_client(timeout) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    rate = float(data["rates"][target])
    fetched_at: str | None = data.get("date")
    return rate, fetched_at
