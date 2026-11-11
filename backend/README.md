# Backend — status and revival notes

`server.py` (1,537 lines) is the FastAPI backend from the Emergent.ai build:
46 routes covering auth, chat threads and messages, file upload + PDF
extraction, an MCP server control panel, phone integration endpoints
(location / battery / notification / clipboard), and the ClawCode engine
endpoints. `cli_routes.py` adds the CLI-specific routes (context sync,
session summarize, chat with context injection, agent tracking).

## Why it doesn't run as-is

Two tethers to the dead platform:

1. **`emergentintegrations`** — Emergent's proprietary LLM library. It is not
   published on PyPI (verified 2026-11-11), so the dependency cannot be
   installed. In `server.py` it is used at exactly two call sites
   (`LlmChat(...)` for thread chat and context chat). Revival = replace those
   two sites with a direct provider call (litellm, or the OpenAI / Google
   SDKs, both already in the original requirements).
2. **MongoDB** — the data layer uses `motor` (async MongoDB) and requires
   `MONGO_URL` and `DB_NAME` environment variables. Any local or hosted
   MongoDB instance satisfies this.

Everything else is standard: FastAPI, pydantic, PyJWT/passlib auth, httpx.

## Revival recipe (not yet done)

1. Stand up MongoDB, set `MONGO_URL` / `DB_NAME`.
2. Replace the `emergentintegrations.llm.chat` import with a thin local shim
   exposing the same `LlmChat` / `UserMessage` surface on top of a live
   provider.
3. Trim the original 100-line requirements dump to what the server actually
   imports.
4. Run the original `backend_test.py` suite (kept in the private archive)
   against it.

The ClawCode engine the server exposes (`/api/clawcode/*`) has no such
tethers — it lives dependency-free in `../clawcode/` and runs today.
