"""
JARVIS Web Server API & Static Dashboard Host.
Provides REST API endpoints for state management, task CRUD, command execution,
and serves the futuristic Cyberpunk HUD web dashboard.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import urllib.parse

import brain
import db
import tts

log = logging.getLogger("jarvis.server")

WEB_DIR = Path(__file__).resolve().parent / "web"
LOG_BUFFER: list[dict] = []
MAX_LOGS = 100
START_TIME = time.time()


def add_log_entry(message: str, level: str = "INFO") -> None:
    entry = {
        "timestamp": time.strftime("%H:%M:%S"),
        "level": level,
        "message": message,
    }
    LOG_BUFFER.append(entry)
    if len(LOG_BUFFER) > MAX_LOGS:
        LOG_BUFFER.pop(0)


class JarvisRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        # Suppress default noisy HTTP logging to keep console clean
        pass

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.is_file():
            self.send_error(404, "File not found")
            return
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            uptime = int(time.time() - START_TIME)
            all_tasks = db.list_tasks(include_done=True)
            pending_tasks = [t for t in all_tasks if not t["done"]]
            status_data = {
                "status": "online",
                "system": f"{platform.system()} {platform.release()}",
                "model": brain.MODEL,
                "uptime_seconds": uptime,
                "total_tasks": len(all_tasks),
                "pending_tasks": len(pending_tasks),
                "mic_spec": os.environ.get("JARVIS_INPUT_DEVICE", "Default Mic"),
                "elevenlabs_configured": bool(os.environ.get("ELEVENLABS_API_KEY")),
                "anthropic_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
            }
            self._send_json(status_data)
            return

        if path == "/api/tasks":
            query = urllib.parse.parse_qs(parsed.query)
            include_done = query.get("include_done", ["true"])[0].lower() == "true"
            tasks = db.list_tasks(include_done=include_done)
            self._send_json({"tasks": tasks})
            return

        if path == "/api/logs":
            self._send_json({"logs": LOG_BUFFER})
            return

        # Serve static web files
        if path == "/" or path == "/index.html":
            self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/style.css":
            self._send_file(WEB_DIR / "style.css", "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._send_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        raw_data = self.rfile.read(length) if length > 0 else b"{}"

        try:
            data = json.loads(raw_data.decode("utf-8")) if raw_data else {}
        except Exception:
            data = {}

        if path == "/api/command":
            cmd = data.get("command", "").strip()
            if not cmd:
                self._send_json({"error": "Empty command"}, 400)
                return
            add_log_entry(f"Command received: '{cmd}'")
            reply = brain.handle_command(cmd)
            add_log_entry(f"Reply: '{reply}'")

            # Speak response in background
            threading.Thread(target=tts.speak, args=(reply,), daemon=True).start()
            self._send_json({"command": cmd, "reply": reply})
            return

        if path == "/api/tasks":
            text = data.get("text", "").strip()
            if not text:
                self._send_json({"error": "Text is required"}, 400)
                return
            due_mins = data.get("due_minutes")
            if due_mins is not None:
                try:
                    due_mins = float(due_mins)
                except ValueError:
                    due_mins = None
            tid = db.add_task(text, due_mins)
            add_log_entry(f"Task added: #{tid} - {text}")
            self._send_json({"id": tid, "message": "Task added successfully"})
            return

        if path == "/api/tasks/complete":
            tid = data.get("task_id")
            if not tid:
                self._send_json({"error": "task_id required"}, 400)
                return
            ok = db.complete_task(int(tid))
            add_log_entry(f"Task #{tid} completed")
            self._send_json({"success": ok})
            return

        if path == "/api/tasks/delete":
            tid = data.get("task_id")
            if not tid:
                self._send_json({"error": "task_id required"}, 400)
                return
            ok = db.delete_task(int(tid))
            add_log_entry(f"Task #{tid} deleted")
            self._send_json({"success": ok})
            return

        self.send_error(404, "Not Found")


def run_server(host: str = "127.0.0.1", port: int = 8000) -> HTTPServer:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    server = HTTPServer((host, port), JarvisRequestHandler)
    add_log_entry(f"JARVIS API & Dashboard server running at http://{host}:{port}")
    log.info("JARVIS Web Dashboard & API server listening at http://%s:%d", host, port)
    return server


def start_server_thread(host: str = "127.0.0.1", port: int = 8000) -> threading.Thread:
    server = run_server(host, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    port_val = int(os.environ.get("JARVIS_WEB_PORT", "8000"))
    srv = run_server("127.0.0.1", port_val)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log.info("Server stopped.")
