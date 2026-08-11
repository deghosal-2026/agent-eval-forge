"""Tests for secrets and PII scanning."""

from evalforge.tools.secrets_scanner import (
    ScanIssue,
    ScanReport,
    SecretsScanner,
)


class TestScanIssue:
    def test_creation(self) -> None:
        issue = ScanIssue(
            location="output.final",
            issue_type="api_key",
            matched="sk-proj-abc123...",
            severity="critical",
        )
        assert issue.location == "output.final"
        assert issue.issue_type == "api_key"
        assert issue.matched == "sk-proj-abc123..."
        assert issue.severity == "critical"


class TestScanReport:
    def test_defaults(self) -> None:
        report = ScanReport(artifact_id="test-1")
        assert report.artifact_id == "test-1"
        assert report.issues == []
        assert report.clean is True

    def test_with_issues(self) -> None:
        issue = ScanIssue("loc", "type", "match...", "high")
        report = ScanReport(artifact_id="test-2", issues=[issue], clean=False)
        assert len(report.issues) == 1
        assert report.clean is False


class TestScanText:
    def test_empty_text_returns_empty(self) -> None:
        issues = SecretsScanner.scan_text("")
        assert issues == []

    def test_none_text_returns_empty(self) -> None:
        issues = SecretsScanner.scan_text(None)
        assert issues == []

    def test_no_secrets_returns_empty(self) -> None:
        issues = SecretsScanner.scan_text("hello world, nothing to see here")
        assert issues == []

    def test_detects_openai_api_key(self) -> None:
        issues = SecretsScanner.scan_text("sk-abcdefghijklmnopqrstuvwxyz123456")
        assert len(issues) == 1
        assert issues[0].issue_type == "api_key"
        assert issues[0].severity == "critical"

    def test_detects_anthropic_api_key(self) -> None:
        issues = SecretsScanner.scan_text("sk-ant-api03-abcdefghijklmnopqrstuvwxyz123456")
        assert len(issues) == 1
        assert issues[0].issue_type == "api_key"
        assert issues[0].severity == "critical"

    def test_detects_github_token(self) -> None:
        issues = SecretsScanner.scan_text("ghp_abcdefghijklmnopqrstuvwxyz12")
        assert len(issues) == 1
        assert issues[0].issue_type == "token"
        assert issues[0].severity == "critical"

    def test_detects_github_oauth_token_gho(self) -> None:
        issues = SecretsScanner.scan_text("gho_abcdefghijklmnopqrstuvwxyz12")
        assert len(issues) == 2  # matches both gh[pousr]_ and gho_ patterns
        assert all(i.issue_type == "token" and i.severity == "critical" for i in issues)

    def test_detects_aws_key(self) -> None:
        issues = SecretsScanner.scan_text("AKIA1234567890ABCDEF")
        assert len(issues) == 1
        assert issues[0].issue_type == "aws_key"
        assert issues[0].severity == "critical"

    def test_detects_generic_secret_key_value(self) -> None:
        issues = SecretsScanner.scan_text("api_key=abcdefgh12345678")
        assert len(issues) >= 1
        assert any(i.issue_type == "token" and i.severity == "high" for i in issues)

    def test_detects_generic_secret_colon_value(self) -> None:
        issues = SecretsScanner.scan_text('password: "supersecret123"')
        assert len(issues) >= 1
        assert any(i.issue_type == "token" and i.severity == "high" for i in issues)

    def test_detects_email(self) -> None:
        issues = SecretsScanner.scan_text("contact user@example.com for help")
        assert len(issues) == 1
        assert issues[0].issue_type == "pii_email"
        assert issues[0].severity == "medium"

    def test_detects_us_phone_dashed(self) -> None:
        issues = SecretsScanner.scan_text("call 555-123-4567 today")
        assert len(issues) == 1
        assert issues[0].issue_type == "pii_phone"
        assert issues[0].severity == "medium"

    def test_detects_us_phone_dotted(self) -> None:
        issues = SecretsScanner.scan_text("call 555.123.4567 today")
        assert len(issues) == 1
        assert issues[0].issue_type == "pii_phone"

    def test_detects_us_phone_plain(self) -> None:
        issues = SecretsScanner.scan_text("call 5551234567 today")
        assert len(issues) == 1
        assert issues[0].issue_type == "pii_phone"

    def test_detects_ip_address(self) -> None:
        issues = SecretsScanner.scan_text("server at 192.168.1.1 is down")
        assert len(issues) == 1
        assert issues[0].issue_type == "ip_address"
        assert issues[0].severity == "low"

    def test_detects_credit_card_spaces(self) -> None:
        issues = SecretsScanner.scan_text("card 4111 1111 1111 1111 used")
        assert len(issues) >= 1
        assert any(i.issue_type == "pii_cc" and i.severity == "high" for i in issues)

    def test_detects_credit_card_dashes(self) -> None:
        issues = SecretsScanner.scan_text("card 4111-1111-1111-1111 used")
        assert len(issues) >= 1
        assert any(i.issue_type == "pii_cc" for i in issues)

    def test_detects_credit_card_no_separator(self) -> None:
        issues = SecretsScanner.scan_text("card 4111111111111111 used")
        assert len(issues) >= 1
        assert any(i.issue_type == "pii_cc" for i in issues)

    def test_detects_us_ssn(self) -> None:
        issues = SecretsScanner.scan_text("ssn 123-45-6789 belongs to")
        assert len(issues) == 1
        assert issues[0].issue_type == "pii_ssn"
        assert issues[0].severity == "high"

    def test_multiple_issues_in_one_text(self) -> None:
        text = "email user@example.com and api key sk-abcdefghijklmnopqrstuvwxyz123456"
        issues = SecretsScanner.scan_text(text)
        assert len(issues) >= 2
        types = {i.issue_type for i in issues}
        assert "pii_email" in types
        assert "api_key" in types

    def test_location_is_passed_through(self) -> None:
        issues = SecretsScanner.scan_text("call 555-123-4567", location="trajectory.0.content")
        assert len(issues) == 1
        assert issues[0].location == "trajectory.0.content"

    def test_matched_truncated_to_20_chars(self) -> None:
        issues = SecretsScanner.scan_text("sk-abcdefghijklmnopqrstuvwxyz1234567890")
        matched = issues[0].matched
        assert len(matched) == 23  # 20 chars + "..."
        assert matched.endswith("...")

    def test_ignores_numbers(self) -> None:
        issues = SecretsScanner.scan_text("12345")
        assert issues == []

    def test_case_insensitive_generic_pattern(self) -> None:
        issues = SecretsScanner.scan_text("SECRET=mysecurevalue123")
        assert any(i.issue_type == "token" and i.severity == "high" for i in issues)

    def test_generic_pattern_with_api_key(self) -> None:
        issues = SecretsScanner.scan_text("api-key=abcdefgh12345678")
        assert any(i.issue_type == "token" for i in issues)


