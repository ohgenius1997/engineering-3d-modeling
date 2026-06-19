from __future__ import annotations

import http.client
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_parameter_patch
import init_model_project
import roll_revision
import serve_review
import sync_review_parameters
import validate_model_project


def load_yaml():
    import yaml  # type: ignore

    return yaml


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="e3dm-test-", dir="/private/tmp"))
        self.project = self.tmp / "demo-model"
        init_model_project.scaffold(self.project, "Demo Model", "part", False, False)
        sync_review_parameters.sync(self.project, include_locked=False)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_patch(self, patch: dict) -> None:
        path = self.project / "review" / "parameter_patch.json"
        path.write_text(json.dumps(patch, indent=2) + "\n", encoding="utf-8")

    def patch_doc(self, parameter_id: str, value: object, unit: str = "mm") -> dict:
        return {
            "schema": "engineering-3d-modeling.parameter_patch.v1",
            "patches": [
                {
                    "parameter_id": parameter_id,
                    "value": value,
                    "unit": unit,
                    "reason": "unit-test",
                    "source": "review-html",
                }
            ],
        }

    def test_apply_parameter_patch_rejects_invalid_values(self) -> None:
        cases = [
            (self.patch_doc("unknown", 55.0), "unknown parameter"),
            (self.patch_doc("body_length", "55"), "value type string"),
            (self.patch_doc("body_length", 999.0), "above max"),
            (self.patch_doc("body_height", 8.25), "does not align to step"),
            (self.patch_doc("body_width", 30.0, unit="inch"), "unit 'inch' does not match"),
        ]
        for patch, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                self.write_patch(patch)
                result = apply_parameter_patch.apply_patch(self.project, clear_patch=False, dry_run=False)
                self.assertEqual(result["status"], "fail")
                self.assertIn(expected_error, "\n".join(result["errors"]))

    def test_apply_parameter_patch_accepts_valid_value(self) -> None:
        self.write_patch(self.patch_doc("body_length", 55.0))
        result = apply_parameter_patch.apply_patch(self.project, clear_patch=True, dry_run=False)
        self.assertEqual(result["status"], "pass", result)
        yaml = load_yaml()
        params = yaml.safe_load((self.project / "parameters.yaml").read_text(encoding="utf-8"))
        self.assertEqual(params["parameters"]["body_length"]["value"], 55.0)
        patch = json.loads((self.project / "review" / "parameter_patch.json").read_text(encoding="utf-8"))
        self.assertEqual(patch["patches"], [])

    def post_review(self, server, payload: dict) -> tuple[int, dict]:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        body = json.dumps(payload).encode("utf-8")
        conn.request("POST", "/api/save-review", body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        conn.close()
        return response.status, data

    def test_save_api_validates_payload_before_writing(self) -> None:
        from http.server import ThreadingHTTPServer

        server = ThreadingHTTPServer(("127.0.0.1", 0), serve_review.make_handler(self.project))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            annotations = {"schema": "engineering-3d-modeling.annotations.v1", "annotations": []}
            invalid_patch = self.patch_doc("unknown", 30.0)
            status, body = self.post_review(server, {"annotations": annotations, "parameter_patch": invalid_patch})
            self.assertEqual(status, 400)
            self.assertIn("unknown parameter", "\n".join(body["errors"]))

            malformed = {"schema": "wrong", "patches": []}
            status, body = self.post_review(server, {"annotations": annotations, "parameter_patch": malformed})
            self.assertEqual(status, 400)
            self.assertIn("expected const", "\n".join(body["errors"]))

            valid_patch = self.patch_doc("body_width", 30.0)
            status, body = self.post_review(server, {"annotations": annotations, "parameter_patch": valid_patch})
            self.assertEqual(status, 200, body)
            saved = json.loads((self.project / "review" / "parameter_patch.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["patches"][0]["parameter_id"], "body_width")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_validator_runs_manifest_schema(self) -> None:
        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["parameters"][0]["preview"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        report = validate_model_project.validate(self.project, require_step=False)
        self.assertEqual(report["status"], "fail")
        self.assertIn("missing required property 'preview'", "\n".join(report["errors"]))

    def test_roll_revision_requires_force_for_populated_previous(self) -> None:
        previous = self.project / "previous"
        previous.mkdir(exist_ok=True)
        (previous / "old.txt").write_text("old\n", encoding="utf-8")

        plan = roll_revision.roll(self.project, dry_run=True)
        self.assertEqual(plan["status"], "dry-run")
        self.assertIn("old.txt", plan["would_overwrite"])
        with self.assertRaises(RuntimeError):
            roll_revision.roll(self.project)

        result = roll_revision.roll(self.project, force=True)
        self.assertEqual(result["status"], "pass")
        self.assertFalse((previous / "old.txt").exists())


if __name__ == "__main__":
    unittest.main()
