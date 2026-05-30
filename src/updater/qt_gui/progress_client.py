"""Helpers for the Qt updater GUI progress model."""

import json
import urllib.request
from urllib.parse import urlsplit, urlunsplit


def normalize_progress(payload: dict) -> dict:
    """Normalize updater /progress JSON for QML consumption."""
    try:
        data = payload["data"]
        stage = str(data["stage"])
        progress = int(data["progress"])
        message = str(data["message"])
        error = data.get("error") or ""
    except Exception:
        return {
            "stage": "waiting",
            "progress": 0,
            "message": "Waiting for updater...",
            "error": "",
            "terminal": False,
        }

    return {
        "stage": stage,
        "progress": max(0, min(100, progress)),
        "message": message,
        "error": str(error),
        "terminal": stage in {"success", "failed"},
    }


def merge_progress_update(previous: dict, incoming: dict) -> dict:
    """Merge a new poll result without regressing visible install progress."""
    previous = previous if isinstance(previous, dict) else {}
    incoming = incoming if isinstance(incoming, dict) else {}
    stage = str(incoming.get("stage") or "")
    previous_stage = str(previous.get("stage") or "")

    if stage == "waiting" and previous_stage not in {"", "waiting"}:
        merged = dict(previous)
        merged["message"] = str(incoming.get("message") or merged.get("message") or "")
        merged["error"] = str(incoming.get("error") or "")
        merged["terminal"] = False
        return merged

    if stage == previous_stage == "installing":
        merged = dict(incoming)
        merged["progress"] = max(
            int(previous.get("progress") or 0),
            int(incoming.get("progress") or 0),
        )
        return merged

    return dict(incoming)


def _return_to_system_url(progress_url: str) -> str:
    parts = urlsplit(progress_url)
    path = parts.path
    if path.endswith("/progress"):
        path = path.removesuffix("/progress") + "/return-to-system"
    else:
        path = "/api/v1.0/return-to-system"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def request_return_to_system(progress_url: str, timeout: float = 1.0) -> bool:
    """Ask updater backend to finish terminal wait and switch display back."""
    url = _return_to_system_url(progress_url)
    request = urllib.request.Request(url, data=b"{}", method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
    except Exception:
        return False
    return True


def fetch_progress(url: str, timeout: float = 1.0) -> dict:
    """Fetch and normalize updater progress using stdlib HTTP."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return normalize_progress({})
    return normalize_progress(payload)
