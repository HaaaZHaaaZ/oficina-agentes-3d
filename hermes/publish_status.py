import json, time, os
from datetime import datetime, timezone

JOBS_FILE = "/opt/data/cron/jobs.json"
STATUS_FILE = "/opt/data/virtoffice/status.json"
CURRENT_FILE = "/opt/data/virtoffice/current_task.txt"

def read_cron():
    try:
        d = json.load(open(JOBS_FILE))
        out = []
        for j in d.get("jobs", []):
            sched = j.get("schedule", {})
            expr = sched.get("expr", sched.get("display", ""))
            if not j.get("enabled"):
                continue
            out.append({
                "name": j["name"],
                "schedule": expr,
                "enabled": bool(j.get("enabled")),
                "last_status": j.get("last_status"),
                "next_run_at": j.get("next_run_at"),
            })
        return out
    except Exception:
        return []

def read_current():
    try:
        task = open(CURRENT_FILE).read().strip()
        if task:
            return {"task": task, "since": datetime.now(timezone.utc).isoformat()}
    except FileNotFoundError:
        pass
    return None

while True:
    status = {
        "source": "hermes",
        "updated": datetime.now(timezone.utc).isoformat(),
        "current": read_current(),
        "kanban": [],
        "cron": read_cron(),
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, ensure_ascii=False)
    time.sleep(15)
