import json
import logging

from pricewatch.logging_config import JsonFormatter


def make_record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="pricewatch.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="something happened",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_format_produces_valid_json_with_expected_fields() -> None:
    record = make_record(product_id=42, domain="shop.example")

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "something happened"
    assert payload["level"] == "INFO"
    assert payload["product_id"] == 42
    assert payload["domain"] == "shop.example"
    assert "timestamp" in payload


def test_format_never_includes_sensitive_fields() -> None:
    record = make_record(bot_token="secret-token-value", api_key="another-secret")

    output = JsonFormatter().format(record)

    assert "secret-token-value" not in output
    assert "another-secret" not in output
