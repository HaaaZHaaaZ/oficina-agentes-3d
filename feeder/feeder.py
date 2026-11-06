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


# Where each kind of work happens in the office (see AREAS in office.html).
AREA_WORDS = [
    ("phone", ["esperando", "aprobaci", "confirmaci", "autoriz"]),
    ("server", ["despleg", "deploy", "docker", "contenedor", "portainer", "servidor", "reinici", "stack",
                "logs", "nginx", "cloudflare", "túnel", "tunel", "puerto", "backup", "postgres", "base de datos", "memoria ram"]),
    ("research", ["busca", "investiga", "documenta", "compara", "analiza", "informe", "resumen", "lee ", "leer", "web"]),
]


def classify(text):
    t = (text or "").lower()
    for area, words in AREA_WORDS:
        if any(w in t for w in words):
            return area
    return "desk"


def claude_requests():
    """Running `claude -p` processes in the Claude container: one per Discord request."""
    st, data = docker("GET", f"/containers/{CLAUDE}/top")
    out = []
    if st != 200:
        return out
    d = json.loads(data)
    titles = d.get("Titles") or []
    ipid = titles.index("PID") if "PID" in titles else 1
    istime = titles.index("STIME") if "STIME" in titles else 4
    for p in d.get("Processes") or []:
        args = p[-1]
        if not args.startswith("claude -p"):
            continue
        m = re.search(r"hilo del proyecto «([^»]+)»", args)
        prompt = args.split(" --output-format")[0]
        w = list(re.finditer(r"\[([^\]]{1,40})\] te escribe:", prompt))
        who = w[-1].group(1) if w else "Discord"
        text = short(prompt[w[-1].end():] if w else prompt[len("claude -p"):])
        out.append({"key": f"c{p[ipid]}-{p[istime]}", "who": who, "text": text,
                    "where": f"Proyecto «{m.group(1)}»" if m else "#ubuntu-server",
                    "project": m.group(1) if m else None, "from_hermes": "(Este mensaje es de Hermes" in args})
    return out


def pick_area(text, project, with_other):
    """Area of the office for a request: what it is about first, then where it was asked."""
    if with_other:
        return "meeting"
    area = classify(text)
    if area != "desk":
        return area
    return "project" if project else "desk"


def claude_state():
    runs = CLAUDE_PROCS
    working = bool(runs)
    r = runs[-1] if runs else None
    task = f"{r['text']}" if r else "Esperando mención en Discord"
    return {
        "id": "claude", "name": "Claude", "role": "Claude Code · servidor", "emoji": "🟠",
        "color": "#D97757", "home": "left",
        "status": "working" if working else "idle", "typing": working,
        "area": pick_area(r["text"], r["project"], r["from_hermes"]) if r else "rest",
        "project": r["project"] if r else None,
        "where": r["where"] if r else None, "from": r["who"] if r else None,
        "task": task,
        "tasks": [f"{x['who']}: {x['text']}" for x in runs] or ["Libre"], "output": recent_done("claude"), "mood": 0.85,
        "stats": {"tasksDone": done_today("claude"), "active": len(runs), "hours": hours_today("claude")},
    }


def hermes_status_file(max_age=90):
    """/hermes/virtoffice/status.json from Hermes's publish_status.py, only if it is fresh
    (the publisher stops when Hermes restarts; a stale file would show old work)."""
    p = "/hermes/virtoffice/status.json"
    try:
        if time.time() - os.path.getmtime(p) < max_age:
            return json.load(open(p))
    except Exception:
        pass
    return None


def hermes_current_task():
    """What Hermes says it is doing: current_task.txt (read directly, no publisher needed)."""
    try:
        t = open("/hermes/virtoffice/current_task.txt").read().strip()
        if t:
            return t
    except Exception:
        pass
    own = (hermes_status_file() or {}).get("current") or {}
    return own.get("task")


def hermes_project(task, disc):
    m = re.search(r"[Pp]royecto «?([\w\- ]+)", task)
    if m:
        return m.group(1).strip()
    where = (disc or {}).get("where") or ""
    return where if disc and not where.startswith("#") else None