class TestScanArtifact:
    def test_empty_artifact(self) -> None:
        report = SecretsScanner.scan_artifact({})
        assert report.artifact_id == "unknown"
        assert report.clean is True
        assert report.issues == []

    def test_artifact_with_id(self) -> None:
        report = SecretsScanner.scan_artifact({"id": "run-42"})
        assert report.artifact_id == "run-42"

    def test_clean_output(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "clean-1",
            "output": {"final": "all good here"},
        })
        assert report.clean is True

    def test_output_final_with_secret(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r1",
            "output": {"final": "key is sk-abcdefghijklmnopqrstuvwxyz123456"},
        })
        assert report.clean is False
        assert len(report.issues) == 1
        assert report.issues[0].location == "output.final"

    def test_output_structured_dict_with_secret(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r2",
            "output": {"structured": {"api_key": "sk-abcdefghijklmnopqrstuvwxyz123456"}},
        })
        assert report.clean is False
        assert any(i.location == "output.structured" for i in report.issues)

    def test_output_structured_list_with_secret(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r3",
            "output": {"structured": ["sk-abcdefghijklmnopqrstuvwxyz123456"]},
        })
        assert report.clean is False
        assert any(i.location == "output.structured" for i in report.issues)

    def test_output_final_not_string_skipped(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r4",
            "output": {"final": 42},
        })
        assert report.clean is True

    def test_output_structured_not_dict_or_list_skipped(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r5",
            "output": {"structured": "not a dict or list"},
        })
        assert report.clean is True

    def test_trajectory_steps_scanned(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r6",
            "trajectory": [
                {"content": "user@example.com sent", "result": "ok"},
            ],
        })
        assert report.clean is False
        assert any(i.location == "trajectory.0.content" for i in report.issues)

    def test_trajectory_result_field(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r7",
            "trajectory": [
                {"result": {"secret": "sk-abcdefghijklmnopqrstuvwxyz123456"}},
            ],
        })
        assert report.clean is False
        assert any(i.location == "trajectory.0.result" for i in report.issues)

    def test_trajectory_args_field(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r8",
            "trajectory": [
                {"args": "api_key=abcdefgh12345678"},
            ],
        })
        assert report.clean is False
        assert any(i.location == "trajectory.0.args" for i in report.issues)

    def test_trajectory_non_dict_step_skipped(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r9",
            "trajectory": ["not a dict"],
        })
        assert report.clean is True

    def test_trajectory_not_list_skipped(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r10",
            "trajectory": "not a list",
        })
        assert report.clean is True

    def test_error_field_scanned(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r11",
            "error": "failed with key sk-abcdefghijklmnopqrstuvwxyz123456",
        })
        assert report.clean is False
        assert any(i.location == "error" for i in report.issues)

    def test_error_not_string_skipped(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r12",
            "error": {"code": 500},
        })
        assert report.clean is True

    def test_output_not_dict_skipped(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r13",
            "output": "plain string",
        })
        assert report.clean is True

    def test_multiple_trajectory_steps(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r14",
            "trajectory": [
                {"content": "user@example.com"},
                {"content": "sk-abcdefghijklmnopqrstuvwxyz123456"},
            ],
        })
        assert report.clean is False
        assert len(report.issues) == 2

    def test_combined_secrets_all_fields(self) -> None:
        report = SecretsScanner.scan_artifact({
            "id": "r15",
            "output": {"final": "key: sk-abcdefghijklmnopqrstuvwxyz123456"},
            "trajectory": [
                {"content": "user@example.com"},
            ],
            "error": "AKIA1234567890ABCDEF leaked",
        })
        assert report.clean is False
        assert len(report.issues) >= 3


