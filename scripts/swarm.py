#!/usr/bin/env python3
"""agent-swarm driver: idle-by-default subagent profiles + Kanban swarm.

Profiles exist on disk but are NOT spawned until `launch` is called. The gateway's
embedded dispatcher (launchd-supervised) picks up ready tasks and stays live to
continue work until the task tree completes. No standalone `kanban daemon` (deprecated).

Usage:
  swarm.py setup                 # create+describe 6 role profiles (idempotent); init board
  swarm.py launch "GOAL"         # build swarm graph (scratch); dispatcher picks it up
  swarm.py launch_persistent "GOAL"   # shared dir: workspace survives across agents
  swarm.py launch_vision "GOAL"        # adds a visioner worker (local Ollama) for UI/screenshot tasks
  swarm.py launch_persistent_vision "GOAL"  # persistent + vision
  swarm.py status                # board + gateway dispatcher health
  swarm.py stop                  # manually stand down: reclaim + archive the swarm
  swarm.py models                # show configured models
"""
import json
import os
import subprocess
import sys

HERMES = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")
PROVIDER = "nous"
# Three working FREE models on this Nous Portal, each fit to a role by context size:
#   longcat-2.0  ~1M ctx   -> research/writing/orchestration (huge context)
#   solar-pro4   512K ctx  -> coding/verification (large codebases + test logs)
#   hy3:free     256K ctx  -> default/fallback
# (Every other :free slug 404s; paid models need credits.)
LONGCAT = "meituan/longcat-2.0:free"
SOLAR   = "upstage/solar-pro4:free"
SWARM_MODEL = "tencent/hy3:free"          # fallback / default
# Vision/UI-seeing tasks run on a LOCAL Ollama vision model (no cloud, no cost).
# This is the one vision-capable model pulled on the LAN Ollama host.
VISION_MODEL = "minicpm-v4.6:latest"
VISION_PROVIDER = "ollama"
VISION_BASE_URL = "http://10.0.0.120:11434"

# per-role model assignment (fit model to role by context need)
ROLE_MODEL = {
    "researcher":   LONGCAT,   # long source dumps
    "writer":       LONGCAT,   # long docs
    "orchestrator": LONGCAT,   # holds whole task tree + all outputs
    "coder":        SOLAR,     # large codebases + build logs
    "verifier":     SOLAR,     # reads all artifacts + tests
    "visioner":     VISION_MODEL,  # local Ollama (handled separately)
}

ROLES = {
    "researcher":   "Autonomous research agent. Excels at web search, source extraction, literature/API surveys, fact-checking, and synthesizing findings into structured briefs with citations.",
    "coder":        "Autonomous software engineering agent. Excels at writing, debugging, refactoring, and testing code across Python, web, and shell; runs builds and verifies fixes empirically.",
    "writer":       "Autonomous technical writing agent. Excels at turning research and code into polished docs, READMEs, reports, and user-facing copy.",
    "verifier":     "Autonomous QA/verification agent. Excels at reviewing outputs for correctness, broken links, failed tests, and unmet requirements; requests changes with concrete evidence.",
    "orchestrator": "Autonomous orchestration agent. Excels at decomposing goals into tasks, assigning them to role profiles, monitoring a kanban board, and synthesizing worker outputs into a final deliverable.",
    "visioner":     "Autonomous vision/UI-inspection agent. Runs a local Ollama vision model to look at screenshots, UI states, and rendered output; reports what it sees, detects visual bugs, layout breaks, and missing elements. Use for any task requiring seeing the interface.",
}

# roles that use the local Ollama vision model instead of the cloud SWARM_MODEL
VISION_ROLES = {"visioner"}