def hermes_state():
    try:
        d = json.load(open("/hermes/gateway_state.json"))
    except Exception:
        d = {}
    work = d.get("active_work")
    running = d.get("gateway_state") == "running"
    own = hermes_current_task()  # what Hermes itself wrote, fresher than active_work
    disc = current_task("hermes")
    if own and running:
        work = own
    elif disc and running:
        work = disc["text"]
    if work:
        task = work if isinstance(work, str) else json.dumps(work, ensure_ascii=False)[:80]
        status = "working"
    else:
        task, status = ("Esperando tareas" if running else "Gateway parado"), ("idle" if running else "offline")
    return {
        "id": "hermes", "name": "Hermes", "role": "Hermes Agent · GitHub/Portainer", "emoji": "☤",
        "color": "#8B5CF6", "home": "right", "status": status, "typing": status == "working",
        "area": pick_area(task, hermes_project(task, disc), bool(disc and disc["from"] == "Claude")) if status == "working" else "rest",
        "project": hermes_project(task, disc) if status == "working" else None,
        "where": disc["where"] if disc else None, "from": disc["from"] if disc else None,
        "task": task, "tasks": [f"{disc['from']}: {task}" if disc and work == disc["text"] else task] if work else ["Libre"],
        "output": recent_done("hermes"), "mood": 0.85,
        "stats": {"tasksDone": done_today("hermes"), "active": 1 if work else 0, "hours": hours_today("hermes")},
    }


EVENTS = []  # recent status changes, newest first

# --- Encargos por Discord: lo que se pide a cada agente, con su estado ---
TASKS_FILE = os.environ.get("TASKS_FILE", "/data/tasks.json")
NAMES = {"HaZ": "Brayan", "HaZ_Claude": "Claude", "HaZ_Hermes": "Hermes"}
DISCORD_IDS = {"468243292551774209": "Brayan", "1567165207988412527": "Claude"}


def load_tasks():
    try:
        return json.load(open(TASKS_FILE))
    except Exception:
        return []


def save_tasks(tasks):
    try:
        os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
        tmp = TASKS_FILE + ".tmp"
        json.dump(tasks, open(tmp, "w"), ensure_ascii=False)
        os.replace(tmp, TASKS_FILE)
    except Exception as e:
        print("tasks save error:", e, flush=True)


TASKS = load_tasks()
CLAUDE_PROCS = []  # running `claude -p` requests: dicts with key, who, text, where


def short(text, n=240):
    t = re.sub(r"<@&?\d+>", "", text or "")
    t = re.sub(r"\*\*|__|`", "", t)  # Discord markdown
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[:n - 1] + "…"


def claude_tasks(now):
    keys = set()
    for p in CLAUDE_PROCS:
        keys.add(p["key"])
        if not any(t["id"] == p["key"] for t in TASKS):
            TASKS.append({"id": p["key"], "agent": "claude", "from": p["who"], "text": p["text"], "where": p["where"],
                          "started": now, "ended": None, "status": "working"})
    for t in TASKS:
        if t["agent"] == "claude" and t["status"] == "working" and t["id"] not in keys:
            t["status"], t["ended"] = "done", now


SKIP_HEADERS = ("Replying to", "Context around", "Recent channel messages", "New message")


def parse_hermes_message(content):
    """(sender, text) of the new message inside what the gateway hands Hermes, or None for notices."""
    c = content or ""
    if "[INTERNAL NOTIFICATION" in c or "[IMPORTANT: Background process" in c[:200]:
        return None
    if c.startswith("[OUT-OF-BAND USER MESSAGE"):
        body = c.split("fields are insufficient.", 1)[-1].split("[/OUT-OF-BAND", 1)[0]
        uid = re.search(r'"user_id": "(\d+)"', c)
        return DISCORD_IDS.get(uid.group(1) if uid else "", "Discord"), body
    last = None
    for m in re.finditer(r"(?m)^\[([^\]\n]{1,40})\] ?", c):
        if not m.group(1).startswith(SKIP_HEADERS):
            last = m
    if not last:
        return None
    who = last.group(1).replace(" [bot]", "").strip()
    return NAMES.get(who, who), c[last.end():]


