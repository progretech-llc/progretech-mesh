from pathlib import Path


APP_JS = (Path(__file__).resolve().parents[1] / "static" / "js" / "app.js").read_text(encoding="utf-8")


def test_copy_uses_secure_clipboard_when_available():
    assert "window.isSecureContext && navigator.clipboard?.writeText" in APP_JS


def test_copy_has_private_lan_http_compatible_fallback():
    assert 'document.execCommand?.("copy")' in APP_JS
    assert 'document.createElement("textarea")' in APP_JS


def test_copy_failure_selects_message_for_manual_ctrl_c():
    assert "selectEnrollmentMessageForManualCopy" in APP_JS
    assert "press Ctrl+C" in APP_JS
