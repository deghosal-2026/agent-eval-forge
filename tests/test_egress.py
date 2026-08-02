"""Tests for egress control and HTTP policy."""


from evalforge.security.egress import (
    EgressController,
    EgressPolicy,
    EgressPolicyBuilder,
)


class TestEgressCheck:
    def test_allowed_url_passes(self) -> None:
        policy = EgressPolicy(
            allowed_domains=["api.example.com"],
            allowed_schemes=["https"],
            allowed_ports=[443],
        )
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("https://api.example.com/data")
        assert allowed
        assert "allowed" in reason

    def test_blocked_domain_rejected(self) -> None:
        policy = EgressPolicy(
            allowed_domains=["example.com"],
            blocked_domains=["evil.com"],
        )
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("https://evil.com/hook")
        assert not allowed
        assert "blocked" in reason

    def test_blocked_subdomain_rejected(self) -> None:
        policy = EgressPolicy(
            allowed_domains=["example.com"],
            blocked_domains=["evil.com"],
        )
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("https://sub.evil.com/hook")
        assert not allowed

    def test_localhost_blocked_in_strict_policy(self) -> None:
        policy = EgressPolicyBuilder.strict_production()
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("https://localhost/api")
        assert not allowed
        assert "localhost" in reason

    def test_localhost_allowed_in_dev_policy(self) -> None:
        policy = EgressPolicyBuilder.development()
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("http://localhost:3000/api")
        assert allowed

    def test_private_ip_detection(self) -> None:
        ctrl = EgressController()
        assert ctrl.is_private_ip("10.0.0.1")
        assert ctrl.is_private_ip("192.168.1.1")
        assert ctrl.is_private_ip("172.16.0.1")
        assert not ctrl.is_private_ip("example.com")

    def test_localhost_detection(self) -> None:
        ctrl = EgressController()
        assert ctrl.is_localhost("localhost")
        assert ctrl.is_localhost("127.0.0.1")
        assert ctrl.is_localhost("::1")
        assert not ctrl.is_localhost("example.com")

    def test_port_restriction_enforcement(self) -> None:
        policy = EgressPolicy(
            allowed_domains=["example.com"],
            allowed_ports=[443],
        )
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("https://example.com:8080/api")
        assert not allowed
        assert "port" in reason

    def test_scheme_restriction_http_blocked(self) -> None:
        policy = EgressPolicy(
            allowed_domains=["example.com"],
            allowed_schemes=["https"],
            allowed_ports=[443],
        )
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("http://example.com/api")
        assert not allowed
        assert "scheme" in reason

    def test_request_logging_captures_all(self) -> None:
        policy = EgressPolicy(
            allowed_domains=["api.example.com"],
            allow_localhost=True,
        )
        ctrl = EgressController(policy)
        ctrl.check_request("GET", "https://api.example.com/data")
        ctrl.check_request("POST", "https://localhost/test")
        ctrl.check_request("PUT", "http://evil.com/steal")

        log = ctrl.get_request_log()
        assert len(log) == 3
        assert log[0]["method"] == "GET"
        assert log[1]["method"] == "POST"
        assert log[2]["method"] == "PUT"

    def test_allow_list_policy(self) -> None:
        policy = EgressPolicyBuilder.allow_list(["api.example.com", "docs.example.com"])
        assert policy.allowed_domains == ["api.example.com", "docs.example.com"]
        assert not policy.allow_localhost

    def test_block_list_policy(self) -> None:
        policy = EgressPolicyBuilder.block_list(["evil.com", "bad.org"])
        assert "evil.com" in policy.blocked_domains
        assert "bad.org" in policy.blocked_domains
        assert "*" in policy.allowed_domains

    def test_strict_production_policy(self) -> None:
        policy = EgressPolicyBuilder.strict_production()
        assert policy.allowed_schemes == ["https"]
        assert policy.allowed_ports == [443]
        assert not policy.allow_localhost
        assert not policy.allow_private_ips

    def test_development_policy(self) -> None:
        policy = EgressPolicyBuilder.development()
        assert policy.allow_localhost
        assert policy.allow_private_ips
        assert "http" in policy.allowed_schemes
        assert "https" in policy.allowed_schemes

    def test_air_gapped_policy(self) -> None:
        policy = EgressPolicyBuilder.air_gapped()
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("https://example.com/api")
        assert not allowed

        allowed, reason = ctrl.check_url("http://localhost/api")
        assert not allowed

    def test_parse_url_default_ports(self) -> None:
        scheme, host, port, path = EgressController.parse_url("https://example.com")
        assert scheme == "https"
        assert host == "example.com"
        assert port == 443
        assert path == "/"

        scheme, host, port, path = EgressController.parse_url("http://example.com")
        assert port == 80

    def test_parse_url_explicit_port(self) -> None:
        scheme, host, port, path = EgressController.parse_url("https://example.com:8443/path")
        assert scheme == "https"
        assert host == "example.com"
        assert port == 8443
        assert path == "/path"

    def test_logging_disabled_when_flag_false(self) -> None:
        policy = EgressPolicy(
            allowed_domains=["example.com"],
            log_all_requests=False,
        )
        ctrl = EgressController(policy)
        ctrl.check_url("https://example.com/api")
        assert ctrl.get_request_log() == []

    def test_allowed_subdomain_matches(self) -> None:
        policy = EgressPolicy(allowed_domains=["example.com"])
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("https://api.example.com/data")
        assert allowed

    def test_deny_all_by_default_policy(self) -> None:
        policy = EgressPolicyBuilder.DEFAULT_DENY_ALL
        ctrl = EgressController(policy)
        allowed, reason = ctrl.check_url("https://any-site.com/api")
        assert not allowed
