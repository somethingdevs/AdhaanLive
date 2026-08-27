"""Controlled local smoke test for imports and HTTP/static serving."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def fetch(url: str) -> bytes:
    with urlopen(url, timeout=2) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return response.read()


def wait_for_server(url: str, process: subprocess.Popen, timeout: float = 10) -> bytes:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"Server exited during startup:\n{output}")
        try:
            return fetch(url)
        except (URLError, TimeoutError):
            time.sleep(0.1)
    raise RuntimeError(f"Server did not become ready within {timeout} seconds")


def main() -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    subprocess.run(
        [sys.executable, "-B", "-c", "import main"],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )

    port = available_port()
    base_url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-m",
            "uvicorn",
            "api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        health = json.loads(wait_for_server(f"{base_url}/health", process))
        if health != {"status": "ok"}:
            raise RuntimeError(f"Unexpected health response: {health}")

        schedule = json.loads(fetch(f"{base_url}/schedule"))
        if "error" not in schedule:
            required_schedule_fields = {"date", "timezone", "prayers"}
            if not required_schedule_fields.issubset(schedule):
                raise RuntimeError(f"Unexpected schedule response: {schedule}")

        index = fetch(f"{base_url}/").decode("utf-8")
        policy = fetch(f"{base_url}/static/playback_policy.js").decode("utf-8")
        schedule_time = fetch(
            f"{base_url}/static/schedule_time.js"
        ).decode("utf-8")
        app_js = fetch(f"{base_url}/static/app.js").decode("utf-8")

        if 'id="adhaan-player"' not in index:
            raise RuntimeError("Frontend did not include the Adhaan audio player")
        if "shouldPlayAdhaan" not in policy or "shouldPlayAdhaan" not in app_js:
            raise RuntimeError("Frontend playback policy was not served or connected")
        if "getPrayerState" not in schedule_time or "getPrayerState" not in app_js:
            raise RuntimeError("Frontend schedule policy was not served or connected")

        print("Smoke test passed: imports, health endpoint, and frontend assets are ready")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
