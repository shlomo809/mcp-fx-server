# mcp-fx-server

A small **Model Context Protocol (MCP)** server that exposes two tools for live currency exchange:

- `get_rate(base, target)` — returns the current exchange rate
- `convert(amount, from_currency, to_currency)` — converts an amount using the latest rate

The server speaks MCP over HTTP using **Server-Sent Events (SSE)** and **JSON-RPC 2.0**, fetches rates from a public FX API, validates I/O with Pydantic v2, and applies a simple in-memory TTL cache.

See [app/main.py](app/main.py), [app/provider.py](app/provider.py), and [app/cache.py](app/cache.py) for the core logic.

---

## Highlights & Techniques

- **MCP over SSE with JSON-RPC 2.0**
  Uses the `streamable-http` transport (SSE). Clients must send an `Accept` header that includes both `application/json` and `text/event-stream`.
  See MDN on [Server-Sent Events](https://developer.mozilla.org/docs/Web/API/Server-sent_events) and [HTTP `Accept` content negotiation](https://developer.mozilla.org/docs/Web/HTTP/Content_negotiation#the_accept_header).

- **Typed request/response contracts with Pydantic v2**
  Strong validation via `Annotated` constraints and `validate_call` in [app/schemas.py](app/schemas.py).
  Enforces 3-letter ISO currency codes and non-negative amounts.

- **Application-layer TTL cache**
  Minimal in-memory cache with per-key TTL in [app/cache.py](app/cache.py).
  Tuned via `CACHE_TTL_SECONDS`. Keeps responses fast while the upstream provider’s data is stable.
  (Contrast with MDN’s overview of [HTTP caching](https://developer.mozilla.org/docs/Web/HTTP/Caching) — this cache is deliberate, server-side, and explicit.)

- **Small, testable provider boundary**
  HTTP calls isolated in [app/provider.py](app/provider.py) using `httpx` with timeouts and a scoped `User-Agent`.
  Tests monkey-patch the `httpx.Client.get` method to simulate provider responses without network I/O (see [tests/test_main.py](tests/test_main.py)).

- **Straightforward, configurable logging**
  Centralized setup in [app/logging_utils.py](app/logging_utils.py).
  Uses stdlib `logging`, level set via `LOG_LEVEL`. Emits concise, grep-friendly lines; can be extended to JSON if needed.

- **Production-lean Docker image**
  Based on `python:3.12-slim`, non-root user, health check for `/mcp`, and a clean `CMD` that runs the app as a module (see [Dockerfile](Dockerfile)).

- **Tight feedback loop via toolchain**

  - Pre-commit pipeline with Ruff, Black, and MyPy (see [.pre-commit-config.yaml](.pre-commit-config.yaml))
  - Strict MyPy config and editor-friendly line lengths (see [pyproject.toml](pyproject.toml))
  - CI with GitHub Actions and **uv** for reproducible installs (see [.github/workflows/ci.yml](.github/workflows/ci.yml))

---

## Notable Dependencies

- **Model Context Protocol (MCP)** — Python implementation of the MCP spec

  - Spec: [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)
  - Package: [https://pypi.org/project/mcp/](https://pypi.org/project/mcp/)

- **httpx** — modern HTTP client with async and timeout support
  [https://www.python-httpx.org/](https://www.python-httpx.org/)

- **Pydantic v2** — data validation and settings using `pydantic-core`
  [https://docs.pydantic.dev/](https://docs.pydantic.dev/)

- **Uvicorn** — ASGI server (used by FastMCP under the hood)
  [https://www.uvicorn.org/](https://www.uvicorn.org/)

- **Ruff / Black / MyPy / Pytest / pre-commit** — code quality, formatting, typing, testing

  - Ruff: [https://docs.astral.sh/ruff/](https://docs.astral.sh/ruff/)
  - Black: [https://black.readthedocs.io/](https://black.readthedocs.io/)
  - MyPy: [https://mypy.readthedocs.io/](https://mypy.readthedocs.io/)
  - Pytest: [https://docs.pytest.org/](https://docs.pytest.org/)
  - pre-commit: [https://pre-commit.com/](https://pre-commit.com/)

- **uv** — fast dependency and environment manager
  [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)

> Fonts: none are used in this project.

---

## Project Structure

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

**Directory notes:**

- **app/** — runtime logic

  - **main.py** — MCP server definition and tool registration (`get_rate`, `convert`)
  - **provider.py** — outbound HTTP client logic
  - **cache.py** — simple in-memory TTL cache
  - **schemas.py** — Pydantic models and type validators
  - **logging_utils.py** — centralized logging configuration

- **tests/** — unit tests with `pytest` and `monkeypatch`
- **.github/workflows/** — CI setup using `uv`, Ruff, Black, MyPy, and Pytest

---

## ⚙️ Configuration

This project uses environment variables for configuration.
Example `.env`:

```env
# Server
PORT=8000

# FX provider
FX_API_BASE=https://api.frankfurter.dev/v1
HTTP_TIMEOUT=6.0

# Caching (seconds)
CACHE_TTL_SECONDS=30

# Logging
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_STYLE=plain         # plain or json
```

---

## 🚀 Deployment & Local Testing

### Run Locally

```bash
# From repo root
uv sync

# Optional: copy and edit env file
cp .env.example .env

# Run with env vars
uv run --env-file .env python -m app.main
```

Logs should show:

```
INFO: starting MCP server on port 8000
```

### Run with Docker

```bash
# Build image
docker build -t mcp-fx:local .

# Run container
docker run --rm -p 8000:8000 \
  -e PORT=8000 \
  -e FX_API_BASE=https://api.frankfurter.dev/v1 \
  -e HTTP_TIMEOUT=6.0 \
  -e CACHE_TTL_SECONDS=30 \
  -e LOG_LEVEL=INFO \
  -e LOG_STYLE=plain \
  mcp-fx:local
```

MCP endpoint:

```
http://localhost:8000/mcp
```

---

## 🧠 MCP Inspector (Optional)

You can test your MCP tools interactively using the [Model Context Protocol Inspector](https://www.npmjs.com/package/@modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector
```

Then select:

- **Transport:** Streamable HTTP
- **URL:**

  - Local: `http://localhost:8000/mcp`
  - Render: `https://mcp-fx-server.onrender.com/mcp`

Once connected, use “List Tools” → try `get_rate` or `convert`.

---
