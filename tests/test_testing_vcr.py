"""Tests for evalforge.testing.vcr."""

import json
import tempfile
from pathlib import Path

import pytest

from evalforge.testing.vcr import LLMVCR, LLMCassette


class TestLLMCassette:
    def test_defaults(self) -> None:
        c = LLMCassette(name="test-cassette")
        assert c.name == "test-cassette"
        assert c.interactions == []

    def test_with_interactions(self) -> None:
        interactions = [
            {"request": {"method": "POST", "uri": "/v1/chat"}, "response": {"status": 200}}
        ]
        c = LLMCassette(name="c1", interactions=interactions)
        assert len(c.interactions) == 1
        assert c.interactions[0]["request"]["method"] == "POST"


class TestLLMVCR:
    def test_init_stores_cassette_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_dir = Path(tmpdir) / "cassettes"
            vcr = LLMVCR(cassette_dir=str(cassette_dir))
            assert str(vcr._cassette_dir) == str(cassette_dir)

    def test_start_recording(self) -> None:
        vcr = LLMVCR()
        vcr.start_recording("my-cassette")
        assert vcr._current_cassette == "my-cassette"

    def test_stop_recording_when_not_recording(self) -> None:
        vcr = LLMVCR()
        vcr.stop_recording()

    def test_stop_recording_saves_cassette(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vcr = LLMVCR(cassette_dir=tmpdir)
            vcr._recording.record(
                "test-cassette",
                {"uri": "/v1/chat", "method": "POST"},
                {"status": 200, "body": {"choices": [{"message": {"content": "hi"}}]}},
            )
            vcr.start_recording("test-cassette")
            vcr.stop_recording()
            cassette_path = Path(tmpdir) / "test-cassette.json"
            assert cassette_path.exists()
            data = json.loads(cassette_path.read_text())
            assert len(data["interactions"]) == 1

    def test_replay_raises_file_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vcr = LLMVCR(cassette_dir=tmpdir)
            with pytest.raises(FileNotFoundError):
                vcr.replay("nonexistent")

    def test_replay_loads_cassette(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "test-replay.json"
            cassette_data = {
                "version": 1,
                "interactions": [
                    {
                        "request": {"uri": "/v1/chat", "method": "POST", "body": {"messages": []}},
                        "response": {"status": 200, "body": {"choices": [{"content": "hello"}]}},
                    }
                ],
            }
            cassette_path.write_text(json.dumps(cassette_data))
            vcr = LLMVCR(cassette_dir=tmpdir)
            cassette = vcr.replay("test-replay")
            assert cassette.name == "test-replay"
            assert len(cassette.interactions) == 1
            assert cassette.interactions[0]["request"]["uri"] == "/v1/chat"
            assert cassette.interactions[0]["response"]["status"] == 200

    def test_replay_caches_loaded_cassette(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette_path = Path(tmpdir) / "cache-test.json"
            cassette_path.write_text(json.dumps({
                "version": 1,
                "interactions": [
                    {
                        "request": {"uri": "/v1/chat", "method": "POST"},
                        "response": {"status": 200},
                    }
                ],
            }))
            vcr = LLMVCR(cassette_dir=tmpdir)
            vcr.replay("cache-test")
            assert "cache-test" in vcr._loaded_cassettes

    def test_get_llm_response_raises_when_not_recording(self) -> None:
        vcr = LLMVCR()
        with pytest.raises(RuntimeError, match="Not currently recording"):
            vcr.get_llm_response([{"role": "user", "content": "hi"}], "gpt-4o")

    def test_get_llm_response_uses_current_cassette(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vcr = LLMVCR(cassette_dir=tmpdir)
            vcr._recording.record(
                "chat-cassette",
                {"uri": "llm://gpt-4o/chat", "method": "POST"},
                {"choices": [{"message": {"content": "hi back"}}]},
            )
            vcr.start_recording("chat-cassette")
            response = vcr.get_llm_response([{"role": "user"}], "gpt-4o")
            assert response == {"choices": [{"message": {"content": "hi back"}}]}

    def test_list_cassettes_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vcr = LLMVCR(cassette_dir=tmpdir)
            assert vcr.list_cassettes() == []

    def test_list_cassettes_non_existent_dir(self) -> None:
        vcr = LLMVCR(cassette_dir="/nonexistent/dir/12345")
        assert vcr.list_cassettes() == []

    def test_list_cassettes_returns_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.json").write_text("{}")
            (Path(tmpdir) / "b.json").write_text("{}")
            (Path(tmpdir) / "not-json.txt").write_text("nope")
            vcr = LLMVCR(cassette_dir=tmpdir)
            result = vcr.list_cassettes()
            assert result == ["a", "b"]


class TestVerifyTrajectory:
    def test_exact_match(self) -> None:
        vcr = LLMVCR()
        cassette = LLMCassette(
            name="t",
            interactions=[
                {
                    "request": {"body": {"messages": ["msg1"]}},
                    "response": {},
                },
                {
                    "request": {"body": {"messages": ["msg2"]}},
                    "response": {},
                },
            ],
        )
        trajectory = [{"messages": ["msg1"]}, {"messages": ["msg2"]}]
        result = vcr.verify_trajectory(cassette, trajectory)
        assert result["passed"] is True
        assert result["total_expected"] == 2
        assert result["total_actual"] == 2
        assert result["matched"] == 2
        assert len(result["mismatches"]) == 0

    def test_mismatch_in_content(self) -> None:
        vcr = LLMVCR()
        cassette = LLMCassette(
            name="t",
            interactions=[
                {
                    "request": {"body": {"messages": ["expected"]}},
                    "response": {},
                },
            ],
        )
        trajectory = [{"messages": ["different"]}]
        result = vcr.verify_trajectory(cassette, trajectory)
        assert result["passed"] is False
        assert result["matched"] == 0
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["expected"] == ["expected"]
        assert result["mismatches"][0]["actual"] == ["different"]

    def test_more_actual_than_recorded(self) -> None:
        vcr = LLMVCR()
        cassette = LLMCassette(
            name="t",
            interactions=[
                {
                    "request": {"body": {"messages": ["msg1"]}},
                    "response": {},
                },
            ],
        )
        trajectory = [{"messages": ["msg1"]}, {"messages": ["msg2"]}]
        result = vcr.verify_trajectory(cassette, trajectory)
        assert result["passed"] is False
        assert result["matched"] == 1
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["expected"] is None
        assert result["mismatches"][0]["actual"] == ["msg2"]

    def test_more_recorded_than_actual(self) -> None:
        vcr = LLMVCR()
        cassette = LLMCassette(
            name="t",
            interactions=[
                {
                    "request": {"body": {"messages": ["msg1"]}},
                    "response": {},
                },
                {
                    "request": {"body": {"messages": ["msg2"]}},
                    "response": {},
                },
            ],
        )
        trajectory = [{"messages": ["msg1"]}]
        result = vcr.verify_trajectory(cassette, trajectory)
        assert result["passed"] is False
        assert result["matched"] == 1
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["expected"] == ["msg2"]
        assert result["mismatches"][0]["actual"] is None

    def test_empty_both(self) -> None:
        vcr = LLMVCR()
        cassette = LLMCassette(name="t", interactions=[])
        trajectory: list = []
        result = vcr.verify_trajectory(cassette, trajectory)
        assert result["passed"] is True
        assert result["matched"] == 0
        assert len(result["mismatches"]) == 0

    def test_missing_messages_key_handled(self) -> None:
        vcr = LLMVCR()
        cassette = LLMCassette(
            name="t",
            interactions=[
                {
                    "request": {},
                    "response": {},
                },
            ],
        )
        trajectory = [{}]
        result = vcr.verify_trajectory(cassette, trajectory)
        assert result["matched"] == 1
