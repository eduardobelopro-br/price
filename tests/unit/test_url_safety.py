import pytest

from pricewatch.net.url_safety import (
    UrlSafetyError,
    resolve_pinned_ip,
    validate_port,
    validate_scheme_and_credentials,
)


def test_blocks_localhost() -> None:
    with pytest.raises(UrlSafetyError):
        resolve_pinned_ip("localhost", 80)


def test_blocks_ipv4_loopback() -> None:
    with pytest.raises(UrlSafetyError):
        resolve_pinned_ip("127.0.0.1", 80)


@pytest.mark.parametrize("host", ["10.0.0.5", "172.16.0.1", "192.168.1.1"])
def test_blocks_rfc1918_private_ranges(host: str) -> None:
    with pytest.raises(UrlSafetyError):
        resolve_pinned_ip(host, 80)


def test_blocks_link_local() -> None:
    with pytest.raises(UrlSafetyError):
        resolve_pinned_ip("169.254.1.1", 80)


def test_blocks_unspecified_address() -> None:
    with pytest.raises(UrlSafetyError):
        resolve_pinned_ip("0.0.0.0", 80)


def test_allows_public_ip() -> None:
    assert resolve_pinned_ip("93.184.216.34", 443) == "93.184.216.34"


def test_rejects_file_scheme() -> None:
    with pytest.raises(UrlSafetyError):
        validate_scheme_and_credentials("file:///etc/passwd")


def test_rejects_embedded_credentials() -> None:
    with pytest.raises(UrlSafetyError):
        validate_scheme_and_credentials("http://user:pass@93.184.216.34/")


def test_rejects_disallowed_port() -> None:
    with pytest.raises(UrlSafetyError):
        validate_port(8080)
