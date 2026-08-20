---
name: agent-swarm
description: "Use when the user wants autonomous multi-agent swarms — role-based subagent profiles that stay IDLE until invoked, then run a Kanban swarm driven by the gateway dispatcher, staying live to pick up and continue work until the task tree completes. Trigger on: 'swarm', 'run agents autonomously', 'subagent profiles', 'start the swarm', 'autonomous task agents', 'feed it a swarm'."
version: 1.1.0
author: TheGMPTeam
license: MIT
metadata:
  hermes:
    tags: [multi-agent, swarm, kanban, autonomous, delegation, profiles, vision]
---

# Agent Swarm (idle-by-default, live-on-call)

A reusable swarm harness: 6 role-based Hermes **profiles** (isolated agent identities)
that do nothing until you call them, then run a **Kanban swarm** (parallel workers →
verifier → synthesizer) driven by the gateway's embedded dispatcher. The dispatcher
stays live to pick up and continue work; the swarm only stands down (idles) when the
whole task tree is complete (root + verifier + synthesizer marked done).

## Idle vs Live semantics (the core design)
- **IDLE by default** — no swarm processes run. Profiles exist on disk but are not spawned.
- **On call** — `launch` builds a swarm graph on the Kanban board. The gateway
  dispatcher (launchd-supervised, `hermes gateway status`) claims ready tasks and
  spawns the assigned profile as a real subprocess.
- **LIVE until done** — the dispatcher keeps ticking (default every 60s) and picks up
  any task that becomes ready, so workers → verifier → synthesizer flow automatically
  and continue across the board. Nothing is torn down mid-task.
- **Stands down only on completion** — when the root swarm card is `done`, the swarm is
  finished. (Use `stop` to manually stand down early.)

## Role profiles (created by `setup`) — each fit to its role
| Profile        | Model (provider)                              | Context | Role |
|----------------|-----------------------------------------------|---------|------|
| `researcher`   | `meituan/longcat-2.0:free` (nous)            | 1M      | Web research, source extraction, fact-checking, citations |
| `writer`       | `meituan/longcat-2.0:free` (nous)            | 1M      | Docs, READMEs, polished user-facing copy |
| `orchestrator` | `meituan/longcat-2.0:free` (nous)            | 1M      | Decompose goals + synthesize final deliverable (holds whole tree) |
| `coder`        | `upstage/solar-pro4:free` (nous)             | 512K    | Code, debugging, builds, tests, empirical verification |
| `verifier`     | `upstage/solar-pro4:free` (nous)             | 512K    | QA gate — correctness, broken tests/links, unmet reqs |
| `visioner`     | `minicpm-v4.6:latest` (**local ollama @ 10.0.0.120:11434**) | — | **Vision/UI inspection** — sees screenshots & UI, reports what it sees |

Models are fit to role by context need (verified working free models on this Portal).
Change `LONGCAT` / `SOLAR` / `VISION_MODEL` / `VISION_BASE_URL` / `ROLE_MODEL` in
`scripts/swarm.py` to repoint. `hy3:free` remains the fallback/`SWARM_MODEL`.

## Quick start
```bash
# 1. Ensure profiles exist + board is ready (idempotent, no processes spawned)
python3 ~/.hermes/skills/agent-swarm/scripts/swarm.py setup

# 2. Launch a swarm for a goal (this is what "starts" the autonomous run)
python3 ~/.hermes/skills/agent-swarm/scripts/swarm.py launch "Produce a comparison of local LLM inference tools..."

# 3. Watch it run (dispatcher is already live via the gateway)
python3 ~/.hermes/skills/agent-swarm/scripts/swarm.py status
```

## VirusGPT integration — `vgctl swarm`
If you are working in the VirusGPT repo (`/Users/Master/virusgpt-mac`), there is a
dedicated `vgctl swarm` subcommand that wraps this skill and targets the stack:
```bash
python3 vgctl.py swarm setup          # create profiles + board (idle)
python3 vgctl.py swarm run            # persistent-vision swarm w/ a sensible VirusGPT goal
python3 vgctl.py swarm run "your goal here"
python3 vgctl.py swarm --no-vision run "goal"   # omit the UI-inspection worker
python3 vgctl.py swarm status         # board + dispatcher health
python3 vgctl.py swarm stop           # manually stand down
python3 vgctl.py swarm models         # show configured models
```

