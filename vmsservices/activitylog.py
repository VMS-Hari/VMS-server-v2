import json
import threading
from datetime import datetime

from pathlib import Path
from django.conf import settings
from django.utils import timezone

# Menus that have backend logging. Add a key here for each new module.
ACTIVITY_MODULES = ["site_type", "site_model"]

_lock = threading.Lock()


def _log_dir():
    return Path(getattr(settings, "ACTIVITY_LOG_DIR", settings.BASE_DIR / "logs"))


def _log_file(module, day):
    return _log_dir() / module / f"{module}_{day:%Y-%m-%d}.log"


def write_log(module, action, user, details, status="SUCCESS", ref=None):
    """Append one line to today's log file. Never breaks the request."""
    now = timezone.localtime()

    entry = {
        "timestamp": now.isoformat(),
        "date_time": now.strftime("%d-%m-%Y %I:%M:%S %p"),
        "user": getattr(user, "login_id", None) or "anonymous",
        "action": action,        # Created / Updated / Deleted / Failed
        "status": status,        # SUCCESS / FAILED
        "details": details,
        "ref": ref,              # guid of the record
    }

    try:
        path = _log_file(module, now.date())
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_logs(module, day):
    """Return that day's entries, newest first."""
    path = _log_file(module, day)

    if not path.exists():
        return []

    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    entries.reverse()
    return entries