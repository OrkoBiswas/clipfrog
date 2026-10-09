from __future__ import annotations

import hmac
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MOGRT_DIR = ROOT / "subtitles" / "pack 1"
JSX_TEMPLATE = ROOT / "scripts" / "mogrt_render.jsx"
STATE_DIR = ROOT / ".local" / "mogrt-agent"
TOKEN_FILE = STATE_DIR / "token"
PORT = int(os.environ.get("CLIPFORGE_MOGRT_AGENT_PORT", "8765"))
TEMPLATE_NUMBERS = {f"mogrt-pack1-{index:02}": f"{index:02}" for index in range(1, 5)}
RENDER_LOCK = threading.Lock()


def executable(name: str, env_name: str, candidates: list[Path]) -> str:
    configured = os.environ.get(env_name)
    if configured and Path(configured).is_file():
        return configured
    available = shutil.which(name)
    if available:
        return available
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(f"{name} was not found; configure {env_name}.")


def after_effects_tools() -> tuple[str, str, str]:
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    support = program_files / "Adobe" / "Adobe After Effects 2025" / "Support Files"
    afterfx = executable("AfterFX.com", "CLIPFORGE_AFTERFX_CONSOLE", [support / "AfterFX.com"])
    aerender = executable("aerender.exe", "CLIPFORGE_AERENDER", [support / "aerender.exe"])
    ffmpeg = executable(
        "ffmpeg.exe",
        "CLIPFORGE_FFMPEG",
        [Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"],
    )
    return afterfx, aerender, ffmpeg


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Render request must be a JSON object.")
    template_id = payload.get("template")
    number = TEMPLATE_NUMBERS.get(template_id)
    if not number:
        raise ValueError("Unknown Pack 1 MOGRT template.")
    width, height = payload.get("width"), payload.get("height")
    duration = payload.get("duration")
    size = payload.get("size", 42)
    if not isinstance(width, int) or not 2 <= width <= 3840:
        raise ValueError("Render width must be between 2 and 3840 pixels.")
    if not isinstance(height, int) or not 2 <= height <= 3840:
        raise ValueError("Render height must be between 2 and 3840 pixels.")
    if not isinstance(duration, (int, float)) or not 0 < duration <= 300:
        raise ValueError("Render duration must be between 0 and 300 seconds.")
    if not isinstance(size, (int, float)) or not 20 <= size <= 120:
        raise ValueError("Caption size must be between 20 and 120.")
    raw_cues = payload.get("cues")
    if not isinstance(raw_cues, list) or len(raw_cues) > 300:
        raise ValueError("A render can contain at most 300 caption cues.")
    cues = []
    for cue in raw_cues:
        if not isinstance(cue, dict):
            continue
        text = cue.get("text")
        start, end = cue.get("start"), cue.get("end")
        if not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        start = max(0.0, float(start))
        end = min(float(duration), float(end))
        if end <= start:
            continue
        cues.append(
            {
                "text": " ".join(text.replace("\x00", "").split())[:500],
                "start": start,
                "end": end,
                "x": min(0.95, max(0.05, float(cue.get("x", 0.5)))),
                "y": min(0.95, max(0.05, float(cue.get("y", 0.5)))),
            }
        )
    return {
        "number": number,
        "template": template_id,
        "width": width,
        "height": height,
        "duration": float(duration),
        "size": float(size),
        "primary_color": payload.get("primary_color", "#FFFFFF"),
        "effect_color": payload.get("effect_color", "#0054FF"),
        "shadow_color": payload.get("shadow_color", "#000000"),
        "shadow_opacity": min(1.0, max(0.0, float(payload.get("shadow_opacity", 0.5)))),
        "weight": payload.get("weight", 700),
        "cues": cues,
    }


def render(payload: dict[str, Any]) -> Path:
    afterfx, aerender, ffmpeg = after_effects_tools()
    number = payload["number"]
    mogrt_path = MOGRT_DIR / f"Subtitles {number}.mogrt"
    if not mogrt_path.is_file():
        raise RuntimeError(f"Source MOGRT is missing: {mogrt_path.name}")
    with tempfile.TemporaryDirectory(prefix="clipforge-mogrt-") as directory:
        work = Path(directory)
        with zipfile.ZipFile(mogrt_path) as archive:
            graphic = archive.read("project.aegraphic")
        with zipfile.ZipFile(__import__("io").BytesIO(graphic)) as archive:
            project_bytes = archive.read("Subtitles MOGRT.aep")
        input_project = work / "template.aep"
        input_project.write_bytes(project_bytes)
        output_project = work / "render.aep"
        raw_render = work / "render.avi"
        alpha_render = work / "overlay.mov"
        ae_payload = {
            **payload,
            "input_project": str(input_project),
            "output_project": str(output_project),
            "status_file": str(work / "ae-status.txt"),
            "export_comp": f"Subtitles {number} Export",
        }
        template = JSX_TEMPLATE.read_text(encoding="utf-8")
        jsx = template.replace("__MOGRT_PAYLOAD__", json.dumps(ae_payload, ensure_ascii=True))
        jsx_path = work / "render.jsx"
        jsx_path.write_text(jsx, encoding="utf-8")
        completed = subprocess.run(
            [afterfx, "-r", str(jsx_path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        status_file = work / "ae-status.txt"
        status = status_file.read_text(encoding="utf-8") if status_file.is_file() else "no AE status"
        if completed.returncode or not output_project.is_file() or status.startswith("error:"):
            detail = (completed.stderr or completed.stdout)[-4000:]
            raise RuntimeError(f"After Effects could not prepare the MOGRT ({status}): {detail}")
        render_result = subprocess.run(
            [
                aerender,
                "-project",
                str(output_project),
                "-comp",
                "ClipForge MOGRT Sequence",
                "-OMtemplate",
                "Lossless with Alpha",
                "-output",
                str(raw_render),
                "-v",
                "ERRORS",
            ],
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        if render_result.returncode or not raw_render.is_file():
            detail = (render_result.stderr or render_result.stdout)[-4000:]
            raise RuntimeError(f"After Effects failed to render the MOGRT: {detail}")
        encoded = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(raw_render),
                "-an",
                "-c:v",
                "qtrle",
                "-pix_fmt",
                "argb",
                str(alpha_render),
                "-y",
            ],
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        if encoded.returncode or not alpha_render.is_file():
            detail = (encoded.stderr or encoded.stdout)[-4000:]
            raise RuntimeError(f"Could not encode the MOGRT alpha overlay: {detail}")
        result = STATE_DIR / f"overlay-{secrets.token_hex(12)}.mov"
        shutil.copyfile(alpha_render, result)
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "ClipForgeMogrtAgent/1.0"

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        body = b'{"status":"ok","renderer":"After Effects"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/render":
            self.send_error(404)
            return
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        supplied = self.headers.get("X-ClipForge-MOGRT-Token", "")
        if not hmac.compare_digest(token, supplied):
            self.send_error(401)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 2_000_000:
            self.send_error(413)
            return
        try:
            payload = validate_payload(json.loads(self.rfile.read(length)))
            with RENDER_LOCK:
                result = render(payload)
            body = result.read_bytes()
            result.unlink(missing_ok=True)
            self.send_response(200)
            self.send_header("Content-Type", "video/quicktime")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as error:
            body = json.dumps({"detail": str(error)}).encode("utf-8")
            self.send_response(422)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print("MOGRT agent:", format % args)


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not TOKEN_FILE.exists():
        TOKEN_FILE.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"ClipForge After Effects MOGRT agent listening on port {PORT}.")
    print(f"Worker token shared at {TOKEN_FILE}.")
    server.serve_forever()


if __name__ == "__main__":
    main()