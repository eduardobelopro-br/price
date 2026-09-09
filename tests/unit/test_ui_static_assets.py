import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).parents[2] / "src" / "pricewatch" / "api" / "static"
UI_JS = (STATIC_DIR / "ui.js").read_text(encoding="utf-8")

_SAFE_EXTERNAL_URL_SOURCE = re.search(
    r"function safeExternalUrl\(raw\) \{.*?\n\}", UI_JS, re.DOTALL
)
assert _SAFE_EXTERNAL_URL_SOURCE is not None, "safeExternalUrl helper not found in ui.js"


def test_ui_js_never_uses_innerhtml() -> None:
    """innerHTML is the XSS vector: remote titles/sellers/errors must only
    ever reach the DOM via textContent/createElement, never string-built
    markup. This is a source-level regression guard, not a runtime check.
    """
    assert "innerHTML" not in UI_JS


def test_ui_js_never_persists_the_api_key() -> None:
    assert "price_api_key" not in UI_JS
    assert "runtimeApiKey" in UI_JS


def test_ui_js_validates_url_scheme_before_assigning_href() -> None:
    assert "safeExternalUrl" in UI_JS
    assert "javascript:" not in UI_JS


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not available in this environment")
def test_safe_external_url_rejects_javascript_scheme_and_accepts_http() -> None:
    script = f"""
    global.window = {{ location: {{ origin: 'https://price.local' }} }};
    {_SAFE_EXTERNAL_URL_SOURCE.group(0)}
    const results = [];
    try {{ results.push(safeExternalUrl('javascript:alert(1)')); }} catch (e) {{ results.push('rejected'); }}
    try {{ results.push(safeExternalUrl('https://example.com/product')); }} catch (e) {{ results.push('rejected'); }}
    console.log(JSON.stringify(results));
    """
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=10, check=False
    )
    assert result.returncode == 0, result.stderr
    outcome = result.stdout.strip().splitlines()[-1]
    assert outcome == '["rejected","https://example.com/product"]'