def hermes_tasks(now):
    """Turns of Hermes in Discord from its state.db: a user message starts a task, the final
    assistant reply (no tool calls) ends it."""
    import sqlite3
    try:
        c = sqlite3.connect("file:/hermes/state.db?mode=ro", uri=True, timeout=2)
        top = c.execute("select max(id) from messages").fetchone()[0] or 0
        rows = c.execute(
            "select m.id, m.session_id, m.role, m.content, m.tool_calls, m.timestamp, s.display_name "
            "from messages m join sessions s on s.id = m.session_id "
            "where m.id > ? and s.source = 'discord' order by m.id", (top - 4000,)).fetchall()
        c.close()
    except Exception as e:
        return {"error": str(e)}
    open_by_session, last_activity = {}, 0
    for mid, sid, role, content, tool_calls, ts, name in rows:
        last_activity = max(last_activity, ts)
        cur = open_by_session.get(sid)
        if role == "user":
            msg = parse_hermes_message(content)
            if not msg or not short(msg[1]):
                continue
            if cur:
                cur["status"], cur["ended"] = "done", ts
            key = f"h{mid}"
            t = next((x for x in TASKS if x["id"] == key), None)
            if not t:
                t = {"id": key, "agent": "hermes", "from": msg[0], "text": short(msg[1]),
                     "where": (name or "").split(" / ")[-1], "started": ts, "ended": None, "status": "working"}
                TASKS.append(t)
            open_by_session[sid] = t
        elif cur and role == "assistant" and not tool_calls and (content or "").strip():
            cur["status"], cur["ended"] = "done", ts
            open_by_session.pop(sid, None)
    # A turn left open long ago (gateway restart, crash) is not still running.
    for t in open_by_session.values():
        if now - t["started"] > 1800 and now - last_activity > 600:
            t["status"], t["ended"] = "done", t["ended"] or last_activity
    return {}


def update_tasks():
    now = time.time()
    before = json.dumps(TASKS, sort_keys=True)
    claude_tasks(now)
    hermes_tasks(now)
    TASKS.sort(key=lambda t: t["started"])
    del TASKS[:-150]
    if json.dumps(TASKS, sort_keys=True) != before:
        save_tasks(TASKS)


def current_task(agent):
    """Newest unfinished Discord request of an agent."""
    for t in reversed(TASKS):
        if t["agent"] == agent and t["status"] == "working":
            return t
    return None


def hours_today(agent):
    start = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
    now = time.time()
    secs = sum(max(0, (t["ended"] or now) - max(t["started"], start)) for t in TASKS
               if t["agent"] == agent and (t["ended"] or now) > start)
    return round(secs / 3600, 1)


def recent_done(agent, n=5):
    return [f"✅ {t['from']}: {short(t['text'], 120)}" for t in reversed(TASKS)
            if t["agent"] == agent and t["status"] == "done"][:n]


def done_today(agent):
    day = time.strftime("%Y-%m-%d")
    return sum(1 for t in TASKS if t["agent"] == agent and t["status"] == "done"
               and time.strftime("%Y-%m-%d", time.localtime(t["ended"] or t["started"])) == day)


def note_changes(prev, agents):
    old = {a["id"]: (a["status"], a["task"]) for a in (prev or [])}
    for a in agents:
        if old.get(a["id"]) != (a["status"], a["task"]):
            EVENTS.insert(0, {"t": time.strftime("%H:%M:%S"), "who": a["name"], "status": a["status"], "task": a["task"]})
    del EVENTS[60:]


def hermes_extra():
    """Fresh status.json from Hermes if there is one; otherwise read its kanban and cron files directly."""
    fresh = hermes_status_file()
    if fresh:
        return fresh
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
        CLAUDE_PROCS[:] = claude_requests()
        update_tasks()
        agents = [hermes_state(), claude_state()]
        h, c = agents
        if h["project"] and c["project"] and h["project"].lower() == c["project"].lower():
            h["area"] = c["area"] = "meeting"
        for a in agents:
            if a["area"] != "rest" and a["project"] and a["area"] == "desk":
                a["area"] = "project"
        key = json.dumps(agents, sort_keys=True)
        if key != last:
            note_changes(prev, agents)
            print(time.strftime("%H:%M:%S"), push(agents), [(a["name"], a["status"], a["task"]) for a in agents], flush=True)
            last, prev = key, agents
        if tick % 2 == 0:  # panels: every 10 s
            data = {"updated": time.strftime("%H:%M:%S"), "agents": agents, "events": EVENTS,
                    "hermes": hermes_extra(), "metrics": metrics(),
                    "tasks": [dict(t, started=int(t["started"]), ended=int(t["ended"]) if t["ended"] else None)
                              for t in reversed(TASKS[-60:])]}
            put_file("/app/public", "data.json", json.dumps(data, ensure_ascii=False).encode())
        tick += 1
    except Exception as e:
        print("error:", e, flush=True)
    time.sleep(5)
