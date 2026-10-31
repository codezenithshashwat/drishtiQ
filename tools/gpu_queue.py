"""Self-running sequential GPU job queue. Runs detached; nothing depends on an interactive session.

    .venv\\Scripts\\python tools\\gpu_queue.py            # run the queue (normally started by tools\\start_queue.ps1)
    .venv\\Scripts\\python tools\\gpu_queue.py --status   # rewrite queue/STATUS.md and exit

queue/jobs.yaml lists jobs in priority order. Each job has: id, title, est_gpu_min, enabled, large_output, steps (shell
commands run from the project root; a leading "python" means the project venv). Before every job the file is re-read,
so jobs can be added or enabled while the queue runs. The first enabled job that is neither done nor failed runs next.

- Steps are recorded in queue/state.json as they finish; a retry starts at the failed step. Training scripts resume
  from their own per-epoch checkpoints, so a retried training step continues where it stopped.
- A failed job is retried once; a second failure is logged and the queue moves on.
- Every 10 minutes nvidia-smi readings are appended to queue/logs/gpu.csv.
- Jobs with large_output: true are skipped (and logged) if free disk space is below 40 GB.
- With no runnable job the queue polls every 60 s; create queue/STOP to make it exit.
- Lines a step prints that start with "RESULT:" become the job's result in STATUS.md.
"""
import datetime as dt
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
Q = Path(os.environ.get("GPU_QUEUE_DIR", ROOT / "queue"))  # override only for testing the queue itself
LOGS = Q / "logs"
STATE = Q / "state.json"
PY = str(ROOT / ".venv/Scripts/python.exe")
MIN_FREE_GB = 40
GPU_EVERY_S = 600
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def log(msg):
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "queue.log", "a", encoding="utf-8") as f:
        f.write(f"{now()} {msg}\n")


def load_jobs():
    jobs = yaml.safe_load((Q / "jobs.yaml").read_text(encoding="utf-8"))["jobs"]
    for job in jobs:  # an unquoted step containing ": " parses as a mapping; refuse it rather than run something else
        bad = [k for k, st in enumerate(job["steps"]) if not isinstance(st, str)]
        if bad:
            job["invalid"] = f"steps {bad} are not plain strings; quote them in jobs.yaml"
    return jobs


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE)


def free_gb():
    return shutil.disk_usage(ROOT).free / 2**30


def gpu_monitor(stop):
    f = LOGS / "gpu.csv"
    while not stop.is_set():
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw",
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
            new = not f.exists()
            with open(f, "a", encoding="utf-8") as fh:
                if new:
                    fh.write("time,temp_c,util_pct,mem_used_mib,mem_total_mib,power_w,free_disk_gb\n")
                fh.write(f"{now()},{out.stdout.strip().replace(' ', '')},{free_gb():.0f}\n")
        except Exception as e:  # monitoring must never stop the queue
            log(f"gpu monitor error: {e}")
        stop.wait(GPU_EVERY_S)


def run_step(job_id, k, cmd):
    """Run one shell step; returns (ok, RESULT lines)."""
    argv = shlex.split(cmd, posix=True)
    if argv[0] == "python":
        argv[0] = PY
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    path = LOGS / f"{job_id}.step{k}.log"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"\n===== {now()} {cmd}\n")
        fh.flush()
        rc = subprocess.run(argv, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, creationflags=NO_WINDOW).returncode
        fh.write(f"===== {now()} exit {rc}\n")
    results = [l.strip()[7:].strip() for l in path.read_text(encoding="utf-8", errors="replace").splitlines() if l.startswith("RESULT:")]
    return rc == 0, results


def run_job(job, state):
    s = state.setdefault(job["id"], dict(status="pending", attempts=0, steps_done=0, results=[]))
    while s["attempts"] < 2:
        s["attempts"] += 1
        s.update(status="running", start=s.get("start") or now())
        save_state(state)
        write_status(load_jobs(), state)
        log(f"{job['id']}: attempt {s['attempts']} from step {s['steps_done']}")
        ok = True
        for k in range(s["steps_done"], len(job["steps"])):
            try:
                ok, results = run_step(job["id"], k, job["steps"][k])
            except Exception:
                ok, results = False, []
                log(f"{job['id']} step {k} raised:\n{traceback.format_exc()}")
            if results:
                s["results"] = results
            if not ok:
                log(f"{job['id']}: step {k} failed (see logs/{job['id']}.step{k}.log)")
                break
            s["steps_done"] = k + 1
            save_state(state)
        if ok:
            s.update(status="done", end=now())
            break
    else:
        s.update(status="failed", end=now(), error=f"failed twice; see queue/logs/{job['id']}.step{s['steps_done']}.log")
    save_state(state)
    log(f"{job['id']}: {s['status']}")


