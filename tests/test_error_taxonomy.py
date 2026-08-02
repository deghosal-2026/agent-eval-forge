from __future__ import annotations

from evalforge.errors import AdapterErrorTaxonomy


class TestAdapterErrorTaxonomy:
    def test_categorize_import_error(self) -> None:
        err = ModuleNotFoundError("No module named 'my_agent'")
        assert AdapterErrorTaxonomy.categorize(err) == "import_error"

    def test_categorize_timeout(self) -> None:
        err = TimeoutError("Process timed out after 30s")
        assert AdapterErrorTaxonomy.categorize(err) == "timeout"

    def test_categorize_connection_refused(self) -> None:
        err = ConnectionError("Connection refused on port 8080")
        assert AdapterErrorTaxonomy.categorize(err) == "connection_refused"

    def test_categorize_api_key_missing(self) -> None:
        err = RuntimeError("OPENAI_API_KEY not set")
        assert AdapterErrorTaxonomy.categorize(err) == "api_key_missing"

    def test_categorize_unknown(self) -> None:
        err = ValueError("something weird")
        assert AdapterErrorTaxonomy.categorize(err) == "unknown"

    def test_normalize_returns_all_fields(self) -> None:
        err = ImportError("No module named 'x'")
        result = AdapterErrorTaxonomy.normalize(err, "subprocess")
        assert "category" in result
        assert "reason" in result
        assert "actionable" in result
        assert "adapter_type" in result

    def test_to_result_json_is_envelope(self) -> None:
        err = TimeoutError("timed out")
        envelope = AdapterErrorTaxonomy.to_result_json(err, "subprocess")
        assert envelope["status"] == "error"
        assert envelope["schema_version"] == "evalforge.run_envelope.v1"
        assert envelope["error_category"] == "timeout"
        assert "actionable" in envelope or "error_actionable" in envelope

    def test_all_categories_have_messages(self) -> None:
        for _cat, msg in AdapterErrorTaxonomy.ERROR_CATEGORIES.items():
            assert isinstance(msg, str)
            assert len(msg) > 0
