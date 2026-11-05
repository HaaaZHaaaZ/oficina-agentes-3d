"""Writes /app/agents.json in the virtoffice container with the live state of Hermes and Claude.

Hermes: /hermes/gateway_state.json (active_work). Claude: `claude -p` processes in the
claude-discord container. Talks to Docker through its API socket; no docker CLI needed.
Runs as the `feeder` service of docker-compose.yml.
"""
import http.client, io, json, os, re, socket, tarfile, time

SOCK = "/var/run/docker.sock"
OFFICE = os.environ.get("OFFICE_CONTAINER", "virtoffice")
CLAUDE = os.environ.get("CLAUDE_CONTAINER", "claude-discord")


class UnixConn(http.client.HTTPConnection):
    def __init__(self):
        super().__init__("localhost", timeout=10)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(SOCK)


def docker(method, path, body=None, headers=None):
    c = UnixConn()
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


def claude_state():
    st, data = docker("GET", f"/containers/{CLAUDE}/top")
    runs = []
    if st == 200:
        for args in [p[-1] for p in json.loads(data).get("Processes") or []]:
            if args.startswith("claude -p"):
                m = re.search(r"hilo del proyecto «([^»]+)»", args)
                runs.append(f"Proyecto «{m.group(1)}»" if m else "Canal #ubuntu-server")
    working = bool(runs)
    return {
        "id": "claude", "name": "Claude", "role": "Claude Code · servidor", "emoji": "🟠",
        "color": "#D97757", "home": "left",
        "status": "working" if working else "idle", "typing": working,
        "task": " · ".join(runs) if working else "Esperando mención en Discord",
        "tasks": runs or ["Libre"], "output": [], "mood": 0.85,
        "stats": {"tasksDone": 0, "active": len(runs), "hours": 0},
    }


def hermes_state():
    try:
        d = json.load(open("/hermes/gateway_state.json"))
    except Exception:
        d = {}
    work = d.get("active_work")
    running = d.get("gateway_state") == "running"
    try:  # what Hermes itself says it is doing (/hermes/virtoffice/status.json), fresher than active_work
        own = json.load(open("/hermes/virtoffice/status.json")).get("current")
        if own and own.get("task"):
            work = own["task"]
    except Exception:
        pass
    if work:
        task = work if isinstance(work, str) else json.dumps(work, ensure_ascii=False)[:80]
        status = "working"
    else:
        task, status = ("Esperando tareas" if running else "Gateway parado"), ("idle" if running else "offline")
    return {
        "id": "hermes", "name": "Hermes", "role": "Hermes Agent · GitHub/Portainer", "emoji": "☤",
        "color": "#8B5CF6", "home": "right", "status": status, "typing": status == "working",
        "task": task, "tasks": [task], "output": [], "mood": 0.85,
        "stats": {"tasksDone": 0, "active": 1 if work else 0, "hours": 0},
    }


EVENTS = []  # recent status changes, newest first


def note_changes(prev, agents):
    old = {a["id"]: (a["status"], a["task"]) for a in (prev or [])}
    for a in agents:
        if old.get(a["id"]) != (a["status"], a["task"]):
            EVENTS.insert(0, {"t": time.strftime("%H:%M:%S"), "who": a["name"], "status": a["status"], "task": a["task"]})
    del EVENTS[60:]


def hermes_extra():
    """Hermes publishes /hermes/virtoffice/status.json (tasks, cron, current work). Until then,
    read its kanban and cron files directly."""
    try:
        return json.load(open("/hermes/virtoffice/status.json"))
    except Exception:
        pass
    out = {"source": "fallback", "kanban": [], "cron": []}
    try:
        import sqlite3
        c = sqlite3.connect("file:/hermes/kanban.db?mode=ro", uri=True)
        out["kanban"] = [dict(zip(("id", "title", "status", "assignee"), r)) for r in c.execute(
            "select id, title, status, assignee from tasks where status != 'archived' order by created_at desc limit 20")]
        c.close()
    except Exception as e:
        out["kanban_error"] = str(e)
    try:
        d = json.load(open("/hermes/cron/jobs.json"))
        for j in (d.get("jobs", d) if isinstance(d, dict) else d):
            out["cron"].append({"name": j.get("name"), "schedule": (j.get("schedule") or {}).get("display") if isinstance(j.get("schedule"), dict) else j.get("schedule_display"),
                                "enabled": j.get("enabled", True), "last_status": j.get("last_status"), "next_run_at": j.get("next_run_at")})
    except Exception as e:
        out["cron_error"] = str(e)
    return out


def metrics():
    m = {}
    try:
        m["load"] = [float(x) for x in open("/proc/loadavg").read().split()[:3]]
        info = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}
        m["mem_total_mb"] = info["MemTotal"] // 1024
        m["mem_used_mb"] = (info["MemTotal"] - info["MemAvailable"]) // 1024
        m["swap_total_mb"] = info["SwapTotal"] // 1024
        m["swap_used_mb"] = (info["SwapTotal"] - info["SwapFree"]) // 1024
        m["cpus"] = open("/proc/cpuinfo").read().count("processor\t:")
        st = os.statvfs("/hermes")
        m["disk_total_gb"] = round(st.f_blocks * st.f_frsize / 1e9)
        m["disk_used_gb"] = round((st.f_blocks - st.f_bfree) * st.f_frsize / 1e9)
        m["uptime_h"] = round(float(open("/proc/uptime").read().split()[0]) / 3600, 1)
    except Exception as e:
        m["error"] = str(e)
    st, data = docker("GET", "/containers/json?all=1")
    if st == 200:
        m["containers"] = sorted(({"name": c["Names"][0].lstrip("/"), "state": c["State"], "status": c["Status"]}
                                  for c in json.loads(data)), key=lambda c: (c["state"] != "running", c["name"]))
    return m


def put_file(path, name, raw):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name)
        info.size, info.mode, info.mtime = len(raw), 0o644, int(time.time())
        tar.addfile(info, io.BytesIO(raw))
    return docker("PUT", f"/containers/{OFFICE}/archive?path={path}", buf.getvalue(), {"Content-Type": "application/x-tar"})[0]


def push(agents):
    raw = json.dumps({"agents": agents}, ensure_ascii=False).encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo("agents.json")
        info.size, info.mode, info.mtime = len(raw), 0o644, int(time.time())
        tar.addfile(info, io.BytesIO(raw))
    return docker("PUT", f"/containers/{OFFICE}/archive?path=/app", buf.getvalue(), {"Content-Type": "application/x-tar"})[0]


last, prev, tick = None, None, 0
while True:
    try:
        agents = [hermes_state(), claude_state()]
        key = json.dumps(agents, sort_keys=True)
        if key != last:
            note_changes(prev, agents)
            print(time.strftime("%H:%M:%S"), push(agents), [(a["name"], a["status"], a["task"]) for a in agents], flush=True)
            last, prev = key, agents
        if tick % 2 == 0:  # panels: every 10 s
            data = {"updated": time.strftime("%H:%M:%S"), "agents": agents, "events": EVENTS,
                    "hermes": hermes_extra(), "metrics": metrics()}
            put_file("/app/public", "data.json", json.dumps(data, ensure_ascii=False).encode())
        tick += 1
    except Exception as e:
        print("error:", e, flush=True)
    time.sleep(5)
