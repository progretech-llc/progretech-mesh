#!/usr/bin/env python3
from __future__ import annotations

import argparse
import email
import importlib.util
import imaplib
import json
import re
import socket
import ssl
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from typing import Any

HOME = Path.home()
MESH_ROOT = HOME / "PycharmProjects" / "progretech-mesh"
SECRET_BROKER_PATH = MESH_ROOT / "scripts" / "secret-broker.py"

SECRET_HOST = "imap-review-host"
SECRET_USER = "imap-review-user"
SECRET_PASSWORD = "imap-review-password"

DEFAULT_PORT = 993
DEFAULT_TIMEOUT = 10
MAX_MESSAGES = 50
MAX_HEADER_BYTES = 65536
MAILBOX_RE = re.compile(r"^[A-Za-z0-9._/\-]{1,128}$")


class ImapReviewError(RuntimeError):
    pass


def _load_secret_broker():
    if not SECRET_BROKER_PATH.is_file():
        raise ImapReviewError("secret_broker_unavailable")
    spec = importlib.util.spec_from_file_location("progretech_secret_broker", SECRET_BROKER_PATH)
    if spec is None or spec.loader is None:
        raise ImapReviewError("secret_broker_load_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "get_secret"):
        raise ImapReviewError("secret_broker_contract_missing")
    return module


def _secret(name: str) -> str | None:
    module = _load_secret_broker()
    value = module.get_secret(name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def configuration_status() -> dict[str, Any]:
    # Never disclose values. This command is intentionally safe for runtime/UI use.
    try:
        host = _secret(SECRET_HOST)
        user = _secret(SECRET_USER)
        password = _secret(SECRET_PASSWORD)
        broker_ok = True
    except Exception:
        host = user = password = None
        broker_ok = False
    return {
        "provider": "imap",
        "secret_broker_available": broker_ok,
        "host_configured": bool(host),
        "user_configured": bool(user),
        "password_configured": bool(password),
        "port": DEFAULT_PORT,
        "read_only": True,
        "body_fetch_allowed": False,
        "send_allowed": False,
        "delete_allowed": False,
        "max_messages": MAX_MESSAGES,
        "max_header_bytes": MAX_HEADER_BYTES,
    }


def load_configuration() -> tuple[str, str, str]:
    host = _secret(SECRET_HOST)
    user = _secret(SECRET_USER)
    password = _secret(SECRET_PASSWORD)
    missing = []
    if not host:
        missing.append(SECRET_HOST)
    if not user:
        missing.append(SECRET_USER)
    if not password:
        missing.append(SECRET_PASSWORD)
    if missing:
        raise ImapReviewError("imap_configuration_incomplete:" + ",".join(missing))
    return host, user, password


def validate_mailbox(value: str) -> str:
    mailbox = (value or "").strip()
    if not MAILBOX_RE.fullmatch(mailbox):
        raise ValueError("invalid_mailbox")
    return mailbox


def validate_limit(value: int) -> int:
    try:
        limit = int(value)
    except Exception as exc:
        raise ValueError("invalid_limit") from exc
    if not 1 <= limit <= MAX_MESSAGES:
        raise ValueError(f"limit_out_of_bounds:1..{MAX_MESSAGES}")
    return limit


def _header_text(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value[:1000]


def _parse_header_blob(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_HEADER_BYTES:
        raise ImapReviewError("header_too_large")
    msg = BytesParser(policy=default).parsebytes(raw, headersonly=True)
    return {
        "date": _header_text(msg.get("Date")),
        "from": _header_text(msg.get("From")),
        "to": _header_text(msg.get("To")),
        "cc": _header_text(msg.get("Cc")),
        "subject": _header_text(msg.get("Subject")),
        "message_id": _header_text(msg.get("Message-ID")),
    }


def _extract_fetch_bytes(data: Any) -> bytes:
    if not data:
        raise ImapReviewError("imap_fetch_empty")
    for item in data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])
    raise ImapReviewError("imap_fetch_unexpected_shape")


def list_headers(
    mailbox: str = "INBOX",
    limit: int = 10,
    *,
    imap_factory=imaplib.IMAP4_SSL,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    mailbox = validate_mailbox(mailbox)
    limit = validate_limit(limit)
    host, user, password = load_configuration()

    client = None
    try:
        client = imap_factory(
            host,
            DEFAULT_PORT,
            ssl_context=ssl.create_default_context(),
            timeout=timeout,
        )
        typ, _ = client.login(user, password)
        if typ != "OK":
            raise ImapReviewError("imap_login_failed")

        typ, _ = client.select(mailbox, readonly=True)
        if typ != "OK":
            raise ImapReviewError("imap_select_failed")

        typ, data = client.search(None, "ALL")
        if typ != "OK":
            raise ImapReviewError("imap_search_failed")

        ids = []
        if data and isinstance(data[0], (bytes, bytearray)):
            ids = bytes(data[0]).split()

        selected = ids[-limit:]
        rows: list[dict[str, Any]] = []
        fetch_spec = "(BODY.PEEK[HEADER.FIELDS (DATE FROM TO CC SUBJECT MESSAGE-ID)] RFC822.SIZE)"

        for message_id in reversed(selected):
            typ, fetched = client.fetch(message_id, fetch_spec)
            if typ != "OK":
                raise ImapReviewError("imap_fetch_failed")
            raw = _extract_fetch_bytes(fetched)
            row = _parse_header_blob(raw)
            row["sequence"] = message_id.decode("ascii", errors="replace")
            rows.append(row)

        return rows

    except (socket.timeout, TimeoutError) as exc:
        raise ImapReviewError("imap_timeout") from exc
    except (socket.gaierror, ConnectionError, OSError) as exc:
        raise ImapReviewError("imap_offline") from exc
    except imaplib.IMAP4.error as exc:
        raise ImapReviewError("imap_protocol_error") from exc
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


def cmd_status(_args) -> None:
    print(json.dumps(configuration_status(), indent=2, sort_keys=True))


def cmd_list_headers(args) -> None:
    rows = list_headers(args.mailbox, args.limit, timeout=args.timeout)
    print(json.dumps({
        "mailbox": args.mailbox,
        "count": len(rows),
        "messages": rows,
        "read_only": True,
    }, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ProgreTech bounded read-only IMAP review provider"
    )
    s = p.add_subparsers(dest="cmd", required=True)

    x = s.add_parser("status")
    x.set_defaults(fn=cmd_status)

    x = s.add_parser("list-headers")
    x.add_argument("--mailbox", default="INBOX")
    x.add_argument("--limit", type=int, default=10)
    x.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    x.set_defaults(fn=cmd_list_headers)

    return p


def main() -> int:
    args = parser().parse_args()
    try:
        args.fn(args)
        return 0
    except (ValueError, ImapReviewError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
