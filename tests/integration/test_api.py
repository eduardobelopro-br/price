import pytest
from fastapi.testclient import TestClient

from pricewatch.api.app import app

API_KEY = "test-key"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PRICE_DATABASE_URL", f"sqlite:///{tmp_path / 'price.db'}")
    monkeypatch.setenv("PRICE_API_KEY", API_KEY)
    with TestClient(app) as test_client:
        yield test_client


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


def test_health_does_not_require_api_key(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_products_require_api_key(client: TestClient) -> None:
    response = client.get("/api/v1/products")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_create_list_and_get_product(client: TestClient) -> None:
    create = client.post(
        "/api/v1/products",
        json={"url": "https://demo.pricewatch.invalid/x", "check_interval_seconds": 60},
        headers=auth_headers(),
    )
    assert create.status_code == 201
    product = create.json()
    assert product["status"] == "active"

    listed = client.get("/api/v1/products", headers=auth_headers())
    assert len(listed.json()) == 1

    detail = client.get(f"/api/v1/products/{product['id']}", headers=auth_headers())
    assert detail.status_code == 200
    assert detail.json()["recent_errors"] == []


def test_create_product_rejects_unsafe_scheme(client: TestClient) -> None:
    response = client.post(
        "/api/v1/products", json={"url": "file:///etc/passwd"}, headers=auth_headers()
    )
    assert response.status_code == 422


def test_create_product_rejects_duplicate_url(client: TestClient) -> None:
    payload = {"url": "https://demo.pricewatch.invalid/dup"}
    first = client.post("/api/v1/products", json=payload, headers=auth_headers())
    assert first.status_code == 201
    second = client.post("/api/v1/products", json=payload, headers=auth_headers())
    assert second.status_code == 409


def test_patch_pauses_product(client: TestClient) -> None:
    create = client.post(
        "/api/v1/products", json={"url": "https://demo.pricewatch.invalid/pause"}, headers=auth_headers()
    )
    product_id = create.json()["id"]

    patched = client.patch(
        f"/api/v1/products/{product_id}", json={"status": "paused"}, headers=auth_headers()
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "paused"


def test_check_now_collects_and_returns_updated_product(client: TestClient) -> None:
    create = client.post(
        "/api/v1/products", json={"url": "https://demo.pricewatch.invalid/check"}, headers=auth_headers()
    )
    product_id = create.json()["id"]

    checked = client.post(f"/api/v1/products/{product_id}/check", headers=auth_headers())
    assert checked.status_code == 200
    assert checked.json()["last_price_currency"] == "BRL"

    history = client.get(f"/api/v1/products/{product_id}/history", headers=auth_headers())
    assert len(history.json()) == 1

    rate_limited = client.post(f"/api/v1/products/{product_id}/check", headers=auth_headers())
    assert rate_limited.status_code == 429


def test_rules_lifecycle(client: TestClient) -> None:
    create = client.post(
        "/api/v1/products", json={"url": "https://demo.pricewatch.invalid/rules"}, headers=auth_headers()
    )
    product_id = create.json()["id"]

    created_rule = client.post(
        f"/api/v1/products/{product_id}/rules",
        json={"kind": "target_price", "threshold": "19.90"},
        headers=auth_headers(),
    )
    assert created_rule.status_code == 201
    rule_id = created_rule.json()["id"]

    listed = client.get(f"/api/v1/products/{product_id}/rules", headers=auth_headers())
    assert len(listed.json()) == 1

    deleted = client.delete(f"/api/v1/rules/{rule_id}", headers=auth_headers())
    assert deleted.status_code == 204

    listed_after = client.get(f"/api/v1/products/{product_id}/rules", headers=auth_headers())
    assert listed_after.json() == []


def test_archive_product_sets_archived_status(client: TestClient) -> None:
    create = client.post(
        "/api/v1/products", json={"url": "https://demo.pricewatch.invalid/archive"}, headers=auth_headers()
    )
    product_id = create.json()["id"]

    archived = client.delete(f"/api/v1/products/{product_id}", headers=auth_headers())
    assert archived.status_code == 204

    detail = client.get(f"/api/v1/products/{product_id}", headers=auth_headers())
    assert detail.json()["status"] == "archived"


def test_alerts_endpoint_returns_empty_list_by_default(client: TestClient) -> None:
    response = client.get("/api/v1/alerts", headers=auth_headers())
    assert response.status_code == 200
    assert response.json() == []


def test_ui_page_is_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_ui_page_has_no_inline_scripts_or_remote_data(client: TestClient) -> None:
    response = client.get("/")
    assert "<script>" not in response.text
    assert '<script src="/static/ui.js">' in response.text
    assert "innerHTML" not in response.text
    assert "localStorage" not in response.text


def test_static_assets_are_served(client: TestClient) -> None:
    js_response = client.get("/static/ui.js")
    assert js_response.status_code == 200
    assert "innerHTML" not in js_response.text

    css_response = client.get("/static/ui.css")
    assert css_response.status_code == 200


def test_content_security_policy_header_is_present_on_every_response(client: TestClient) -> None:
    for path in ("/", "/health", "/static/ui.js"):
        response = client.get(path)
        csp = response.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "object-src 'none'" in csp