## Swarm shape
```
goal (root, done when synthesizer finishes)
 ├─ worker: researcher   →  research findings        (longcat-2.0)
 ├─ worker: coder        →  implementation / script   (solar-pro4)
 ├─ worker: writer       →  documentation             (longcat-2.0)
 ├─ worker: visioner     →  UI / screenshot report    (local Ollama, optional)
 ├─ verifier: verifier   (gated on all workers)        (solar-pro4)
 └─ synthesizer: orchestrator (gated on verifier)      (longcat-2.0)
```
Dependency gating is automatic: verifier won't start until workers complete;
synthesizer won't start until verifier passes. The dispatcher drives all of it.

## Persistent handoff (important)
- `launch` / `launch_vision` use **scratch** workspaces that are DELETED when a worker
  completes — the next agent can't read prior output and the final deliverable vanishes.
- `launch_persistent` / `launch_persistent_vision` give **every agent one shared `dir:`**
  workspace, so output survives across the chain (the next agent reads the prior agent's
  files) and the final deliverable persists after completion. **Use these when you want
  the swarm's result to outlive the run.** Handoff = the filesystem in that shared dir.

## Commands (scripts/swarm.py)
- `setup`           — create+describe the 6 profiles (idempotent), init board. No spawn.
- `launch "GOAL"`   — scratch-workspace swarm; dispatcher picks it up.
- `launch_vision "GOAL"` — adds the visioner worker (local Ollama) for UI/screenshot tasks.
- `launch_persistent "GOAL"` — shared `dir:` workspace; handoff survives.
- `launch_persistent_vision "GOAL"` — persistent + visioner.
- `status`          — kanban list + gateway dispatcher health.
- `stop`            — manually stand down: reclaim running claims, archive the swarm.
- `models`          — show the configured models and how to change them.

## Pitfalls
- Do NOT run `hermes kanban daemon` — it is DEPRECATED in v0.20.4 and exits immediately.
  The dispatcher lives INSIDE the gateway (`hermes gateway status` must show running).
  If the gateway is down, `hermes gateway start`.
- Two dispatchers racing for claims = bad. Never run the standalone daemon alongside
  the gateway.
- **Worker exec crash (exit 1 → auto-blocked):** dispatcher-spawned workers are scoped
  to a TIGHT toolset. If a worker needs bash/python/file ops it crashes on the first
  tool call. Fix: set a full toolset on each role profile (the `setup` command does this
  automatically). Symptom: cards flip to `blocked`, gateway.log shows `crashed=N auto_blocked=N`.
- **Colons in `--worker` titles break the `PROFILE:TITLE[:SKILLS]` parser** — the goal
  text leaks into the `skills` field. Keep worker titles colon-free.
- `work kanban task X` is a DISPATCHER-ONLY command (needs `HERMES_KANBAN_TASK` env +
  kanban toolset). A plain `hermes chat -q "work kanban task X"` will NOT work. Always
  drive workers via the gateway dispatcher.
- **`kanban link` direction is PARENT->CHILD.** `link A B` means B depends on A. To make
  the verifier wait for workers, link each WORKER (parent) to the VERIFIER (child):
  `kanban link <worker_id> <verifier_id>`. Linking the wrong way blocks workers forever.
- Root blackboard cards must be `complete`d (or auto-done by `kanban swarm`) so children
  promote out of `todo`. A root left `running` will not promote its children.
- **Vision needs a real vision model.** The `visioner` profile points at a LOCAL Ollama
  host (`10.0.0.120:11434`) running `minicpm-v4.6` (verified to describe real images).
  If that host/Ollama is down, vision workers fail — fall back to `--no-vision` or fix the
  Ollama base URL in `VISION_BASE_URL`. Verify it actually sees images before a run —
  see `references/ollama-vision-test.md`.
- **Publishing this skill to GitHub (SSH, no PAT):** the machine's SSH key is a
  per-repo **deploy key** — pushing to a DIFFERENT repo fails with
  `denied to deploy key`. Convert https→`git@github.com:...`, add the key to the
  target repo with **Allow write access**, then push. Full recipe + fix in
  `references/github-ssh-deploy-keys.md`.

## References
- `references/kanban-swarm-debugging.md` — debugging notes from the original build (dispatcher, link direction, scratch vs dir:).
- `references/nous-free-models.md` — which free Nous models actually work on this Portal (longcat-2.0, solar-pro4, hy3; everything else 404s).
- `references/ollama-vision-test.md` — how to prove a local Ollama vision model genuinely sees images before trusting it in a swarm.
- `references/github-ssh-deploy-keys.md` — SSH deploy-key `denied to deploy key` fix for the no-PAT publishing workflow.
