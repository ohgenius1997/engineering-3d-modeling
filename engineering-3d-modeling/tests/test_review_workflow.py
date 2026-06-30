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
import zipfile


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_parameter_patch
import audit_project_consistency
import audit_spec_coverage
import audit_review_parameters
import begin_model_iteration
import checkpoint_preview_revision
import create_handoff_package
import export_step
import init_model_project
import iteration_utils
import promote_model_project
import regenerate_from_review
import restore_preview_revision
import restore_previous
import roll_revision
import review_validation
import serve_review
import summarize_model_project
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
        step_path = self.project / "outputs" / "step" / "demo-model.step"
        if step_path.is_file():
            iteration_utils.update_review_manifest_current(
                self.project,
                source_path=self.project / "source" / "model.py",
                step_path=step_path,
            )
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
            "provenance": {
                "spec_hash": validate_model_project.file_sha256(self.project / "spec" / "current.yaml"),
                "parameters_hash": validate_model_project.file_sha256(self.project / "parameters.yaml"),
                "source_hash": validate_model_project.file_sha256(self.project / "source" / "model.py"),
                "manifest_hash": validate_model_project.file_sha256(self.project / "review" / "manifest.json"),
                "generated_by": "unit-test",
                "generated_at": "2026-06-29T00:00:00Z",
            },
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

    def test_scaffold_agents_wakes_skill_without_copying_full_routing_table(self) -> None:
        agents = (self.project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("$engineering-3d-modeling", agents)
        self.assertIn("validation/current_context.json", agents)
        self.assertIn("references/context-routing.md", agents)
        self.assertIn("scripts/summarize_model_project.py", agents)
        self.assertIn("review annotation clarity gate", agents)
        self.assertNotIn("new_model_project", agents)
        self.assertNotIn("preview_vs_cad_mismatch", agents)

    def test_scaffold_brief_is_short_and_has_no_open_questions(self) -> None:
        brief = (self.project / "brief.md").read_text(encoding="utf-8")
        self.assertNotIn("Open Questions", brief)
        self.assertNotIn("## Assumptions", brief)
        self.assertLessEqual(len([line for line in brief.splitlines() if line.strip()]), 16)
        self.assertIn("spec/current.yaml", brief)

    def test_scaffold_spec_has_structured_authoring_sections(self) -> None:
        yaml = load_yaml()
        spec = yaml.safe_load((self.project / "spec" / "current.yaml").read_text(encoding="utf-8"))
        for key in [
            "coordinate_system",
            "placements",
            "features",
            "constraints",
            "decisions",
            "validation_targets",
        ]:
            self.assertIn(key, spec)
        self.assertIn("current_context", spec["validation"])
        self.assertIn("spec_coverage", spec["validation"])
        self.assertIn("feature_registry", spec["validation"])
        self.assertIn("layout_report", spec["validation"])

    def test_scaffold_source_smoke_does_not_write_step_or_manifest(self) -> None:
        manifest = json.loads((self.project / "review" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["versions"]["current"]["source"], "../source/model.py")
        self.assertIsNone(manifest["versions"]["current"]["step"])
        self.assertFalse((self.project / "outputs" / "step" / "manifest.json").exists())

        result = subprocess.run(
            [sys.executable, str(self.project / "source" / "model.py")],
            cwd=str(self.project),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STEP export is deferred", result.stdout)
        self.assertFalse(list((self.project / "outputs" / "step").glob("*.step")))
        self.assertFalse((self.project / "outputs" / "step" / "manifest.json").exists())

    def test_context_routing_reference_contains_tags_artifacts_and_clarity_gate(self) -> None:
        routing = (SKILL_ROOT / "references" / "context-routing.md").read_text(encoding="utf-8")
        for tag in [
            "new_model_project",
            "continue_existing_project",
            "consume_review_feedback",
            "update_review_preview",
            "parameter_preview_or_adapter",
            "geometry_feature_change",
            "assembly_alignment",
            "spec_coverage_audit",
            "step_export",
            "handoff_package",
            "preview_rollback",
            "preview_vs_cad_mismatch",
            "validation_failure",
        ]:
            self.assertIn(f"`{tag}`", routing)
        self.assertIn("## Artifact Directory", routing)
        self.assertIn("validation/feature_registry.json", routing)
        self.assertIn("## Review Annotation Clarity Gate", routing)
        for dimension in ["target", "operation", "reference", "direction", "dimensions", "scope", "preserve", "validation"]:
            self.assertIn(dimension, routing)
        self.assertIn("no direct STEP export", routing)
        self.assertIn("preview confirmation", routing)

    def test_summarize_model_project_human_json_and_current_context_outputs(self) -> None:
        annotations = {
            "schema": "engineering-3d-modeling.annotations.v1",
            "annotations": [
                {
                    "id": "ann-001",
                    "created_at": "2026-06-29T00:00:00Z",
                    "text": "Change selected hole to 3 mm.",
                    "target": None,
                    "status": "open",
                }
            ],
        }
        (self.project / "review" / "annotations.json").write_text(json.dumps(annotations, indent=2) + "\n", encoding="utf-8")
        self.write_patch(self.patch_doc("body_length", 55.0))

        context = summarize_model_project.summarize(self.project)
        self.assertEqual(context["project"]["name"], "Demo Model")
        self.assertEqual(context["pending_review"]["annotations"], 1)
        self.assertEqual(context["pending_review"]["parameter_patches"], 1)
        self.assertIn("review/annotations.json", context["recommended_next_reads"])
        self.assertIn("review/parameter_patch.json", context["recommended_next_reads"])

        human = summarize_model_project.human_summary(context)
        self.assertIn("Pending review: 1 annotation(s), 1 parameter patch(es)", human)

        written = summarize_model_project.write_current_context(self.project)
        saved = json.loads((self.project / "validation" / "current_context.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["schema"], "engineering-3d-modeling.current_context.v1")
        self.assertEqual(saved["pending_review"], written["pending_review"])

        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "summarize_model_project.py"), str(self.project), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        cli_context = json.loads(result.stdout)
        self.assertEqual(cli_context["pending_review"]["annotations"], 1)

    def test_current_context_control_plane_keeps_current_project_tiny(self) -> None:
        self.write_mesh_cache()

        context = summarize_model_project.summarize(self.project)

        self.assertEqual(context["routing"]["next_action"], "inspect")
        self.assertEqual(context["routing"]["context_cost"], "tiny")
        self.assertEqual(context["routing"]["minimum_reads"], ["validation/current_context.json"])
        self.assertNotIn("step_export", context["routing"]["recommended_tags"])
        self.assertEqual(context["trust"]["step"], "not_exported")
        self.assertTrue(context["ready_states"]["draft_review_ready"])
        self.assertFalse(context["ready_states"]["export_ready"])
        skipped = {item["gate"]: item["reason"] for item in context["gate_plan"]["skipped"]}
        self.assertIn("step_export", skipped)
        self.assertIn("user did not request STEP", skipped["step_export"])

    def test_current_context_parameter_patch_uses_small_context_projection(self) -> None:
        self.write_mesh_cache()
        self.write_patch(self.patch_doc("body_length", 55.0))

        context = summarize_model_project.summarize(self.project)

        self.assertEqual(context["routing"]["next_action"], "apply_parameter_patch")
        self.assertEqual(context["routing"]["context_cost"], "small")
        self.assertIn("review/parameter_patch.json", context["routing"]["minimum_reads"])
        self.assertIn("parameters.yaml", context["routing"]["minimum_reads"])
        self.assertNotIn("spec/current.yaml", context["routing"]["minimum_reads"])
        self.assertNotIn("source/model.py", context["routing"]["minimum_reads"])
        body_length = {item["id"]: item for item in context["parameter_state"]}["body_length"]
        self.assertEqual(body_length["status"], "patch_pending")
        self.assertEqual(body_length["truth_value"], 40.0)
        self.assertEqual(body_length["pending_patch_value"], 55.0)
        self.assertEqual(context["review_state"]["pending_input"]["parameter_patches"], 1)
        self.assertIn("apply_parameter_patch", context["gate_plan"]["required"])

    def test_current_context_high_risk_annotation_escalates_to_clarity_route(self) -> None:
        annotations = {
            "schema": "engineering-3d-modeling.annotations.v1",
            "annotations": [
                {
                    "id": "ann-hole",
                    "created_at": "2026-06-29T00:00:00Z",
                    "text": "Move this hole a bit.",
                    "target": None,
                    "status": "open",
                }
            ],
        }
        (self.project / "review" / "annotations.json").write_text(json.dumps(annotations, indent=2) + "\n", encoding="utf-8")

        context = summarize_model_project.summarize(self.project)

        self.assertEqual(context["routing"]["next_action"], "clarify_review_annotation")
        self.assertEqual(context["routing"]["context_cost"], "large")
        self.assertIn("high-risk annotation", " ".join(context["routing"]["escalation_reasons"]))
        self.assertIn("review_clarity", context["gate_plan"]["required"])
        self.assertIn("review/annotations.json", context["routing"]["minimum_reads"])
        self.assertIn("review/manifest.json", context["routing"]["minimum_reads"])
        self.assertEqual(context["review_state"]["annotation_clarity"]["status"], "fail")
        self.assertGreater(context["review_state"]["annotation_clarity"]["blocking_count"], 0)
        self.assertIn("high-risk", " ".join(context["blockers"]))

    def test_current_context_chinese_high_risk_annotation_escalates(self) -> None:
        for text, expected_term in [
            ("给这个孔加 M3 螺纹", "孔"),
            ("移动电池间隙", "电池"),
            ("调整卡扣槽", "卡扣"),
        ]:
            with self.subTest(text=text):
                annotations = {
                    "schema": "engineering-3d-modeling.annotations.v1",
                    "annotations": [
                        {
                            "id": "ann-cn",
                            "created_at": "2026-06-30T00:00:00Z",
                            "text": text,
                            "target": None,
                            "status": "open",
                        }
                    ],
                }
                (self.project / "review" / "annotations.json").write_text(
                    json.dumps(annotations, indent=2) + "\n",
                    encoding="utf-8",
                )

                context = summarize_model_project.summarize(self.project)

                self.assertEqual(context["routing"]["next_action"], "clarify_review_annotation")
                self.assertEqual(context["routing"]["context_cost"], "large")
                item = context["review_state"]["annotation_clarity"]["items"][0]
                self.assertTrue(item["high_risk"])
                self.assertIn(expected_term, item["risk_terms"])

    def test_current_context_snake_case_parameter_patch_escalates_context(self) -> None:
        yaml = load_yaml()
        params_path = self.project / "parameters.yaml"
        params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        params["parameters"]["pcb_mount_gap"] = {
            "value": 2.0,
            "unit": "mm",
            "validation": {"affects_geometry": True},
        }
        params_path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")
        self.write_patch(self.patch_doc("pcb_mount_gap", 3.0))

        context = summarize_model_project.summarize(self.project)

        self.assertEqual(context["routing"]["next_action"], "apply_parameter_patch")
        self.assertEqual(context["routing"]["context_cost"], "medium")
        self.assertIn("high-risk parameter", " ".join(context["routing"]["escalation_reasons"]))
        self.assertIn("spec/current.yaml", context["routing"]["minimum_reads"])
        self.assertIn("source/model.py", context["routing"]["minimum_reads"])
        self.assertIn("coverage_audit", context["gate_plan"]["required"])

    def test_scaffold_current_context_exposes_draft_review_without_step_export(self) -> None:
        context = json.loads((self.project / "validation" / "current_context.json").read_text(encoding="utf-8"))

        self.assertEqual(context["routing"]["next_action"], "update_review_preview")
        self.assertEqual(context["routing"]["context_cost"], "medium")
        self.assertTrue(context["ready_states"]["authoring_ready"])
        self.assertFalse(context["ready_states"]["review_preview_ready"])
        self.assertFalse(context["ready_states"]["draft_review_ready"])
        self.assertFalse(context["ready_states"]["export_ready"])
        self.assertEqual(context["trust"]["step"], "not_exported")
        self.assertIn("step_export", {item["gate"] for item in context["gate_plan"]["skipped"]})

    def test_review_validation_high_risk_terms_cover_identifiers_and_chinese(self) -> None:
        self.assertIn("hole", review_validation.high_risk_terms("hole_diameter"))
        self.assertIn("pcb", review_validation.high_risk_terms("pcb_mount_gap"))
        self.assertIn("孔", review_validation.high_risk_terms("给这个孔加 M3 螺纹"))

    def test_spec_coverage_audit_reports_missing_feature_and_unused_geometry_parameter(self) -> None:
        yaml = load_yaml()
        spec_path = self.project / "spec" / "current.yaml"
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        spec["features"] = [{"id": "fan_grille", "purpose": "air outlet"}]
        spec_path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

        params_path = self.project / "parameters.yaml"
        params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        params["parameters"]["battery_boost_gap"] = {
            "value": 2.0,
            "unit": "mm",
            "validation": {"affects_geometry": True},
        }
        params_path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")

        report = audit_spec_coverage.audit(self.project, write=True)
        self.assertEqual(report["status"], "warn", report)
        self.assertEqual(report["feature_gaps"][0]["id"], "fan_grille")
        self.assertEqual(report["unused_geometry_parameters"][0]["id"], "battery_boost_gap")
        self.assertTrue((self.project / "validation" / "spec_coverage.json").is_file())

        context = summarize_model_project.summarize(self.project)
        self.assertEqual(context["coverage"]["status"], "warn")
        self.assertIn("spec_coverage_audit", context["routing"]["recommended_tags"])
        self.assertIn("validation/spec_coverage.json", context["recommended_next_reads"])

    def test_spec_coverage_audit_honors_unused_reason(self) -> None:
        yaml = load_yaml()
        params_path = self.project / "parameters.yaml"
        params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        params["parameters"]["documentation_only_gap"] = {
            "value": 2.0,
            "unit": "mm",
            "validation": {"affects_geometry": True, "unused_reason": "reserved for later option"},
        }
        params_path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")

        report = audit_spec_coverage.audit(self.project)
        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["waived_unused_geometry_parameters"][0]["id"], "documentation_only_gap")

    def test_validate_model_project_checks_source_interface(self) -> None:
        source = self.project / "source" / "model.py"
        source.write_text(
            "from pathlib import Path\n"
            "def load_parameters(path: Path):\n"
            "    return {}\n",
            encoding="utf-8",
        )
        report = validate_model_project.validate(self.project, require_step=False)
        self.assertEqual(report["status"], "fail", report)
        self.assertIn("build_model", "\n".join(report["errors"]))

    def test_validate_model_project_warns_legacy_direct_source_step_export(self) -> None:
        source = self.project / "source" / "model.py"
        source.write_text(
            "from pathlib import Path\n"
            "def load_parameters(path: Path):\n"
            "    return {}\n"
            "def build_model(params):\n"
            "    return object()\n"
            "def write_step(model, path: Path):\n"
            "    pass\n"
            "def main():\n"
            "    write_step(build_model({}), Path('outputs/step/demo-model.step'))\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )
        report = validate_model_project.validate(self.project, require_step=False)
        self.assertIn("direct run appears to export STEP", "\n".join(report["warnings"]))

        strict = validate_model_project.validate(self.project, require_step=True)
        self.assertIn("direct run appears to export STEP", "\n".join(strict["errors"]))

    def test_summarize_model_project_reports_step_freshness_and_stale_hashes(self) -> None:
        self.write_exporting_fake_model_source()
        exported = export_step.export_step(self.project, python_executable=sys.executable)
        self.assertEqual(exported["status"], "pass", exported)

        fresh = summarize_model_project.summarize(self.project)
        self.assertEqual(fresh["step"]["state"], "exported")
        self.assertFalse(fresh["step"]["stale"], fresh["step"])

        yaml = load_yaml()
        params_path = self.project / "parameters.yaml"
        params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        params["parameters"]["body_length"]["value"] = 61.0
        params_path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")

        stale = summarize_model_project.summarize(self.project)
        self.assertTrue(stale["step"]["stale"], stale["step"])
        self.assertIn("parameters_hash", stale["step"]["freshness_mismatches"])

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

    def write_exporting_fake_model_source(self) -> None:
        self.write_fake_model_source()
        path = self.project / "source" / "model.py"
        path.write_text(
            path.read_text(encoding="utf-8")
            + '''

def write_step(model, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ISO-10303-21;\\nHEADER;\\nENDSEC;\\nDATA;\\nENDSEC;\\nEND-ISO-10303-21;\\n", encoding="utf-8")
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

    def test_validator_does_not_force_step_from_legacy_accepted_phase(self) -> None:
        self.set_phase("accepted_current")
        report = validate_model_project.validate(self.project)
        self.assertEqual(report["status"], "pass", report)
        self.assertFalse(report["step_requirement"]["required"])
        self.assertIn("allows missing STEP/STP", "\n".join(report["warnings"]))

        self.write_step_output()
        self.write_step_manifest("exported")
        report = validate_model_project.validate(self.project)
        self.assertEqual(report["status"], "pass", report)
        self.assertIn({"check": "step-output", "status": "pass"}, report["checks"])

    def test_consistency_audit_warns_when_draft_review_lacks_step(self) -> None:
        report = audit_project_consistency.audit(self.project)
        self.assertEqual(report["status"], "warn", report)
        codes = {item["code"]: item["severity"] for item in report["issues"]}
        self.assertEqual(codes.get("step_missing_draft"), "warning")
        self.assertNotIn("step_missing_required_phase", codes)

    def test_consistency_audit_warns_when_legacy_phases_lack_step_but_strict_fails(self) -> None:
        for phase in ["accepted_current", "release_handoff"]:
            with self.subTest(phase=phase):
                self.set_phase(phase)
                report = audit_project_consistency.audit(self.project)
                self.assertEqual(report["status"], "warn", report)
                codes = {item["code"] for item in report["warnings"]}
                self.assertIn("step_missing_draft", codes)
                strict = audit_project_consistency.audit(self.project, mode="strict")
                self.assertEqual(strict["status"], "fail", strict)

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

    def test_preview_provenance_stale_is_reported_by_audit_and_current_context(self) -> None:
        self.write_mesh_cache()
        source = self.project / "source" / "model.py"
        source.write_text(source.read_text(encoding="utf-8") + "\n# changed after preview\n", encoding="utf-8")

        report = audit_project_consistency.audit(self.project)
        codes = {item["code"] for item in report["warnings"]}
        self.assertIn("preview_provenance_stale", codes)

        context = summarize_model_project.summarize(self.project)
        self.assertEqual(context["preview"]["status"], "stale")
        self.assertIn("source_hash", context["preview"]["stale_reasons"])

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

    def test_validator_release_handoff_phase_is_lightweight_unless_strict_requested(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_mesh_cache()
        self.set_phase("release_handoff")
        self.write_step_manifest("release_handoff")
        self.write_current_validation_report()

        report = validate_model_project.validate(self.project)
        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["review_parameter_audit_mode"], "basic")
        self.assertFalse(report["step_requirement"]["required"])
        self.assertEqual(report["consistency_audit_mode"], "off")

        strict = validate_model_project.validate(self.project, require_step=True, consistency_audit="strict")
        self.assertEqual(strict["status"], "pass", strict)
        self.assertEqual(strict["consistency_audit_mode"], "strict")

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

    def test_regenerate_from_review_allows_legacy_accepted_phase_with_preview_checkpoint(self) -> None:
        self.write_fake_model_source()
        self.set_phase("accepted_current")
        result = self.regenerate_review_project()
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["phase"]["value"], "accepted_current")
        self.assertTrue((self.project / "checkpoints" / "preview_previous" / "parameters.yaml").is_file())

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

    def test_regenerate_blocks_unclear_high_risk_annotation(self) -> None:
        annotations = {
            "schema": "engineering-3d-modeling.annotations.v1",
            "annotations": [
                {
                    "id": "ann-hole",
                    "created_at": "2026-06-29T00:00:00Z",
                    "text": "Move this hole a bit.",
                    "target": None,
                    "status": "open",
                }
            ],
        }
        (self.project / "review" / "annotations.json").write_text(json.dumps(annotations, indent=2) + "\n", encoding="utf-8")

        result = regenerate_from_review.regenerate(
            self.project,
            python_executable=sys.executable,
            skip_environment_check=True,
            skip_sync_review_parameters=True,
            skip_review_parameter_audit=True,
            review_parameter_audit_mode="basic",
            skip_validation=True,
            skip_geometry_smoke=True,
            keep_patch=True,
            allow_pending_annotations=True,
            clear_annotations=True,
        )
        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(result["transaction"]["status"], "restored")
        self.assertIn("annotation-clarity", [step["step"] for step in result["steps"]])

    def test_regenerate_records_low_risk_clarity_assumption(self) -> None:
        self.write_fake_model_source()
        annotations = {
            "schema": "engineering-3d-modeling.annotations.v1",
            "annotations": [
                {
                    "id": "ann-label",
                    "created_at": "2026-06-29T00:00:00Z",
                    "text": "Make the label nicer.",
                    "target": None,
                    "status": "open",
                }
            ],
        }
        (self.project / "review" / "annotations.json").write_text(json.dumps(annotations, indent=2) + "\n", encoding="utf-8")

        result = regenerate_from_review.regenerate(
            self.project,
            python_executable=sys.executable,
            skip_environment_check=True,
            skip_sync_review_parameters=True,
            skip_review_parameter_audit=True,
            review_parameter_audit_mode="basic",
            skip_validation=True,
            skip_geometry_smoke=True,
            keep_patch=True,
            allow_pending_annotations=True,
            clear_annotations=False,
        )
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["transaction"]["status"], "committed")
        context = json.loads((self.project / "validation" / "current_context.json").read_text(encoding="utf-8"))
        self.assertEqual(context["assumptions"][0]["annotation_id"], "ann-label")

    def test_regenerate_failure_restores_transaction_files(self) -> None:
        original_context = json.loads((self.project / "validation" / "current_context.json").read_text(encoding="utf-8"))
        self.write_patch(self.patch_doc("unknown_parameter", 5.0))

        result = regenerate_from_review.regenerate(
            self.project,
            python_executable=sys.executable,
            skip_environment_check=True,
            skip_sync_review_parameters=True,
            skip_review_parameter_audit=True,
            review_parameter_audit_mode="basic",
            skip_validation=True,
            skip_geometry_smoke=True,
            keep_patch=True,
            allow_pending_annotations=False,
            clear_annotations=False,
        )
        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(result["transaction"]["status"], "restored")
        restored_context = json.loads((self.project / "validation" / "current_context.json").read_text(encoding="utf-8"))
        self.assertEqual(restored_context, original_context)

    def test_promote_draft_review_to_accepted_current(self) -> None:
        self.write_step_output()

        result = promote_model_project.promote(self.project, target_phase="accepted_current")

        self.assertEqual(result["status"], "pass", result)
        self.assertIn("compatibility flow", "\n".join(result["warnings"]))
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
        self.write_mesh_cache()
        self.set_phase("accepted_current")
        self.write_step_manifest("accepted_current")
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
        self.write_mesh_cache()
        self.set_phase("accepted_current")
        self.write_step_manifest("accepted_current")

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

    def test_draft_review_patch_creates_preview_checkpoint_by_default(self) -> None:
        self.write_fake_model_source()
        self.write_patch(self.patch_doc("body_length", 55.0))

        result = self.regenerate_review_project()
        self.assertEqual(result["status"], "pass", result)
        self.assertTrue((self.project / "checkpoints" / "preview_previous" / "parameters.yaml").is_file())
        preview_revision = json.loads((self.project / "validation" / "preview_revision.json").read_text(encoding="utf-8"))
        self.assertEqual(preview_revision["schema"], "engineering-3d-modeling.preview_revision.v1")

        begun = begin_model_iteration.begin_iteration(self.project, reason="unit-test")
        self.assertEqual(begun["status"], "pass", begun)
        self.assertTrue((self.project / "previous" / "parameters.yaml").is_file())
        self.write_patch(self.patch_doc("body_width", 30.0))
        result = self.regenerate_review_project()
        self.assertEqual(result["status"], "pass", result)
        iteration = json.loads((self.project / "validation" / "iteration.json").read_text(encoding="utf-8"))
        self.assertEqual(iteration["status"], "completed")

    def test_accepted_current_patch_marks_existing_step_stale_by_default(self) -> None:
        self.write_fake_model_source()
        self.write_step_output()
        self.write_step_manifest("accepted_current")
        self.set_phase("accepted_current")
        self.write_patch(self.patch_doc("body_length", 55.0))

        result = self.regenerate_review_project()
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(self.current_phase(), "accepted_current")
        manifest = json.loads((self.project / "outputs" / "step" / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["stale"])

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

    def test_draft_step_does_not_satisfy_forced_delivery_when_stale(self) -> None:
        self.write_step_output()
        self.write_step_manifest("draft", stale=True)
        for phase in ["accepted_current", "release_handoff"]:
            with self.subTest(phase=phase):
                self.set_phase(phase)
                report = validate_model_project.validate(self.project, require_step=True)
                self.assertEqual(report["status"], "fail")
                self.assertIn("STEP manifest is stale", "\n".join(report["errors"]))

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
        self.write_mesh_cache()
        self.set_phase("accepted_current")
        self.write_step_manifest("accepted_current")
        self.write_current_validation_report()

        result = promote_model_project.promote(self.project, target_phase="release_handoff")

        self.assertEqual(result["status"], "pass", result)
        manifest = json.loads((self.project / "outputs" / "step" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "release_handoff")
        self.assertEqual(manifest["generated_for_phase"], "release_handoff")
        self.assertEqual(manifest["promoted_by"], "scripts/promote_model_project.py")

    def test_preview_checkpoint_create_and_restore(self) -> None:
        yaml = load_yaml()
        params_path = self.project / "parameters.yaml"
        original = yaml.safe_load(params_path.read_text(encoding="utf-8"))

        result = checkpoint_preview_revision.checkpoint(self.project, reason="unit-test before preview edit")
        self.assertEqual(result["status"], "pass", result)
        self.assertTrue((self.project / "checkpoints" / "preview_previous" / "parameters.yaml").is_file())

        changed = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        changed["parameters"]["body_length"]["value"] = 66.0
        params_path.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")

        dry = restore_preview_revision.restore_preview_revision(self.project)
        self.assertEqual(dry["status"], "dry-run")
        restored = restore_preview_revision.restore_preview_revision(self.project, force=True)
        self.assertEqual(restored["status"], "pass", restored)
        current = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        self.assertEqual(current["parameters"]["body_length"]["value"], original["parameters"]["body_length"]["value"])

    def test_export_step_writes_fresh_manifest_and_validation_report(self) -> None:
        self.write_exporting_fake_model_source()
        self.write_mesh_cache()

        result = export_step.export_step(self.project, python_executable=sys.executable)

        self.assertEqual(result["status"], "pass", result)
        manifest = json.loads((self.project / "outputs" / "step" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "exported")
        self.assertFalse(manifest["stale"])
        self.assertEqual(manifest["generated_by"], "scripts/export_step.py")
        self.assertIn("review_mesh_hash", manifest)
        review_manifest = json.loads((self.project / "review" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(review_manifest["versions"]["current"]["source"], "../source/model.py")
        self.assertEqual(review_manifest["versions"]["current"]["step"], "../outputs/step/demo-model.step")
        current_context = json.loads((self.project / "validation" / "current_context.json").read_text(encoding="utf-8"))
        self.assertEqual(current_context["step"]["state"], "exported")
        self.assertFalse(current_context["step"]["stale"])
        self.assertTrue((self.project / "validation" / "report.json").is_file())

    def test_export_step_fails_with_pending_review_data(self) -> None:
        self.write_exporting_fake_model_source()
        self.write_patch(self.patch_doc("body_length", 55.0))

        result = export_step.export_step(self.project, python_executable=sys.executable)

        self.assertEqual(result["status"], "fail", result)
        self.assertIn("unconsumed review data", "\n".join(result["errors"]))

    def test_step_manifest_becomes_stale_after_authoring_truth_changes(self) -> None:
        self.write_exporting_fake_model_source()
        exported = export_step.export_step(self.project, python_executable=sys.executable)
        self.assertEqual(exported["status"], "pass", exported)

        yaml = load_yaml()
        params_path = self.project / "parameters.yaml"
        params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        params["parameters"]["body_length"]["value"] = 61.0
        params_path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")

        report = validate_model_project.validate(self.project, require_step=True)
        self.assertEqual(report["status"], "fail")
        manifest = json.loads((self.project / "outputs" / "step" / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["stale"])

    def test_create_handoff_package_zip_uses_whitelist_and_blocks_pending_review(self) -> None:
        self.write_exporting_fake_model_source()
        self.write_mesh_cache()
        exported = export_step.export_step(self.project, python_executable=sys.executable)
        self.assertEqual(exported["status"], "pass", exported)

        blocked_annotations = {
            "schema": "engineering-3d-modeling.annotations.v1",
            "annotations": [
                {
                    "id": "ann-001",
                    "created_at": "2026-06-26T00:00:00Z",
                    "text": "pending",
                    "target": None,
                    "status": "open",
                }
            ],
        }
        (self.project / "review" / "annotations.json").write_text(json.dumps(blocked_annotations, indent=2) + "\n", encoding="utf-8")
        blocked = create_handoff_package.create_package(self.project)
        self.assertEqual(blocked["status"], "fail", blocked)
        self.assertIn("unconsumed review", "\n".join(blocked["errors"]))

        (self.project / "review" / "annotations.json").write_text(
            json.dumps({"schema": "engineering-3d-modeling.annotations.v1", "annotations": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        package = create_handoff_package.create_package(self.project)
        self.assertEqual(package["status"], "pass", package)
        with zipfile.ZipFile(package["package"]) as archive:
            names = set(archive.namelist())
        self.assertIn("handoff_manifest.json", names)
        self.assertIn("README.md", names)
        self.assertIn("outputs/step/demo-model.step", names)
        self.assertIn("spec/current.yaml", names)
        self.assertIn("review/cache/current_mesh.json", names)
        self.assertNotIn("previous/REVISION_INFO.json", names)
        self.assertFalse(any(name.startswith("checkpoints/") for name in names))
        self.assertFalse(any(name.endswith("parameter_patch.json") for name in names))

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
