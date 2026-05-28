"""Helpers for the Qt updater GUI progress model."""

import json
import urllib.request


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


def fetch_progress(url: str, timeout: float = 1.0) -> dict:
    """Fetch and normalize updater progress using stdlib HTTP."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return normalize_progress({})
    return normalize_progress(payload)
