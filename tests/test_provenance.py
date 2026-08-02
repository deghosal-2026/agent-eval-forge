"""Tests for data provenance tracking."""

import hashlib
import json
import tempfile
from pathlib import Path

from evalforge.provenance.tracker import ProvenanceInfo, ProvenanceTracker


class TestProvenanceCapture:
    def test_capture_includes_required_fields(self) -> None:
        tracker = ProvenanceTracker()
        info = tracker.capture()

        assert info.timestamp != ""
        assert info.python_version != ""
        assert info.evalforge_version != ""
        assert info.platform != ""

    def test_content_hash_is_deterministic(self) -> None:
        content = "hello world"
        h1 = ProvenanceTracker.compute_content_hash(content)
        h2 = ProvenanceTracker.compute_content_hash(content)
        h3 = ProvenanceTracker.compute_content_hash(b"hello world")

        assert h1 == h2
        assert h1 == h3
        assert len(h1) == 64

    def test_file_hash_matches_expected(self) -> None:
        content = b"test file content\n"
        expected = hashlib.sha256(content).hexdigest()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            tmp_path = f.name

        try:
            result = ProvenanceTracker.compute_file_hash(tmp_path)
            assert result == expected
        finally:
            Path(tmp_path).unlink()

    def test_verify_detects_timestamp_format(self) -> None:
        info = ProvenanceInfo(
            timestamp="not-a-timestamp",
            evalforge_version="0.1.0",
        )
        tracker = ProvenanceTracker()
        issues = tracker.verify(info)
        assert any("timestamp" in issue for issue in issues)

    def test_verify_detects_missing_version(self) -> None:
        info = ProvenanceInfo()
        tracker = ProvenanceTracker()
        issues = tracker.verify(info)
        assert any("evalforge_version" in issue for issue in issues)

    def test_verify_detects_pack_hash_mismatch(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
            json.dump({"pack": {"name": "test", "version": "1.0"}}, f)
            tmp_path = f.name

        try:
            ProvenanceTracker.compute_file_hash(tmp_path)

            info = ProvenanceInfo(
                pack_uri=tmp_path,
                pack_hash=ProvenanceTracker.compute_content_hash("tampered"),
                evalforge_version="0.1.0",
            )
            tracker = ProvenanceTracker()
            issues = tracker.verify(info)
            assert any("mismatch" in issue for issue in issues)
        finally:
            Path(tmp_path).unlink()

    def test_verify_passes_for_consistent_info(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
            json.dump({"pack": {"name": "test", "version": "1.0"}}, f)
            tmp_path = f.name

        try:
            file_hash = ProvenanceTracker.compute_file_hash(tmp_path)
            info = ProvenanceInfo(
                pack_uri=tmp_path,
                pack_hash=file_hash,
                agent_source="test:path",
                agent_hash="abc123",
                evalforge_version="0.1.0",
            )
            tracker = ProvenanceTracker()
            issues = tracker.verify(info)
            assert issues == []
        finally:
            Path(tmp_path).unlink()

    def test_capture_agent_from_spec(self) -> None:
        tracker = ProvenanceTracker()
        info = tracker.capture_agent("python:myagent")

        assert info.agent_source == "python:myagent"
        assert info.timestamp != ""
        assert info.evalforge_version != ""

    def test_capture_agent_from_file(self) -> None:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".py", mode="w"
        ) as f:
            f.write("def run(): pass\n")
            tmp_path = f.name

        try:
            tracker = ProvenanceTracker()
            info = tracker.capture_agent(tmp_path)

            assert info.agent_source == tmp_path
            assert info.agent_hash != ""
            assert len(info.agent_hash) == 64
        finally:
            Path(tmp_path).unlink()

    def test_capture_pack_from_path(self) -> None:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".json", mode="w"
        ) as f:
            json.dump({"pack": {"name": "test", "version": "2.0"}}, f)
            tmp_path = f.name

        try:
            tracker = ProvenanceTracker()
            info = tracker.capture_pack(tmp_path)

            assert info.pack_uri == tmp_path
            assert info.pack_hash != ""
            assert info.pack_version == "2.0"
        finally:
            Path(tmp_path).unlink()

    def test_to_artifact_metadata_includes_all_fields(self) -> None:
        tracker = ProvenanceTracker()
        metadata = tracker.to_artifact_metadata()

        prov = metadata["provenance"]
        assert "evalforge_version" in prov
        assert "timestamp" in prov
        assert "python_version" in prov
        assert "platform" in prov
        assert "dependencies" in prov
        assert "pack_uri" in prov
        assert "pack_hash" in prov
        assert "pack_version" in prov
        assert "agent_source" in prov
        assert "agent_hash" in prov
        assert "judge_model" in prov

    def test_compute_content_hash_empty(self) -> None:
        h1 = ProvenanceTracker.compute_content_hash("")
        h2 = ProvenanceTracker.compute_content_hash(b"")

        assert h1 == hashlib.sha256(b"").hexdigest()
        assert h1 == h2

    def test_verify_detects_missing_pack_hash(self) -> None:
        info = ProvenanceInfo(
            pack_uri="/some/pack.yaml",
            evalforge_version="0.1.0",
        )
        tracker = ProvenanceTracker()
        issues = tracker.verify(info)
        assert any("pack_hash" in issue for issue in issues)

    def test_verify_detects_missing_agent_hash(self) -> None:
        info = ProvenanceInfo(
            agent_source="python:agent",
            evalforge_version="0.1.0",
        )
        tracker = ProvenanceTracker()
        issues = tracker.verify(info)
        assert any("agent_hash" in issue for issue in issues)

    def test_capture_pack_yaml_path(self) -> None:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".yaml", mode="w"
        ) as f:
            f.write("pack:\n  name: test\n  version: '3.0'\n")
            tmp_path = f.name

        try:
            tracker = ProvenanceTracker()
            info = tracker.capture_pack(tmp_path)

            assert info.pack_version == "3.0"
        finally:
            Path(tmp_path).unlink()
