"""Unit tests for Qt updater GUI progress normalization."""

from updater.qt_gui.progress_client import normalize_progress


def test_normalize_success_response():
    result = normalize_progress(
        {
            "code": 200,
            "msg": "success",
            "data": {
                "stage": "installing",
                "progress": 42,
                "message": "Installing module printer-gui...",
                "error": None,
            },
        }
    )

    assert result == {
        "stage": "installing",
        "progress": 42,
        "message": "Installing module printer-gui...",
        "error": "",
        "terminal": False,
    }


def test_normalize_failed_response_is_terminal():
    result = normalize_progress(
        {
            "code": 500,
            "msg": "Update failed",
            "data": {
                "stage": "failed",
                "progress": 0,
                "message": "Update failed",
                "error": "DEPLOYMENT_FAILED",
            },
        }
    )

    assert result["stage"] == "failed"
    assert result["terminal"] is True
    assert result["error"] == "DEPLOYMENT_FAILED"


def test_normalize_invalid_response_returns_waiting_state():
    result = normalize_progress({"bad": "shape"})

    assert result["stage"] == "waiting"
    assert result["progress"] == 0
    assert result["terminal"] is False


def test_normalize_clamps_progress_to_100():
    result = normalize_progress(
        {
            "data": {
                "stage": "installing",
                "progress": 150,
                "message": "Installing...",
                "error": None,
            },
        }
    )

    assert result["progress"] == 100
