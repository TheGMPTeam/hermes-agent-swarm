# Free models available on this Nous Portal

Probed 2026-08-20 to find `:free` models usable as swarm worker roles. Result: only ONE is
agent-grade.

## Working (agent-grade, ≥64K context)
- `tencent/hy3:free` — used by all roles in `scripts/swarm.py` (`SWARM_MODEL`).
  Verified: returns text and runs fine as a subprocess worker.

## Exists but rejected
- `google/gemma-2-9b:free` — exists, but Hermes rejects it:
  *"context window of 8,192 tokens, which is below the minimum 64,000 required"*.
  Not usable for agent work.

## Does not exist (404)
Every other `:free` slug tested 404'd: `deepseek/*`, `qwen/*`, `moonshot/*`, `mistral/*`,
`meta/llama*`, `x-ai/*`, `anthropic/*`, `openai/*`, `minimax/*`, `nous/hermes*`, etc.
The only free slug that resolves is `tencent/hy3:free`.

## Paid models
`claude-opus-4.8`, `gpt-5.6-sol`, etc. **exist** but return *"Billing or credits
exhausted"*.

## How the probing was done (reusable technique)
- Raw `GET /v1/models` with the Portal `access_token` → HTTP **403** (Nous restricts model
  listing; the token in `auth.json` is not the chat credential).
- Brute-forcing chat with guessed slugs → 404 / "not found".
- **Reliable method:** `hermes chat -m "<model>" -q "say pong"` and read the error line:
  - *"not found"* → slug invalid
  - *"Billing or credits exhausted"* → exists, no credits
  - *"context window ... below minimum"* → exists, too small

## To use a stronger model later
- Change `SWARM_MODEL` in `scripts/swarm.py`, OR
- Per-task override: `hermes kanban set-model <task_id> <provider/model>`
  (takes effect on the next dispatch).
