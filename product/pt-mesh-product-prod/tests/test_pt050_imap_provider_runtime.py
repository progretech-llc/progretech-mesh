from __future__ import annotations

import importlib.util
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "imap-review.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pt050_imap_review_provider", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable_to_load_imap_provider")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeIMAP:
    last_instance = None

    def __init__(self, host, port, ssl_context=None, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.readonly = None
        self.mailbox = None
        self.fetch_calls = []
        FakeIMAP.last_instance = self

    def login(self, user, password):
        self.user = user
        self.password = password
        return "OK", [b"logged"]

    def select(self, mailbox, readonly=False):
        self.mailbox = mailbox
        self.readonly = readonly
        return "OK", [b"2"]

    def search(self, charset, criteria):
        return "OK", [b"1 2"]

    def fetch(self, message_id, spec):
        self.fetch_calls.append((message_id, spec))
        subject = b"Second" if message_id == b"2" else b"First"
        raw = (
            b"Date: Tue, 22 Sep 2026 12:00:00 -0400\r\n"
            b"From: sender@example.com\r\n"
            b"To: rend@example.com\r\n"
            b"Subject: " + subject + b"\r\n"
            b"Message-ID: <m@example.com>\r\n\r\n"
        )
        return "OK", [(b"meta", raw)]

    def logout(self):
        return "BYE", [b"done"]


class TestPT050ImapProviderRuntime(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def _configured(self):
        return mock.patch.object(
            self.mod,
            "load_configuration",
            return_value=("imap.example.com", "rend@example.com", "super-secret"),
        )

    def test_status_never_discloses_values(self):
        def fake_secret(name):
            return {
                self.mod.SECRET_HOST: "imap.example.com",
                self.mod.SECRET_USER: "rend@example.com",
                self.mod.SECRET_PASSWORD: "super-secret",
            }[name]
        with mock.patch.object(self.mod, "_secret", side_effect=fake_secret):
            status = self.mod.configuration_status()
        blob = json.dumps(status)
        self.assertNotIn("imap.example.com", blob)
        self.assertNotIn("rend@example.com", blob)
        self.assertNotIn("super-secret", blob)
        self.assertTrue(status["read_only"])
        self.assertFalse(status["body_fetch_allowed"])
        self.assertFalse(status["send_allowed"])
        self.assertFalse(status["delete_allowed"])

    def test_representative_success_is_read_only_headers_only(self):
        with self._configured():
            rows = self.mod.list_headers(
                "INBOX",
                2,
                imap_factory=FakeIMAP,
                timeout=7,
            )
        self.assertEqual([x["subject"] for x in rows], ["Second", "First"])
        inst = FakeIMAP.last_instance
        self.assertTrue(inst.readonly)
        self.assertEqual(inst.timeout, 7)
        self.assertTrue(inst.fetch_calls)
        for _, spec in inst.fetch_calls:
            self.assertIn("BODY.PEEK[HEADER.FIELDS", spec)
            self.assertNotIn("BODY[]", spec)

    def test_malformed_mailbox_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_mailbox"):
            self.mod.validate_mailbox("INBOX\nDELETE")

    def test_limit_is_resource_bounded(self):
        with self.assertRaisesRegex(ValueError, "limit_out_of_bounds"):
            self.mod.validate_limit(self.mod.MAX_MESSAGES + 1)

    def test_oversized_header_is_rejected(self):
        raw = b"Subject: x\r\nX-Fill: " + (b"x" * self.mod.MAX_HEADER_BYTES)
        with self.assertRaisesRegex(self.mod.ImapReviewError, "header_too_large"):
            self.mod._parse_header_blob(raw)

    def test_offline_failure_is_sanitized(self):
        class Offline:
            def __init__(self, *a, **kw):
                raise OSError("sensitive resolver detail")
        with self._configured():
            with self.assertRaisesRegex(self.mod.ImapReviewError, "^imap_offline$"):
                self.mod.list_headers(imap_factory=Offline)

    def test_timeout_failure_is_sanitized(self):
        class TimedOut:
            def __init__(self, *a, **kw):
                raise TimeoutError("sensitive timeout detail")
        with self._configured():
            with self.assertRaisesRegex(self.mod.ImapReviewError, "^imap_timeout$"):
                self.mod.list_headers(imap_factory=TimedOut)

    def test_missing_configuration_fails_closed(self):
        with mock.patch.object(self.mod, "_secret", return_value=None):
            with self.assertRaisesRegex(self.mod.ImapReviewError, "imap_configuration_incomplete"):
                self.mod.load_configuration()

    def test_cli_exposes_no_mutating_mail_actions(self):
        parser = self.mod.parser()
        help_text = parser.format_help().lower()
        self.assertNotIn("send", help_text)
        self.assertNotIn("delete", help_text)
        self.assertNotIn("store", help_text)

    def test_secret_broker_path_is_internal_not_cli_output(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('get_secret', source)
        self.assertNotIn('print(password', source)
        self.assertNotIn('print(user', source)

    def test_logout_occurs_after_success(self):
        with self._configured():
            self.mod.list_headers(imap_factory=FakeIMAP)
        self.assertIsNotNone(FakeIMAP.last_instance)


if __name__ == "__main__":
    unittest.main()