def next_job(jobs, state):
    for job in jobs:
        st = state.get(job["id"], {}).get("status")
        if job.get("enabled", True) and st not in ("done", "failed", "skipped"):
            return job
    return None


def write_status(jobs, state):
    """Table in file order; the timeline runs the running job first, then enabled pending jobs in file order."""
    t, running, when = dt.datetime.now(), None, {}
    for job in jobs:
        s = state.get(job["id"], {})
        if s.get("status") == "running":
            running = job["id"]
            t = max(t, dt.datetime.fromisoformat(s["start"]) + dt.timedelta(minutes=job.get("est_gpu_min", 0)))
            when[job["id"]] = f"started {s['start'][11:16]}, est. end {t:%H:%M}"
    for job in jobs:
        s = state.get(job["id"], {})
        if s.get("status") in (None, "pending") and job.get("enabled", True):
            t = t + dt.timedelta(minutes=job.get("est_gpu_min", 0))
            when[job["id"]] = f"est. end {t:%a %H:%M}"
    rows = []
    for job in jobs:
        s = state.get(job["id"], {})
        st = s.get("status", "pending" if job.get("enabled", True) else "waiting (not enabled)")
        w = when.get(job["id"]) or (f"{s.get('start', '')[11:16]} to {s.get('end', '')[11:16]}" if s.get("end") else "")
        result = "; ".join(s.get("results", [])) or s.get("error", "")
        rows.append(f"| {job['id']} | {job['title']} | {job.get('est_gpu_min', '?')} | {st} | {w} | {result} |")
    nxt = next_job(jobs, state)
    gpu = ""
    g = LOGS / "gpu.csv"
    if g.exists():
        last = g.read_text().strip().splitlines()[-1].split(",")
        gpu = f"Last GPU reading {last[0][11:16]}: {last[1]} °C, {last[2]}% util, {last[3]} MiB VRAM; {last[6]} GB disk free."
    text = "\n".join([
        "# GPU queue status", "",
        f"Updated {now()}. Queue process PID {(Q / 'queue.pid').read_text().strip() if (Q / 'queue.pid').exists() else '?'}. Running: {running or 'nothing'}. Next: {nxt['id'] if nxt else 'none'}.",
        gpu, "",
        "Timeline: the running job first, then enabled pending jobs top to bottom (estimates).", "",
        "| Job | What | Est. GPU min | Status | When | Result |", "|---|---|---|---|---|---|", *rows, "",
        "Logs: queue/logs/ (queue.log, <job>.step<N>.log, gpu.csv). Decisions: queue/decisions/. Stop: create queue/STOP.", "",
        # Hand-written operator notes (incidents, decisions) survive every rewrite of this file.
        (Q / "NOTES.md").read_text(encoding="utf-8") if (Q / "NOTES.md").exists() else ""])
    (Q / "STATUS.md").write_text(text, encoding="utf-8")


def single_instance():
    pid_file = Q / "queue.pid"
    if pid_file.exists():
        pid = int(pid_file.read_text().strip() or 0)
        alive = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                               creationflags=NO_WINDOW).stdout
        if str(pid) in alive and "python" in alive.lower():
            raise SystemExit(f"queue already running (PID {pid})")
    pid_file.write_text(str(os.getpid()))


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    if "--status" in sys.argv:
        write_status(load_jobs(), load_state())
        return
    single_instance()
    stop = threading.Event()
    threading.Thread(target=gpu_monitor, args=(stop,), daemon=True).start()
    log(f"queue started, PID {os.getpid()}")
    idle_logged = False
    while not (Q / "STOP").exists():
        try:
            jobs, state = load_jobs(), load_state()
        except Exception as e:  # a half-edited jobs.yaml must not kill the queue
            log(f"could not read jobs.yaml/state: {e}")
            time.sleep(60)
            continue
        job = next_job(jobs, state)
        if job is None:
            if not idle_logged:
                log("no runnable job; polling every 60 s")
                idle_logged = True
            write_status(jobs, state)
            time.sleep(60)
            continue
        idle_logged = False
        if job.get("invalid"):
            state[job["id"]] = dict(status="failed", start=now(), end=now(), error=job["invalid"])
            save_state(state)
            log(f"{job['id']}: {job['invalid']}")
            continue
        if job.get("large_output") and free_gb() < MIN_FREE_GB:
            state[job["id"]] = dict(status="skipped", start=now(), end=now(), error=f"free disk {free_gb():.0f} GB < {MIN_FREE_GB} GB")
            save_state(state)
            log(f"{job['id']}: skipped, low disk")
            continue
        run_job(job, state)
        write_status(load_jobs(), load_state())
    stop.set()
    log("STOP file found; queue exiting")
    write_status(load_jobs(), load_state())


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        log(f"queue exit: {e}")
        raise
    except Exception:
        log("queue crashed:\n" + traceback.format_exc())
        raise
