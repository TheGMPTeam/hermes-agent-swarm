# Debugging a blocked / crashed agent swarm

## Symptom
`hermes kanban list` shows worker cards flipped to `blocked` (not `running`), and
`~/.hermes/logs/gateway.log` shows a tick like:
```
kanban dispatcher [default]: spawned=3 reclaimed=0 crashed=3 timed_out=0 promoted=3 auto_blocked=3
```

## Root cause
The gateway dispatcher spawns workers with a **tight toolset** (kanban-only by default).
The first time a worker calls `terminal` / `code_execution` / `file` (e.g. to run or write
code), the tool is absent → the worker exits 1 → the dispatcher auto-blocks the task after
`failure_limit` (default 2) consecutive failures.

## Fix (one-time per role profile)
Set a full toolset on every role profile the swarm uses:
```bash
for p in researcher coder writer verifier orchestrator; do
  hermes config set toolsets "terminal,code_execution,file,kanban,web,skills,memory,todo,vision" --profile "$p"
done
```
(The `setup` command in `scripts/swarm.py` does this automatically.)

## Verify the fix
After the next ~60s dispatcher tick:
```bash
hermes kanban list                                   # workers show ● running, NOT ⊘ blocked
grep "spawned" ~/.hermes/logs/gateway.log | tail -1  # should read crashed=0 auto_blocked=0
```

## `work kanban task X` is dispatcher-only
Do NOT test a worker by hand with `hermes chat -q "work kanban task X"` — a plain chat
session has no kanban tools and the agent wanders off looking for a "kanban system".
It only works when the dispatcher sets `HERMES_KANBAN_TASK` (and the kanban toolset is on).
If you must reproduce manually:
```bash
HERMES_KANBAN_TASK=<id> HERMES_KANBAN_RUN_ID=1 \
  hermes -p <role> --cli --toolsets kanban chat -q "work kanban task <id>"
```
Caveat: a manual run that wasn't the in-flight dispatcher run can't call `kanban_complete`
— the card stays `blocked`. Always let the dispatcher do the closing.

## `hermes kanban daemon` is DEPRECATED (v0.20.4)
Running it prints a deprecation notice and exits immediately. The dispatcher lives INSIDE
the gateway. If the gateway is down: `hermes gateway start`. Never run the standalone
daemon alongside the gateway — they race for claims.

## Colon trap in `--worker` titles
`--worker 'profile:Title:skills'` — a colon in `Title` breaks the `PROFILE:TITLE[:SKILLS]`
parser and leaks the goal text into the `skills` field. Keep worker titles colon-free; put
the goal in the top-level `swarm` argument instead.

## Watch without blocking
```bash
hermes kanban list                  # all cards + assignees + status
hermes kanban show <id>             # events / runs / workspace path
tail -f ~/.hermes/logs/gateway.log # dispatcher ticks (spawned/crashed/promoted)
```
The swarm root card shows `done` immediately by design (it's the shared blackboard); that
is NOT a bug — parallel workers start because of it.
