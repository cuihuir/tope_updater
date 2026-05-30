"""Unit tests for Qt updater GUI progress normalization."""

from updater.qt_gui.progress_client import (
    merge_progress_update,
    normalize_progress,
    request_return_to_system,
)


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

def test_merge_progress_keeps_last_valid_progress_on_temporary_waiting_state():
    previous = {
        "stage": "installing",
        "progress": 47,
        "message": "Installing module printer-gui...",
        "error": "",
        "terminal": False,
    }
    incoming = {
        "stage": "waiting",
        "progress": 0,
        "message": "Waiting for updater...",
        "error": "",
        "terminal": False,
    }

    result = merge_progress_update(previous, incoming)

    assert result["stage"] == "installing"
    assert result["progress"] == 47
    assert result["message"] == "Waiting for updater..."

def test_merge_progress_does_not_regress_installing_progress():
    previous = {
        "stage": "installing",
        "progress": 64,
        "message": "Installing module printer-gui-0320...",
        "error": "",
        "terminal": False,
    }
    incoming = {
        "stage": "installing",
        "progress": 5,
        "message": "Installing version 0.1.6...",
        "error": "",
        "terminal": False,
    }

    result = merge_progress_update(previous, incoming)

    assert result["stage"] == "installing"
    assert result["progress"] == 64
    assert result["message"] == "Installing version 0.1.6..."

def test_request_return_to_system_posts_to_return_endpoint(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, request.get_method(), timeout))

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"code":200}'

        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert request_return_to_system("http://127.0.0.1:12315/api/v1.0/progress")

    assert calls == [
        ("http://127.0.0.1:12315/api/v1.0/return-to-system", "POST", 1.0)
    ]
