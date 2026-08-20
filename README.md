# hermes-agent-swarm

> Idle-by-default, live-on-call autonomous agent swarms for [Hermes Agent](https://github.com/NousResearch/Hermes), with role-fit models and local-Ollama vision.

A reusable skill that turns Hermes into a **multi-agent orchestrator**. It defines 6 role-based
profiles (isolated agent identities) that do nothing until invoked, then runs a **Kanban swarm**
(parallel workers → verifier → synthesizer) driven by the gateway's embedded dispatcher. The
dispatcher stays live to pick up and continue work until the whole task tree completes.

```
goal (root)
 ├─ worker: researcher   →  research findings        (longcat-2.0:free, 1M ctx)
 ├─ worker: coder        →  implementation / script   (solar-pro4:free, 512K ctx)
 ├─ worker: writer       →  documentation             (longcat-2.0:free, 1M ctx)
 ├─ worker: visioner     →  UI / screenshot report    (local Ollama minicpm-v4.6)
 ├─ verifier: verifier   (gated on all workers)        (solar-pro4:free)
 └─ synthesizer: orchestrator (gated on verifier)      (longcat-2.0:free)
```

## Why

- **Idle by default.** Profiles exist on disk but spawn nothing. No running cost until you call them.
- **Live on call.** `launch` builds a swarm graph; the launchd-supervised gateway dispatcher
  claims ready tasks and spawns the assigned profile as a real subprocess.
- **Lives until done.** The dispatcher ticks (~60s) and picks up any task that becomes ready,
  so workers → verifier → synthesizer flow automatically and continue across the board.
- **Role-fit models.** Each profile uses a free model matched to its job (huge-context research/
  writing/orchestration vs. code/verification vs. local vision).
- **Persistent handoff.** `launch_persistent*` gives every agent one shared `dir:` workspace so
  output survives across the chain and the final deliverable outlives the run.

## Install

This is a Hermes **skill**. Drop it into your skills directory:

```bash
# clone into your Hermes skills folder (or copy the directory)
git clone git@github.com:TheGMPTeam/hermes-agent-swarm.git ~/.hermes/skills/agent-swarm
```

Requires Hermes Agent v0.20.4+ (Kanban + gateway dispatcher) and a Nous Portal account for the
cloud roles. Vision uses a **local Ollama** host running `minicpm-v4.6` (or any vision model).

## Usage

```bash
# 1. Idle-safe setup: create+describe the 6 profiles, init the board. No processes spawned.
python3 ~/.hermes/skills/agent-swarm/scripts/swarm.py setup

# 2. Launch a swarm for a goal (this is what "starts" the autonomous run)
python3 ~/.hermes/skills/agent-swarm/scripts/swarm.py launch "Produce a comparison of local LLM inference tools: research, build a benchmark script, write a README, verify, synthesize a report."

# 3. Watch it run (the gateway dispatcher is already live)
python3 ~/.hermes/skills/agent-swarm/scripts/swarm.py status
```

### Variants

| Command | What it does |
|---|---|
| `launch "GOAL"` | Scratch-workspace swarm; dispatcher picks it up. |
| `launch_vision "GOAL"` | Adds the `visioner` worker (local Ollama) for UI/screenshot tasks. |
| `launch_persistent "GOAL"` | Shared `dir:` workspace — handoff survives across agents. |
| `launch_persistent_vision "GOAL"` | Persistent + visioner. |
| `status` | Kanban board + gateway dispatcher health. |
| `stop` | Manually stand down: reclaim running claims, archive the swarm. |
| `models` | Show the configured models and how to change them. |

### VirusGPT integration — `vgctl swarm`

Inside the VirusGPT repo (`/Users/Master/virusgpt-mac`), a `vgctl swarm` subcommand wraps this
skill and targets the stack:

```bash
python3 vgctl.py swarm run            # persistent-vision swarm with a sensible VirusGPT goal
python3 vgctl.py swarm run "your goal here"
python3 vgctl.py swarm --no-vision run "goal"   # omit the UI-inspection worker
python3 vgctl.py swarm status | stop | models
```

## Role profiles (fit to role)

| Profile | Model | Provider | Context | Role |
|---|---|---|---|---|
| `researcher` | `meituan/longcat-2.0:free` | nous | 1M | Web research, extraction, citations |
| `writer` | `meituan/longcat-2.0:free` | nous | 1M | Docs, READMEs, copy |
| `orchestrator` | `meituan/longcat-2.0:free` | nous | 1M | Decompose goals + synthesize |
| `coder` | `upstage/solar-pro4:free` | nous | 512K | Code, builds, tests |
| `verifier` | `upstage/solar-pro4:free` | nous | 512K | QA gate |
| `visioner` | `minicpm-v4.6:latest` | **local ollama @ 10.0.0.120:11434** | — | Vision/UI inspection |

Repoint any model via the constants at the top of `scripts/swarm.py`
(`LONGCAT`, `SOLAR`, `VISION_MODEL`, `VISION_BASE_URL`, `ROLE_MODEL`).

## How it works

- **Dispatcher, not a daemon.** The standalone `hermes kanban daemon` is deprecated; the real
  dispatcher lives inside the gateway (`hermes gateway status` must show running).
- **Gating.** Verifier is linked as a child of every worker (PARENT→CHILD), so it can't start
  until they finish; the synthesizer is linked as a child of the verifier. The dispatcher drives
  all of it.
- **Persistent handoff.** `launch_persistent*` assigns every card the same `dir:` workspace. The
  handoff between agents is the filesystem in that shared directory.

See [`references/`](references/) for the debugging notes and free-model probe results gathered
while building this.

## License

[MIT](LICENSE) © TheGMPTeam
