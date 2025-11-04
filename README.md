# mcp-fx-server

A small Model Context Protocol (MCP) server that exposes two tools for live currency exchange:

- `get_rate(base, target)` — returns the current exchange rate
- `convert(amount, from_currency, to_currency)` — converts an amount using the latest rate

The server speaks MCP over HTTP using **server-sent events (SSE)** and **JSON-RPC 2.0**, fetches rates from a public FX API, validates I/O with Pydantic v2, and applies a simple in-memory TTL cache. See [app/main.py](app/main.py), [app/provider.py](app/provider.py), and [app/cache.py](app/cache.py) for the core logic.

---

## Highlights & techniques

- **MCP over SSE with JSON-RPC 2.0**
  Uses the `streamable-http` transport (SSE). Clients must send an `Accept` header that includes both `application/json` and `text/event-stream`. See MDN on [Server-Sent Events](https://developer.mozilla.org/docs/Web/API/Server-sent_events) and [HTTP `Accept` content negotiation](https://developer.mozilla.org/docs/Web/HTTP/Content_negotiation#the_accept_header).

- **Typed request/response contracts with Pydantic v2**
  Strong validation via `Annotated` constraints and `validate_call` in [app/schemas.py](app/schemas.py). Enforces 3-letter ISO currency codes and non-negative amounts.

- **Application-layer TTL cache**
  Minimal in-memory cache with per-key TTL in [app/cache.py](app/cache.py). Tuned via `CACHE_TTL_SECONDS`. Keeps responses fast while the upstream provider’s data is stable. (Contrast with MDN’s overview of [HTTP caching](https://developer.mozilla.org/docs/Web/HTTP/Caching) — this cache is deliberate, server-side, and explicit.)

- **Small, testable provider boundary**
  HTTP calls isolated in [app/provider.py](app/provider.py) using `httpx` with timeouts and a scoped `User-Agent`. Tests monkey-patch the `httpx.Client.get` method to simulate provider responses without network I/O (see [tests/test_main.py](tests/test_main.py)).

- **Straightforward, configurable logging**
  Centralized setup in [app/logging_utils.py](app/logging_utils.py). Uses stdlib `logging`, level set via `LOG_LEVEL`. Emits concise, grep-friendly lines; can be extended to JSON if needed.

- **Production-lean Docker image**
  Based on `python:3.12-slim`, non-root user, health check for `/mcp`, and a clean `CMD` that runs the app as a module (see [Dockerfile](Dockerfile)).

- **Tight feedback loop via toolchain**
  - Pre-commit pipeline with Ruff, Black, and MyPy (see [.pre-commit-config.yaml](.pre-commit-config.yaml)).
  - Strict-ish MyPy config and editor-friendly line lengths (see [pyproject.toml](pyproject.toml)).
  - CI with GitHub Actions and **uv** for reproducible installs (see [.github/workflows/ci.yml](.github/workflows/ci.yml)).

---

## Notable dependencies (and why they matter)

- **Model Context Protocol (MCP)** — `mcp` Python package implementing the MCP spec and transports.

  - Spec: <https://modelcontextprotocol.io/>
  - Python package: <https://pypi.org/project/mcp/>

- **httpx** — modern HTTP client with async/timeout support and a clean API.
  <https://www.python-httpx.org/>

- **Pydantic v2** — data validation and settings with fast `pydantic-core`.
  <https://docs.pydantic.dev/>

- **Uvicorn** (via FastMCP) — ASGI server that backs the SSE transport.
  <https://www.uvicorn.org/>

- **Ruff / Black / MyPy / Pytest / pre-commit** — code quality, formatting, typing, tests, and local hooks.

  - Ruff: <https://docs.astral.sh/ruff/>
  - Black: <https://black.readthedocs.io/>
  - MyPy: <https://mypy.readthedocs.io/>
  - Pytest: <https://docs.pytest.org/>
  - pre-commit: <https://pre-commit.com/>

- **uv** — fast Python project and dependency manager used in CI.
  <https://docs.astral.sh/uv/>

> Fonts: none are used in this project.

---

## Project structure

```text
.
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ cache.py
│  ├─ provider.py
│  ├─ schemas.py
│  └─ logging_utils.py
├─ tests/
├─ .github/
│  └─ workflows/
├─ .pre-commit-config.yaml
├─ pyproject.toml
├─ requirements.txt
├─ Dockerfile
├─ .env.example
└─ README.md
```

**Directory notes**

- **app/** — runtime code

  - **main.py** — MCP server definition, tools (`get_rate`, `convert`), and wiring.
  - **provider.py** — outbound HTTP calls and response shaping.
  - **cache.py** — in-memory TTL cache (simple and explicit).
  - **schemas.py** — request/response models and validators.
  - **logging_utils.py** — centralized logging setup.

- **tests/** — unit tests for server tools and provider behavior (uses `pytest` and `monkeypatch`).

- **.github/workflows/** — CI pipeline using **uv** for deterministic installs, then Ruff/Black/MyPy/Pytest.

- **.env.example** — environment variables for local runs.

### To run your code

    *Localy*

# from repo root

uv sync

# optional: copy the example env and tweak

cp .env.example .env

# run with env file (defaults shown)

uv run --env-file .env python -m app.main

# logs should show something like: "listening on 0.0.0.0:8000"

    *Docker*
    # build

docker build -t mcp-fx:local .

# run docer with recomended env

docker run --rm -p 8000:8000 \
 -e PORT=8000 \
 -e FX_API_BASE=https://api.frankfurter.dev/v1 \
 -e HTTP_TIMEOUT=6.0 \
 -e CACHE_TTL_SECONDS=30 \
 -e LOG_LEVEL=INFO \
 -e LOG_STYLE=plain \
 mcp-fx:local

To test the mcp you can use modelcontextprotocol inspector.

use ut by runing npx @modelcontextprotocol/inspector,

Then:

Transport: Streamable HTTP

URL:

Local: http://localhost:8000/mcp

Render: https://mcp-fx-server.onrender.com/mcp
