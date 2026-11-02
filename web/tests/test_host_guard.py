"""DNS-rebinding defense: only loopback Host headers are accepted."""

from __future__ import annotations

from web.app import is_loopback_host


def test_helper_accepts_loopback_variants():
    for host in (
        "127.0.0.1:8765",
        "127.0.0.1",
        "127.1.2.3:80",
        "localhost:8765",
        "localhost",
        "[::1]:8765",
        "[::1]",
    ):
        assert is_loopback_host(host), host


def test_helper_rejects_non_loopback_and_malformed():
    for host in (
        "example.com:8765",
        "evil.attacker.test",
        "10.0.0.1:8765",
        "192.168.1.5:80",
        "8.8.8.8",
        "[::2]:8765",
        "",
        None,
        "[::1",
    ):
        assert not is_loopback_host(host), host


def test_non_loopback_host_is_rejected_with_403(web_server):
    _, httpd = web_server
    response = httpd.app.dispatch("GET", "/api/health", {"Host": "evil.example.com:8765"}, b"")
    assert response.status == 403
    assert b"forbidden_host" in response.body


def test_missing_host_is_rejected_with_403(web_server):
    _, httpd = web_server
    response = httpd.app.dispatch("GET", "/api/health", {}, b"")
    assert response.status == 403


def test_loopback_host_still_routes(web_server):
    _, httpd = web_server
    response = httpd.app.dispatch("GET", "/api/health", {"Host": "127.0.0.1:8765"}, b"")
    assert response.status == 200