def run(*args, check=True):
    r = subprocess.run([HERMES, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.stderr.write(r.stderr)
    return r


def setup():
    print("== agent-swarm setup ==")
    # init board (idempotent)
    run("kanban", "init", check=False)
    # create profiles (clone default -> inherits model/provider)
    for name in ROLES:
        r = run("profile", "create", name, "--clone", "--no-alias", check=False)
        print(f"  profile {name}: {'exists/created' if r.returncode == 0 or 'already' in r.stderr else r.stderr.strip()[:60]}")
    # set role descriptions
    for name, desc in ROLES.items():
        run("profile", "describe", name, "--text", desc, check=False)
        print(f"  described {name}")
    # point every role at its fit-to-role model
    for name in ROLES:
        if name in VISION_ROLES:
            run("config", "set", "model", VISION_MODEL, "--profile", name, check=False)
            run("config", "set", "model.provider", VISION_PROVIDER, "--profile", name, check=False)
            run("config", "set", "model.base_url", VISION_BASE_URL, "--profile", name, check=False)
        else:
            run("config", "set", "model", ROLE_MODEL.get(name, SWARM_MODEL), "--profile", name, check=False)
            # reset provider/base_url to the cloud so a stale Ollama base_url can't leak in
            run("config", "set", "model.provider", PROVIDER, "--profile", name, check=False)
            run("config", "set", "model.base_url", "https://inference-api.nousresearch.com/v1", "--profile", name, check=False)
        # give workers the exec tools they need (dispatcher spawns are scoped tight)
        run("config", "set", "toolsets",
            "terminal,code_execution,file,kanban,web,skills,memory,todo,vision",
            "--profile", name, check=False)
    print(f"  roles -> researcher/writer/orchestrator:{LONGCAT}  coder/verifier:{SOLAR}  vision:{VISION_MODEL}@{VISION_BASE_URL}  + toolset")
    # ensure gateway dispatcher is up (it does the autonomous picking-up)
    g = run("gateway", "status", check=False)
    if "Gateway is supervised" in g.stdout or "running" in g.stdout.lower():
        print("  gateway dispatcher: RUNNING (autonomous pickup live)")
    else:
        print("  gateway NOT running -> `hermes gateway start` to enable autonomous pickup")
    print("setup complete (nothing running yet — idle).")


def launch(goal, persistent=False, workspace=None, with_vision=False):
    print("== agent-swarm launch ==")
    setup()
    # worker roster — visioner (local Ollama) is added only when requested
    workers = [("Research and gather findings", "researcher"),
               ("Implement or build the artifacts", "coder"),
               ("Draft the documentation and READMEs", "writer")]
    if with_vision:
        workers.append(("Inspect the UI / screenshots and report what is visible", "visioner"))
    if not persistent:
        args = ["kanban", "swarm", goal]
        for title, profile in workers:
            args += ["--worker", f"{profile}:{title}"]
        args += ["--verifier", "verifier", "--synthesizer", "orchestrator",
                 "--priority", "10", "--created-by", "default", "--json"]
        r = run(*args, check=False)
        try:
            info = json.loads(r.stdout)
            print("  swarm built:")
            print(f"    root:       {info['root_id']}")
            for i, w in enumerate(info["worker_ids"]):
                print(f"    worker[{i}]:  {w}")
            print(f"    verifier:   {info['verifier_id']}")
            print(f"    synthesizer:{info['synthesizer_id']}")
        except Exception:
            print(r.stdout, r.stderr)
    else:
        # Persistent shared workspace: every agent writes to the SAME dir: path,
        # so output survives across the chain and the final deliverable persists
        # after completion (scratch would delete it). The handoff is the filesystem.
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", goal.lower())[:40].strip("-")
        if not workspace:
            workspace = os.path.expanduser(f"~/.hermes/swarm-workspaces/{slug}")
        os.makedirs(workspace, exist_ok=True)
        wspec = f"dir:{workspace}"
        # root blackboard — complete it immediately so children can promote
        # (matches the `kanban swarm` root behavior: a shared audit anchor)
        root = run("kanban", "create", f"Swarm: {goal}",
                   "--assignee", "default", "--workspace", "scratch",
                   "--priority", "10", "--created-by", "default", "--json", check=False)
        root_id = json.loads(root.stdout)["id"] if root.stdout.strip().startswith("{") else None
        run("kanban", "complete", root_id, check=False)
        # parallel workers share the persistent dir
        worker_ids = []
        for title, profile in workers:
            a = run("kanban", "create", title, "--assignee", profile,
                    "--parent", root_id, "--workspace", wspec,
                    "--priority", "10", "--created-by", "default", "--json", check=False)
            try:
                worker_ids.append(json.loads(a.stdout)["id"])
            except Exception:
                pass
        # verifier gated on all workers; also persistent so it can read their output.
        # link direction is PARENT->CHILD, so link each WORKER (parent) to VERIFIER (child).
        ver = run("kanban", "create", "Verify swarm outputs", "--assignee", "verifier",
                  "--parent", root_id, "--workspace", wspec,
                  "--priority", "10", "--created-by", "default", "--json", check=False)
        ver_id = json.loads(ver.stdout)["id"] if ver.stdout.strip().startswith("{") else None
        for w in worker_ids:
            run("kanban", "link", w, ver_id, check=False)  # verifier depends on each worker
        # synthesizer gated on verifier; persistent -> final deliverable survives.
        # link VERIFIER (parent) to SYNTHESIZER (child).
        syn = run("kanban", "create", "Synthesize swarm outputs", "--assignee", "orchestrator",
                  "--parent", root_id, "--workspace", wspec,
                  "--priority", "10", "--created-by", "default", "--json", check=False)
        syn_id = json.loads(syn.stdout)["id"] if syn.stdout.strip().startswith("{") else None
        run("kanban", "link", ver_id, syn_id, check=False)
        print(f"  persistent swarm built in: {workspace}")
        print(f"    root:       {root_id}")
        print(f"    workers:    {worker_ids}")
        print(f"    verifier:   {ver_id}")
        print(f"    synthesizer:{syn_id}")
    print("  dispatcher will pick up ready tasks on its next tick (idle->live).")
    print("  watch:  python3", __file__, "status")


def launch_persistent(goal):
    launch(goal, persistent=True)


def launch_vision(goal):
    launch(goal, with_vision=True)


def launch_persistent_vision(goal):
    launch(goal, persistent=True, with_vision=True)


def status():
    print("== agent-swarm status ==")
    run("kanban", "list", check=False)
    print("--- gateway dispatcher ---")
    run("gateway", "status", check=False)


def stop():
    print("== agent-swarm stop (manual stand-down) ==")
    # reclaim any running claims, then archive the swarm root + children
    ls = run("kanban", "list", "--json", check=False)
    try:
        rows = json.loads(ls.stdout)
    except Exception:
        rows = []
    for row in rows:
        tid = row.get("id")
        if row.get("status") == "running":
            run("kanban", "reclaim", tid, check=False)
            print("  reclaimed", tid)
    run("pkill", "-f", "work kanban task", check=False)
    # archive root swarm cards (those with a root/swarm prefix) — archive all non-done
    ls2 = run("kanban", "list", "--json", check=False)
    try:
        rows2 = json.loads(ls2.stdout)
    except Exception:
        rows2 = []
    for row in rows2:
        tid = row.get("id")
        if row.get("status") != "done":
            run("kanban", "archive", tid, check=False)
            print("  archived", tid)
    print("stand-down complete (board idle).")


def models():
    print("SWARM_MODEL =", SWARM_MODEL, f"(provider: {PROVIDER})")
    print("To change: edit SWARM_MODEL in", __file__, "then re-run `setup`.")
    print("Or per-task override: hermes kanban set-model <task_id> <provider/model>")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "setup":
        setup()
    elif cmd == "launch":
        if len(sys.argv) < 3:
            print("usage: swarm.py launch \"GOAL\""); sys.exit(1)
        launch(sys.argv[2])
    elif cmd == "launch_persistent":
        if len(sys.argv) < 3:
            print("usage: swarm.py launch_persistent \"GOAL\""); sys.exit(1)
        launch_persistent(sys.argv[2])
    elif cmd == "launch_vision":
        if len(sys.argv) < 3:
            print("usage: swarm.py launch_vision \"GOAL\""); sys.exit(1)
        launch_vision(sys.argv[2])
    elif cmd == "launch_persistent_vision":
        if len(sys.argv) < 3:
            print("usage: swarm.py launch_persistent_vision \"GOAL\""); sys.exit(1)
        launch_persistent_vision(sys.argv[2])
    elif cmd == "status":
        status()
    elif cmd == "stop":
        stop()
    elif cmd == "models":
        models()
    else:
        print(__doc__); sys.exit(1)