class TestSanitizeArtifact:
    def test_clean_artifact_unchanged(self) -> None:
        artifact = {"id": "s1", "output": {"final": "hello world"}}
        sanitized = SecretsScanner.sanitize_artifact(artifact)
        assert sanitized == artifact

    def test_redacts_secret_in_output_final(self) -> None:
        artifact = {
            "id": "s2",
            "output": {"final": "key is sk-abcdefghijklmnopqrstuvwxyz123456"},
        }
        sanitized = SecretsScanner.sanitize_artifact(artifact)
        assert "[REDACTED:api_key]" in sanitized["output"]["final"]
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in sanitized["output"]["final"]

    def test_redacts_email_in_output_final(self) -> None:
        artifact = {
            "id": "s3",
            "output": {"final": "email user@example.com here"},
        }
        sanitized = SecretsScanner.sanitize_artifact(artifact)
        assert "[REDACTED:pii_email]" in sanitized["output"]["final"]

    def test_preserves_non_output_final_keys(self) -> None:
        artifact = {
            "id": "s4",
            "output": {"final": "key is sk-abcdefghijklmnopqrstuvwxyz123456", "other": "keep"},
            "extra": "value",
        }
        sanitized = SecretsScanner.sanitize_artifact(artifact)
        assert sanitized["output"]["other"] == "keep"
        assert sanitized["extra"] == "value"

    def test_does_not_mutate_original(self) -> None:
        artifact = {
            "id": "s5",
            "output": {"final": "clean text no secrets here"},
        }
        sanitized = SecretsScanner.sanitize_artifact(artifact)
        assert sanitized == artifact
        assert sanitized is not artifact

    def test_no_output_key_returns_copy(self) -> None:
        artifact = {"id": "s6", "not_output": "hello"}
        sanitized = SecretsScanner.sanitize_artifact(artifact)
        assert sanitized == artifact
        assert sanitized is not artifact

    def test_output_final_not_string_handled(self) -> None:
        artifact = {"id": "s7", "output": {"final": 42}}
        sanitized = SecretsScanner.sanitize_artifact(artifact)
        assert sanitized == artifact

    def test_multiple_redactions(self) -> None:
        artifact = {
            "id": "s8",
            "output": {"final": "key1: sk-abcdefghijklmnopqrstuvwxyz123456 contact user@example.com"},  # noqa: E501
        }
        sanitized = SecretsScanner.sanitize_artifact(artifact)
        assert "[REDACTED:api_key]" in sanitized["output"]["final"]
        assert "[REDACTED:pii_email]" in sanitized["output"]["final"]
