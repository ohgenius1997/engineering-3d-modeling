#!/usr/bin/env python3
"""Serve a model project's review UI and save review data to local files."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import review_validation


MAX_BODY_BYTES = 5 * 1024 * 1024


def json_bytes(data: object) -> bytes:
    return (json.dumps(data, indent=2) + "\n").encode("utf-8")


def safe_path(project: Path, request_path: str) -> Path | None:
    parsed = urlparse(request_path)
    raw = unquote(parsed.path)
    if raw == "/":
        raw = "/review/index.html"
    candidate = (project / raw.lstrip("/")).resolve()
    if candidate == project or project in candidate.parents:
        return candidate
    return None


def make_handler(project: Path):
    class ReviewHandler(BaseHTTPRequestHandler):
        server_version = "EngineeringReview/0.1"

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.address_string()} - {format % args}")

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def send_json(self, status: HTTPStatus, payload: object) -> None:
            body = json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Allow", "GET, POST, OPTIONS")
            self.end_headers()

        def do_GET(self) -> None:
            if urlparse(self.path).path == "/api/review-state":
                self.handle_review_state()
                return

            path = safe_path(project, self.path)
            if path is None or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/save-review":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.handle_save_review()

        def handle_review_state(self) -> None:
            annotations_path = project / "review" / "annotations.json"
            patch_path = project / "review" / "parameter_patch.json"
            self.send_json(
                HTTPStatus.OK,
                {
                    "schema": "engineering-3d-modeling.review_state.v1",
                    "project": str(project),
                    "targets": {
                        "annotations": str(annotations_path.relative_to(project)),
                        "parameter_patch": str(patch_path.relative_to(project)),
                    },
                    "exists": {
                        "annotations": annotations_path.exists(),
                        "parameter_patch": patch_path.exists(),
                    },
                },
            )

        def handle_save_review(self) -> None:
            content_length = self.headers.get("Content-Length")
            if content_length is None:
                self.send_json(HTTPStatus.LENGTH_REQUIRED, {"error": "missing Content-Length"})
                return

            try:
                length = int(content_length)
            except ValueError:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid Content-Length"})
                return

            if length > MAX_BODY_BYTES:
                self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request body too large"})
                return

            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": f"invalid JSON: {exc}"})
                return

            annotations = payload.get("annotations") if isinstance(payload, dict) else None
            parameter_patch = payload.get("parameter_patch") if isinstance(payload, dict) else None
            if not isinstance(annotations, dict) or not isinstance(parameter_patch, dict):
                self.send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "payload must include object fields: annotations, parameter_patch"},
                )
                return
            if not isinstance(annotations.get("annotations"), list):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "annotations.annotations must be a list"})
                return
            if not isinstance(parameter_patch.get("patches"), list):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "parameter_patch.patches must be a list"})
                return

            errors = []
            try:
                errors.extend(f"annotations: {error}" for error in review_validation.validate_annotations_schema(annotations))
                errors.extend(
                    f"parameter_patch: {error}"
                    for error in review_validation.validate_patch_against_project(project, parameter_patch)
                )
            except RuntimeError as exc:
                errors.append(str(exc))
            if errors:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid review payload", "errors": errors})
                return

            review_dir = project / "review"
            review_dir.mkdir(parents=True, exist_ok=True)
            annotations_path = review_dir / "annotations.json"
            patch_path = review_dir / "parameter_patch.json"
            annotations_path.write_bytes(json_bytes(annotations))
            patch_path.write_bytes(json_bytes(parameter_patch))

            self.send_json(
                HTTPStatus.OK,
                {
                    "schema": "engineering-3d-modeling.save_result.v1",
                    "status": "saved",
                    "written": [
                        str(annotations_path.relative_to(project)),
                        str(patch_path.relative_to(project)),
                    ],
                },
            )

    return ReviewHandler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root containing review/index.html")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    project = Path(args.project_path).expanduser().resolve()
    if not project.is_dir():
        parser.error(f"project_path is not a directory: {project}")

    server = ThreadingHTTPServer((args.host, args.port), make_handler(project))
    host, port = server.server_address
    print(f"Serving review UI for {project}")
    print(f"http://{host}:{port}/review/index.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping review server")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
