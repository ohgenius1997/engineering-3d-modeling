from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_parameter_patch
import audit_project_consistency
import audit_review_parameters
import begin_model_iteration
import init_model_project
import iteration_utils
import promote_model_project
import regenerate_from_review
import restore_previous
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

    def set_phase(self, phase: str, *, backend_override: dict | None = None) -> None:
        yaml = load_yaml()
        spec_path = self.project / "spec" / "current.yaml"
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        spec.setdefault("lifecycle", {})["phase"] = phase
        if backend_override is not None:
            spec.setdefault("backend", {})["override"] = backend_override
        spec_path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

    def current_phase(self) -> str:
        yaml = load_yaml()
        spec = yaml.safe_load((self.project / "spec" / "current.yaml").read_text(encoding="utf-8"))
        return spec["lifecycle"]["phase"]

    def write_step_output(self) -> None:
        step_path = self.project / "outputs" / "step" / "demo-model.step"
        step_path.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")

    def write_step_manifest(self, state: str, *, stale: bool = False) -> None:
        iteration_utils.write_step_manifest(
            self.project,
            state=state,
            generated_for_phase="draft_review" if state == "draft" else state,
            generated_by="unit-test",
            promoted_by="scripts/promote_model_project.py" if state in {"accepted_current", "release_handoff"} else None,
            stale=stale,
            stale_reason="unit test" if stale else None,
        )

    def write_mesh_cache(self) -> None:
        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["versions"]["current"]["source"] = "../source/model.py"
        manifest["preview"]["mesh_json"] = "cache/current_mesh.json"
        manifest["preview"]["mesh_closed"] = True
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        yaml = load_yaml()
        params = yaml.safe_load((self.project / "parameters.yaml").read_text(encoding="utf-8"))
        mesh_parameters = {
            parameter_id: data["value"]
            for parameter_id, data in params["parameters"].items()
            if isinstance(data, dict) and "value" in data
        }
        mesh = {
            "schema": "engineering-3d-modeling.preview_mesh.v1",
            "units": "mm",
            "source": "source/model.py",
            "parameters": mesh_parameters,
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "faces": [
                {"indices": [0, 2, 1]},
                {"indices": [0, 1, 3]},
                {"indices": [1, 2, 3]},
                {"indices": [2, 0, 3]},
            ],
        }
        (self.project / "review" / "cache" / "current_mesh.json").write_text(
            json.dumps(mesh, indent=2) + "\n",
            encoding="utf-8",
        )

    def write_current_validation_report(self) -> None:
        yaml = load_yaml()
        spec = yaml.safe_load((self.project / "spec" / "current.yaml").read_text(encoding="utf-8"))
        phase = spec["lifecycle"]["phase"]
        manifest = json.loads((self.project / "review" / "manifest.json").read_text(encoding="utf-8"))
        step_files = sorted((self.project / "outputs" / "step").glob("*.step"))
        snapshot = validate_model_project.build_snapshot(
            self.project,
            phase=phase,
            phase_source="spec.lifecycle.phase",
            spec=spec,
            manifest=manifest,
            step_files=step_files,
        )
        report = {
            "schema": "engineering-3d-modeling.validation_report.v1",
            "generated_at": snapshot["generated_at"],
            "phase": {"value": phase, "source": "spec.lifecycle.phase"},
            "status": "pass",
            "checks": [{"check": "step_export", "status": "pass", "path": "outputs/step/demo-model.step"}],
            "warnings": [],
            "errors": [],
            "outputs": {"assembly_step": "outputs/step/demo-model.step", "part_steps": []},
            "snapshot": snapshot,
        }
        (self.project / "validation" / "report.json").write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

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

    def write_fake_model_source(self) -> None:
        (self.project / "source" / "model.py").write_text(
            '''from __future__ import annotations

from pathlib import Path


class Vec:
    def __init__(self, x: float, y: float, z: float) -> None:
        self.X = x
        self.Y = y
        self.Z = z


class Box:
    def __init__(self, length: float, width: float, height: float) -> None:
        self.min = Vec(-length / 2, -width / 2, -height / 2)
        self.max = Vec(length / 2, width / 2, height / 2)
        self.size = Vec(length, width, height)


class Model:
    def __init__(self, length: float, width: float, height: float) -> None:
        self.length = length
        self.width = width
        self.height = height

    def bounding_box(self) -> Box:
        return Box(self.length, self.width, self.height)

    def volume(self) -> float:
        return self.length * self.width * self.height

    def area(self) -> float:
        return 2 * (self.length * self.width + self.length * self.height + self.width * self.height)


def load_parameters(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def value(params: dict, parameter_id: str) -> float:
    return float(params["parameters"][parameter_id]["value"])


def build_model(params: dict) -> Model:
    return Model(value(params, "body_length"), value(params, "body_width"), value(params, "body_height"))
''',
            encoding="utf-8",
        )

    def test_review_template_uses_cached_cad_edges_and_precise_pick_helpers(self) -> None:
        template = (SKILL_ROOT / "assets" / "review-template" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('data-edge-mode="mesh"', template)
        self.assertNotIn('data-edge-mode="off"', template)
        self.assertNotIn("eg3dReviewEdgeMode", template)
        self.assertNotIn("buildEdgeIndex", template)
        self.assertIn("function buildRenderCache", template)
        self.assertIn("RENDER_CACHE_EDGE_FACE_LIMIT", template)
        self.assertIn("DIRECT_PREVIEW_EDGE_MAX_SEGMENTS", template)
        self.assertIn("function classifyEdgeCacheGroups", template)
        self.assertIn("function addEdgesForFaces", template)
        self.assertIn("limitedFaceIndices", template)
        self.assertIn("function drawDirectPreviewEdges", template)
        self.assertIn("cadEdgeCandidates", template)
        self.assertIn("function barycentric2d", template)
        self.assertIn("function closestPointOnSegment", template)
        self.assertIn("state.hoverTarget", template)

        node = shutil.which("node")
        if not node:
            self.skipTest("node is required for inline review-template JS syntax check")
        script = template.split("<script>", 1)[1].split("</script>", 1)[0]
        result = subprocess.run(
            [node, "-e", "new Function(require('fs').readFileSync(0, 'utf-8'))"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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

    def test_validator_allows_missing_step_in_draft_review_phase(self) -> None:
        report = validate_model_project.validate(self.project)
        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["phase"]["value"], "draft_review")
        self.assertFalse(report["step_requirement"]["required"])
        self.assertIn("phase draft_review allows missing STEP/STP", "\n".join(report["warnings"]))

    def test_validator_requires_step_in_accepted_current_phase(self) -> None:
        self.set_phase("accepted_current")
        report = validate_model_project.validate(self.project)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(report["step_requirement"]["required"])
        self.assertIn("phase accepted_current requires STEP/STP output", "\n".join(report["errors"]))

        self.write_step_output()
        self.write_step_manifest("accepted_current")
        report = validate_model_project.validate(self.project)
        self.assertEqual(report["status"], "pass", report)
        self.assertIn({"check": "step-output", "status": "pass"}, report["checks"])

    def test_consistency_audit_warns_when_draft_review_lacks_step(self) -> None:
        report = audit_project_consistency.audit(self.project)
        self.assertEqual(report["status"], "warn", report)
        codes = {item["code"]: item["severity"] for item in report["issues"]}
        self.assertEqual(codes.get("step_missing_draft"), "warning")
        self.assertNotIn("step_missing_required_phase", codes)

    def test_consistency_audit_fails_when_current_phases_lack_step(self) -> None:
        for phase in ["accepted_current", "release_handoff"]:
            with self.subTest(phase=phase):
                self.set_phase(phase)
                report = audit_project_consistency.audit(self.project)
                self.assertEqual(report["status"], "fail", report)
                codes = {item["code"] for item in report["errors"]}
                self.assertIn("step_missing_required_phase", codes)

    def test_consistency_audit_flags_manifest_legacy_source(self) -> None:
        legacy_source = self.project / "source" / "fusion360_legacy.py"
        legacy_source.write_text("# legacy Fusion source\n", encoding="utf-8")
        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["versions"]["current"]["source"] = "../source/fusion360_legacy.py"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        report = audit_project_consistency.audit(self.project)
        codes = {item["code"]: item["severity"] for item in report["issues"]}
        self.assertEqual(codes.get("manifest_current_source_legacy_backend"), "warning")

        strict = audit_project_consistency.audit(self.project, mode="strict")
        strict_codes = {item["code"]: item["severity"] for item in strict["errors"]}
        self.assertEqual(strict_codes.get("manifest_current_source_legacy_backend"), "error")

    def test_consistency_audit_warns_on_stale_brief_backend_or_parameter(self) -> None:
        (self.project / "brief.md").write_text(
            """# Demo Model

The current model is a Fusion 360 API script.

- Body length: 99.0 mm.
""",
            encoding="utf-8",
        )
        report = audit_project_consistency.audit(self.project)
        codes = {item["code"] for item in report["warnings"]}
        self.assertIn("brief_stale_backend_reference", codes)
        self.assertIn("brief_stale_parameter_value", codes)

    def test_consistency_audit_fails_on_stale_validation_report_current_fields(self) -> None:
        self.write_step_output()
        self.write_mesh_cache()
        self.set_phase("accepted_current")
        self.write_current_validation_report()
        report_path = self.project / "validation" / "report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["current_body_length"] = "99.0 mm"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        strict = audit_project_consistency.audit(self.project, mode="strict")
        codes = {item["code"] for item in strict["errors"]}
        self.assertIn("validation_report_stale_parameter_value", codes)

    @unittest.skipUnless(os.environ.get("ENGINEERING_3D_SAMPLE_PROJECT"), "sample project path not configured")
    def test_consistency_audit_detects_guide_vane_sample_drift(self) -> None:
        sample = Path(os.environ["ENGINEERING_3D_SAMPLE_PROJECT"])
        report = audit_project_consistency.audit(sample, mode="strict")
        self.assertEqual(report["status"], "fail", report)
        codes = {item["code"] for item in report["errors"] + report["warnings"]}
        self.assertIn("step_manifest_missing", codes)
        self.assertIn("brief_stale_backend_reference", codes)
        self.assertIn("validation_report_stale_parameter_value", codes)

    def test_validator_uses_strict_audit_for_release_handoff_phase(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_step_manifest("release_handoff")
        self.write_mesh_cache()
        self.set_phase("release_handoff")
        self.write_current_validation_report()

        report = validate_model_project.validate(self.project)
        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["review_parameter_audit_mode"], "strict")
        self.assertEqual(report["step_requirement"]["reason"], "phase:release_handoff")
        self.assertEqual(report["consistency_audit_mode"], "strict")

    def test_validator_require_step_overrides_draft_review_phase(self) -> None:
        report = validate_model_project.validate(self.project, require_step=True)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(report["step_requirement"]["required"])
        self.assertEqual(report["step_requirement"]["reason"], "--require-step")

    def test_validator_requires_backend_override_record(self) -> None:
        self.set_phase("backend_override")
        report = validate_model_project.validate(self.project)
        self.assertEqual(report["status"], "fail")
        self.assertIn("phase backend_override requires", "\n".join(report["errors"]))

        self.set_phase("backend_override", backend_override={"backend": "fusion360", "reason": "legacy solid backend"})
        report = validate_model_project.validate(self.project)
        self.assertEqual(report["status"], "pass", report)
        self.assertIn({"check": "phase:backend_override-record", "status": "pass"}, report["checks"])

    def regenerate_review_project(self) -> dict:
        return regenerate_from_review.regenerate(
            self.project,
            python_executable=sys.executable,
            skip_environment_check=True,
            skip_sync_review_parameters=False,
            skip_review_parameter_audit=False,
            review_parameter_audit_mode="basic",
            skip_validation=False,
            skip_geometry_smoke=True,
            keep_patch=False,
            allow_pending_annotations=False,
            clear_annotations=False,
        )

    def regenerate_review_project_starting_iteration(self, *, force_iteration: bool = False) -> dict:
        return regenerate_from_review.regenerate(
            self.project,
            python_executable=sys.executable,
            skip_environment_check=True,
            skip_sync_review_parameters=False,
            skip_review_parameter_audit=False,
            review_parameter_audit_mode="basic",
            skip_validation=False,
            skip_geometry_smoke=True,
            keep_patch=False,
            allow_pending_annotations=False,
            clear_annotations=False,
            start_new_iteration=True,
            force_iteration=force_iteration,
            iteration_reason="unit-test",
        )

    def test_regenerate_from_review_allows_missing_step_in_draft_review(self) -> None:
        self.write_fake_model_source()
        result = self.regenerate_review_project()
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["phase"]["value"], "draft_review")
        self.assertFalse(result["step_requirement"]["required"])
        self.assertFalse(list((self.project / "outputs" / "step").glob("*.step")))

    def test_regenerate_from_review_requires_step_in_accepted_current(self) -> None:
        self.write_fake_model_source()
        self.set_phase("accepted_current")
        result = self.regenerate_review_project()
        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(result["phase"]["value"], "accepted_current")
        self.assertIn("new iteration boundary", result["steps"][-1]["message"])

    def test_regenerate_release_handoff_starts_new_iteration_as_draft(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_step_manifest("release_handoff")
        self.write_mesh_cache()
        self.set_phase("release_handoff")

        result = self.regenerate_review_project_starting_iteration()
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(self.current_phase(), "draft_review")
        self.assertTrue((self.project / "previous" / "spec" / "current.yaml").is_file())
        manifest = json.loads((self.project / "outputs" / "step" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "draft")

    def test_promote_draft_review_to_accepted_current(self) -> None:
        self.write_step_output()

        result = promote_model_project.promote(self.project, target_phase="accepted_current")

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(self.current_phase(), "accepted_current")
        self.assertIn("spec/current.yaml", result["written"])
        self.assertIn("validation/report.json", result["written"])
        validation_report = json.loads((self.project / "validation" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(validation_report["phase"]["value"], "accepted_current")
        self.assertTrue(validation_report["step_requirement"]["required"])

    def test_promote_treats_invalid_phase_as_draft_with_warning(self) -> None:
        self.write_step_output()
        self.set_phase("stale_done")

        result = promote_model_project.promote(self.project, target_phase="accepted_current")

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(self.current_phase(), "accepted_current")
        self.assertIn("not a valid lifecycle phase", "\n".join(result["warnings"]))

    def test_promote_fails_with_unconsumed_annotations_without_phase_change(self) -> None:
        annotations = {
            "schema": "engineering-3d-modeling.annotations.v1",
            "annotations": [
                {
                    "id": "ann-001",
                    "created_at": "2026-06-19T00:00:00Z",
                    "text": "Increase clearance.",
                    "target": None,
                    "status": "open",
                }
            ],
        }
        (self.project / "review" / "annotations.json").write_text(
            json.dumps(annotations, indent=2) + "\n",
            encoding="utf-8",
        )

        result = promote_model_project.promote(self.project, target_phase="accepted_current")

        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(self.current_phase(), "draft_review")
        self.assertIn("unconsumed annotation", "\n".join(result["errors"]))

    def test_promote_fails_with_unapplied_parameter_patch_without_phase_change(self) -> None:
        self.write_patch(self.patch_doc("body_length", 55.0))

        result = promote_model_project.promote(self.project, target_phase="accepted_current")

        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(self.current_phase(), "draft_review")
        self.assertIn("unapplied patch", "\n".join(result["errors"]))

    def test_promote_accepted_current_to_release_handoff(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_step_manifest("accepted_current")
        self.write_mesh_cache()
        self.set_phase("accepted_current")
        self.write_current_validation_report()

        result = promote_model_project.promote(self.project, target_phase="release_handoff")

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(self.current_phase(), "release_handoff")
        step_names = [step["step"] for step in result["steps"]]
        self.assertIn("accepted-current-consistency", step_names)
        self.assertIn("release-validation", step_names)
        self.assertIn("release-consistency", step_names)
        validation_report = json.loads((self.project / "validation" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(validation_report["phase"]["value"], "release_handoff")
        self.assertEqual(validation_report["consistency_audit_mode"], "strict")
        self.assertIn("snapshot", validation_report)

    def test_promote_release_fails_without_current_report_snapshot(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_step_manifest("accepted_current")
        self.write_mesh_cache()
        self.set_phase("accepted_current")

        result = promote_model_project.promote(self.project, target_phase="release_handoff")

        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(self.current_phase(), "accepted_current")
        self.assertIn("validation/report.json", "\n".join(result["errors"]))

    def test_promote_blocks_backend_override_without_acceptance_reason(self) -> None:
        self.write_step_output()
        self.set_phase("backend_override", backend_override={"backend": "fusion360", "reason": "legacy solid backend"})

        result = promote_model_project.promote(self.project, target_phase="accepted_current")

        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(self.current_phase(), "backend_override")
        self.assertIn("backend_override", "\n".join(result["errors"]))

    def test_promote_blocks_direct_release_unless_skip_is_explicit(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_mesh_cache()

        blocked = promote_model_project.promote(self.project, target_phase="release_handoff")
        self.assertEqual(blocked["status"], "fail", blocked)
        self.assertEqual(self.current_phase(), "draft_review")
        self.assertIn("cannot promote directly", "\n".join(blocked["errors"]))

        promoted = promote_model_project.promote(
            self.project,
            target_phase="release_handoff",
            allow_skip_accepted=True,
        )
        self.assertEqual(promoted["status"], "pass", promoted)
        self.assertEqual(self.current_phase(), "release_handoff")
        step_names = [step["step"] for step in promoted["steps"]]
        self.assertIn("accepted-validation", step_names)
        self.assertIn("release-validation", step_names)

    def test_validator_accepts_declared_preview_adapter(self) -> None:
        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["preview"]["adapter_js"] = "cache/preview_adapter.js"
        manifest["parameters"][0]["preview"] = {"effect": "adapter", "baseline": manifest["parameters"][0]["value"]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        adapter_path = self.project / "review" / "cache" / "preview_adapter.js"
        adapter_path.write_text(
            "window.Engineering3DPreviewAdapter = {generateMesh() { return {vertices: [[0,0,0]], faces: []}; }};\n",
            encoding="utf-8",
        )

        report = validate_model_project.validate(self.project, require_step=False)
        self.assertEqual(report["status"], "pass", report)
        self.assertIn({"check": "preview-adapter", "status": "pass"}, report["checks"])

    def test_validator_rejects_adapter_parameter_without_adapter_script(self) -> None:
        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["parameters"][0]["preview"] = {"effect": "adapter", "baseline": manifest["parameters"][0]["value"]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        report = validate_model_project.validate(self.project, require_step=False)
        self.assertEqual(report["status"], "fail")
        self.assertIn("require preview.adapter_js", "\n".join(report["errors"]))

    def test_validator_rejects_preview_adapter_outside_review(self) -> None:
        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["preview"]["adapter_js"] = "../outside.js"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        report = validate_model_project.validate(self.project, require_step=False)
        self.assertEqual(report["status"], "fail")
        self.assertIn("adapter_js must stay under review", "\n".join(report["errors"]))

    def test_review_parameter_audit_rejects_stale_manifest_parameter(self) -> None:
        self.write_fake_model_source()
        yaml = load_yaml()
        params_path = self.project / "parameters.yaml"
        params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        params["parameters"]["shroud_wall"] = {
            "value": 2.0,
            "unit": "mm",
            "preview": {"effect": "scale_axis", "axis": "x", "baseline": 2.0, "anchor": "center"},
            "ui": {"editable": True, "control": "slider", "min": 1.0, "max": 5.0, "step": 0.5},
            "validation": {"affects_geometry": True},
        }
        params_path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")

        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["parameters"].append(
            {
                "id": "shroud_wall",
                "label": "Shroud wall",
                "value": 2.0,
                "unit": "mm",
                "min": 1.0,
                "max": 5.0,
                "step": 0.5,
                "preview": {"effect": "scale_axis", "axis": "x", "baseline": 2.0, "anchor": "center"},
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        audit = audit_review_parameters.audit(self.project, mode="strict")
        self.assertEqual(audit["status"], "fail", audit)
        disabled = {item["id"]: item["reason"] for item in audit["disabled_parameters"]}
        self.assertIn("shroud_wall", disabled)
        self.assertIn("did not change backend geometry", disabled["shroud_wall"])

        report = validate_model_project.validate(self.project, require_step=False, review_parameter_audit="strict")
        self.assertEqual(report["status"], "fail")
        self.assertIn("shroud_wall", "\n".join(report["errors"]))

    def test_review_parameter_audit_rejects_local_feature_generic_morph(self) -> None:
        yaml = load_yaml()
        params_path = self.project / "parameters.yaml"
        params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        params["parameters"]["front_chamfer_width"] = {
            "value": 1.0,
            "unit": "mm",
            "role": "localized_chamfer",
            "preview": {"effect": "generic_morph", "baseline": 1.0, "rationale": "incorrect test binding"},
            "ui": {"editable": True, "control": "slider", "min": 0.0, "max": 3.0, "step": 0.25},
            "validation": {"affects_geometry": True, "affects_local_feature": True},
        }
        params_path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")

        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["parameters"].append(
            {
                "id": "front_chamfer_width",
                "label": "Front chamfer width",
                "value": 1.0,
                "unit": "mm",
                "min": 0.0,
                "max": 3.0,
                "step": 0.25,
                "preview": {"effect": "generic_morph", "baseline": 1.0, "rationale": "incorrect test binding"},
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        audit = audit_review_parameters.audit(self.project, mode="basic")
        self.assertEqual(audit["status"], "fail", audit)
        disabled = {item["id"]: item["reason"] for item in audit["disabled_parameters"]}
        self.assertIn("front_chamfer_width", disabled)
        self.assertIn("must not use preview.effect generic_morph", disabled["front_chamfer_width"])

    def test_review_parameter_audit_requires_scope_for_generic_morph_in_strict_mode(self) -> None:
        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["parameters"][0]["preview"] = {"effect": "generic_morph", "baseline": manifest["parameters"][0]["value"]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        basic = audit_review_parameters.audit(self.project, mode="basic")
        self.assertEqual(basic["status"], "warn", basic)
        self.assertIn("generic_morph must declare", "\n".join(basic["warnings"]))

        strict = audit_review_parameters.audit(self.project, mode="strict")
        self.assertEqual(strict["status"], "fail", strict)
        disabled = {item["id"]: item["reason"] for item in strict["disabled_parameters"]}
        self.assertIn("body_length", disabled)
        self.assertIn("generic_morph must declare", disabled["body_length"])

    def test_review_parameter_audit_allows_scoped_generic_morph_for_global_parameter(self) -> None:
        self.write_fake_model_source()
        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["parameters"][0]["preview"] = {
            "effect": "generic_morph",
            "baseline": manifest["parameters"][0]["value"],
            "scope": "whole-envelope preview approximation",
            "rationale": "unit test global envelope parameter",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        audit = audit_review_parameters.audit(self.project, mode="strict")
        self.assertNotEqual(audit["status"], "fail", audit)
        self.assertIn("body_length", audit["valid_preview_parameters"])

    def test_review_parameter_audit_reports_backend_only_candidate(self) -> None:
        self.write_fake_model_source()
        manifest_path = self.project / "review" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["parameters"] = [param for param in manifest["parameters"] if param["id"] != "body_length"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        yaml = load_yaml()
        params_path = self.project / "parameters.yaml"
        params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        del params["parameters"]["body_length"]["preview"]
        params_path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")

        audit = audit_review_parameters.audit(self.project, mode="strict")
        candidates = {item["id"]: item["reason"] for item in audit["new_candidates"]}
        self.assertIn("body_length", candidates)
        self.assertIn("affects backend geometry", candidates["body_length"])

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

    def test_draft_review_patch_requires_iteration_boundary(self) -> None:
        self.write_fake_model_source()
        self.write_patch(self.patch_doc("body_length", 55.0))

        blocked = self.regenerate_review_project()
        self.assertEqual(blocked["status"], "fail", blocked)
        self.assertIn("new iteration boundary", blocked["steps"][-1]["message"])

        begun = begin_model_iteration.begin_iteration(self.project, reason="unit-test")
        self.assertEqual(begun["status"], "pass", begun)
        self.assertTrue((self.project / "previous" / "parameters.yaml").is_file())
        result = self.regenerate_review_project()
        self.assertEqual(result["status"], "pass", result)
        iteration = json.loads((self.project / "validation" / "iteration.json").read_text(encoding="utf-8"))
        self.assertEqual(iteration["status"], "completed")

    def test_accepted_current_patch_requires_iteration_by_default(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_step_manifest("accepted_current")
        self.set_phase("accepted_current")
        self.write_patch(self.patch_doc("body_length", 55.0))

        result = self.regenerate_review_project()
        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(self.current_phase(), "accepted_current")
        self.assertIn("new iteration boundary", result["steps"][-1]["message"])

    def test_accepted_current_start_new_iteration_returns_to_draft(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_step_manifest("accepted_current")
        self.set_phase("accepted_current")
        self.write_patch(self.patch_doc("body_length", 55.0))

        result = self.regenerate_review_project_starting_iteration()
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(self.current_phase(), "draft_review")
        self.assertTrue((self.project / "previous" / "outputs" / "step" / "demo-model.step").is_file())
        manifest = json.loads((self.project / "outputs" / "step" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "draft")
        self.assertIsNone(manifest["promoted_by"])

    def test_draft_step_does_not_satisfy_accepted_or_release_validation(self) -> None:
        self.write_step_output()
        self.write_step_manifest("draft")
        for phase in ["accepted_current", "release_handoff"]:
            with self.subTest(phase=phase):
                self.set_phase(phase)
                report = validate_model_project.validate(self.project)
                self.assertEqual(report["status"], "fail")
                self.assertIn("requires outputs/step/manifest.json state", "\n".join(report["errors"]))

    def test_promote_accepted_current_marks_step_manifest(self) -> None:
        self.write_step_output()

        result = promote_model_project.promote(self.project, target_phase="accepted_current")

        self.assertEqual(result["status"], "pass", result)
        manifest = json.loads((self.project / "outputs" / "step" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "accepted_current")
        self.assertEqual(manifest["generated_for_phase"], "accepted_current")
        self.assertEqual(manifest["promoted_by"], "scripts/promote_model_project.py")

    def test_promote_release_handoff_marks_step_manifest(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_step_manifest("accepted_current")
        self.write_mesh_cache()
        self.set_phase("accepted_current")
        self.write_current_validation_report()

        result = promote_model_project.promote(self.project, target_phase="release_handoff")

        self.assertEqual(result["status"], "pass", result)
        manifest = json.loads((self.project / "outputs" / "step" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "release_handoff")
        self.assertEqual(manifest["generated_for_phase"], "release_handoff")
        self.assertEqual(manifest["promoted_by"], "scripts/promote_model_project.py")

    def test_restore_previous_restores_current_truth_and_outputs(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_step_manifest("accepted_current")
        self.write_mesh_cache()
        self.set_phase("accepted_current")
        self.write_current_validation_report()

        begun = begin_model_iteration.begin_iteration(self.project, reason="unit-test")
        self.assertEqual(begun["status"], "pass", begun)

        yaml = load_yaml()
        params_path = self.project / "parameters.yaml"
        params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        params["parameters"]["body_length"]["value"] = 77.0
        params_path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")
        (self.project / "source" / "model.py").write_text("# modified source\n", encoding="utf-8")
        self.set_phase("draft_review")
        (self.project / "validation" / "report.json").write_text('{"modified": true}\n', encoding="utf-8")
        self.write_patch(self.patch_doc("body_width", 30.0))
        (self.project / "outputs" / "step" / "demo-model.step").write_text("modified step\n", encoding="utf-8")

        dry = restore_previous.restore_previous(self.project)
        self.assertEqual(dry["status"], "dry-run")
        restored = restore_previous.restore_previous(self.project, force=True)
        self.assertEqual(restored["status"], "pass", restored)

        params = yaml.safe_load((self.project / "parameters.yaml").read_text(encoding="utf-8"))
        self.assertEqual(params["parameters"]["body_length"]["value"], 40.0)
        self.assertIn("class Model", (self.project / "source" / "model.py").read_text(encoding="utf-8"))
        self.assertEqual(self.current_phase(), "accepted_current")
        report = json.loads((self.project / "validation" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["phase"]["value"], "accepted_current")
        patch = json.loads((self.project / "review" / "parameter_patch.json").read_text(encoding="utf-8"))
        self.assertEqual(patch["patches"], [])
        self.assertIn("ISO-10303-21", (self.project / "outputs" / "step" / "demo-model.step").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
